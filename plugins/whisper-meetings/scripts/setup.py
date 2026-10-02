#!/usr/bin/env python3
"""Explicit one-time dependency/model setup; never invoked by capture tools."""
import argparse
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

PLUGIN = Path(__file__).resolve().parents[1]


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["tiny", "base", "small", "medium", "large-v3", "turbo"], default="small")
    parser.add_argument("--skip-model", action="store_true")
    parser.add_argument("--diarization", action="store_true", help="Install optional native speaker processing and public Core ML models; no account required")
    args = parser.parse_args()
    if sys.platform != "darwin" or int(platform.mac_ver()[0].split(".")[0]) < 15:
        parser.error("Recording requires macOS 15+. File transcription code can run on other platforms.")
    uv = shutil.which("uv") or str(Path.home() / ".local/bin/uv")
    if not Path(uv).is_file():
        parser.error("Install uv first: https://docs.astral.sh/uv/getting-started/installation/")
    home = Path(os.environ.get("WHISPER_MEETINGS_HOME", "~/.local/share/whisper-meetings")).expanduser().resolve()
    runtime = home / "runtime"
    runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name in ("pyproject.toml", "uv.lock"):
        shutil.copyfile(PLUGIN / name, runtime / name)
    subprocess.run([uv, "sync", "--project", str(runtime), "--python", "3.12", "--frozen", "--no-dev"], check=True)
    architecture = platform.machine()
    binary = runtime / "capture-0.5.0"
    subprocess.run(["xcrun", "swiftc", "-O", "-parse-as-library", "-swift-version", "5",
                    "-target", architecture + "-apple-macosx15.0", str(PLUGIN / "native/Capture.swift"),
                    "-Xlinker", "-sectcreate", "-Xlinker", "__TEXT", "-Xlinker", "__info_plist", "-Xlinker", str(PLUGIN / "native/Info.plist"),
                    "-o", str(binary)], check=True)
    subprocess.run(["codesign", "--force", "--sign", "-", "--identifier", "in.legost.whisper-meetings.capture", str(binary)], check=True)
    if not args.skip_model:
        subprocess.run([str(runtime / ".venv/bin/python"), str(PLUGIN / "scripts/download_model.py"), args.model], check=True)
    if args.diarization:
        if architecture != 'arm64':
            parser.error('Optional Core ML diarization currently requires an Apple Silicon Mac.')
        from build_diarization import build
        build(PLUGIN, runtime)
        subprocess.run([str(runtime / ".venv/bin/python"), str(PLUGIN / "scripts/download_diarization.py")], check=True)
    print("Setup complete. Data:", home)
    subprocess.run([str(binary), "--check"], check=True)


if __name__ == "__main__":
    main()
