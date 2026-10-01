#!/bin/sh
set -eu
PLUGIN_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
DATA_DIR=${WHISPER_MEETINGS_HOME:-"$HOME/.local/share/whisper-meetings"}
PYTHON="$DATA_DIR/runtime/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  echo "Run: python3 \"$PLUGIN_DIR/scripts/setup.py\" before using Whisper Meetings." >&2
  exit 1
fi
exec "$PYTHON" "$PLUGIN_DIR/server.py"
