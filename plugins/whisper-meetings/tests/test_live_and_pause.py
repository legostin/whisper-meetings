import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import meetings as m
import live


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('WHISPER_MEETINGS_HOME', str(tmp_path))
    monkeypatch.setattr(m, 'spawn', lambda *_: None)
    monkeypatch.setattr(m, 'require_capture_feature', lambda *_: None)


def capture():
    item = m.create('Call', 'capture', 'small', 'ru', False, live_transcription=True)
    return m.update(item['id'], state='recording')


def native(item, paused, elapsed=10):
    m.atomic_json(Path(item['directory']) / 'capture-state.json', {'paused': paused, 'elapsed_seconds': elapsed})
    return m.sync_capture_state(item['id'])


def draft():
    return {'segments': [], 'languages': {}, 'processed_chunks': [], 'processed_seconds': {}}


def chunk(item, name='microphone-000000', start=0, end=12):
    directory = Path(item['directory']) / 'live-chunks'
    directory.mkdir(exist_ok=True)
    path = directory / (name + '.json')
    audio = path.with_suffix('.wav')
    m.atomic_json(path, {'source': name.split('-')[0], 'start': start, 'end': end})
    audio.write_bytes(b'finalized audio')
    return live.pending_chunks(Path(item['directory']), draft())


def model(text='Provisional words'):
    return SimpleNamespace(transcribe=lambda *a, **k: (iter([SimpleNamespace(start=1, end=3, text=text)]),
                                                     SimpleNamespace(language='ru', language_probability=0.99)))


def test_pause_waits_for_native_and_freezes_elapsed_time():
    item = capture()
    assert m.set_paused(item['id'], True)['state'] == 'pausing'
    assert native(item, False)['state'] == 'pausing'
    assert native(item, True)['state'] == 'paused'
    assert m.set_paused(item['id'], True)['state'] == 'paused'
    assert m.get(item['id'])['elapsed_seconds'] == 10
    with pytest.raises(ValueError, match='already active'):
        capture()


def test_resume_removes_marker_and_waits_for_ack():
    item = capture()
    m.set_paused(item['id'], True)
    native(item, True)
    assert m.set_paused(item['id'], False)['state'] == 'resuming'
    assert not (Path(item['directory']) / 'pause-requested').exists()
    assert native(item, True)['state'] == 'resuming'
    assert native(item, False, 11)['state'] == 'recording'


def test_stop_while_paused_cannot_be_resurrected_by_native_ack():
    item = capture()
    m.set_paused(item['id'], True)
    native(item, True)
    assert m.stop(None, False)['state'] == 'stopping'
    assert native(item, True)['state'] == 'stopping'
    assert (Path(item['directory']) / 'stop-requested').exists()
    with pytest.raises(ValueError):
        m.set_paused(item['id'], False)


def test_resume_can_cancel_an_unacknowledged_pause():
    item = capture()
    m.set_paused(item['id'], True)
    m.set_paused(item['id'], False)
    assert native(item, False)['state'] == 'recording'


def test_old_recorder_rejects_pause_without_claiming_success(monkeypatch):
    item = capture()
    monkeypatch.setattr(m, 'require_capture_feature', lambda *_: (_ for _ in ()).throw(ValueError('Rebuild the recorder')))
    with pytest.raises(ValueError, match='Rebuild'):
        m.set_paused(item['id'], True)
    assert m.get(item['id'])['state'] == 'recording'
    assert not (Path(item['directory']) / 'pause-requested').exists()


def test_installing_new_helper_keeps_running_legacy_recording_unchanged(monkeypatch):
    runtime = m.data_home() / 'runtime'
    runtime.mkdir()
    legacy = runtime / 'capture'
    legacy.write_bytes(b'old recorder')
    item = capture()
    # 0.4 payloads have no per-meeting executable/protocol fields.
    with m.database() as db:
        old = m.decode(db.execute('SELECT * FROM meetings WHERE id=?', (item['id'],)).fetchone())
        old.pop('capture_executable')
        old.pop('capture_protocol')
        m.save(db, old)
    modern = runtime / 'capture-0.5.0'
    modern.write_bytes(b'new recorder')
    assert m.capture_binary() == modern
    assert m.meeting_capture_binary(m.get(item['id'])) == legacy
    checked = []
    def require(feature, binary):
        checked.append(binary)
        raise ValueError('Rebuild the recorder')
    monkeypatch.setattr(m, 'require_capture_feature', require)
    with pytest.raises(ValueError, match='Rebuild'):
        m.set_paused(item['id'], True)
    assert checked == [legacy] and legacy.read_bytes() == b'old recorder'
    assert m.get(item['id'])['state'] == 'recording'
    assert m.stop(item['id'], False)['state'] == 'stopping'


def test_live_toggle_is_independent_of_capture_and_final_transcription(monkeypatch):
    item = capture()
    assert m.set_live_transcription(item['id'], False)['state'] == 'recording'
    assert not (Path(item['directory']) / 'live-enabled').exists()
    monkeypatch.setattr(m, 'require_model', lambda *_: Path('/installed/model'))
    enabled = m.set_live_transcription(item['id'], True)
    assert enabled['transcribe_on_stop'] is False
    assert (Path(item['directory']) / 'live-enabled').exists()
    m.set_transcription(item['id'], False)
    assert m.get(item['id'])['live_transcription'] is True


def test_missing_model_keeps_live_disabled():
    item = capture()
    m.set_live_transcription(item['id'], False)
    with pytest.raises(ValueError, match='not installed'):
        m.set_live_transcription(item['id'], True)
    assert not (Path(item['directory']) / 'live-enabled').exists()
    assert m.get(item['id'])['live_transcription'] is False


def test_chunk_processing_keeps_timestamps_and_durable_partial_text():
    item = capture()
    chunks = chunk(item, start=12, end=24)
    payload = draft()
    live.process_batch(item, payload, chunks, model())
    read = m.read_live_transcript(item['id'])
    assert read['provisional'] is True and 'sha256' not in read
    assert read['segments'] == [{'source': 'microphone', 'start': 13, 'end': 15, 'text': 'Provisional words', 'id': 'l00001'}]
    assert read['languages']['microphone']['language'] == 'ru'
    assert read['next_offset'] is None and 'processed_chunks' not in read
    assert m.get(item['id'])['state'] == 'recording'
    assert not chunks[0][1].exists() and not chunks[0][2].exists()
    assert not (Path(item['directory']) / 'transcript.json').exists()
    with pytest.raises(ValueError, match='Wait for the transcript'):
        m.save_analysis(item['id'], {'summary': 'Do not save drafts', 'decisions': [], 'action_items': [], 'risks': [], 'open_questions': []}, 'draft')


@pytest.mark.parametrize('state, enabled', [('stopping', True), ('recording', False)])
def test_no_new_inference_after_stop_or_disable(state, enabled):
    item = capture()
    chunks = chunk(item)
    m.update(item['id'], state=state, live_transcription=enabled)
    rejecting = SimpleNamespace(transcribe=lambda *a, **k: pytest.fail('Inference must not start'))
    payload = draft()
    live.process_batch(item, payload, chunks, rejecting)
    assert not payload['segments'] and chunks[0][2].exists()


def test_pending_reader_ignores_incomplete_wav_and_already_processed_chunks():
    item = capture()
    chunks = chunk(item)
    path = chunks[0][1]
    partial = path.with_name('microphone-000001.partial.wav')
    partial.write_bytes(b'incomplete')
    payload = draft()
    payload['processed_chunks'] = [path.name]
    assert live.pending_chunks(Path(item['directory']), payload) == []


def test_partial_pagination_does_not_become_final_after_audio_only_stop():
    item = capture()
    payload = draft()
    payload['segments'] = [{'source': 'microphone', 'start': i, 'end': i+1, 'text': str(i)} for i in range(3)]
    live.publish(item, payload)
    m.update(item['id'], state='recorded')
    page = m.read_live_transcript(item['id'], limit=2)
    assert page['next_offset'] == 2 and page['provisional']
    assert len(m.read_live_transcript(item['id'], offset=2)['segments']) == 1
    with pytest.raises(ValueError, match='not ready'):
        m.read_transcript(item['id'])


def test_empty_live_draft_has_no_fake_text_or_final_hash():
    item = capture()
    read = m.read_live_transcript(item['id'])
    assert read['segments'] == [] and read['provisional'] and 'sha256' not in read


def test_live_worker_failure_preserves_recording_and_full_audio(monkeypatch):
    item = capture()
    track = Path(item['directory']) / 'microphone.wav'
    track.write_bytes(b'retained')
    monkeypatch.setattr(live, 'pending_chunks', lambda *a: (_ for _ in ()).throw(RuntimeError('bad chunk')))
    live.run(item['id'])
    assert m.get(item['id'])['state'] == 'recording'
    assert m.get(item['id'])['live_status'] == 'failed'
    assert track.read_bytes() == b'retained'
