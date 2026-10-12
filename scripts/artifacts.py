#!/usr/bin/env python3
"""Stage unchanged ViBe exports, or fetch files from an explicitly pinned HF lock."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import shlex
import tempfile
import urllib.parse
import urllib.request

import yaml

from experiment import FAMILIES, ROOT, load, pair


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


def import_exports(name, policy, encoder, family, artifact_root):
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]*', name):
        raise ValueError('Use a simple experiment name')
    policy, policy_manifest, _ = pair(policy, Path.cwd())
    encoder, encoder_manifest, _ = pair(encoder, Path.cwd())
    artifact_root = artifact_root.expanduser().resolve()
    descriptor = artifact_root / 'experiments' / (name + '.yaml')
    # Validate together before copying any input or publishing a descriptor.
    config = dict(schema='vibe.experiment.v1', task_family=family,
                  policy=policy, encoder=encoder, scene='repose' if family == 'repose' else 'g1')
    with tempfile.TemporaryDirectory() as directory:
        candidate = Path(directory) / 'experiment.yaml'
        candidate.write_text(yaml.safe_dump(config))
        load(str(candidate), artifact_root=artifact_root)
    for key, source, manifest in [('policy', policy, policy_manifest), ('encoder', encoder, encoder_manifest)]:
        subdir = ('models' if key == 'policy' else 'encoders') + '/' + digest(source)[:16]
        for filename in [source, manifest]:
            destination = artifact_root / subdir / Path(filename).name
            checked_copy(filename, destination, digest(filename))
        config[key] = subdir + '/' + Path(source).name
    if family == 'repose':
        config.update(goal_color=4, planner='v9.3')
    if descriptor.exists() and yaml.safe_load(descriptor.read_text()) != config:
        raise ValueError('Different experiment exists; left untouched: ' + str(descriptor))
    descriptor.parent.mkdir(parents=True, exist_ok=True)
    descriptor.write_text(yaml.safe_dump(config, sort_keys=False))
    print('Experiment: ' + str(descriptor))
    print('VIBE_ARTIFACT_ROOT=' + shlex.quote(str(artifact_root)) + ' ./run.sh tracker ' + shlex.quote(name))


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
    commands = parser.add_subparsers(dest='command', required=True)
    add = commands.add_parser('import')
    add.add_argument('--name', required=True)
    add.add_argument('--policy', required=True)
    add.add_argument('--encoder', required=True)
    add.add_argument('--task-family', choices=sorted(FAMILIES), required=True)
    download = commands.add_parser('fetch')
    download.add_argument('--lock', required=True)
    args = parser.parse_args()
    if args.command == 'import':
        import_exports(args.name, args.policy, args.encoder, args.task_family, args.root)
    else:
        fetch(args.lock, args.root)


if __name__ == '__main__':
    main()
