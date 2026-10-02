# Whisper Meetings

**Record a meeting. Transcribe it locally. Turn the conversation into useful next steps.**

A macOS plugin for Codex with local Whisper transcription, optional speaker detection, structured meeting reports and context packages for other chats.

[Latest release](https://github.com/legostin/whisper-meetings/releases/tag/v0.5.0) · [Installation help](docs/INSTALLATION.md) · [Changelog](CHANGELOG.md) · [Report an issue](https://github.com/legostin/whisper-meetings/issues)

> **Preview release · v0.5.0.** Available through the Git marketplace. This plugin has not been approved for the public OpenAI Plugins Directory. See [validation results](VALIDATION.md) for tested behavior and remaining checks.

## What you can do

- **Record and pause meeting audio** from Zoom, Google Meet or other apps: microphone only, or microphone and Mac playback when wearing headphones.
- **Transcribe locally during the meeting** with Whisper. Provisional text arrives in roughly 12-second chunks plus processing time; final text follows after stopping. Automatic language detection, Russian and English are available in the panel; the interface is English.
- **Distinguish speakers** with optional local Core ML models and mark overlapping or uncertain speech.
- **Ask Codex for a report** with a short summary, themed bullet points, decisions, tasks, risks and open questions.
- **Link a calendar event** through an available calendar integration in Codex.
- **Prepare context for another chat** as Markdown and JSON, then explicitly ask Codex to deliver it to a named recipient.

Audio processing stays on your Mac. Text you ask Codex to analyze is processed by your configured Codex model.

## Install

You need:

- **macOS 15 or later.** Optional speaker detection also requires Apple Silicon and Swift 6.2 or later.
- **Codex with plugin support**, including the `codex` command in your terminal.
- **Apple Command Line Tools or Xcode.** If needed, run `xcode-select --install` and finish the macOS installation dialog.
- **[uv](https://docs.astral.sh/uv/getting-started/installation/)** for the Python runtime.

Paste this into Terminal:

```sh
git clone --branch v0.5.0 https://github.com/legostin/whisper-meetings.git
cd whisper-meetings
python3 plugins/whisper-meetings/scripts/setup.py
codex plugin marketplace add legostin/whisper-meetings --ref v0.5.0
codex plugin add whisper-meetings@whisper-local
```

Setup builds the recorder and downloads the default Whisper `small` model, about 460 MB. The first setup needs internet access; transcription then uses the installed local model. No OpenAI API key or Hugging Face account is required by the plugin.

Open a new Codex chat and ask:

> Open the meeting panel.

If the plugin does not appear, restart Codex. Already installed an earlier version? Follow the [update instructions](docs/INSTALLATION.md#update).

## Record your first meeting

1. Open your Zoom or Meet call, then open the meeting panel in Codex.
2. Enter a meeting title. Check **I am wearing headphones** if you use headphones; leave it unchecked when using speakers.
3. Click **Start recording** and allow the macOS audio permissions when prompted. With **Transcribe during recording** enabled, watch provisional text in **Transcript**. Use **Pause recording** / **Resume recording** to exclude breaks from the same recording.
4. Click **Stop recording**. With **Transcribe after stopping** enabled, Whisper processes the saved audio.
5. Open **Decisions & tasks** and click **Analyze with Codex**.

With headphones unchecked, only the microphone is recorded: remote voices must be audible through your speakers. With headphones checked, the recorder captures the microphone and **all Mac playback**, including other apps and notifications.

Opening the panel or linking an event never starts recording. Stop an active recording before disabling or uninstalling the plugin.

## Use it from chat

| Ask Codex | Result |
| --- | --- |
| “Start recording this meeting. I am wearing headphones.” | Record the microphone and Mac playback. |
| “Pause recording.” / “Resume recording.” | Pause or continue the same meeting; paused audio is excluded. |
| “Stop without transcription.” | Save audio without final Whisper processing; any existing live draft stays provisional. |
| “Transcribe `/absolute/path/meeting.m4a`.” | Import and transcribe an existing recording. |
| “Analyze my last meeting: decisions, tasks and risks.” | Read the transcript and save a structured report. |
| “Link this recording to the calendar event I select.” | Attach the selected event and Calendar/Meet links. |
| “Prepare this meeting's context for engineering.” | Save a local Markdown/JSON context package. |
| “Send that package to the existing chat named Release planning.” | Ask Codex to deliver it to that specific chat, when supported. |

You can ask in your own language. Reports follow your requested language or otherwise the transcript language.

## Optional speaker detection

From the cloned repository, run:

```sh
python3 plugins/whisper-meetings/scripts/setup.py --diarization
```

Then enable **Distinguish speakers** before recording or importing, or click **Identify speakers** on a transcribed meeting.

This uses public models without a login or token. Speaker labels are estimates within one meeting and audio channel; you supply names. Detection marks overlap but cannot recover words missing from the Whisper transcript. [Details and model credits](docs/USAGE.md#speaker-detection).

## Privacy and current limits

Recordings, transcripts and exports are stored under `~/.local/share/whisper-meetings/`, separately from the plugin cache. They survive plugin updates and remain until you remove them.

- Audio is not uploaded by the plugin. Analysis sends the transcript text into the current Codex agent's context.
- Calendar access uses a separately connected host integration. This plugin does not store Google credentials, join Meet or change calendar events.
- Recording and transcription run in the background. Live text is provisional and can lag behind on slower hardware. Final transcription and optional speaker detection run after stopping.
- The panel and cross-chat delivery depend on host capabilities. Live device scenarios and production-host integration still need verification; synthetic tests do not establish live-call reliability.

[Privacy policy](plugins/whisper-meetings/PRIVACY.md) · [Usage terms](plugins/whisper-meetings/TERMS.md) · [MIT license](LICENSE)

## Documentation

- [Installation, updates and troubleshooting](docs/INSTALLATION.md)
- [Recording, speakers, calendar links and local files](docs/USAGE.md)
- [Development and verification](docs/DEVELOPMENT.md)
- [Validation results](VALIDATION.md)
- [OpenAI compatibility and directory status](docs/OPENAI_STANDARDS.md)

Built with [faster-whisper](https://github.com/SYSTRAN/faster-whisper), Apple's audio frameworks, MCP Apps and optional [FluidAudio](https://github.com/FluidInference/FluidAudio). Third-party licenses and model attribution are retained during setup; see [notices](plugins/whisper-meetings/THIRD_PARTY_NOTICES.md).
