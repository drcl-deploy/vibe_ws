#!/usr/bin/env python3
"""Download unchanged model files from an explicitly pinned Hugging Face lock."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    result = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def checked_copy(source, target, expected):
    """Never replace a different local export or leave a partial destination."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if digest(target) != expected:
            raise ValueError('Different local file exists; left untouched: ' + str(target))
        return
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
        temporary = Path(stream.name)
    try:
        shutil.copyfile(source, temporary)
        if digest(temporary) != expected:
            raise ValueError('Artifact checksum mismatch: ' + str(target))
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def fetch(lock_path, artifact_root):
    lock = json.loads(Path(lock_path).read_text())
    if lock.get('schema') != 'vibe.hf_artifacts.v1':
        raise ValueError('Expected a vibe.hf_artifacts.v1 lock with full HF commit revisions')
    for relative, spec in lock['files'].items():
        destination = artifact_root / relative
        if artifact_root.resolve() not in destination.resolve().parents:
            raise ValueError('Artifact destination escapes storage root')
        if not re.fullmatch(r'[0-9a-f]{40}', spec['revision']):
            raise ValueError('HF revision must be a full commit SHA')
        if not re.fullmatch(r'[0-9a-f]{64}', spec['sha256']):
            raise ValueError('Invalid SHA-256')
        if destination.exists():
            if digest(destination) != spec['sha256']:
                raise ValueError('Different local artifact; left untouched: ' + str(destination))
            print('Verified: ' + relative)
            continue
        url = 'https://huggingface.co/{}/resolve/{}/{}'.format(
            urllib.parse.quote(spec['repo_id'], safe='/'), spec['revision'],
            urllib.parse.quote(spec['path'], safe='/'))
        with tempfile.TemporaryDirectory() as directory:
            downloaded = Path(directory) / 'payload'
            request = urllib.request.Request(url)
            with urllib.request.urlopen(request, timeout=120) as response, downloaded.open('wb') as output:
                shutil.copyfileobj(response, output)
            if downloaded.stat().st_size != spec['bytes']:
                raise ValueError('Artifact byte count mismatch: ' + relative)
            checked_copy(downloaded, destination, spec['sha256'])
        print('Fetched and verified: ' + relative)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(os.environ.get('VIBE_ARTIFACT_ROOT', ROOT / 'artifacts')))
    parser.add_argument('--lock', required=True)
    args = parser.parse_args()
    fetch(args.lock, args.root)



if __name__ == '__main__':
    main()
