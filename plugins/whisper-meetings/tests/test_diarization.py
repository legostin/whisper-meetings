import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import threading
from types import SimpleNamespace
import sys

import pytest
import diarization as d
import meetings as m


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('WHISPER_MEETINGS_HOME', str(tmp_path))
    monkeypatch.setattr(m, 'spawn', lambda *_: None)


def turn(start, end, speaker='system:A'):
    return {'start': start, 'end': end, 'speaker_id': speaker}


def segment(start, end, **extra):
    return {'source': 'system', 'start': start, 'end': end, 'text': 'Проверим выпуск в пятницу.', **extra}


def ready():
    item = m.create('Встреча', 'import', 'small', 'ru', False)
    transcript = m.write_transcript(item, [segment(0, 3)], {'system': {'language': 'ru'}})
    m.update(item['id'], state='ready', tracks={'system': str(Path(item['directory']) / 'test.wav')})
    return m.get(item['id']), transcript


def with_speakers(monkeypatch):
    item, transcript = ready()
    monkeypatch.setattr(d, 'infer', lambda _: {'system': [turn(0, 3)]})
    d.model_directory().mkdir(parents=True)
    (d.model_directory() / 'download.json').write_text(json.dumps({'revision': d.REVISION}))
    return item, d.process(item, transcript)


def test_simultaneous_voices_preserve_text_and_do_not_pick_one_speaker():
    original = segment(0, 4, words=[{'start': 0, 'end': 1, 'word': 'Привет'}, {'start': 2, 'end': 3, 'word': 'выпуск'}])
    annotated, speakers, overlaps = d.annotate([original], {'system': [turn(0, 4), turn(2, 3, 'system:B')]})
    assert annotated[0]['text'] == original['text']
    assert annotated[0]['speaker_id'] is None
    assert annotated[0]['speaker_ids'] == ['system:A', 'system:B']
    assert annotated[0]['overlapping_speech'] is True
    assert annotated[0]['words'][0]['speaker_id'] == 'system:A'
    assert annotated[0]['words'][1]['speaker_id'] is None
    assert overlaps['system'] == [[2, 3]]
    assert all(s['name'] is None for s in speakers)


def test_sequential_speakers_are_ambiguous_but_not_simultaneous():
    annotated, _, overlaps = d.annotate([segment(0, 4)], {'system': [turn(0, 2), turn(2, 4, 'system:B')]})
    assert annotated[0]['speaker_id'] is None
    assert annotated[0]['overlapping_speech'] is False
    assert overlaps['system'] == []


def test_duplicate_turns_from_same_speaker_do_not_create_overlap():
    assert d.overlap_intervals([turn(0, 3), turn(1, 2)]) == []


def test_three_speakers_and_disjoint_overlap_windows():
    assert d.overlap_intervals([turn(0, 10), turn(1, 3, 'system:B'), turn(2, 4, 'system:C'),
                                turn(8, 9, 'system:B')]) == [[1, 4], [8, 9]]


def test_low_coverage_and_zero_duration_never_get_single_speaker():
    for start, end in [(0, 5), (0, 0)]:
        result = d.assign(start, end, [turn(0, 1)], [])
        assert result['speaker_id'] is None and result['speaker_assignment'] == 'uncertain'


def test_channel_labels_are_not_merged_and_cross_channel_overlap_is_explicit():
    annotated, speakers, _ = d.annotate([segment(0, 2)], {'system': [turn(0, 2)],
        'microphone': [turn(0, 2, 'microphone:A')]})
    assert len(speakers) == 2
    assert annotated[0]['overlapping_channels'] is True
    assert annotated[0]['overlapping_speech'] is False


def test_reprocessing_changes_hash_and_makes_old_analysis_stale(monkeypatch):
    import server
    item, transcript = ready()
    analysis = {'summary': 'Выпуск', 'decisions': [], 'action_items': [], 'risks': [], 'open_questions': []}
    m.save_analysis(item['id'], analysis, transcript['sha256'])
    monkeypatch.setattr(d, 'infer', lambda _: {'system': [turn(0, 3)]})
    d.model_directory().mkdir(parents=True)
    (d.model_directory() / 'download.json').write_text(json.dumps({'revision': d.REVISION}))
    updated = d.process(item, transcript)
    assert updated['sha256'] != transcript['sha256']
    assert updated['segments'][0]['id'] == transcript['segments'][0]['id']
    assert server.meetings_read_analysis(item['id'])['stale'] is True


def test_manual_name_is_alias_preserved_in_exports_and_changes_hash(monkeypatch):
    item, transcript = with_speakers(monkeypatch)
    result = d.rename(item['id'], 'system:A', 'Алексей')
    assert result['identity'] == 'user_supplied_alias'
    renamed = m.read_transcript(item['id'])
    assert renamed['sha256'] != transcript['sha256']
    assert renamed['speakers'][0]['name'] == 'Алексей'
    bundle = m.handoff(item['id'], 'engineering', 'Проверить решения', True)
    assert json.loads(Path(bundle['json']).read_text())['speakers'][0]['name'] == 'Алексей'
    assert 'Алексей' in Path(bundle['markdown']).read_text()
    assert 'Алексей' in (Path(item['directory']) / 'transcript.srt').read_text()


@pytest.mark.parametrize('name', ['', '   ', 'A\nB', 'A'*81])
def test_invalid_alias_rejected_without_transcript_change(monkeypatch, name):
    item, transcript = with_speakers(monkeypatch)
    with pytest.raises(ValueError, match='Speaker name'):
        d.rename(item['id'], 'system:A', name)
    assert m.read_transcript(item['id'])['sha256'] == transcript['sha256']


def test_unknown_speaker_and_running_job_cannot_be_renamed(monkeypatch):
    item, transcript = with_speakers(monkeypatch)
    with pytest.raises(ValueError, match='Unknown speaker'):
        d.rename(item['id'], '../outside', 'Someone')
    m.update(item['id'], state='diarizing')
    with pytest.raises(ValueError, match='ready transcript'):
        d.rename(item['id'], 'system:A', 'Someone')


def test_concurrent_clients_cannot_queue_two_diarization_jobs(monkeypatch):
    item, _ = ready()
    monkeypatch.setattr(d, 'require_available', lambda: None)
    barrier = threading.Barrier(2)
    def enqueue(_):
        barrier.wait()
        try:
            return d.queue(item['id'])['state']
        except ValueError:
            return None
    with ThreadPoolExecutor(2) as pool:
        assert list(pool.map(enqueue, range(2))).count('diarizing') == 1


def test_failed_native_processing_preserves_ready_transcript(monkeypatch):
    import worker
    item, transcript = ready()
    m.update(item['id'], state='diarizing')
    monkeypatch.setattr(d, 'infer', lambda _: (_ for _ in ()).throw(RuntimeError('Native test failure')))
    worker.run(item['id'], 'diarize')
    assert m.get(item['id'])['state'] == 'ready'
    assert m.get(item['id'])['diarization_status'] == 'failed'
    assert m.read_transcript(item['id'])['sha256'] == transcript['sha256']


def test_optional_processing_failure_does_not_lose_successful_russian_asr(monkeypatch):
    item, _ = ready()
    item['diarize_on_stop'] = True
    output = SimpleNamespace(text='Встреча состоится в понедельник.', start=0., end=3.,
                             avg_logprob=-.1, no_speech_prob=.01, words=None)
    class Model:
        def __init__(self, *args, **kwargs): pass
        def transcribe(self, *args, **kwargs):
            assert kwargs['language'] == 'ru'
            return [output], SimpleNamespace(language='ru', language_probability=1.)
    monkeypatch.setitem(sys.modules, 'faster_whisper', SimpleNamespace(WhisperModel=Model))
    monkeypatch.setattr(m, 'require_model', lambda _: Path(item['directory']))
    monkeypatch.setattr(d, 'infer', lambda _: (_ for _ in ()).throw(RuntimeError('Native test failure')))
    m.transcribe(item)
    assert m.get(item['id'])['state'] == 'ready'
    assert m.get(item['id'])['diarization_status'] == 'failed'
    assert 'понедельник' in m.read_transcript(item['id'])['segments'][0]['text']


def test_missing_model_does_not_disable_base_transcription_or_download():
    assert d.availability()['available'] is False
    assert d.availability()['account_required'] is False
    with pytest.raises(ValueError, match='No Hugging Face account'):
        d.require_available()


def test_crashed_speaker_worker_restores_ready_transcript():
    from datetime import datetime, timedelta, timezone
    item, transcript = ready()
    item.update(state='diarizing', diarization_status='running',
                updated_at=(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat())
    with m.database() as db:
        # Simulate a crashed worker without refreshing the timestamp through save().
        db.execute('UPDATE meetings SET state=?,payload=? WHERE id=?',
                   ('diarizing', json.dumps(item), item['id']))
    recovered = m.list_meetings()[0]
    assert recovered['state'] == 'ready' and recovered['diarization_status'] == 'failed'
    assert m.read_transcript(item['id'])['sha256'] == transcript['sha256']
