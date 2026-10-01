"""Optional, local speaker diarization. Labels are scoped to a track/meeting.

Regular (overlap-preserving) turns are used, never exclusive diarization.
Speaker assignment is a conservative timestamp heuristic, not a probability.
No voiceprints are persisted or matched across meetings.
"""
import math
from pathlib import Path

MODEL = 'FluidInference/speaker-diarization-coreml'
REVISION = 'df2625ac79a7ac6b65ad868fee6d80f320da4232'
NOTE = ('Speaker labels are estimated within this meeting and separately per audio channel. '
        'They are not verified identities. Names are user-supplied aliases. '
        'Overlapping or ambiguous text must not be attributed to a single person. '
        'Diarization does not recover words lost from mixed speech. Simultaneous speech across channels may be echo; labels on different channels are not matched identities.')


def model_directory():
    from meetings import data_home
    return data_home() / 'models' / 'speaker-diarization-coreml'


def binary_path():
    from meetings import data_home
    return data_home() / 'runtime' / 'meeting-diarizer'


def availability():
    import json
    directory = model_directory()
    try:
        manifest = json.loads((directory / 'download.json').read_text())
        model_installed = manifest['revision'] == REVISION and bool(manifest['sha256']) and all((directory / p).is_file() for p in manifest['sha256'])
    except (OSError, ValueError, KeyError, TypeError):
        model_installed = False
    return {'available': binary_path().is_file() and model_installed, 'native_available': binary_path().is_file(),
            'model_installed': model_installed, 'model': MODEL, 'engine': 'local Core ML / FluidAudio offline VBx',
            'setup': 'python3 scripts/setup.py --diarization', 'account_required': False,
            'model_url': 'https://huggingface.co/' + MODEL}


def require_available():
    if not availability()['available']:
        raise ValueError('Local speaker processing is not installed. Run python3 scripts/setup.py --diarization '
                         'on an Apple Silicon Mac with macOS 15+ and Swift 6.2+. No Hugging Face account or token is required.')


def merge_intervals(intervals):
    merged = []
    for start, end in sorted(intervals):
        if end <= start:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def overlap_intervals(turns):
    """Sweep intervals; duplicate turns from one speaker do not imply overlap."""
    events = {}
    for turn in turns:
        for time, delta in ((turn['start'], 1), (turn['end'], -1)):
            events.setdefault(time, []).append((turn['speaker_id'], delta))
    active, output, previous = {}, [], None
    for time, changes in sorted(events.items()):
        if previous is not None and time > previous and len(active) > 1:
            output.append([previous, time])
        for speaker, delta in changes:
            active[speaker] = active.get(speaker, 0) + delta
            if active[speaker] == 0:
                del active[speaker]
        previous = time
    return merge_intervals(output)


def assign(start, end, turns, overlaps):
    candidates = sorted({t['speaker_id'] for t in turns if min(end, t['end']) > max(start, t['start'])})
    simultaneous = any(min(end, b) > max(start, a) for a, b in overlaps)
    covered = merge_intervals((max(start, t['start']), min(end, t['end'])) for t in turns)
    coverage = sum(b-a for a, b in covered) / (end-start) if end > start else 0
    certain = len(candidates) == 1 and coverage >= .8 and not simultaneous
    return {'speaker_id': candidates[0] if certain else None, 'speaker_ids': candidates,
            'overlapping_speech': simultaneous, 'speaker_assignment': 'estimated' if certain else 'uncertain'}


def annotate(segments, turns_by_source):
    """Preserve ASR text. Ambiguous segments retain all candidate IDs."""
    overlaps = {source: overlap_intervals(turns) for source, turns in turns_by_source.items()}
    output = []
    for segment in segments:
        turns = turns_by_source.get(segment['source'], [])
        flags = assign(segment['start'], segment['end'], turns, overlaps.get(segment['source'], []))
        result = {**segment, **flags}
        result['overlapping_channels'] = any(min(segment['end'], turn['end']) > max(segment['start'], turn['start'])
                                            for source, turns in turns_by_source.items() if source != segment['source']
                                            for turn in turns)
        # Word timestamps improve attribution without inventing a separated transcript.
        if segment.get('words'):
            result['words'] = [{**word, **assign(word['start'], word['end'], turns, overlaps.get(segment['source'], []))}
                               for word in segment['words']]
        output.append(result)
    speakers = [{'id': sid, 'source': source, 'name': None}
                for source, turns in sorted(turns_by_source.items())
                for sid in sorted({t['speaker_id'] for t in turns})]
    return output, speakers, overlaps


def convert_track(filename, destination):
    import av
    import wave
    count, peak = 0, 0
    with av.open(filename) as container, wave.open(str(destination), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        resampler = av.AudioResampler(format='s16', layout='mono', rate=16000)
        def write(frames):
            nonlocal count, peak
            for frame in frames:
                samples = frame.to_ndarray().astype('<i2')
                if samples.size:
                    peak = max(peak, int(abs(samples.astype('int32')).max()))
                output.writeframesraw(samples.tobytes())
                count += frame.samples
        for frame in container.decode(container.streams.audio[0]):
            write(resampler.resample(frame))
        write(resampler.resample(None))
    return count, peak


def infer(tracks):
    require_available()
    import hashlib
    import json
    import subprocess
    import tempfile
    from meetings import data_home
    manifest = json.loads((model_directory() / 'download.json').read_text())
    if not all(hashlib.sha256((model_directory() / p).read_bytes()).hexdigest() == digest
               for p, digest in manifest['sha256'].items()):
        raise RuntimeError('Local diarization model integrity check failed; rerun explicit setup')
    result = {}
    with tempfile.TemporaryDirectory(prefix='diarization-', dir=data_home()) as temporary:
        for source, filename in sorted(tracks.items()):
            audio, output = Path(temporary) / 'audio.wav', Path(temporary) / 'turns.json'
            count, peak = convert_track(filename, audio)
            if not count or peak == 0:
                result[source] = []
                continue
            process = subprocess.run([str(binary_path()), str(model_directory()), str(audio), str(output)],
                                     capture_output=True, text=True, timeout=7200)
            if process.returncode:
                raise RuntimeError(f'Local speaker processing failed (exit {process.returncode}): ' + process.stderr[-2000:])
            turns = []
            for turn in json.loads(output.read_text()):
                start, end = float(turn['start']), float(turn['end'])
                if not math.isfinite(start) or not math.isfinite(end) or end <= start:
                    continue
                turns.append({'start': max(0, start), 'end': end, 'speaker_id': f"{source}:{turn['speaker']}"})
            result[source] = sorted(turns, key=lambda t: (t['start'], t['end'], t['speaker_id']))
    return result


def process(item, transcript):
    import json
    import meetings
    turns = infer(item['tracks'])
    segments, speakers, overlaps = annotate(transcript['segments'], turns)
    manifest = json.loads((model_directory() / 'download.json').read_text())
    report = {'model': MODEL, 'revision': manifest['revision'], 'note': NOTE, 'turns': turns,
              'overlap_intervals': overlaps}
    path = Path(item['directory']) / 'diarization.json'
    meetings.atomic_json(path, report)
    info = {'status': 'complete', 'engine': 'Core ML / FluidAudio offline VBx', 'model': MODEL, 'revision': manifest['revision'], 'note': NOTE,
            'report_path': str(path), 'overlap_seconds': {s: sum(b-a for a,b in intervals) for s,intervals in overlaps.items()}}
    result = meetings.write_transcript(item, segments, transcript['languages'], speakers, info)
    meetings.update(item['id'], diarization_status='complete', diarization_error=None,
                    speaker_count=len(speakers), transcript_sha256=result['sha256'])
    return result


def queue(meeting_id):
    import meetings
    require_available()
    with meetings.database() as db:
        row = db.execute('SELECT * FROM meetings WHERE id=?', (meeting_id,)).fetchone()
        if row is None:
            raise ValueError('Meeting not found')
        item = meetings.decode(row)
        if item['state'] != 'ready':
            raise ValueError('Wait for a ready transcript before diarization')
        if not item['tracks']:
            raise ValueError('No retained audio tracks')
        item.update(state='diarizing', diarization_status='running', diarization_error=None)
        meetings.save(db, item)
    try:
        meetings.spawn(meeting_id, 'diarize')
    except Exception:
        meetings.update(meeting_id, state='ready', diarization_status='failed', diarization_error='Could not start worker')
        raise
    return item


def rename(meeting_id, speaker_id, name):
    import json
    import meetings
    if not name.strip() or len(name) > 80 or any(ord(c) < 32 for c in name):
        raise ValueError('Speaker name must be 1..80 characters without control characters')
    with meetings.database() as db:
        row = db.execute('SELECT * FROM meetings WHERE id=?', (meeting_id,)).fetchone()
        if row is None:
            raise ValueError('Meeting not found')
        item = meetings.decode(row)
        if item['state'] != 'ready':
            raise ValueError('Wait for a ready transcript before renaming')
        transcript = json.loads((Path(item['directory']) / 'transcript.json').read_text())
        speaker = next((s for s in transcript.get('speakers', []) if s['id'] == speaker_id), None)
        if speaker is None:
            raise ValueError('Unknown speaker ID; read the current transcript')
        speaker['name'] = name.strip()
        result = meetings.write_transcript(item, transcript['segments'], transcript['languages'],
                                           transcript['speakers'], transcript['diarization'])
        item['transcript_sha256'] = result['sha256']
        meetings.save(db, item)
    return {'speaker_id': speaker_id, 'name': name.strip(), 'transcript_sha256': result['sha256'],
            'identity': 'user_supplied_alias', 'analysis': 'previous analysis becomes stale'}
