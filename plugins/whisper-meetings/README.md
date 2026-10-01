# Whisper Meetings

Local microphone + Mac audio recording, offline Whisper transcription, and an MCP Apps meeting workspace for Codex. Optional Calendar/Meet event binding uses minimal metadata explicitly supplied by the user or host. Current-agent analysis and cross-chat delivery depend on host capabilities.

This is an independent macOS 15+ project, not an official OpenAI, Apple, Google or Zoom product. Version 0.2.0 is a prerelease; see the repository's validation notes for tested behavior and limitations.

## Setup

Install [uv](https://docs.astral.sh/uv/) and Apple Command Line Tools/Xcode. From this directory:

```sh
python3 scripts/setup.py
```

Setup installs locked Python dependencies into `~/.local/share/whisper-meetings/runtime/`, compiles the recorder and downloads the selected `small` model. Setup is explicit and needs the network; subsequent transcription uses only installed model files. No API key is required. Use `--skip-model` for runtime/capture only or `--model base` for a smaller model. Run `scripts/download_model.py` with the runtime Python to add another model.

The host starts `mcp.json` over stdio. Opening the panel never starts recording. Ask “Open the meeting panel”, “Start recording this meeting”, “Stop without transcription”, or “Analyze the last meeting”. Stop an active recording before uninstalling or disabling the plugin; detached jobs survive MCP reconnects. Maximum capture duration is twelve hours.

All Mac playback is captured, not only the conference app. Headphones help avoid echo. Channel labels are not speaker identities. Transcripts can be incorrect, especially with overlapping voices. Streamed live captions and speaker diarization are not included.

Calendar binding is optional. The server never reads/writes Google Calendar or stores Google credentials. A connected host integration can obtain events on an explicit request; the user selects which metadata to attach. Attaching an event does not join Meet or begin capture. The same metadata can be supplied directly without a connector.

Audio stays local. Text read/analyzed by the current agent is processed under that host/model provider's settings. Preparing a handoff writes local files; sending it to a named chat is a separate, explicit request handled by the host.

Full installation, development and validation: [repository](https://github.com/legostin/whisper-meetings).
[Privacy policy](PRIVACY.md) · [Usage terms](TERMS.md) · [Support](https://github.com/legostin/whisper-meetings/issues).
