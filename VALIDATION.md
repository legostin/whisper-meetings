# Verification — Whisper Meetings 0.5.0

Checked October 2, 2026 on Apple Silicon macOS. Scope and evidence are separated below; no directory approval or live-call recording success is claimed.

## Passed

- **0.5 pause/native chunk capture**: production audio writers exercised with generated PCM through `--test-streaming-sinks`. Five paused seconds excluded from both 25-second tracks; paused 0.9-amplitude PCM absent. Shared chunk boundaries 0–12, 12–24, 24–25; every published chunk decoded as a valid finalized WAV. Async microphone writer separately retains two of three buffers across pause/resume, with no system track. Native capture release compiles; no input device opened.
- **0.5 actual live Whisper worker**: `scripts/smoke_live.py` with offline Russian synthetic speech produced correct provisional text while a synthetic meeting remained recording. Draft survived another read/stop; no final hash or final transcript was fabricated, and no microphone was opened.
- **65 Python tests**: earlier 50 plus pause/native acknowledgement races, resume cancelling pending pause, stop while paused, paused single-recording exclusion, old-recorder rejection, independent live/final toggles, missing models, finalized chunk consumption/timestamps/cleanup, incomplete WAV exclusion, no new inference after stop/disable, draft pagination and rejection as final analysis, isolated live failure, and preserving a running legacy recorder during upgrade.

- **0.5 UI preview**: simulated pause/resume, frozen paused timer, stop while paused, independent live/final toggles, retained draft for audio-only stops and replacement by final text passed through the actual SDK bridge. A toggle regression found during browser verification was corrected and checked again. Draft analysis stays disabled; pause/resume controls remain available in compact inline mode. [Paused preview](docs/panel-live-pause-demo.jpg) uses synthetic data only.

- **0.4.1 English interface**: English HTML and control labels, no RU/EN switch or Russian listing translation; Automatic/Russian/English speech choices retained. SDK preview initialized even with a Russian host locale; simulated start/stop, default English meeting title, fullscreen/inline controls and existing Russian transcript display passed. Current official manifest/MCP validation and all 50 Python tests passed at 0.4.1. This change does not add live-device or production-host evidence.

- **0.4 source selection/report regression checks**: default microphone-only state, headphones-to-native-command propagation, readable overview/legacy summary, removed inline references in display/Markdown/handoff, and retained validated JSON evidence. Native `capture --test-microphone-sink` writes 4800 generated PCM frames into a valid 48 kHz WAV and microphone-only stats; no input device is opened. Native release build and diagnostics pass. Actual AVAudioEngine microphone-device capture remains unverified.

- **Previous 50 Python tests**: concurrency/single-recording enforcement, early stop, transcription preference, crash recovery, ordered transcript pagination, silence, timestamp rounding, source/hash validation, stale analysis exclusion, event binding, unneeded event data/unsafe URL/time rejection and explicit tool annotations. Additional cases cover simultaneous/sequential voices, word ambiguity, echo across independent channels, aliases in exports, concurrent diarization, stale analysis after speaker changes and preservation of ASR after a native failure/crash.
- **Official Agent Plugins schemas**: `plugin.json` and `mcp.json` validate against canonical 1.0.0 schemas. Local stdio uses bare `sh` and `${PLUGIN_ROOT}`. `scripts/validate.py` inspects all 22 tools and the actual MCP Apps resource contract, CSP and OpenAI entrypoint metadata.
- **Native build/diagnostics**: Swift compiler succeeded with macOS 15.0 deployment target; recorder ad hoc signed. `capture --check` reports authorized microphone and system-audio permission. This diagnostic does not start capture.
- **Optional speaker processing**: pinned public FluidInference/speaker-diarization-coreml revision `df2625ac79a7ac6b65ad868fee6d80f320da4232`; selected modern assets are CC-BY-4.0 with LICENSE/NOTICE/provenance retained. Explicit download uses `token=False` and succeeded without Hugging Face login. FluidAudio Apache-2.0 source snapshot `c388107348134698135cfd34f3f59dc823b6e7ce`, archive SHA-256 `ad1c45e0b1ee5f29f10f77198e6562e181a2785f66a914d680147c0a5a10b95b`. Native release build/signing and actual Core ML inference passed on Apple Silicon / Swift 6.3.3. Runtime loads supplied local models, disables exclusive-segment trimming and does not save embeddings.
- **Offline model**: faster-whisper `small`, Systran/faster-whisper-small revision `536b0662742c02347bc0e980a01041f333bce120`. Dependencies locked; PyAV 16.1.0 avoids the faster-whisper/PyAV 19 `metadata_errors` incompatibility.
- **Real MCP smoke**: 0.5.0 source smoke with 22 tools; earlier 0.4.0 source/installed smoke with 18 tools. Both read the bundled HTML resource; imported synthetic speech; disconnected/reconnected while the detached worker ran; waited for ready with `HF_HUB_OFFLINE=1`; read the actual transcript; saved/read back a supplied evidence-grounded analysis; staged and bound a synthetic event; exported Markdown/JSON with analysis, event and transcript. Russian auto-language import with diarize=true also passed, including a manual speaker alias and complete local handoff. Temporary audio/archive removed after the test. No microphone capture.
- **Codex registration (previous release)**: CLI installed/enabled 0.4.0; `plugin/read` via app-server finds `whisper_meetings` and enabled `whisper-meetings:meetings`. Inventory verification does not prove rendering of the panel in a production chat.
- **UI through actual MCP Apps SDK + synthetic loopback host**: bridge initialized, compact inline/fullscreen expansion, record/stop simulation, disabling transcription while the simulated recording continues, title search,  preparing a simulated local package, refusal to request delivery without a recipient, explicit recipient-based host message, host light/dark changes, neutral Codex-style controls using host color/font variables, and responsive 390 px view. The 0.3 UI also passed Russian speech-language/diarization option propagation in a simulated start/stop, speaker-name editing, stale analysis after renaming and unknown-speaker/overlap badges. The 0.4 UI passed both simulated headphone choices, frozen source selection during recording, short themed report lists, and absence of source-reference buttons/IDs in the report. DOM measurement: clientWidth 390, scrollWidth 390. The preview is visibly labelled synthetic and never invokes the recorder or sends a message to another Codex chat.

Synthetic English and Russian speech recognized completely:

> We decided to launch the project on Friday. Alex will prepare the release notes. The next meeting is on Monday.

> Мы решили выпустить новую версию в пятницу. Алексей подготовит инструкцию по установке. Следующая встреча состоится в понедельник.

**Real controlled overlap inference**: `scripts/smoke_overlap.py` generates local Samantha/Daniel speech, concatenates A, B, mixed A+B and A again. Native inference resolved two voices. In a 48.23-second fixture, expected mixed interval was 24.63–35.93 seconds and detected overlap was 24.60–35.93 seconds. The repeatable script also passed; synthesized timing varies slightly across runs. Ambiguous mixed text retained both candidates and no single speaker. Generated audio was temporary and removed. This is one controlled synthetic example, not a live-call accuracy benchmark.

The smoke analysis is supplied test data; the smoke does not claim that Whisper generates analysis or that a production Codex agent was exercised.

## Still requires verification

- A real microphone + Zoom/Meet recording, actual two-device timing, muted input, overlapping speech, audio-device switches and sleep/wake.
- Panel mounting, sidebar/thread entrypoints, host messages and calendar selection inside each production Codex/ChatGPT version. The source/SDK contracts and preview pass; actual UI mounting is not yet verified.
- Live Google Calendar retrieval and selection through the user's connected host integration. The local metadata/link/handoff operations are tested with synthetic events; no real calendar has been copied into the release.
- Actual cross-chat delivery through host tools. Local package creation is verified; the preview only verifies the message request contract.

## Directory submission

The authenticated OpenAI portal blocked upload before draft creation with: “You need a verified developer identity before you can create or upload a plugin.” The identity-verification page was opened for the publisher. No package has been submitted for review.

Public MCP submissions currently require remote HTTPS or a supported local-MCP path agreed with OpenAI. This package intentionally retains local stdio for Mac hardware access; see [OPENAI_STANDARDS.md](docs/OPENAI_STANDARDS.md). The Git marketplace and public source release are separate from Universal Plugin Directory approval.
