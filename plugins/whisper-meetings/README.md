# Whisper Meetings

Record meeting audio on your Mac, transcribe it locally with Whisper, and ask Codex for structured reports and context for other chats.

**Version 0.4.1 · Preview release · macOS 15+**

[Full installation guide](https://github.com/legostin/whisper-meetings#install) · [Usage guide](https://github.com/legostin/whisper-meetings/blob/main/docs/USAGE.md) · [Support](https://github.com/legostin/whisper-meetings/issues)

## Set up the local runtime

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Apple Command Line Tools or Xcode. From this plugin directory:

```sh
python3 scripts/setup.py
```

Setup builds the recorder, installs locked Python dependencies and downloads the default Whisper `small` model. The first setup needs internet access; transcription then uses installed local model files. No OpenAI API key or Hugging Face account is required by the plugin.

Use `--model base` for a smaller model or `--skip-model` to build the runtime and recorder without downloading a model.

## Start using it

Ask Codex: **“Open the meeting panel.”**

1. Enter a title and set **I am wearing headphones** to match your audio setup.
2. Click **Start recording** and allow the requested macOS audio permissions.
3. Click **Stop recording**. With **Transcribe after stopping** enabled, Whisper processes the saved audio.
4. Click **Analyze with Codex** under **Decisions & tasks** for a report.

Unchecked headphones means microphone only; remote voices must be audible through your speakers. Checked headphones means microphone and all Mac playback, including other apps. The source choice is locked during recording.

The interface is English. Automatic, Russian and English speech-language choices remain available. Reports use your requested language or otherwise the transcript language. Opening the panel never starts recording.

## Optional speaker detection

On Apple Silicon with Swift 6.2 or later:

```sh
python3 scripts/setup.py --diarization
```

This builds a pinned FluidAudio helper and downloads public Core ML models without a login or token. Enable **Distinguish speakers** before recording/importing, or click **Identify speakers** on a transcribed meeting.

Labels estimate voices within one meeting and channel; names are user-supplied. Overlap and ambiguous attribution remain marked. Detection cannot recover lost words. Renaming or reprocessing invalidates the old analysis; analyze again. A speaker-processing failure preserves the successful Whisper transcript.

## Calendar and other chats

**Choose from Google Calendar** asks the host to obtain selected events through an available, separately connected calendar integration. The plugin stores minimal event metadata and Calendar/Meet links. It does not store Google credentials, modify events, join Meet or start recording when an event is attached.

**Another agent** prepares local Markdown/JSON context packages. Sending a package is a separate, explicit request to Codex with an exact recipient chat name. Delivery and panel rendering depend on the host's capabilities.

## Data and limits

Audio stays on your Mac. Text read by the Codex agent is processed under that host/model provider's settings. Reports contain a short opening, themed points, decisions, tasks and risks, without visible recording links or segment IDs; JSON retains internal evidence validation.

The default archive is `~/.local/share/whisper-meetings/`, outside the plugin cache. It survives updates and has no automatic deletion. `WHISPER_MEETINGS_HOME` changes the directory.

Stop recording before disabling or uninstalling the plugin: background jobs survive MCP reconnects. One recording can run at a time, with a twelve-hour maximum. Transcription starts after stopping; live captions are not included.

This preview release still needs live device and production-host verification. It has not been approved for the OpenAI Plugins Directory. See [validation results](https://github.com/legostin/whisper-meetings/blob/main/VALIDATION.md).

[Privacy policy](PRIVACY.md) · [Usage terms](TERMS.md) · [License](LICENSE)
