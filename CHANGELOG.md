# Changelog

## 0.4.1 — 2026-10-02

- English-only interface and install listing; removed Russian interface copy and RU/EN switch.
- Automatic, Russian and English speech recognition remain available.
- Report requests follow the requested language or the transcript language independently of the interface. Existing reports are preserved.

## 0.4.0 — 2026-10-01

- Unchecked headphones checkbox defaults new recordings to microphone only through AVAudioEngine; headphones enable microphone + Mac playback. The source choice is frozen while recording.
- Short report summary and themed bullet sections; legacy long summaries are presented as readable points.
- Removed segment links/IDs from report UI and Markdown; structured JSON retains evidence validation.
- Explicit local report-format refresh, preserving source JSON/audio.
- Added capture-routing/report regression tests and a native synthetic microphone-writer check.

## 0.3.0 — 2026-10-01

- Optional native Core ML speaker diarization with a pinned public FluidAudio SDK/model snapshot; no account, Hugging Face token or API key required.
- Track-scoped speaker estimates, regular overlap-preserving time intervals, conservative segment/word attribution and explicit ambiguity/echo flags.
- User-supplied speaker aliases propagated to exports/handoffs; renaming or reprocessing invalidates previous analysis.
- Background postprocessing of ready recordings and preservation of successful ASR if optional processing fails.
- Russian/English/automatic speech-language controls independent of interface language.
- Additional concurrency, overlap, attribution, export and failure-recovery tests.

## 0.2.0 — 2026-10-01

- MCP Apps panel with compact inline recording controls and a full meeting workspace.
- RU/EN UI, host theme/style tokens, keyboard-accessible tabs and responsive layouts.
- Meeting library, filtering, paginated timestamped transcripts and evidence links.
- Local microphone/system-audio capture with durable background jobs, stop controls and optional offline Whisper transcription.
- Codex analysis request and local structured analysis with transcript hash/evidence validation.
- Local Markdown/JSON handoff packages and explicit recipient-based transfer requests through the host.
- Optional Calendar/Meet event binding using user/host-supplied minimal event metadata. Connected host calendar integrations remain separate.
- Portable Agent Plugins packaging, explicit tool annotations, privacy/usage documents and reproducible builds.

This is a prerelease. Synthetic transcription and protocol/UI tests pass. Live Zoom/Meet capture, device switching, sleep/wake and rendering in each production host still need real-world verification. No universal-directory approval is claimed.
