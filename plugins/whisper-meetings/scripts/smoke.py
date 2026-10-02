"""Exercise the installed MCP plugin on synthetic audio, never record live input."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import tempfile
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def payload(result):
    if result.isError:
        raise RuntimeError(result.content)
    if result.structuredContent is not None:
        value = result.structuredContent
        return value.get("result", value)
    return json.loads(next(c.text for c in result.content if c.type == "text"))


async def main(plugin, fixture, language='en', diarize=False):
    real_home = Path(os.environ.get("WHISPER_MEETINGS_HOME", "~/.local/share/whisper-meetings")).expanduser()
    with tempfile.TemporaryDirectory(prefix="whisper-meetings-smoke-") as temporary:
        home = Path(temporary)
        (home / "runtime").symlink_to(real_home / "runtime", target_is_directory=True)
        (home / "models").symlink_to(real_home / "models", target_is_directory=True)
        server = json.loads((plugin / "mcp.json").read_text())["mcpServers"]["whisper_meetings"]
        assert "/" not in server["command"], "Portable stdio executable must be a bare name"
        parameters = StdioServerParameters(command=server["command"],
                    args=[arg.replace("${PLUGIN_ROOT}", str(plugin)) for arg in server["args"]], cwd=str(plugin),
                    env={**os.environ, "WHISPER_MEETINGS_HOME": str(home), "HF_HUB_OFFLINE": "1"})
        async with stdio_client(parameters) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                tools = await session.list_tools()
                print("MCP tools:", len(tools.tools), flush=True)
                assert len(tools.tools) == 26
                panel = next(t for t in tools.tools if t.name == "meetings_open_panel")
                assert panel.meta["ui"]["resourceUri"] == "ui://whisper-meetings/panel-0.6.0.html"
                resource = await session.read_resource(panel.meta["ui"]["resourceUri"])
                assert resource.contents[0].mimeType == "text/html;profile=mcp-app"
                assert "Whisper Meetings" in resource.contents[0].text
                assert "/* WIDGET_SCRIPT */" not in resource.contents[0].text
                for tool in tools.tools:
                    assert all(isinstance(getattr(tool.annotations, key), bool) for key in ("readOnlyHint", "destructiveHint", "openWorldHint"))
                check = payload(await session.call_tool("meetings_doctor", {}))
                assert "small" in check["models"]
                imported = payload(await session.call_tool("meetings_import", {"source_file": str(fixture), "title": "Self-test: synthetic speech", "language": None if language == "auto" else language, "diarize": diarize}))
                identity = imported["id"]
                print("Import:", imported["state"], flush=True)
        # Reconnect while detached transcription is running.
        async with stdio_client(parameters) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                deadline = time.monotonic() + 180
                while time.monotonic() < deadline:
                    state = payload(await session.call_tool("meetings_status", {"meeting_id": identity}))
                    if state["state"] in {"ready", "failed", "interrupted"}:
                        break
                    await asyncio.sleep(1)
                assert state["state"] == "ready", state
                transcript = payload(await session.call_tool("meetings_read_transcript", {"meeting_id": identity}))
                text = " ".join(s["text"] for s in transcript["segments"])
                print("Transcript:", text, flush=True)
                if language == 'en':
                    assert "friday" in text.lower() and "release notes" in text.lower(), text
                else:
                    assert 'пятниц' in text.lower() and 'инструкц' in text.lower(), text
                    assert transcript['languages']['imported']['language'] == 'ru'
                if diarize:
                    assert state['diarization_status'] == 'complete', state
                    assert transcript['speakers']
                    assert transcript['diarization']['engine'] == 'Core ML / FluidAudio offline VBx'
                    assert 'speaker_assignment' in transcript['segments'][0]
                    renamed = payload(await session.call_tool('meetings_rename_speaker', {
                        'meeting_id': identity, 'speaker_id': transcript['speakers'][0]['id'], 'name': 'Тестовый голос'}))
                    assert renamed['identity'] == 'user_supplied_alias'
                    transcript = payload(await session.call_tool('meetings_read_transcript', {'meeting_id': identity}))
                    assert transcript['speakers'][0]['name'] == 'Тестовый голос'
                    print('PASS: native offline speaker inference and manual alias', flush=True)
                evidence = [s["id"] for s in transcript["segments"]]
                russian = language != 'en'
                owner = 'Алексей' if russian else 'Alex'
                analysis = {"summary": "Планирование выпуска новой версии." if russian else "Synthetic smoke test: project release planning.", "decisions": [
                    {"text": "Выпустить новую версию в пятницу." if russian else "Launch the project on Friday.", "evidence_segment_ids": evidence}],
                    "action_items": [{"text": "Подготовить инструкцию по установке." if russian else "Prepare the release notes.", "owner": owner, "due_date": None, "evidence_segment_ids": evidence}],
                    "risks": [], "open_questions": []}
                saved = payload(await session.call_tool("meetings_save_analysis", {
                    "meeting_id": identity, "transcript_sha256": transcript["sha256"], "analysis": analysis}))
                assert Path(saved["markdown"]).exists()
                read_back = payload(await session.call_tool("meetings_read_analysis", {"meeting_id": identity}))
                assert read_back["analysis"]["transcript_sha256"] == transcript["sha256"]
                event = {"calendar_id": "primary", "event_id": "synthetic-event", "title": "Synthetic planning", "start": "2026-10-01T10:00:00Z", "end": "2026-10-01T11:00:00Z", "meet_url": "https://meet.google.com/abc-defg-hij"}
                staged = payload(await session.call_tool("meetings_stage_calendar_events", {"events": [event]}))
                assert staged["count"] == 1
                linked = payload(await session.call_tool("meetings_link_calendar_event", {"meeting_id": identity, "event": event}))
                assert linked["calendar_modified"] is False
                bundle = payload(await session.call_tool("meetings_prepare_handoff", {
                    "meeting_id": identity, "area": "engineering", "brief": "Prepare the release plan based on the meeting.", "include_transcript": True}))
                exported = json.loads(Path(bundle["json"]).read_text())
                assert exported["analysis"]["action_items"][0]["owner"] == owner
                assert exported["transcript"]["segments"]
                assert exported["calendar_event"]["event_id"] == "synthetic-event"
                assert "## Calendar event" in Path(bundle["markdown"]).read_text()
                print("PASS: offline transcription, reconnect, evidence-backed analysis calendar binding and local handoff", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--plugin", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--language', choices=['en','ru','auto'], default='en')
    parser.add_argument('--diarize', action='store_true')
    args = parser.parse_args()
    asyncio.run(main(args.plugin.resolve(), args.fixture.resolve(), args.language, args.diarize))
