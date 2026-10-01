import json
import os
from pathlib import Path
import sys
from huggingface_hub import HfApi, snapshot_download

model = sys.argv[1]
if model not in {"tiny", "base", "small", "medium", "large-v3", "turbo"}:
    raise ValueError("Unsupported model")
repo = "mobiuslabsgmbh/faster-whisper-large-v3-turbo" if model == "turbo" else f"Systran/faster-whisper-{model}"
home = Path(os.environ.get("WHISPER_MEETINGS_HOME", "~/.local/share/whisper-meetings")).expanduser().resolve()
target = home / "models" / model
if (target / "model.bin").exists() and (target / "installed.json").exists():
    print("Already installed:", target)
else:
    revision = HfApi().model_info(repo).sha
    snapshot_download(repo, revision=revision, local_dir=target,
                      allow_patterns=["model.bin", "config.json", "tokenizer.json", "vocabulary.*", "preprocessor_config.json"])
    (target / "installed.json").write_text(json.dumps({"repository": repo, "revision": revision}, indent=2))
    print("Model installed:", target, "revision:", revision)
