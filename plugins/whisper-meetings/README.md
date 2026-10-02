# Whisper Meetings

Local microphone recording (plus Mac audio when headphones are confirmed), offline Whisper transcription, and an MCP Apps meeting workspace for Codex. Optional Calendar/Meet event binding uses minimal metadata explicitly supplied by the user or host. Current-agent analysis and cross-chat delivery depend on host capabilities.

This is an independent macOS 15+ project, not an official OpenAI, Apple, Google or Zoom product. Version 0.4.1 is a prerelease; see the repository's validation notes for tested behavior and limitations.

## Setup

Install [uv](https://docs.astral.sh/uv/) and Apple Command Line Tools/Xcode. From this directory:

```sh
python3 scripts/setup.py
```

Setup installs locked Python dependencies into `~/.local/share/whisper-meetings/runtime/`, compiles the recorder and downloads the selected `small` model. Setup is explicit and needs the network; subsequent transcription uses only installed model files. No API key is required. Use `--skip-model` for runtime/capture only or `--model base` for a smaller model. Run `scripts/download_model.py` with the runtime Python to add another model.

Optional speaker processing on Apple Silicon requires Swift 6.2+:

```sh
python3 scripts/setup.py --diarization
```

This builds a pinned native FluidAudio helper and downloads public Community-1-derived Core ML assets. No Hugging Face login, token or API key is needed. Enable “Distinguish speakers” before capture/import or identify speakers in a ready recording. Speaker assignment is an estimate; overlapping/ambiguous words are not assigned to one person. Diarization does not recover missing words. Renaming or reprocessing changes the transcript hash, invalidating old analysis. Russian ASR supports automatic detection and explicit `language="ru"`.

The host starts `mcp.json` over stdio. Opening the panel never starts recording. Ask “Open the meeting panel”, “Start recording this meeting”, “Stop without transcription”, or “Analyze the last meeting”. Stop an active recording before uninstalling or disabling the plugin; detached jobs survive MCP reconnects. Maximum capture duration is twelve hours.

The unchecked headphones checkbox records microphone only via AVAudioEngine. Speakers must be audible for remote voices to reach the microphone. Confirming headphones enables microphone + all Mac playback, including other apps. Microphone-only mode does not request screen recording permission. Channel labels are not speaker identities. Transcripts can be incorrect, especially with overlapping voices. Streamed live captions are not included. Optional local Core ML diarization estimates speakers and preserves overlap intervals; names are user-supplied aliases scoped to one meeting/channel.

Calendar binding is optional. The server never reads/writes Google Calendar or stores Google credentials. A connected host integration can obtain events on an explicit request; the user selects which metadata to attach. Attaching an event does not join Meet or begin capture. The same metadata can be supplied directly without a connector.

Audio stays local. Text read/analyzed by the current agent is processed under that host/model provider's settings. Preparing a handoff writes local files; sending it to a named chat is a separate, explicit request handled by the host.

Full installation, development and validation: [repository](https://github.com/legostin/whisper-meetings).
[Privacy policy](PRIVACY.md) · [Usage terms](TERMS.md) · [Support](https://github.com/legostin/whisper-meetings/issues).

Reports use a short opening and themed bullet sections, followed by decisions, tasks, risks and open questions. Recording links and segment IDs are omitted from the UI and human-readable reports; evidence metadata remains in structured JSON. `scripts/refresh_reports.py` reformats existing local Markdown reports without modifying their JSON or audio.

The interface is currently English only. Speech language is independent: automatic detection, Russian and English remain available. Analysis requests use the requested report language or otherwise the transcript language; existing reports are preserved.
