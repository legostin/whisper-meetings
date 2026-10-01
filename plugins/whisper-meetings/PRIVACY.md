# Whisper Meetings privacy policy

Effective date: October 1, 2026. Publisher: [legostin](https://github.com/legostin).
Support: [GitHub Issues](https://github.com/legostin/whisper-meetings/issues).

Whisper Meetings is a local application for macOS. Recording begins only after a user requests it. It records microphone audio and all Mac playback, which can include voices, other applications and notifications. Use headphones and obtain the permissions needed for your meeting. It stores the audio, meeting title and times, transcription, optional analysis and handoff packages on the user's computer. It does not save video or screen images.

Optional calendar binding stores only event/calendar identifiers, title, start/end times and Calendar/Meet links supplied by the user or host. It does not store attendees, event descriptions, Google credentials or OAuth tokens. A connected host calendar integration has its own permissions and privacy policy. Whisper Meetings does not read or change Google Calendar directly.

Whisper transcription runs locally with the installed model. The publisher operates no meeting backend, collects no analytics and receives no recordings, transcripts or account information. The embedded UI contains no remote assets or tracking. Installation downloads dependencies and model files from their registries/providers; those providers may receive normal request information such as IP address. The publisher does not receive it.

When a user asks the current Codex agent to read or analyze a transcript, the text becomes part of that agent's context and may be processed by the user's configured model provider, including OpenAI. This analysis is not necessarily offline. When the user explicitly chooses another chat or project and requests a transfer, the host may share the selected package there. Merely preparing a handoff creates local files and sends no message. Audio is never uploaded by this plugin.

Data is retained locally until the user removes it. By default the archive is `~/.local/share/whisper-meetings/`. Files created by the server/worker have owner-only permissions. Uninstalling the plugin does not remove the archive or stop an already active recording; stop recording before uninstalling. There is no automatic deletion or cloud synchronization. To remove data, first stop all recording/transcription jobs, then remove selected meeting folders (and their corresponding local metadata) or the entire archive with your normal file tools. Removing the entire archive also removes the runtime and installed models.

Do not submit confidential recordings, transcripts, credentials or private logs to public GitHub Issues. Reports posted there are public and are handled under GitHub's privacy policy. If this application's data practices change, this policy and the package version will be updated. The publisher cannot access or delete records stored only on your computer.
