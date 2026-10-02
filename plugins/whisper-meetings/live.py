"""Provisional local ASR from finalized native chunks, independent of capture."""
import fcntl
import json
import os
from pathlib import Path
import time

from meetings import atomic_json, data_home, fail_live, get, now, require_model, update

CAPTURING = {'starting', 'recording', 'pausing', 'paused', 'resuming'}


def publish(item, draft):
    draft['segments'].sort(key=lambda s: (s['start'], s['end'], s['source']))
    for i, segment in enumerate(draft['segments'], 1):
        segment['id'] = f'l{i:05}'
    draft.update(meeting_id=item['id'], provisional=True, updated_at=now(),
                 note='Partial chunk transcription; final text and speaker labels follow after stopping.')
    atomic_json(Path(item['directory']) / 'live-transcript.json', draft)
    update(item['id'], live_segment_count=len(draft['segments']), live_updated_at=draft['updated_at'],
           live_processed_seconds=max(draft.get('processed_seconds', {}).values(), default=0))


def pending_chunks(directory, draft):
    chunks = []
    for path in (directory / 'live-chunks').glob('*.json'):
        if path.name in draft['processed_chunks']:
            continue
        metadata = json.loads(path.read_text())
        audio = path.with_suffix('.wav')
        if not audio.is_file():
            continue
        if metadata['source'] not in {'microphone', 'system'} or not 0 <= metadata['start'] < metadata['end'] <= 86400:
            raise ValueError('Invalid native audio chunk metadata')
        chunks.append((metadata, path, audio))
    return sorted(chunks, key=lambda c: (c[0]['start'], c[0]['source']))


def process_batch(item, draft, chunks, model):
    for metadata, path, audio in chunks:
        # Stop / disable requests take priority over starting another inference.
        current = get(item['id'])
        if current['state'] not in CAPTURING or not current.get('live_transcription'):
            break
        output, info = model.transcribe(str(audio), language=item['language'], beam_size=1,
                                       vad_filter=True, condition_on_previous_text=False)
        additions = []
        for segment in output:
            text = segment.text.strip()
            if text:
                start = max(metadata['start'], metadata['start'] + segment.start)
                end = min(metadata['end'], metadata['start'] + segment.end)
                if end > start:
                    additions.append({'source': metadata['source'], 'start': start, 'end': end, 'text': text})
        draft['segments'].extend(additions)
        draft['languages'][metadata['source']] = {'language': info.language, 'probability': info.language_probability}
        draft['processed_chunks'].append(path.name)
        draft['processed_seconds'][metadata['source']] = metadata['end']
        publish(item, draft)
        # Full audio is retained separately. Bound temporary chunk storage.
        audio.unlink(missing_ok=True)
        path.unlink(missing_ok=True)


def run(meeting_id):
    parent = os.getppid()
    item = get(meeting_id)
    directory = Path(item['directory'])
    with (directory / 'live-worker.lock').open('a') as own_lock:
        try:
            fcntl.flock(own_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        path = directory / 'live-transcript.json'
        draft = json.loads(path.read_text()) if path.exists() else {'segments': [], 'languages': {}, 'processed_chunks': [], 'processed_seconds': {}}
        try:
            while os.getppid() == parent:
                item = get(meeting_id)
                if item['state'] not in CAPTURING:
                    break
                if not item.get('live_transcription'):
                    time.sleep(0.3)
                    continue
                chunks = pending_chunks(directory, draft)
                if not chunks:
                    time.sleep(0.3)
                    continue
                # One bounded batch owns the shared model lock. Capture never waits
                # for ASR. Release the model between batches to bound RAM and let
                # imports/final transcripts acquire the same lock.
                with (data_home() / 'transcription.lock').open('a') as model_lock:
                    try:
                        fcntl.flock(model_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        time.sleep(0.3)
                        continue
                    from faster_whisper import WhisperModel
                    update(meeting_id, live_status='working', live_error=None)
                    model = WhisperModel(str(require_model(item['model'])), device='cpu', compute_type='int8',
                                         local_files_only=True, cpu_threads=min(4, os.cpu_count() or 4), num_workers=1)
                    try:
                        process_batch(item, draft, chunks[:2], model)
                    finally:
                        del model
                    current = get(meeting_id)
                    if current['state'] in CAPTURING and current.get('live_transcription'):
                        update(meeting_id, live_status='waiting')
        except Exception as exc:
            # A draft failure must never fail or terminate audio capture.
            fail_live(meeting_id, exc)
