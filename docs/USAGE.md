# Using Whisper Meetings

The interface is English. Speech recognition and report language are independent of the interface. Existing meeting titles, transcripts and reports retain their own language.

## Recording sources

| Headphones checkbox | Sources | How remote voices are captured |
| --- | --- | --- |
| Unchecked, the default | Microphone only, through AVAudioEngine | Through your speakers into the microphone. |
| Checked | Microphone and Mac playback, through ScreenCaptureKit | From Mac playback, including sounds from other apps. |

The choice is locked during recording. Two audio tracks use a shared timeline. Channel labels `microphone` and `system` describe recording sources, not individual people.

Only one recording can run at a time. The recording process survives MCP disconnects, so disabling the plugin does not stop it. Stop explicitly before uninstalling or disabling. The maximum recording duration is twelve hours; the native recorder also stops if its controlling job process is lost.

Use **Pause recording** to discard audio during a break. Wait for **Paused**; **Pausing…** is not yet confirmed. The timer freezes and the paused interval is excluded from both tracks. **Resume recording** continues the same meeting; **Resuming…** becomes **Recording** after native acknowledgement. You can stop while paused.

**Transcribe during recording** is enabled by default for new recordings. Whisper reads separate finalized ~12-second chunks locally. The panel displays recent provisional segments; `meetings_read_live_transcript` exposes the paginated draft. Chunk boundaries, CPU speed and the shared model queue can affect text and latency. Drafts do not have final evidence hashes or reliable speaker identities. Audio capture does not wait for transcription.

Live and final transcription have independent switches. Turning live text off does not stop audio; an already decoding chunk may finish. A live error disables live chunk production, retains the draft and full audio, and leaves capture running. Re-enable live text to retry or process the saved audio later. Analysis and handoffs require the final ready transcript.

Final transcription runs after stopping. Disable **Transcribe after stopping** to keep an audio-only recording, then transcribe it later. A failed job retains audio and exposes the error for retry.

## Transcripts and reports

Whisper runs locally through faster-whisper using CPU/int8 inference. The panel offers Automatic, Russian and English speech-language choices. Automatic detection is the default; Russian can also be selected explicitly with `language="ru"` in a tool call.

**Analyze with Codex** asks the current agent to read the transcript and save the report. Whisper supplies the transcript; the host agent supplies the analysis.

Reports begin with one or two sentences, followed by themed lists, decisions, tasks, risks and open questions. Report text omits recording links, timestamps and segment IDs. Structured JSON retains source evidence IDs and the current transcript hash to validate the saved analysis. Unstated owners and deadlines remain unspecified.

To refresh legacy Markdown report formatting without modifying audio or stored JSON:

```sh
~/.local/share/whisper-meetings/runtime/.venv/bin/python plugins/whisper-meetings/scripts/refresh_reports.py
```

Use your configured runtime path if you changed `WHISPER_MEETINGS_HOME`.

## Speaker detection

[Install the optional models](INSTALLATION.md#add-speaker-detection), then enable **Distinguish speakers** before recording or importing. For a transcribed meeting, use **Identify speakers**. Processing runs after transcription; live speaker labels are not included.

- Labels estimate voices within one meeting and channel. They do not verify identities.
- You can assign names to labels. Embeddings are not saved or compared across meetings.
- Overlapping speech and ambiguous attribution retain candidate speakers rather than assigning the words to one person.
- Simultaneous microphone and Mac speech may be echo; two channels do not prove there are two different people.
- Detection does not recover words lost in mixed audio or create separate remote-participant audio tracks.
- Renaming or reprocessing changes the transcript hash. Analyze the meeting again to refresh the report.
- A speaker-processing failure preserves the successful Whisper transcript.

The selected public [Community-1-derived Core ML models](https://huggingface.co/FluidInference/speaker-diarization-coreml) use CC-BY-4.0; the [FluidAudio SDK](https://github.com/FluidInference/FluidAudio) uses Apache-2.0. Setup downloads pinned revisions and retains licenses, attribution, provenance and checksums alongside the installation. No login or token is required. The native helper preserves overlapping intervals rather than exclusive segments.

## Calendar and Google Meet

**Public preview:** pasting a Meet link works without account setup. Direct Google login appears only in locally configured installations; the public package contains no OAuth client secret. See [Google preview setup](GOOGLE_CALENDAR.md).

In a configured installation, click **Connect Google**. Sign in in your system browser and allow read-only calendar access. Return to the panel: choose a meeting directly from the dropdown. Its title and Calendar/Meet links are attached when you start recording. Use **Refresh meetings** to reload the next seven days from your primary calendar, or **Disconnect** to remove the connection. Google tokens remain in macOS Keychain.

You can instead expand **Or paste a Google Meet link** and paste the URL. Start a recording with that link, or use **Link to selected recording** to attach it to a saved meeting. This does not require a calendar account or a conversation with the agent.

The server requests only identifiers, title, times and meeting links. Attendees and event descriptions are excluded. Older agent-supplied event metadata tools remain available for compatibility.
Linking an event does not join Meet or start recording, and is not Google Meet's native recording feature.

## Context for another chat

Open **Another agent**, choose an area, enter the next task and click **Prepare package**. The plugin saves Markdown and JSON locally. Including the full transcript is optional.

To request delivery, supply the exact existing chat name and click **Ask Codex to transfer**. Codex uses host tools when available and reports the delivery result in chat. Preparing a package alone does not send it. If the host cannot receive panel messages, copy the displayed prompt into your chat.

## Local files

The default data directory is `~/.local/share/whisper-meetings/`. Set `WHISPER_MEETINGS_HOME` to use another directory consistently during setup and server operation.

```text
runtime/                           Python environment and native helpers
models/small/                      Whisper model and revision information
models/speaker-diarization-coreml/  Optional speaker models
meetings.sqlite3                   Job state
meetings/<id>/
  microphone.wav                   When microphone capture is used
  system.wav                       When Mac playback capture is used
  meeting.json                     Meeting metadata
  live-transcript.json             Optional provisional draft
  live-chunks/                     Temporary finalized WAV chunks
  capture-state.json               Native pause acknowledgement and timer
  transcript.json                  Final timed segments and source IDs
  diarization.json                 Optional voice and overlap intervals
  transcript.md / .txt / .srt       Transcript exports
  analysis.json / .md              Agent-supplied report
  handoffs/                        Context packages
```

The archive is outside the plugin cache and survives reinstallation. New files are restricted to the current user. There is no automatic deletion.

Audio processing is local. Transcript text read by the Codex agent follows that host/model provider's processing settings. See the [privacy policy](../plugins/whisper-meetings/PRIVACY.md).
