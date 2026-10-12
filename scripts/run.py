#!/usr/bin/env python3
"""Launch one terminal of a named deployment experiment."""

import argparse
import os
from pathlib import Path
import shlex

from experiment import ROOT, load, tracker_arguments


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('component', choices=['sim', 'tracker', 'planner'])
    parser.add_argument('experiment', nargs='?', default='repose-v9.3')
    parser.add_argument('--with-planner', action='store_true')
    parser.add_argument('--motion', type=Path)
    parser.add_argument('--goal-color', type=int, choices=range(6))
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if os.environ.get('VIBE_PROFILE', 'sim') == 'offboard':
        parser.error('Run control components on sim/onboard; offboard is a telemetry profile')
    experiment = load(args.experiment)
    if args.with_planner and args.component != 'tracker':
        parser.error('--with-planner applies only to the tracker')
    if (args.with_planner or args.component == 'planner') and (
            experiment['task_family'] != 'repose' or experiment.get('planner') != 'v9.3'):
        parser.error('The frozen planner requires a Repose experiment with planner: v9.3')
    if args.motion and args.component != 'tracker':
        parser.error('--motion applies only to the tracker')
    if args.motion and args.with_planner:
        parser.error('Choose either a tracker motion or the planner')
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
    elif args.component == 'planner':
        command = ['ros2', 'launch', 'sledgehammer', 'planner.launch.py',
                   'env:=' + ('sim' if os.environ.get('VIBE_PROFILE', 'sim') == 'sim' else 'real'),
                   'goal_color:=' + str(experiment['goal_color'])]
    else:
        command = ['ros2', 'launch', 'cpp_control', 'g1_vibe_sonic.launch.py'] + tracker_arguments(experiment)
        if args.with_planner:
            from ament_index_python.packages import get_package_share_directory
            share = Path(get_package_share_directory('sledgehammer'))
            walk = share / 'data/sys1_walk/walk_forward_amateur_001__A001/motion.npz'
            command += ['planner:=true', 'stand_yaw_teleop:=true', 'stand_walk_teleop:=true',
                        'stand_walk_motion:=' + str(walk.resolve(strict=True))]
        if args.motion:
            command.append('motion_path:=' + str(args.motion.expanduser().resolve(strict=True)))
    print(shlex.join(command), flush=True)
    if args.with_planner:
        print('Supervised: wait for planner, then stop tracker if its heartbeat is lost.', flush=True)
    if not args.dry_run and args.with_planner:
        from planner_supervisor import supervise
        raise SystemExit(supervise(command))
    if not args.dry_run:
        os.execvp(command[0], command)


if __name__ == '__main__':
    main()
