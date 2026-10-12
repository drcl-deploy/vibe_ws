#!/usr/bin/env python3
"""Import missing pinned repositories, or verify existing checkouts."""

import argparse
from pathlib import Path
import re
import subprocess
import sys

import yaml


def git(path, *args):
    return subprocess.check_output(
        ['git', '-C', str(path), *args], text=True, stderr=subprocess.PIPE
    ).strip()


def inspect(root, repositories):
    missing, problems = {}, []
    for relative, spec in repositories.items():
        path = root / relative
        if (Path(relative).is_absolute() or '..' in Path(relative).parts
                or root not in path.resolve().parents):
            raise ValueError('Source path escapes workspace: ' + relative)
        if spec.get('type') != 'git' or not re.fullmatch(r'[0-9a-f]{40}', spec.get('version', '')):
            raise ValueError('Expected a full Git commit SHA for ' + relative)
        if not path.exists():
            missing[relative] = spec
            print('MISSING', relative)
            continue
        try:
            if Path(git(path, 'rev-parse', '--show-toplevel')).resolve() != path.resolve():
                raise ValueError('not an independent Git checkout')
            head = git(path, 'rev-parse', 'HEAD')
            dirty = git(path, 'status', '--porcelain')
            if head != spec['version']:
                problems.append(f'{relative}: expected {spec["version"]}, found {head}')
            if dirty:
                problems.append(f'{relative}: local changes; left untouched\n{dirty}')
            print(('DIRTY' if dirty else 'PINNED' if head == spec['version'] else 'MISMATCH'),
                  relative, head)
        except (subprocess.CalledProcessError, ValueError) as error:
            problems.append(f'{relative}: {error}')
    return missing, problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['check', 'import'])
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    repositories = yaml.safe_load((root / 'sources.repos').read_text())['repositories']
    missing, problems = inspect(root, repositories)
    if problems:
        print('\n'.join(problems), file=sys.stderr)
        return 1
    if args.command == 'import' and missing:
        # Preflight all existing paths before asking vcstool to create anything.
        # Never checkout/reset/clean an existing repository on the user's behalf.
        subprocess.run(['vcs', 'import', str(root)],
                       input=yaml.safe_dump({'repositories': missing}),
                       text=True, check=True)
        missing, problems = inspect(root, repositories)
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
