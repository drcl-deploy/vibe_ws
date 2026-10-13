#!/usr/bin/env python3
"""Compose the checked-in examples with Unitree's camera-equipped G1."""

import hashlib
import copy
import json
import math
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


def write_xml(element, path):
    ET.indent(element)
    ET.ElementTree(element).write(path, encoding='unicode')


def generate(root=ROOT):
    source = root / 'unitree_mujoco/unitree_robots/g1/g1_29dof_with_camera.xml'
    samples = root / 'data/sample'
    specs = json.loads((samples / 'samples.json').read_text())['samples']
    output = scene_directory(root)
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    original = ET.parse(source, parser=parser).getroot()
    compiler = original.find('compiler')
    compiler.set('meshdir', str((source.parent / compiler.get('meshdir', '.')).resolve()))
    # Same camera rendering convention as the tested Repose generator.
    for geom in original.iter('geom'):
        if geom.get('group') == '1':
            geom.set('group', '2')
        elif geom.get('group', '0') == '0':
            geom.set('group', '3')
    paths = []
    for name, spec in specs.items():
        folder = output / name
        folder.mkdir(parents=True, exist_ok=True)
        robot = copy.deepcopy(original)
        pelvis = robot.find("worldbody/body[@name='pelvis']")
        start = spec['robot_start']
        z = float(pelvis.get('pos').split()[2]) + start['ground_z']
        pelvis.set('pos', ' '.join(map(str, [*start['xy'], z])))
        yaw = start['yaw'] / 2
        pelvis.set('quat', f'{math.cos(yaw)} 0 0 {math.sin(yaw)}')
        write_xml(robot, folder / 'robot.xml')
        scene = ET.parse(samples / name / 'scene.xml').getroot()
        if name == 'repose':
            # Keep the already-tested planner start, independently of the sample clip.
            planner = copy.deepcopy(scene)
            planner.find('include').set('file', 'g1_repose_robot.xml')
            write_xml(original, folder / 'g1_repose_robot.xml')
            write_xml(planner, folder / 'g1_repose.xml')
            body = scene.find("worldbody/body[@name='cube']")
            for key, values in spec['object_start'].items():
                body.set(key, ' '.join(map(str, values)))
        for include in scene.findall('include'):
            relative = include.get('file')
            if relative == 'robot.xml':
                continue
            if relative == 'terrain.xml':
                # Terrain stays in its published frame; robot uses the selected start.
                shutil.copyfile(samples / name / relative, folder / relative)
            elif relative == 'object.xml':
                obj = ET.parse(samples / name / relative).getroot()
                for elem in obj.iter():
                    if 'file' in elem.attrib:
                        elem.set('file', str((samples / name / elem.get('file')).resolve(strict=True)))
                body = obj.find('worldbody/body')
                for key, values in spec['object_start'].items():
                    body.set(key, ' '.join(map(str, values)))
                write_xml(obj, folder / relative)
            else:
                raise ValueError('Unexpected sample include: ' + relative)
        scene_path = folder / 'scene.xml'
        write_xml(scene, scene_path)
        paths.append(scene_path)
        print(f'{name}: {scene_path}\n  motion: {samples / name / "motion.npz"}')
    print('planner: ' + str(output / 'repose/g1_repose.xml'))
    return paths


def main():
    generate()


if __name__ == '__main__':
    main()
