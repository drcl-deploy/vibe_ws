#!/usr/bin/env python3
"""Resumable workspace setup; every stage validates or reuses its inputs."""

import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

from ros_env import check_overlay, identity, select_distro, shell_command

ROOT = Path(__file__).resolve().parents[1]
STAGES = ['sources', 'deps', 'artifacts', 'scene', 'sim', 'ros', 'doctor']


def run(command, cwd=ROOT, env=None):
    print('+ ' + shlex.join([str(part) for part in command]), flush=True)
    subprocess.run([str(part) for part in command], cwd=cwd, env=env, check=True)


def ros_command(command, overlay=False):
    distro = select_distro()
    workspace = ROOT / 'cyclonedds_ws'
    run(shell_command(command, distro, workspace if overlay else None), cwd=workspace)


def system_packages(distro):
    packages = ['build-essential', 'cmake', 'git', 'git-lfs', 'curl', 'pkg-config',
                'python3-venv', 'python3-pip', 'python3-dev', 'python3-colcon-common-extensions',
                'python3-numpy', 'python3-yaml', 'python3-opencv',
                'python3-matplotlib', 'python3-pyqt5',
                'libyaml-cpp-dev', 'libopencv-dev', 'libboost-program-options-dev',
                'libglfw3-dev', 'libgl1-mesa-dev', 'libfmt-dev', 'libeigen3-dev', 'zlib1g-dev']
    packages += ['ros-' + distro + '-' + name for name in (
        'rmw-cyclonedds-cpp', 'rosidl-generator-dds-idl', 'ros2launch',
        'ament-cmake-gtest', 'ament-lint-auto', 'ament-lint-common',
        'rosbag2', 'rosbag2-py', 'rosbag2-storage-default-plugins',
        'rclpy', 'rosidl-runtime-py', 'sensor-msgs', 'geometry-msgs')]
    return packages


def bootstrap(system, distro):
    if system:
        privilege = [] if os.geteuid() == 0 else ['sudo']
        run(privilege + ['apt-get', 'update'])
        run(privilege + ['apt-get', 'install', '-y'] + system_packages(distro))
    venv = ROOT / '.venv'
    if Path(sys.prefix) == venv:
        return
    python = venv / 'bin/python'
    if not python.exists():
        run(['/usr/bin/python3', '-m', 'venv', venv])
    version = subprocess.check_output([str(python), '-c',
        'import sys; print("{}.{}".format(*sys.version_info[:2]))'], text=True).strip()
    if version != '{}.{}'.format(*sys.version_info[:2]):
        raise ValueError('The setup venv uses a different Python version; move .venv aside and retry.')
    run([python, '-m', 'pip', 'install', '--disable-pip-version-check',
         'PyYAML==6.0.2', 'vcstool==0.3.0'])
    os.execv(str(python), [str(python), str(Path(__file__).resolve())]
             + [arg for arg in sys.argv[1:] if arg != '--system'])


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
    parser.add_argument('--system', action='store_true', help='install system dependencies with apt')
    parser.add_argument('--ort-archive', type=Path, help='use a validated local ONNX Runtime SDK archive')
    parser.add_argument('--ort-sha256', help='SHA-256 of --ort-archive')
    args = parser.parse_args()
    if args.jobs < 1 or (args.stage and args.from_stage):
        parser.error('Use positive --jobs and either --stage or --from-stage')
    if bool(args.ort_archive) != bool(args.ort_sha256):
        parser.error('--ort-archive and --ort-sha256 must be supplied together')
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
    distro = None
    if args.system or any(stage in selected for stage in ('ros', 'doctor')):
        distro = select_distro()
        os.environ['ROS_DISTRO'] = distro
        check_overlay(ROOT / 'cyclonedds_ws', distro, runtime=args.profile != 'offboard')
    if args.profile == 'sim' and 'deps' in selected and sys.version_info < (3, 10):
        raise ValueError('Simulation setup requires Python 3.10+ (Humble/Jazzy). '
                         'Foxy is supported for --profile onboard or offboard.')
    bootstrap(args.system, distro)
    ros_environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    ros_environment['PATH'] = str(ROOT / '.venv/bin') + os.pathsep + os.environ['PATH']
    for stage in selected:
        print('\n[' + stage + ']', flush=True)
        if stage == 'sources':
            run([sys.executable, 'scripts/sources.py', 'import'], env=ros_environment)
        elif stage == 'deps':
            if args.profile == 'sim':
                run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements-setup.txt'])
                sdk_setup(args.jobs)
                run(['bash', 'unitree_mujoco/scripts/setup_mujoco.sh', '--install-dir', ROOT / '.deps/mujoco-3.3.6'])
            if args.profile in {'sim', 'onboard'}:
                command = ['bash', 'cyclonedds_ws/src/vision_encoders/scripts/setup_onnxruntime.sh',
                           '--jobs', str(args.jobs)]
                if os.uname().machine == 'x86_64':
                    command.append('--install-cuda-runtime')
                if args.ort_archive:
                    command += ['--archive', args.ort_archive.resolve(), '--sha256', args.ort_sha256]
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
            build = ['/usr/bin/colcon', 'build', '--symlink-install', '--executor', 'sequential',
                     '--parallel-workers', str(args.jobs), '--packages-select']
            os.environ['CMAKE_BUILD_PARALLEL_LEVEL'] = str(args.jobs)
            cmake = ['--cmake-args', '-DCMAKE_BUILD_TYPE=Release',
                     '-DPython3_EXECUTABLE=/usr/bin/python3', '-DPYTHON_EXECUTABLE=/usr/bin/python3']
            ros_command(build + ['unitree_go', 'unitree_hg', 'unitree_api'] + cmake)
            packages = ['cdr_tcp_bridge', 'vision_encoders', 'cpp_control']
            if args.profile != 'offboard':
                if (ROOT / 'cyclonedds_ws/src/sledgehammer/package.xml').is_file():
                    packages.append('sledgehammer')
            ort = str(ROOT / 'cyclonedds_ws/src/vision_encoders/thirdparty/onnxruntime')
            runtime = 'OFF' if args.profile == 'offboard' else 'ON'
            flags = ['-DCPP_CONTROL_BUILD_RUNTIME=' + runtime,
                     '-DVISION_ENCODERS_BUILD_RUNTIME=' + runtime]
            if runtime == 'ON':
                flags += ['-DONNXRUNTIME_ROOT=' + ort, '-DONNXRUNTIME_ROOT_DIR=' + ort]
            ros_command(build + packages + cmake + flags, overlay=True)
            marker = ROOT / 'cyclonedds_ws/install/vibe_build.json'
            marker.write_text(json.dumps(identity(distro, runtime == 'ON'), indent=2) + '\n')
        else:
            run(['/usr/bin/python3', 'scripts/doctor.py', '--profile', args.profile])
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
