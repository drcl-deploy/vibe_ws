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

from install_state import locked, lock_history, read_json, write_json

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


def artifact_path(root, relative):
    path = root / relative
    if root.resolve() not in path.resolve().parents or path.is_symlink():
        raise ValueError('Artifact destination escapes storage root or is a symlink')
    return path


def fetch(lock_path, artifact_root):
    artifact_root = Path(artifact_root)
    lock = json.loads(Path(lock_path).read_text())
    if lock.get('schema') != 'vibe.hf_artifacts.v1':
        raise ValueError('Expected a vibe.hf_artifacts.v1 lock with full HF commit revisions')
    for relative, spec in lock['files'].items():
        artifact_path(artifact_root, relative)
        if not re.fullmatch(r'[0-9a-f]{40}', spec['revision']):
            raise ValueError('HF revision must be a full commit SHA')
        if not re.fullmatch(r'[0-9a-f]{64}', spec['sha256']):
            raise ValueError('Invalid SHA-256')
    artifact_root.mkdir(parents=True, exist_ok=True)
    with locked(artifact_root / '.vibe-artifacts.lock'):
        _fetch(lock['files'], artifact_root, Path(lock_path))


def _fetch(files, root, lock_path):
    receipt_path = root / '.vibe-artifacts.json'
    receipt = read_json(receipt_path)
    installed = receipt.setdefault('files', {})
    # Check every local export before downloading or replacing any of them.
    for relative, spec in files.items():
        destination = artifact_path(root, relative)
        previous = installed.get(relative, {}).get('sha256')
        if destination.exists():
            actual = digest(destination)
            if actual not in (spec['sha256'], previous):
                known = False
                if previous is None and lock_path.name == 'artifacts.lock.json':
                    for text in lock_history(lock_path.parent, lock_path.name):
                        old = json.loads(text).get('files', {}).get(relative, {})
                        if old.get('sha256') == actual:
                            installed[relative] = old
                            known = True
                            break
                if not known:
                    raise ValueError('Different local artifact; left untouched: ' + str(destination))

    pending = receipt.get('pending')
    if pending and (pending['relative'] not in files
                    or pending['sha256'] != files[pending['relative']]['sha256']):
        partial = artifact_path(root, pending['relative']).parent / ('.vibe-' + pending['sha256'] + '.partial')
        if not re.fullmatch(r'[0-9a-f]{64}', pending['sha256']) or partial.is_symlink():
            raise ValueError('Invalid pending artifact receipt')
        partial.unlink(missing_ok=True)
        receipt.pop('pending')
        write_json(receipt_path, receipt)

    for relative, spec in files.items():
        destination = artifact_path(root, relative)
        expected = spec['sha256']
        previous = installed.get(relative, {}).get('sha256')
        if destination.exists() and digest(destination) == expected:
            print('Verified: ' + relative)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            partial = destination.parent / ('.vibe-' + expected + '.partial')
            pending = {'relative': relative, 'sha256': expected}
            if partial.is_symlink() or (partial.exists() and receipt.get('pending') != pending):
                raise ValueError('Unrecognized partial artifact; left untouched: ' + str(partial))
            receipt['pending'] = pending
            write_json(receipt_path, receipt)
            if not (partial.exists() and partial.stat().st_size == spec['bytes']
                    and digest(partial) == expected):
                url = 'https://huggingface.co/{}/resolve/{}/{}'.format(
                    urllib.parse.quote(spec['repo_id'], safe='/'), spec['revision'],
                    urllib.parse.quote(spec['path'], safe='/'))
                with urllib.request.urlopen(urllib.request.Request(url), timeout=120) as response, partial.open('wb') as output:
                    shutil.copyfileobj(response, output)
            if partial.stat().st_size != spec['bytes'] or digest(partial) != expected:
                raise ValueError('Artifact checksum or byte count mismatch: ' + relative)
            # Recheck ownership after the download: an editor may have changed
            # the old export while the network transfer was in progress.
            if destination.exists() and digest(destination) not in (expected, previous):
                raise ValueError('Different local artifact; left untouched: ' + str(destination))
            partial.replace(destination)
            print('Fetched and verified: ' + relative)
        installed[relative] = dict(spec)
        if receipt.get('pending', {}).get('relative') == relative:
            receipt.pop('pending')
        write_json(receipt_path, receipt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(os.environ.get('VIBE_ARTIFACT_ROOT', ROOT / 'artifacts')))
    parser.add_argument('--lock', required=True)
    args = parser.parse_args()
    fetch(args.lock, args.root)



if __name__ == '__main__':
    main()
