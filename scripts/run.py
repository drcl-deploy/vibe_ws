#!/usr/bin/env python3
"""Launch one terminal of a named deployment experiment."""

import argparse
import os
from pathlib import Path
import shlex

from experiment import ROOT, load, tracker_arguments


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('component', choices=['sim', 'tracker'])
    parser.add_argument('experiment', nargs='?', default='repose-v9.3')
    parser.add_argument('--motion', type=Path)
    parser.add_argument('--goal-color', type=int, choices=range(6))
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    experiment = load(args.experiment)
    if args.goal_color is not None:
        experiment['goal_color'] = args.goal_color
    if args.component == 'sim':
        if os.environ.get('VIBE_PROFILE', 'sim') != 'sim':
            raise ValueError('Use the sim profile for the simulator')
        scene = ROOT / ('generated/repose/g1_repose.xml' if experiment.get('scene') == 'repose'
                        else 'generated/g1/g1.xml')
        if not scene.is_file():
            raise ValueError('Generate the scene with ./install.sh --stage scene: ' + str(scene))
        import json
        metadata = json.loads(Path(experiment['encoder_manifest']).read_text())['input']
        command = [str(ROOT / 'unitree_mujoco/simulate/build/unitree_mujoco'),
                   '-r', 'g1', '-i', '1', '-n', 'lo', '-s', str(scene), '--use_joystick', '1',
                   '--camera_fps', '50', '--camera_width', str(metadata['width']),
                   '--camera_height', str(metadata['height']),
                   '--camera_depth_width', str(metadata['width']),
                   '--camera_depth_height', str(metadata['height'])]
        if experiment.get('scene') == 'repose':
            command += ['--camera_textures', '0', '--camera_visual_groups', '1']
    else:
        command = ['ros2', 'launch', 'cpp_control', 'g1_vibe_sonic.launch.py'] + tracker_arguments(experiment)
        if args.motion:
            command.append('motion_path:=' + str(args.motion.expanduser().resolve(strict=True)))
    print(shlex.join(command), flush=True)
    if not args.dry_run:
        os.execvp(command[0], command)


if __name__ == '__main__':
    main()
