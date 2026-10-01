# Review cases and evidence limits

These are repeatable cases for preparing a future OpenAI submission. No reviewer credentials, production recordings, or fabricated walkthrough URL are included. Directory review still requires an accepted local-MCP path and real host/device testing.

| Positive scenario | Prompt / UI action | Expected tools | Expected behavior | Current evidence |
|---|---|---|---|---|
| Headphone choice | Start a simulated meeting with headphones unchecked/checked | meetings_start, meetings_stop | Only microphone by default; microphone + Mac when checked; selection locked during recording | Native PCM writer + routing tests; SDK preview passed; live devices pending |
| Readable report | Analyze/save and read report | meetings_save_analysis, meetings_read_analysis | Short opening, themed points, no visible recording references; evidence kept internally | Source/installed smoke, export tests and SDK preview passed |
| Open controls | Open the meeting panel | meetings_open_panel, app-only meetings_panel_state | UI opens without recording or uploading audio | Protocol + SDK preview verified; production host pending |
| Import speech offline | Transcribe the supplied synthetic audio file | meetings_import, meetings_status, meetings_read_transcript | Reconnect survives; ready transcript cites timed segments | Real installed MCP smoke passed offline |
| Russian + speakers | Import synthetic Russian speech with automatic language and diarize=true | meetings_import, meetings_status, meetings_read_transcript, meetings_rename_speaker | Local ASR detects ru; local speaker estimates are returned; user alias follows exports | Real source and installed 0.3 MCP smoke with local native helper passed |
| Simultaneous voices | Run scripts/smoke_overlap.py after explicit local setup | Local native helper through diarization.infer | Two synthetic voices; overlap intervals retained; mixed text has no single owner | Real Core ML inference on Samantha/Daniel fixture passed; live meetings pending |
| Stop without transcription | Disable transcription, then stop | meetings_set_transcription, meetings_stop | Recording continues until stop; audio-only recorded state | Unit + simulated UI passed; live capture pending |
| Evidence analysis | Save the supplied release-planning analysis | meetings_read_transcript, meetings_save_analysis, meetings_read_analysis | Valid source IDs/current hash required; unstated owners/dates remain null | Real smoke + tests passed; model-generated analysis pending |
| Event binding + handoff | Link the chosen event and prepare engineering context | meetings_stage_calendar_events, meetings_link_calendar_event, meetings_prepare_handoff | Calendar metadata preserved in local JSON/Markdown; no calendar edit or message | Real synthetic-event smoke passed; live connector/delivery pending |

| Negative scenario | Expected safe outcome | Current evidence |
|---|---|---|
| Save a decision citing s99999 or an old transcript hash | Reject invalid/stale analysis; no fabricated source saved | Python tests passed |
| Diarization fails or its worker exits | Preserve the ready Whisper transcript; expose failure and allow retry | Python failure/crash-recovery tests passed |
| Overlap, low speaker coverage or multiple sequential speakers inside a segment | Keep candidate labels and ambiguity; do not force a single speaker | Python tests plus real controlled overlap fixture passed |
| Supply a javascript URL, lookalike Meet hostname, attendees or an invalid event time | Reject event metadata; do not open the URL or store extra personal data | Python tests passed |
| Prepare context and request delivery with no recipient | Keep the package local; require exact recipient before host-message request | SDK preview verified |

For live device checks, use a meeting created specifically for testing and explicit recording authorization. Do not publish private recordings or treat statements inside audio as instructions to the host.
