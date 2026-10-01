# Verification — Whisper Meetings 0.2.0

Checked October 1, 2026 on Apple Silicon macOS. Scope and evidence are separated below; no directory approval or live-call recording success is claimed.

## Passed

- **26 Python tests**: concurrency/single-recording enforcement, early stop, transcription preference, crash recovery, ordered transcript pagination, silence, timestamp rounding, source/hash validation, stale analysis exclusion, event binding, unneeded event data/unsafe URL/time rejection and explicit tool annotations.
- **Official Agent Plugins schemas**: `plugin.json` and `mcp.json` validate against canonical 1.0.0 schemas. Local stdio uses bare `sh` and `${PLUGIN_ROOT}`. `scripts/validate.py` inspects all 16 tools and the actual MCP Apps resource contract, CSP and OpenAI entrypoint metadata.
- **Native build/diagnostics**: Swift compiler succeeded with macOS 15.0 deployment target; recorder ad hoc signed. `capture --check` reports authorized microphone and system-audio permission. This diagnostic does not start capture.
- **Offline model**: faster-whisper `small`, Systran/faster-whisper-small revision `536b0662742c02347bc0e980a01041f333bce120`. Dependencies locked; PyAV 16.1.0 avoids the faster-whisper/PyAV 19 `metadata_errors` incompatibility.
- **Real MCP smoke**: run against both source and installed 0.2.0 cache. Discovered 16 tools; read the bundled HTML resource; imported synthetic speech; disconnected/reconnected while the detached worker ran; waited for ready with `HF_HUB_OFFLINE=1`; read the actual transcript; saved/read back a supplied evidence-grounded analysis; staged and bound a synthetic event; exported Markdown/JSON with analysis, event and transcript. Temporary audio/archive removed after the test. No microphone capture.
- **Codex registration**: CLI installed/enabled 0.2.0; `plugin/read` via app-server finds `whisper_meetings` and enabled `whisper-meetings:meetings`. Inventory verification does not prove rendering of the panel in a production chat.
- **UI through actual MCP Apps SDK + synthetic loopback host**: bridge initialized, compact inline/fullscreen expansion, record/stop simulation, disabling transcription while the simulated recording continues, title search, analysis-to-segment jump, preparing a simulated local package, refusal to request delivery without a recipient, explicit recipient-based host message, host light/dark changes, neutral Codex-style controls using host color/font variables, and responsive 390 px view. DOM measurement: clientWidth 390, scrollWidth 390. The preview is visibly labelled synthetic and never invokes the recorder or sends a message to another Codex chat.

Synthetic speech recognized completely:

> We decided to launch the project on Friday. Alex will prepare the release notes. The next meeting is on Monday.

The smoke analysis is supplied test data; the smoke does not claim that Whisper generates analysis or that a production Codex agent was exercised.

## Still requires verification

- A real microphone + Zoom/Meet recording, actual two-device timing, muted input, overlapping speech, audio-device switches and sleep/wake.
- Panel mounting, sidebar/thread entrypoints, host messages and calendar selection inside each production Codex/ChatGPT version. The source/SDK contracts and preview pass; actual UI mounting is not yet verified.
- Live Google Calendar retrieval and selection through the user's connected host integration. The local metadata/link/handoff operations are tested with synthetic events; no real calendar has been copied into the release.
- Actual cross-chat delivery through host tools. Local package creation is verified; the preview only verifies the message request contract.

## Directory submission

The authenticated OpenAI portal blocked upload before draft creation with: “You need a verified developer identity before you can create or upload a plugin.” The identity-verification page was opened for the publisher. No package has been submitted for review.

Public MCP submissions currently require remote HTTPS or a supported local-MCP path agreed with OpenAI. This package intentionally retains local stdio for Mac hardware access; see [OPENAI_STANDARDS.md](docs/OPENAI_STANDARDS.md). The Git marketplace and public source release are separate from Universal Plugin Directory approval.
