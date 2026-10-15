"""Small, atomic receipts for installer-owned files and build outputs."""

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import subprocess
import tempfile
import uuid


def read_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return {} if default is None else default
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise ValueError('Cannot read installation receipt {}: {}'.format(path, error))
    if not isinstance(value, dict):
        raise ValueError('Invalid installation receipt: ' + str(path))
    return value


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def state_directory(root):
    root = Path(root).resolve()
    path = root / '.cache/vibe-install'
    if root not in path.resolve().parents:
        raise ValueError('Installer cache escapes workspace: ' + str(path))
    return path


def lock_history(root, filename):
    """Recognize releases installed before receipts existed, using local Git only."""
    root = Path(root).resolve()
    if not (root / '.git').exists():
        return
    result = subprocess.run(['git', '-C', str(root), 'log', '-n', '100', '--format=%H', '--', filename],
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if result.returncode:
        return
    for commit in result.stdout.splitlines():
        previous = subprocess.run(['git', '-C', str(root), 'show', commit + ':' + filename],
                                  text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        if previous.returncode == 0:
            yield previous.stdout


@contextmanager
def locked(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Another installer is using ' + str(path))
        yield stream.fileno()


def inside(root, relative):
    root = Path(root).resolve()
    relative = Path(relative)
    path = root / relative
    if (relative.is_absolute() or '..' in relative.parts
            or root not in path.resolve().parents or path.is_symlink()):
        raise ValueError('Managed path escapes workspace or is a symlink: ' + str(relative))
    return path


def archive(root, relative, label):
    """Preserve generated files instead of deleting unknown or failed contents."""
    root = Path(root).resolve()
    path = inside(root, relative)
    if not path.exists():
        return
    destination = state_directory(root) / 'previous' / (label + '-' + uuid.uuid4().hex)
    destination.parent.mkdir(parents=True, exist_ok=True)
    path.rename(destination)
    print('Preserved {} at {}'.format(path, destination), flush=True)
    return destination


def prepare_build(root, name, inputs, outputs):
    """Retire stale outputs once; an interrupted build with the same inputs resumes."""
    root = Path(root).resolve()
    receipt_path = state_directory(root) / 'builds.json'
    receipts = read_json(receipt_path)
    previous = receipts.get(name, {})

    # Finish a rotation interrupted between directory moves. The destination
    # names were persisted before moving anything, so retries never mix builds.
    if 'moving' in previous:
        for relative, backup in previous['moving']:
            source = inside(root, relative)
            destination = inside(root, backup)
            if source.exists():
                if destination.exists():
                    raise ValueError('Both build locations exist; left untouched: ' + str(source))
                destination.parent.mkdir(parents=True, exist_ok=True)
                source.rename(destination)
                print('Preserved {} at {}'.format(source, destination), flush=True)
        previous.pop('moving')
        write_json(receipt_path, receipts)

    if previous.get('inputs') == inputs:
        return

    token = name + '-' + uuid.uuid4().hex
    moves = []
    for relative in outputs:
        source = inside(root, relative)
        if source.exists():
            backup = '.cache/vibe-install/previous/{}/{}'.format(token, relative)
            inside(root, backup)
            moves.append([relative, backup])
    receipts[name] = {'inputs': inputs, 'moving': moves}
    write_json(receipt_path, receipts)
    if moves:
        prepare_build(root, name, inputs, outputs)
    else:
        receipts[name].pop('moving')
        write_json(receipt_path, receipts)
