# Installation and updates

For a first installation, use the [five-command quick start](../README.md#install). Commands below run from the cloned `whisper-meetings` repository unless stated otherwise.

## Before installing

Check the tools in Terminal:

```sh
codex --version
uv --version
xcode-select -p
```

Recording requires macOS 15 or later. Speaker detection additionally requires Apple Silicon and Swift 6.2 or later; check with `xcrun swift --version`.

If Apple Command Line Tools are missing, run `xcode-select --install` and complete the system dialog. If `uv` is missing, follow its [official installation instructions](https://docs.astral.sh/uv/getting-started/installation/). If `codex` is missing, install or configure the [Codex CLI](https://developers.openai.com/codex/cli) before continuing.

Setup uses uv to install a Python 3.12 runtime and locked dependencies, builds the native recorder and downloads a Whisper model. You do not need to create a Python environment manually. Downloads happen during explicit setup, not when you open the panel or start recording.

## Update

Stop any active recording first: installing a plugin can replace its previous cached source files, which an existing recording worker may still need. To update an existing checkout and replace the marketplace's pinned release:

```sh
git fetch origin --tags
git checkout v0.6.0
codex plugin marketplace remove whisper-local
codex plugin marketplace add legostin/whisper-meetings --ref v0.6.0
codex plugin add whisper-meetings@whisper-local
```

Restart Codex or open a new chat to load the installed version. Removing the marketplace registration does not delete your separately stored meeting archive.

Updating from **0.5.x or earlier** requires setup to add the Google Keychain helper. Updates from 0.4.x also rebuild the recorder for pause/resume and live chunks. Installed models are reused:
```sh
python3 plugins/whisper-meetings/scripts/setup.py --skip-model
```

If your clone has local source changes, keep them before checking out another version. Do not discard them to force an update.

## Choose a model

The default is `small`. For a smaller download, choose `base` during setup:

```sh
python3 plugins/whisper-meetings/scripts/setup.py --model base
```

Available setup choices: `tiny`, `base`, `small`, `medium`, `large-v3`, `turbo`. Larger models use more memory and generally take longer to transcribe. Installed models appear in the panel's **Model** selector.

To add a model without rebuilding the recorder, use the installed runtime Python:

```sh
~/.local/share/whisper-meetings/runtime/.venv/bin/python plugins/whisper-meetings/scripts/download_model.py base
```

If you configured `WHISPER_MEETINGS_HOME`, replace the default runtime path above with yours.

## Add speaker detection

```sh
python3 plugins/whisper-meetings/scripts/setup.py --diarization
```

This builds the native FluidAudio helper and downloads pinned public Core ML models. It requires Apple Silicon and Swift 6.2 or later. No Hugging Face account, token or API key is needed. If you do not enable speaker detection, this setup is optional.

## Permissions

macOS asks for **Microphone** permission when recording microphone audio. Recording Mac playback also requires **Screen & System Audio Recording** permission. The recorder does not save video or screenshots.

Microphone-only recording does not request screen-recording permission. The permission entry can refer to the recorder or its launching application. If access is denied, inspect **System Settings → Privacy & Security**, then retry.

Ask Codex to run `meetings_doctor` to inspect setup and permissions without recording or opening a permission prompt.

## Troubleshooting

| Problem | Next step |
| --- | --- |
| `codex` or `uv` is not found | Complete that tool's installation and open a fresh Terminal window. |
| Setup cannot find or build Swift | Finish the Apple Command Line Tools/Xcode installation. Speaker detection needs Swift 6.2 or later. |
| The marketplace is already registered from another source/ref | Use the marketplace remove/add steps in [Update](#update). |
| The plugin or new interface does not appear | Repeat `codex plugin add whisper-meetings@whisper-local`, then restart Codex. |
| The panel cannot be displayed | Use the chat commands; panel rendering requires MCP Apps support in the host. |
| Remote voices are missing | With headphones, enable the headphones checkbox before starting. With speakers, check their volume and microphone placement. |
| Transcription or speaker processing fails | Read the meeting status. Saved audio can be transcribed again; a speaker-processing failure preserves a successful Whisper transcript. |

For issues, include the plugin version, macOS version, Mac architecture and error message in a [GitHub issue](https://github.com/legostin/whisper-meetings/issues). Share a synthetic reproduction when possible; keep private recordings and credentials out of the issue.
