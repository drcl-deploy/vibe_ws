#!/usr/bin/env python3
"""Compose the simulator's camera-equipped G1 and the assets-owned Repose scene."""

import hashlib
import os
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def scene_directory(root=ROOT):
    """Use a share per checkout; keep the existing direct launch paths usable."""
    root = root.resolve()
    share = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share')
    if not share.is_absolute():
        raise ValueError('XDG_DATA_HOME must be absolute')
    key = root.name + '-' + hashlib.sha256(str(root).encode()).hexdigest()[:8]
    output = share / 'vibe/scenes' / key
    shortcut = root / 'generated'
    if shortcut.is_symlink():
        if shortcut.resolve() != output:
            # A moved/copied checkout gets its own files before regeneration.
            # Leave the previous checkout's scenes and any hand edits intact.
            if output.exists():
                raise ValueError('Both scene locations exist; local files left untouched: ' + str(output))
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(shortcut.resolve(strict=True), output)
            shortcut.unlink()
    elif shortcut.exists():
        # Preserve local generated files during the one-time move to the share.
        # Never merge two directories or discard hand edits implicitly.
        if output.exists():
            raise ValueError('Both scene locations exist; local files left untouched: ' + str(output))
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(shortcut), str(output))
    output.mkdir(parents=True, exist_ok=True)
    if not shortcut.is_symlink():
        shortcut.symlink_to(output, target_is_directory=True)
    return output


def main():
    from assets.repose_scene import generate

    source = ROOT / 'unitree_mujoco/unitree_robots/g1/g1_29dof_with_camera.xml'
    scenes = scene_directory()
    print(generate(source, scenes / 'repose'))
    output = scenes / 'g1'
    output.mkdir(parents=True, exist_ok=True)
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    robot = ET.parse(source, parser=parser)
    compiler = robot.getroot().find('compiler')
    compiler.set('meshdir', str((source.parent / compiler.get('meshdir', '.')).resolve()))
    robot.write(output / 'robot.xml', encoding='unicode')
    scene = ET.parse(source.parent / 'scene_29dof.xml')
    scene.getroot().find('include').set('file', 'robot.xml')
    scene_path = output / 'g1.xml'
    scene.write(scene_path, encoding='unicode')
    print(scene_path)


if __name__ == '__main__':
    main()
