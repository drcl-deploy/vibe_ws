#!/usr/bin/env python3
"""Compose the simulator's camera-equipped G1 and the assets-owned Repose scene."""

from pathlib import Path
import xml.etree.ElementTree as ET

from assets.repose_scene import generate

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT / 'unitree_mujoco/unitree_robots/g1/g1_29dof_with_camera.xml'
    print(generate(source, ROOT / 'generated/repose'))
    output = ROOT / 'generated/g1'
    output.mkdir(parents=True, exist_ok=True)
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    robot = ET.parse(source, parser=parser)
    compiler = robot.getroot().find('compiler')
    compiler.set('meshdir', str((source.parent / compiler.get('meshdir', '.')).resolve()))
    robot_path = output / 'robot.xml'
    robot.write(robot_path, encoding='unicode')
    scene = ET.parse(source.parent / 'scene_29dof.xml')
    scene.getroot().find('include').set('file', str(robot_path))
    scene_path = output / 'g1.xml'
    scene.write(scene_path, encoding='unicode')
    print(scene_path)


if __name__ == '__main__':
    main()
