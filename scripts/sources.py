#!/usr/bin/env python3
"""Verify pinned sources, or reconcile clean installer-managed checkouts."""

import argparse
import hashlib
from pathlib import Path
import re
import subprocess
import sys

from install_state import archive, inside, locked, lock_history, read_json, state_directory, write_json


def git(path, *args):
    result = subprocess.run(['git', '-C', str(path), *args], text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise ValueError('{}: {}'.format(path, result.stderr.strip()))
    return result.stdout.strip()


def repositories(root):
    import yaml
    return yaml.safe_load((Path(root) / 'sources.repos').read_text())['repositories']


def validate(root, relative, spec):
    path = inside(root, relative)
    if (spec.get('type') != 'git'
            or not re.fullmatch(r'[0-9a-f]{40}', spec.get('version', ''))
            or not isinstance(spec.get('url'), str) or not spec['url']
            or spec['url'].startswith('-')):
        raise ValueError('Expected a Git URL and full commit SHA for ' + relative)
    return path


def checkout(path):
    if Path(git(path, 'rev-parse', '--show-toplevel')).resolve() != path.resolve():
        raise ValueError('Not an independent Git checkout: ' + str(path))
    dirty = git(path, 'status', '--porcelain')
    if dirty:
        raise ValueError('{}: local changes; left untouched\n{}'.format(path, dirty))
    return git(path, 'rev-parse', 'HEAD')


def inspect(root, specs):
    missing, problems = {}, []
    for relative, spec in specs.items():
        path = validate(root, relative, spec)
        if not path.exists():
            missing[relative] = spec
            print('MISSING', relative)
            continue
        try:
            head = checkout(path)
            if head != spec['version']:
                problems.append('{}: expected {}, found {}'.format(relative, spec['version'], head))
            print('PINNED' if head == spec['version'] else 'MISMATCH', relative, head)
        except (OSError, ValueError) as error:
            problems.append(str(error))
    return missing, problems


def has_commit(path, sha):
    return subprocess.run(['git', '-C', str(path), 'cat-file', '-e', sha + '^{commit}'],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def ancestor(path, before, after):
    return subprocess.run(['git', '-C', str(path), 'merge-base', '--is-ancestor', before, after],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def normalized_url(url):
    value = re.sub(r'^(?:https?://|ssh://)', '', url)
    if value.startswith('git@'):
        value = value[4:]
    value = value.replace(':', '/').rstrip('/')
    return value[:-4] if value.endswith('.git') else value


def legacy_pin(root, relative, head, origin):
    import json
    for text in lock_history(root, 'dependencies.lock.json' if relative == '.deps/unitree_sdk2' else 'sources.repos'):
        try:
            if relative == '.deps/unitree_sdk2':
                pin = json.loads(text)['unitree_sdk2']
                revision = pin['revision']
            else:
                import yaml
                pin = yaml.safe_load(text)['repositories'][relative]
                revision = pin['version']
            if revision == head and normalized_url(pin['url']) == normalized_url(origin):
                return True
        except (ValueError, KeyError, TypeError):
            continue
    return False


def synchronize(root, specs, call=None):
    root = Path(root).resolve()
    if call is None:
        def call(command):
            subprocess.run([str(part) for part in command], check=True)
    state = state_directory(root)
    with locked(state / 'sources.lock'):
        receipt_path = state / 'sources.json'
        receipts = read_json(receipt_path)
        existing = {}
        legacy = set()
        # Check every working tree before any fetch, clone or checkout.
        for relative, spec in specs.items():
            path = validate(root, relative, spec)
            if not path.exists():
                continue
            head = checkout(path)
            record = receipts.get(relative)
            if head != spec['version']:
                if record and head != record.get('revision'):
                    raise ValueError('{}: independent commits; local work left untouched'.format(path))
                if not record:
                    origin = git(path, 'remote', 'get-url', 'origin')
                    if legacy_pin(root, relative, head, origin):
                        legacy.add(relative)
                    elif normalized_url(origin) != normalized_url(spec['url']):
                        raise ValueError('{}: unrecognized checkout; left untouched'.format(path))
            existing[relative] = head

        # Fetch/validate all update targets before changing any working tree.
        for relative, head in existing.items():
            spec = specs[relative]
            path = root / relative
            if head == spec['version']:
                continue
            if not has_commit(path, spec['version']):
                command = ['git', '-C', path, 'fetch']
                if git(path, 'rev-parse', '--is-shallow-repository') == 'true':
                    command.append('--unshallow')
                call(command + [spec['url'], spec['version']])
            if relative not in receipts and relative not in legacy and not ancestor(path, head, spec['version']):
                raise ValueError('{}: independent commits; local work left untouched'.format(path))
            ignored = set(git(path, 'ls-files', '--others', '--ignored', '--exclude-standard').splitlines())
            tracked = set(git(path, 'ls-tree', '-r', '--name-only', spec['version']).splitlines())
            collisions = ignored & tracked
            if collisions:
                raise ValueError('{}: update would replace ignored local files; left untouched: {}'.format(
                    path, ', '.join(sorted(collisions))))

        for relative, spec in specs.items():
            path = root / relative
            target = spec['version']
            if relative not in existing:
                token = hashlib.sha256(relative.encode()).hexdigest()[:16]
                stage = state / 'staging' / ('source-' + token)
                if stage.exists():
                    # This private staging checkout was never exposed as a source
                    # repository. Preserve a failed checkout before starting again.
                    archive(root, stage.relative_to(root), 'partial-source')
                stage.parent.mkdir(parents=True, exist_ok=True)
                call(['git', 'init', '-q', stage])
                call(['git', '-C', stage, 'remote', 'add', 'origin', spec['url']])
                call(['git', '-C', stage, 'fetch', '--depth', '1', 'origin', target])
                call(['git', '-C', stage, '-c', 'advice.detachedHead=false', 'checkout', '--detach', target])
                attributes = stage / '.gitattributes'
                if attributes.is_file() and 'filter=lfs' in attributes.read_text():
                    call(['git', '-C', stage, 'lfs', 'install', '--local'])
                    call(['git', '-C', stage, 'lfs', 'pull'])
                if checkout(stage) != target:
                    raise ValueError('Incomplete source checkout: ' + str(stage))
                path.parent.mkdir(parents=True, exist_ok=True)
                # A concurrent user-created path must never be replaced.
                if path.exists():
                    raise ValueError('Source path appeared during installation: ' + str(path))
                stage.rename(path)
                print('IMPORTED', relative, target)
            elif existing[relative] != target:
                if ancestor(path, existing[relative], target):
                    call(['git', '-C', path, 'merge', '--ff-only', '--no-overwrite-ignore', target])
                else:
                    # An intentional pin rollback keeps the old branch and its
                    # commits intact. Never reset or delete a research branch.
                    call(['git', '-C', path, 'checkout', '--detach', '--no-overwrite-ignore', target])
                print('UPDATED', relative, target)
            else:
                print('PINNED', relative, target)
            receipts[relative] = {'revision': target, 'url': spec['url']}
            write_json(receipt_path, receipts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['check', 'import'])
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    specs = repositories(root)
    if args.command == 'import':
        synchronize(root, specs)
    missing, problems = inspect(root, specs)
    if missing or problems:
        print('\n'.join(problems), file=sys.stderr)
        return 1
    print('All source pins match; tracked and untracked source files are clean.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
