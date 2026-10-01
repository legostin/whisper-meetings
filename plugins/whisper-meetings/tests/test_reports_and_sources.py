import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import meetings as m
import reporting
import server
import worker


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('WHISPER_MEETINGS_HOME', str(tmp_path))
    monkeypatch.setattr(m, 'spawn', lambda *_: None)


@pytest.mark.parametrize('headphones', [False, True])
def test_headphone_choice_persists_and_selects_native_capture_mode(monkeypatch, headphones):
    item = m.create('Call', 'capture', 'small', None, False, headphones=headphones)
    directory = Path(item['directory'])
    expected = ['microphone', 'system'] if headphones else ['microphone']
    assert item['capture_sources'] == expected
    for source in expected:
        (directory / (source+'.wav')).write_bytes(b'test audio')
    commands = []
    def launch(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(poll=lambda: 0, returncode=0)
    monkeypatch.setattr(worker.subprocess, 'Popen', launch)
    worker.run(item['id'], 'capture')
    assert ('--microphone-only' in commands[0]) is not headphones
    assert set(m.get(item['id'])['tracks']) == set(expected)
    assert m.get(item['id'])['state'] == 'recorded'


def test_recording_defaults_to_microphone_only():
    item = m.create('Call', 'capture', 'small', None, False)
    assert item['headphones'] is False and item['capture_sources'] == ['microphone']


def fixture_analysis():
    return {'summary': 'Обсудили выпуск. Согласовали план [s00001, s00002].',
            'overview': [{'title': 'Следующие шаги', 'points': ['Проверить установку [s00002].']}],
            'decisions': [{'text': 'Выпустить в пятницу [s00001](#s00001).', 'evidence_segment_ids': ['s00001']}],
            'action_items': [], 'risks': [], 'open_questions': []}


def test_display_and_exports_hide_references_but_keep_validated_json_evidence():
    item = m.create('Call', 'import', 'small', None, False)
    transcript = m.write_transcript(item, [{'source': 'imported', 'start': 0, 'end': 3, 'text': 'Ship'}], {})
    m.update(item['id'], state='ready')
    analysis = fixture_analysis()
    files = m.save_analysis(item['id'], analysis, transcript['sha256'])
    markdown = Path(files['markdown']).read_text()
    assert 's00001' not in markdown and 's00002' not in markdown
    assert '## Кратко' in markdown and '### Следующие шаги' in markdown
    saved = json.loads(Path(files['json']).read_text())
    assert saved['decisions'][0]['evidence_segment_ids'] == ['s00001']
    shown = server.meetings_read_analysis(item['id'])['analysis']
    assert shown['summary'] == 'Обсудили выпуск. Согласовали план.'
    bundle = m.handoff(item['id'], 'engineering', 'Prepare release')
    assert 's00001' not in Path(bundle['markdown']).read_text()
    assert json.loads(Path(bundle['json']).read_text())['analysis']['decisions'][0]['evidence_segment_ids'] == ['s00001']


def test_legacy_long_summary_splits_without_losing_sentences_or_changing_original():
    sentences = [f'Пункт {i} посвящён обсуждению процесса, проверке установки и срокам подготовки выпуска.' for i in range(12)]
    original = {**fixture_analysis(), 'summary': ' '.join(sentences), 'overview': []}
    shown = reporting.view(original)
    assert shown['summary'] == ' '.join(sentences[:2])
    assert shown['overview'][0]['points'] == sentences[2:]
    assert original['overview'] == [] and original['summary'] == ' '.join(sentences)


def test_report_format_refresh_preserves_stored_analysis_and_transcript():
    item = m.create('Call', 'import', 'small', None, False)
    directory = Path(item['directory'])
    analysis = fixture_analysis()
    m.atomic_json(directory/'analysis.json', analysis)
    before = (directory/'analysis.json').read_bytes()
    m.write_report(item, analysis)
    assert (directory/'analysis.json').read_bytes() == before
    assert 's00001' not in (directory/'analysis.md').read_text()
