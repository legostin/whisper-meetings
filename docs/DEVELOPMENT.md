# Development and verification

Run these commands from the repository root. Recording setup requires macOS 15 or later; optional Core ML speaker processing also requires Apple Silicon and Swift 6.2 or later. UI builds require Node.js and npm.

## Python checks

```sh
cd plugins/whisper-meetings
export UV_PROJECT_ENVIRONMENT="$HOME/.cache/whisper-meetings-dev-venv"
uv sync --python 3.12 --frozen
uv run pytest
uv run python ../../scripts/validate.py
```

The validator fetches canonical Agent Plugins schemas and checks the actual MCP tools, UI resource, CSP and OpenAI entrypoint metadata. It needs internet access for the schemas.

## Build the UI

From the repository root:

```sh
python3 plugins/whisper-meetings/scripts/build_ui.py
```

The build installs locked npm dependencies in a temporary directory outside the plugin and produces `plugins/whisper-meetings/web/dist/widget.html`. The bundled panel has no external scripts, fonts or trackers at runtime and uses host theme/style variables.

## Preview the UI

```sh
python3 scripts/preview.py
```

Open `http://127.0.0.1:8768/`. The preview is explicitly marked synthetic: it does not enable the microphone or deliver messages to Codex chats. Check compact/fullscreen modes, theme changes and responsive layout. Preview success does not establish production-host rendering.

## Install a local checkout

After [runtime setup](INSTALLATION.md), register this checkout instead of the Git release:

```sh
codex plugin marketplace add "$PWD"
codex plugin add whisper-meetings@whisper-local
```

If `whisper-local` is already registered to the public Git source, remove that marketplace registration first. Repeat the plugin add command after rebuilding; the installed plugin runs from Codex's cache, not directly from your source checkout.

Inspect Codex registration without creating a chat:

```sh
python3 plugins/whisper-meetings/scripts/host-check.py
```

## Offline MCP smoke test

After setup, use the installed runtime Python and a local synthetic speech file:

```sh
~/.local/share/whisper-meetings/runtime/.venv/bin/python plugins/whisper-meetings/scripts/smoke.py /absolute/path/synthetic-speech.wav
```

The smoke exercises the MCP resource, tool annotations, import, background transcription and reconnection, supplied grounded analysis, synthetic event binding and local handoff. It does not record the microphone or prove model-generated analysis in a production Codex chat.

For Russian recognition with optional speaker processing, add `--language auto --diarize` and supply a synthetic Russian recording. With speaker setup installed, run a controlled two-voice overlap check:

```sh
~/.local/share/whisper-meetings/runtime/.venv/bin/python plugins/whisper-meetings/scripts/smoke_overlap.py
```

This generates temporary speech with macOS voices, processes an artificial overlap and removes the temporary audio. It is not a live-call accuracy benchmark. If you configured another data directory, adjust the runtime paths.

## Package

```sh
python3 scripts/package.py
```

The deterministic source ZIP and SHA-256 file are written to `dist/`. The package excludes recordings, credentials, downloaded models, the runtime and node_modules.

## Code map

| File | Purpose |
| --- | --- |
| `plugins/whisper-meetings/server.py` | MCP tools and panel resource. |
| `plugins/whisper-meetings/meetings.py` | Archive, job state, analysis and handoffs. |
| `plugins/whisper-meetings/worker.py` | Detached capture/transcription jobs. |
| `plugins/whisper-meetings/calendar_links.py` | Minimal selected-event metadata. |
| `plugins/whisper-meetings/diarization.py` | Local voice estimation and conservative assignments. |
| `plugins/whisper-meetings/reporting.py` | Human-readable report formatting. |
| `plugins/whisper-meetings/native/Capture.swift` | macOS audio capture. |
| `plugins/whisper-meetings/analysis.schema.json` | Structured report schema. |
| `plugins/whisper-meetings/scripts/run-server.sh` | Start the existing runtime; never install dependencies automatically. |

See [validation results](../VALIDATION.md), [review scenarios](REVIEW_CASES.md) and [OpenAI compatibility](OPENAI_STANDARDS.md) for the evidence and remaining work. Public Git distribution is separate from approval for the OpenAI Plugins Directory.
