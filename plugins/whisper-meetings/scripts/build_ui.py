"""Build with locked npm dependencies outside the distributable plugin folder."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

web = Path(__file__).resolve().parents[1] / "web"
with tempfile.TemporaryDirectory(prefix="whisper-meetings-build-") as temporary:
    for name in ("package.json", "package-lock.json"):
        shutil.copyfile(web / name, Path(temporary) / name)
    subprocess.run(["npm", "ci", "--prefix", temporary, "--no-audit", "--no-fund"], check=True)
    subprocess.run(["node", str(web / "build.mjs")], env={**os.environ, "WHISPER_BUILD_DEPS": temporary}, check=True)
