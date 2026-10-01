"""Build a deterministic, source-only plugin ZIP. Never includes audio or models."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugins/whisper-meetings'
version = json.loads((PLUGIN / 'plugin.json').read_text())['version']
paths = ['plugin.json','mcp.json','pyproject.toml','uv.lock','server.py','meetings.py','calendar_links.py','diarization.py','worker.py','analysis.schema.json','README.md','LICENSE','PRIVACY.md','TERMS.md','THIRD_PARTY_NOTICES.md','web/dist/widget.html']
for directory in ('skills','scripts','native','assets','web'):
    paths += [p.relative_to(PLUGIN).as_posix() for p in (PLUGIN / directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts and not p.is_symlink()]
assert all(not Path(p).is_absolute() and '..' not in Path(p).parts for p in paths)
output = ROOT / 'dist'
output.mkdir(exist_ok=True)
archive = output / f'whisper-meetings-{version}.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for name in sorted(set(paths)):
        source=PLUGIN/name
        if source.is_symlink():
            raise ValueError(f'Symlink not allowed: {name}')
        info=zipfile.ZipInfo(name,date_time=(2026,10,1,0,0,0))
        info.external_attr=(0o100755 if name.endswith('.sh') else 0o100644)<<16
        info.compress_type=zipfile.ZIP_DEFLATED
        z.writestr(info,source.read_bytes())
checksum=hashlib.sha256(archive.read_bytes()).hexdigest()
(archive.with_suffix('.zip.sha256')).write_text(f'{checksum}  {archive.name}\n')
print(f'{archive.name}: {archive.stat().st_size} bytes; sha256={checksum}')
