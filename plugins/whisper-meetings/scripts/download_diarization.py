#!/usr/bin/env python3
"""Explicit public Core ML model download. No login, token, or account required."""
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from diarization import MODEL, REVISION, model_directory


def main():
    os.umask(0o077)
    os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
    from huggingface_hub import snapshot_download
    directory = model_directory()
    manifest = directory / 'download.json'
    if manifest.exists():
        saved = json.loads(manifest.read_text())
        if saved.get('revision') == REVISION and all((directory / name).is_file() and
                hashlib.sha256((directory / name).read_bytes()).hexdigest() == checksum
                for name, checksum in saved['sha256'].items()):
            print('Verified local Core ML diarization model already installed.')
            return
    # Only Community-1-derived assets covered by the publisher's CC-BY-4.0 notice.
    patterns = ['Segmentation.mlmodelc/**', 'FBank.mlmodelc/**', 'Embedding.mlmodelc/**', 'PldaRho.mlmodelc/**',
                'plda-parameters.json', 'LICENSE', 'NOTICE.md', 'PROVENANCE.md', 'provenance.json', 'README.md']
    snapshot_download(MODEL, revision=REVISION, local_dir=directory, allow_patterns=patterns, token=False)
    names = [p.relative_to(directory).as_posix() for name in ('Segmentation', 'FBank', 'Embedding', 'PldaRho') for p in (directory / (name + '.mlmodelc')).rglob('*') if p.is_file()]
    names += ['plda-parameters.json']
    required = ['Segmentation.mlmodelc/coremldata.bin', 'FBank.mlmodelc/coremldata.bin',
                'Embedding.mlmodelc/coremldata.bin', 'PldaRho.mlmodelc/coremldata.bin']
    if not all((directory / name).is_file() for name in required) or len(names) < 10:
        sys.exit('Model download incomplete; retry explicit setup.')
    payload = {'model': MODEL, 'revision': REVISION, 'license': 'CC-BY-4.0',
               'attribution': 'Fluid Inference conversion of pyannote Community-1 — https://huggingface.co/' + MODEL,
               'sha256': {name: hashlib.sha256((directory / name).read_bytes()).hexdigest() for name in sorted(names)}}
    temporary = directory / 'download.json.tmp'
    temporary.write_text(json.dumps(payload, indent=2))
    temporary.replace(manifest)
    print('Installed public Core ML diarization model:', REVISION)


if __name__ == '__main__':
    main()
