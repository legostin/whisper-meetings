import json
import os
from pathlib import Path
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
import meetings


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("WHISPER_MEETINGS_HOME", str(tmp_path))
    monkeypatch.setattr(meetings, "spawn", lambda *_: None)


def create_capture():
    return meetings.create("Standup", "capture", "small", None, False)


def ready_meeting():
    item = create_capture()
    transcript = meetings.write_transcript(item, [
        {"source": "system", "start": 2.2, "end": 3.1, "text": "Ship on Friday"},
        {"source": "microphone", "start": 0.5, "end": 1.4, "text": "We need a decision"},
    ], {"system": {"language": "en"}})
    meetings.update(item["id"], state="ready")
    return item, transcript


def test_single_recording_atomic_across_clients():
    barrier = threading.Barrier(2)
    def attempt():
        barrier.wait()
        try:
            return create_capture()["id"]
        except ValueError:
            return None
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    assert sum(value is not None for value in results) == 1


def test_stop_during_startup_is_not_overwritten_by_ready_signal():
    item = create_capture()
    stopped = meetings.stop(item["id"], False)
    announced = meetings.mark_recording(item["id"])
    assert stopped["state"] == announced["state"] == "stopping"
    assert (Path(item["directory"]) / "stop-requested").exists()
    assert meetings.stop(item["id"])["state"] == "stopping"


def test_disable_transcription_keeps_capture_active():
    item = create_capture()
    meetings.update(item["id"], state="recording", transcribe_on_stop=True)
    disabled = meetings.set_transcription(item["id"], False)
    assert disabled["state"] == "recording"
    assert disabled["transcribe_on_stop"] is False


def test_missing_model_does_not_enable_transcription():
    item = create_capture()
    with pytest.raises(ValueError, match="not installed"):
        meetings.set_transcription(item["id"], True)
    assert meetings.get(item["id"])["transcribe_on_stop"] is False


def test_durable_state_after_new_connection():
    item = create_capture()
    assert meetings.get(item["id"])["id"] == meetings.list_meetings()[0]["id"]
    assert json.loads((Path(item["directory"]) / "meeting.json").read_text())["title"] == "Standup"


def test_crashed_worker_is_interrupted_and_audio_retained():
    item = create_capture()
    audio = Path(item["directory"]) / "microphone.wav"
    audio.write_bytes(b"retained")
    with meetings.database() as db:
        item["updated_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        db.execute("UPDATE meetings SET payload=? WHERE id=?", (json.dumps(item), item["id"]))
    assert meetings.list_meetings()[0]["state"] == "interrupted"
    assert audio.read_bytes() == b"retained"


def test_transcript_orders_sources_and_paginates():
    item, transcript = ready_meeting()
    assert transcript["segments"][0]["source"] == "microphone"
    first = meetings.read_transcript(item["id"], limit=1)
    second = meetings.read_transcript(item["id"], offset=first["next_offset"], limit=1)
    assert first["segments"][0]["id"] == "s00001"
    assert second["segments"][0]["id"] == "s00002"
    assert second["next_offset"] is None
    assert "00:00:00,500 --> 00:00:01,400" in (Path(item["directory"]) / "transcript.srt").read_text()


def test_transcript_cannot_be_read_while_reprocessing():
    item, _ = ready_meeting()
    meetings.update(item["id"], state="transcribing")
    with pytest.raises(ValueError, match="not ready"):
        meetings.read_transcript(item["id"])


def analysis():
    return {"summary": "Release discussion", "decisions": [], "risks": [], "open_questions": [],
            "action_items": [{"text": "Ship", "owner": None, "due_date": None, "evidence_segment_ids": ["s00002"]}]}


def test_analysis_rejects_invented_evidence():
    item, transcript = ready_meeting()
    payload = analysis()
    payload["action_items"][0]["evidence_segment_ids"] = ["s99999"]
    with pytest.raises(ValueError, match="unknown transcript"):
        meetings.save_analysis(item["id"], payload, transcript["sha256"])
    assert not (Path(item["directory"]) / "analysis.json").exists()


def test_analysis_and_handoff_preserve_null_owner_and_no_delivery(tmp_path):
    item, transcript = ready_meeting()
    result = meetings.save_analysis(item["id"], analysis(), transcript["sha256"])
    assert "владелец не указан" in Path(result["markdown"]).read_text()
    target = tmp_path / "engineering-inbox"
    target.mkdir()
    bundle = meetings.handoff(item["id"], "engineering", "Prepare release", True, str(target))
    payload = json.loads(Path(bundle["json"]).read_text())
    assert payload["analysis"]["action_items"][0]["owner"] is None
    assert payload["transcript"]["segments"][1]["id"] == "s00002"
    assert "no message sent" in bundle["delivery"]
    assert Path(bundle["json"]).parent == target
    assert '## Summary' in Path(bundle['markdown']).read_text()
    assert '## Transcript' in Path(bundle['markdown']).read_text()


def test_analysis_from_old_transcript_is_rejected():
    item, transcript = ready_meeting()
    meetings.write_transcript(item, [], {})
    with pytest.raises(ValueError, match="Transcript changed"):
        meetings.save_analysis(item["id"], analysis(), transcript["sha256"])


def test_handoff_omits_stale_analysis_after_retranscription():
    item, transcript = ready_meeting()
    meetings.save_analysis(item["id"], analysis(), transcript["sha256"])
    meetings.write_transcript(item, [], {})
    result = meetings.handoff(item["id"], "product", "Check decisions")
    payload = json.loads(Path(result["json"]).read_text())
    assert "analysis" not in payload
    assert "stale" in payload["analysis_note"]


def test_invalid_meeting_id_cannot_traverse_archive():
    with pytest.raises(ValueError, match="not found"):
        meetings.get("../../outside")


def test_failed_spawn_reports_failure(monkeypatch):
    monkeypatch.setattr(meetings, "spawn", lambda *_: (_ for _ in ()).throw(OSError("spawn failed")))
    with pytest.raises(OSError):
        create_capture()
    assert meetings.list_meetings()[0]["state"] == "failed"


def test_silence_produces_empty_transcript_not_invented_content():
    item = create_capture()
    transcript = meetings.write_transcript(item, [], {})
    meetings.update(item["id"], state="ready")
    assert transcript["segments"] == []
    assert meetings.read_transcript(item["id"])["total_segments"] == 0


def test_timestamp_rounding_carries_minutes():
    assert meetings.timestamp(59.9996, True) == "00:01:00,000"


def test_panel_state_contains_no_transcript_or_analysis():
    import server
    item, transcript = ready_meeting()
    meetings.save_analysis(item['id'], analysis(), transcript['sha256'])
    state = server.meetings_panel_state()
    assert len(state['meetings']) == 1
    assert 'segments' not in json.dumps(state)
    assert 'Ship on Friday' not in json.dumps(state)
    assert server.meetings_open_panel()['panel'].startswith('ui://')
    assert meetings.get(item['id'])['state'] == 'ready'


def test_panel_analysis_omits_stale_and_in_progress_results():
    import server
    item, transcript = ready_meeting()
    assert server.meetings_read_analysis(item['id']) == {'analysis': None}
    meetings.save_analysis(item['id'], analysis(), transcript['sha256'])
    assert server.meetings_read_analysis(item['id'])['analysis']['summary'] == 'Release discussion'
    meetings.write_transcript(item, [], {})
    assert server.meetings_read_analysis(item['id']) == {'analysis': None, 'stale': True}
    meetings.update(item['id'], state='transcribing')
    assert server.meetings_read_analysis(item['id']) == {'analysis': None}


def event():
    return {'calendar_id':'primary','event_id':'google-event-123','title':'Planning',
            'start':'2026-10-01T10:00:00+06:00','end':'2026-10-01T11:00:00+06:00',
            'meet_url':'https://meet.google.com/abc-defg-hij','event_url':'https://www.google.com/calendar/event?eid=test'}


def test_event_binding_survives_handoff_without_changing_transcript():
    import calendar_links
    item, transcript = ready_meeting()
    calendar_links.stage([event()])
    linked = calendar_links.link(item['id'],calendar_links.resolve('primary','google-event-123'))
    assert linked['calendar_modified'] is False
    read = meetings.read_transcript(item['id'])
    assert read['sha256'] == transcript['sha256']
    assert read['calendar_event']['meet_url'] == event()['meet_url']
    result = meetings.handoff(item['id'],'engineering','Implement decisions')
    assert json.loads(Path(result['json']).read_text())['calendar_event']['event_id'] == event()['event_id']
    assert meetings.get(item['id'])['state'] == 'ready'


@pytest.mark.parametrize('changes',[
    {'meet_url':'https://meet.google.com.attacker.example/link'},
    {'meet_url':'javascript:alert(1)'},
    {'event_url':'https://www.google.com/url?redirect=elsewhere'},
    {'start':'2026-10-01T10:00:00'},
    {'end':'2026-09-30T10:00:00+06:00'},
    {'attendees':['someone@example.com']},
])
def test_event_metadata_rejects_unsafe_or_unneeded_data(changes):
    import calendar_links
    with pytest.raises(ValueError):
        calendar_links.stage([{**event(),**changes}])
    assert calendar_links.options()['events'] == []


def test_all_public_tools_have_explicit_truthful_annotations():
    import asyncio
    import server
    tools = asyncio.run(server.mcp.list_tools())
    for tool in tools:
        for field in ('readOnlyHint','destructiveHint','openWorldHint'):
            assert isinstance(getattr(tool.annotations,field),bool), tool.name
    names = {tool.name:tool for tool in tools}
    assert names['meetings_start'].annotations.readOnlyHint is False
    assert names['meetings_save_analysis'].annotations.destructiveHint is True
    assert names['meetings_read_transcript'].annotations.readOnlyHint is True
