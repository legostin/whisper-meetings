"""Build the optional helper from a pinned, checksummed public SDK snapshot.
Avoid fetching the SDK's entire Git history on every new user's machine.
"""
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
from urllib.request import urlopen

REVISION = 'c388107348134698135cfd34f3f59dc823b6e7ce'
ARCHIVE_SHA256 = 'ad1c45e0b1ee5f29f10f77198e6562e181a2785f66a914d680147c0a5a10b95b'


def build(plugin, runtime):
    archive = runtime / ('FluidAudio-' + REVISION + '.tar.gz')
    if not archive.is_file() or hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA256:
        with urlopen('https://codeload.github.com/FluidInference/FluidAudio/tar.gz/' + REVISION, timeout=60) as response:
            data = response.read(32 * 1024 * 1024 + 1)
        if len(data) > 32 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != ARCHIVE_SHA256:
            raise RuntimeError('SDK snapshot integrity check failed; no code was executed')
        archive.write_bytes(data)
    project = runtime / 'diarizer-source'
    project.mkdir(exist_ok=True)
    sdk = project / 'FluidAudio'
    if not (sdk / '.verified-snapshot').exists():
        with tarfile.open(archive) as tar:
            members = tar.getmembers()
            if sum(member.size for member in members) > 128 * 1024 * 1024:
                raise RuntimeError('SDK snapshot unexpectedly large')
            for member in members:
                relative = Path(*Path(member.name).parts[1:])
                destination = sdk / relative
                if relative.is_absolute() or '..' in relative.parts or member.issym() or member.islnk():
                    raise RuntimeError('Unsafe SDK archive entry')
                if member.isdir():
                    destination.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(tar.extractfile(member).read())
        (sdk / '.verified-snapshot').write_text(ARCHIVE_SHA256)
    template = (plugin / 'native/diarization/Package.swift').read_text()
    template, count = re.subn(r'\.package\(url: "https://github.com/FluidInference/FluidAudio.git",\s*revision: "' + REVISION + r'", traits: \[\]\)',
                             '.package(path: "FluidAudio", traits: [])', template)
    if count != 1:
        raise RuntimeError('Unexpected helper dependency; update the pinned SDK builder')
    (project / 'Package.swift').write_text(template)
    shutil.copytree(plugin / 'native/diarization/Sources', project / 'Sources', dirs_exist_ok=True)
    scratch = runtime / 'native-diarization-build'
    subprocess.run(['xcrun', 'swift', 'build', '--package-path', str(project), '--scratch-path', str(scratch),
                    '-c', 'release', '--product', 'meeting-diarizer'], check=True)
    target = runtime / 'meeting-diarizer'
    shutil.copyfile(scratch / 'release/meeting-diarizer', target)
    target.chmod(0o700)
    for bundle in (scratch / 'release').glob('FluidAudio*.bundle'):
        shutil.copytree(bundle, runtime / bundle.name, dirs_exist_ok=True)
    for name in ('LICENSE', 'NOTICE'):
        source = sdk / name
        if source.exists():
            shutil.copyfile(source, runtime / ('FluidAudio-' + name))
    subprocess.run(['codesign', '--force', '--sign', '-', str(target)], check=True)
