#!/usr/bin/env python3
"""Resumable workspace setup; every stage validates or reuses its inputs."""

import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STAGES = ['sources', 'deps', 'artifacts', 'scene', 'sim', 'ros', 'doctor']


def run(command, cwd=ROOT, env=None):
    print('+ ' + shlex.join([str(part) for part in command]), flush=True)
    subprocess.run([str(part) for part in command], cwd=cwd, env=env, check=True)


def ros_command(command, overlay=False):
    distro = os.environ.get('ROS_DISTRO', 'humble')
    if distro not in {'foxy', 'humble'}:
        raise ValueError('ROS_DISTRO must be foxy or humble')
    setup = Path('/opt/ros') / distro / 'setup.bash'
    if not setup.is_file():
        raise ValueError('Install ROS ' + distro + ' first: missing ' + str(setup))
    script = 'set -e; source ' + shlex.quote(str(setup)) + '; '
    if overlay:
        script += 'source ' + shlex.quote(str(ROOT / 'cyclonedds_ws/install/setup.bash')) + '; '
    script += shlex.join([str(part) for part in command])
    run(['bash', '-c', script], cwd=ROOT / 'cyclonedds_ws')


def sdk_setup(jobs):
    pin = json.loads((ROOT / 'dependencies.lock.json').read_text())['unitree_sdk2']
    source = ROOT / '.deps/unitree_sdk2'
    if not source.exists():
        run(['git', 'init', source])
        run(['git', '-C', source, 'remote', 'add', 'origin', pin['url']])
        run(['git', '-C', source, 'fetch', '--depth', '1', 'origin', pin['revision']])
        run(['git', '-C', source, 'checkout', '--detach', pin['revision']])
    head = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'], text=True).strip()
    if head != pin['revision'] or dirty:
        raise ValueError('SDK checkout differs from its pin; local work left untouched: ' + str(source))
    build = ROOT / '.deps/sdk-build'
    prefix = ROOT / '.deps/sdk-install'
    run(['cmake', '-S', source, '-B', build, '-DBUILD_EXAMPLES=OFF',
         '-DCMAKE_INSTALL_PREFIX=' + str(prefix), '-DCMAKE_INSTALL_LIBDIR=lib'])
    run(['cmake', '--build', build, '-j', str(jobs)])
    run(['cmake', '--install', build])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=STAGES, action='append', help='repeat to select stages')
    parser.add_argument('--from-stage', choices=STAGES)
    parser.add_argument('--profile', choices=['sim', 'onboard', 'offboard'], default='sim')
    parser.add_argument('--jobs', type=int, default=2)
    parser.add_argument('--plan', action='store_true', help='show stages without changing the workspace')
    args = parser.parse_args()
    if args.jobs < 1 or (args.stage and args.from_stage):
        parser.error('Use positive --jobs and either --stage or --from-stage')
    selected = args.stage or STAGES
    if args.from_stage:
        selected = STAGES[STAGES.index(args.from_stage):]
    if args.profile != 'sim':
        selected = [stage for stage in selected if stage not in {'scene', 'sim'}]
    if args.profile == 'offboard':
        selected = [stage for stage in selected if stage != 'artifacts']
    if args.plan:
        print(' -> '.join(selected))
        return
    ros_environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    ros_environment['PATH'] = str(ROOT / '.venv/bin') + os.pathsep + os.environ['PATH']
    for stage in selected:
        print('\n[' + stage + ']', flush=True)
        if stage == 'sources':
            run([sys.executable, 'scripts/sources.py', 'import'], env=ros_environment)
        elif stage == 'deps':
            if args.profile == 'sim':
                if sys.version_info < (3, 10):
                    raise ValueError('Simulation asset generation requires Python 3.10+; use Humble/22.04')
                run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements-setup.txt'])
                sdk_setup(args.jobs)
                run(['bash', 'unitree_mujoco/scripts/setup_mujoco.sh', '--install-dir', ROOT / '.deps/mujoco-3.3.6'])
            if args.profile in {'sim', 'onboard'}:
                command = ['bash', 'cyclonedds_ws/src/vision_encoders/scripts/setup_onnxruntime.sh']
                if os.uname().machine == 'x86_64':
                    command.append('--install-cuda-runtime')
                run(command)
        elif stage == 'artifacts':
            run([sys.executable, 'scripts/artifacts.py', '--lock', ROOT / 'artifacts.lock.json'])
        elif stage == 'scene':
            run([sys.executable, 'scripts/scenes.py'])
        elif stage == 'sim':
            run(['cmake', '-S', 'unitree_mujoco/simulate', '-B', 'unitree_mujoco/simulate/build',
                 '-Dunitree_sdk2_DIR=' + str(ROOT / '.deps/sdk-install/lib/cmake/unitree_sdk2'),
                 '-DMUJOCO_ROOT=' + str(ROOT / '.deps/mujoco-3.3.6'),
                 '-DCMAKE_BUILD_TYPE=Release', '-DBUILD_TESTING=ON'])
            run(['cmake', '--build', 'unitree_mujoco/simulate/build', '-j', str(args.jobs)])
        elif stage == 'ros':
            build = ['colcon', 'build', '--symlink-install', '--executor', 'sequential',
                     '--parallel-workers', str(args.jobs), '--packages-select']
            os.environ['CMAKE_BUILD_PARALLEL_LEVEL'] = str(args.jobs)
            ros_command(build + ['unitree_go', 'unitree_hg', 'unitree_api',
                                 '--cmake-args', '-DCMAKE_BUILD_TYPE=Release'])
            packages = ['cdr_tcp_bridge']
            if args.profile != 'offboard':
                packages += ['vision_encoders', 'cpp_control']
                if (ROOT / 'cyclonedds_ws/src/sledgehammer/package.xml').is_file():
                    packages.append('sledgehammer')
            ort = str(ROOT / 'cyclonedds_ws/src/vision_encoders/thirdparty/onnxruntime')
            ros_command(build + packages + ['--cmake-args', '-DCMAKE_BUILD_TYPE=Release',
                        '-DONNXRUNTIME_ROOT=' + ort, '-DONNXRUNTIME_ROOT_DIR=' + ort], overlay=True)
        else:
            run([sys.executable, 'scripts/doctor.py', '--profile', args.profile, '--build-only'])
    print('\nCompleted stages: ' + ', '.join(selected))
    print('ONNX exports stay in ignored artifacts/.')
    if args.profile == 'sim' and 'doctor' in selected:
        print('Sample scenes: ' + str((ROOT / 'generated').resolve()))
        print('Direct simulator and ROS commands: README.md#usage')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print('Setup stopped: ' + str(error), file=sys.stderr)
        sys.exit(1)
