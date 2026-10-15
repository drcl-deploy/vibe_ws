#!/usr/bin/env python3
"""Reconcile pinned sources and dependencies, then build and verify the workspace."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import shlex
import subprocess
import sys

from artifacts import digest
from install_state import archive, locked, prepare_build, read_json, state_directory, write_json
from ros_env import ROS_ROOT, identity, select_distro, shell_command
from sources import repositories, synchronize

ROOT = Path(__file__).resolve().parents[1]
STAGES = ['sources', 'deps', 'artifacts', 'scene', 'sim', 'ros', 'doctor']
LOCK_FD = None


def run(command, cwd=ROOT, env=None):
    command = [str(part) for part in command]
    print('+ ' + shlex.join(command), flush=True)
    descriptors = () if LOCK_FD is None else (LOCK_FD,)
    with subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, errors='replace',
                          pass_fds=descriptors) as process:
        try:
            for line in process.stdout:
                print(line, end='', flush=True)
            code = process.wait()
        except BaseException:
            process.terminate()
            process.wait()
            raise
    if code:
        raise subprocess.CalledProcessError(code, command)


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
    elif distro:
        packages = system_packages(distro)
        result = subprocess.run(['dpkg-query', '-W', '-f', '${Package} ${db:Status-Status}\n'] + packages,
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        installed = {line.split()[0] for line in result.stdout.splitlines()
                     if line.endswith(' installed')}
        missing = sorted(set(packages) - installed)
        if missing:
            raise ValueError('Missing system packages: {}. Run ./install.sh --system.'.format(', '.join(missing)))
    venv = ROOT / '.venv'
    if venv.is_symlink():
        raise ValueError('Setup venv is a symlink; left untouched: ' + str(venv))
    python = venv / 'bin/python'
    receipt_path = state_directory(ROOT) / 'python.json'
    expected = {'path': str(venv), 'architecture': platform.machine(),
                'python': '{}.{}'.format(*sys.version_info[:2])}
    recorded = read_json(receipt_path)
    ready = False
    if python.exists() and (not recorded or recorded == expected):
        try:
            result = subprocess.run([str(python), '-c',
                'import sys, pip, json; print(json.dumps({"version": "{}.{}".format(*sys.version_info[:2]), '
                '"prefix": sys.prefix, "base": sys.base_prefix}))'],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            info = json.loads(result.stdout)
            ready = (result.returncode == 0 and Path(info['prefix']).resolve() == venv.resolve()
                     and info['prefix'] != info['base']
                     and info['version'] == '{}.{}'.format(*sys.version_info[:2]))
        except (OSError, ValueError, KeyError, TypeError):
            ready = False
    if recorded and recorded != expected:
        ready = False
    if not ready:
        archive(ROOT, '.venv', 'setup-venv')
        run(['/usr/bin/python3', '-m', 'venv', venv])
    setuptools = '80.9.0' if sys.version_info >= (3, 9) else '68.2.2'
    required = {'setuptools': setuptools, 'PyYAML': '6.0.2', 'vcstool': '0.3.0'}
    probe = subprocess.run([str(python), '-c',
        'import importlib.metadata as m, json, yaml, vcstool; '
        'print(json.dumps({p: m.version(p) for p in ["setuptools", "PyYAML", "vcstool"]}))'],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    try:
        packages_ready = probe.returncode == 0 and json.loads(probe.stdout) == required
    except ValueError:
        packages_ready = False
    vcs = venv / 'bin/vcs'
    if packages_ready:
        packages_ready = vcs.is_file() and subprocess.run(
            [str(vcs), '--version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    if not packages_ready:
        if ready:
            # A killed pip installation can leave broken metadata/entry points
            # that pip cannot uninstall. Preserve and recreate our setup venv.
            archive(ROOT, '.venv', 'setup-venv')
            run(['/usr/bin/python3', '-m', 'venv', venv])
        run([python, '-m', 'pip', 'install', '--disable-pip-version-check']
            + [name + '==' + version for name, version in required.items()])
    run([venv / 'bin/vcs', '--version'])
    write_json(receipt_path, expected)
    return python


def native_identity():
    compiler = os.environ.get('CXX', 'c++')
    version = subprocess.check_output([compiler, '--version'], text=True).splitlines()[0]
    return {'architecture': platform.machine(), 'compiler': version, 'checkout': str(ROOT)}


def sdk_setup(jobs):
    pin = json.loads((ROOT / 'dependencies.lock.json').read_text())['unitree_sdk2']
    synchronize(ROOT, {'.deps/unitree_sdk2': dict(type='git', url=pin['url'], version=pin['revision'])}, call=run)
    prepare_build(ROOT, 'sdk', dict(native_identity(), revision=pin['revision']),
                  ['.deps/sdk-build', '.deps/sdk-install'])
    source = ROOT / '.deps/unitree_sdk2'
    build = ROOT / '.deps/sdk-build'
    prefix = ROOT / '.deps/sdk-install'
    run(['cmake', '-S', source, '-B', build, '-DBUILD_EXAMPLES=OFF',
         '-DCMAKE_INSTALL_PREFIX=' + str(prefix), '-DCMAKE_INSTALL_LIBDIR=lib'])
    run(['cmake', '--build', build, '-j', str(jobs)])
    run(['cmake', '--install', build])


def dependency(name, command, target, required, inputs=None):
    """Use the package's setup helper; recover only outputs we own receipts for."""
    target = Path(target)
    receipt_path = state_directory(ROOT) / 'dependencies.json'
    receipts = read_json(receipt_path)
    key = name + ':' + str(target)
    record = receipts.get(key, receipts.get(name, {}))
    inputs = inputs or {}
    ready = all((target / relative).is_file() for relative in required)
    owned = ROOT in target.resolve().parents and not target.is_symlink()
    if target.exists() and (not ready or (record.get('inputs') != inputs and record.get('path') == str(target))):
        if not (owned and record.get('owned') and record.get('path') == str(target)):
            raise ValueError('Unrecognized or incomplete dependency; left untouched: ' + str(target))
        archive(ROOT, target.relative_to(ROOT), name)
    # Persist ownership before the helper starts, including on its first run.
    receipts[key] = {'path': str(target), 'inputs': inputs, 'owned': owned}
    write_json(receipt_path, receipts)
    temporary = state_directory(ROOT) / 'staging'
    temporary.mkdir(parents=True, exist_ok=True)
    run(command, env=dict(os.environ, TMPDIR=str(temporary)))
    if not all((target / relative).is_file() for relative in required):
        raise ValueError('Dependency helper did not finish installing ' + str(target))


def setup_ort(args):
    command = ['bash', 'cyclonedds_ws/src/vision_encoders/scripts/setup_onnxruntime.sh', '--jobs', str(args.jobs)]
    if os.uname().machine == 'x86_64':
        command.append('--install-cuda-runtime')
    if args.ort_archive:
        command += ['--archive', args.ort_archive.resolve(), '--sha256', args.ort_sha256]
    # Ask the encoder's public dry-run for its selected SDK location. CUDA/JetPack
    # version selection remains in that package, rather than being duplicated here.
    probe = subprocess.run([str(part) for part in command] + ['--dry-run'], cwd=ROOT, text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    selection = probe.stdout
    print(selection, end='', flush=True)
    if probe.returncode:
        raise ValueError('Encoder SDK selection failed; see the helper output above')
    match = re.search(r'^setup_onnxruntime: install root: (.+)$', selection, re.MULTILINE)
    if not match:
        raise ValueError('Encoder setup did not report its selected SDK location')
    inputs = {key: os.environ.get(key, '') for key in ('CUDA_HOME', 'CUDNN_HOME', 'VISION_ENCODERS_CUDA_ARCHITECTURES')}
    inputs['archive_sha256'] = args.ort_sha256
    dependency('onnxruntime', command, Path(match.group(1)),
               ['include/onnxruntime_cxx_api.h', 'lib/libonnxruntime.so',
                'lib/libonnxruntime_providers_cuda.so', 'lib/libonnxruntime_providers_shared.so'], inputs)


def build_inputs(distro, profile):
    pins = repositories(ROOT)
    result = dict(identity(distro, profile != 'offboard'), profile=profile,
                  sources={path: spec['version'] for path, spec in pins.items()}, checkout=str(ROOT))
    messages = ROOT / 'cyclonedds_ws/src/unitree'
    result['unitree_messages'] = {
        str(path.relative_to(messages)): digest(path)
        for path in sorted(messages.rglob('*'))
        if path.is_file() and path.suffix in ('.msg', '.srv', '.xml', '.txt')}
    result['compiler'] = native_identity()['compiler']
    if profile != 'offboard':
        sdk = (ROOT / 'cyclonedds_ws/src/vision_encoders/thirdparty/onnxruntime').resolve()
        result['onnxruntime'] = {'path': str(sdk), 'header': digest(sdk / 'include/onnxruntime_cxx_api.h'),
                                'library': digest(sdk / 'lib/libonnxruntime.so')}
    return result


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=STAGES, action='append', help='repeat to select stages')
    parser.add_argument('--from-stage', choices=STAGES)
    parser.add_argument('--profile', choices=['sim', 'onboard', 'offboard'], help='default: previous selection, or sim')
    parser.add_argument('--jobs', type=int, help='maximum compilation jobs; default: previous selection, or 2')
    parser.add_argument('--plan', action='store_true', help='show stages without changing the workspace')
    parser.add_argument('--system', action='store_true', help='install system dependencies with apt')
    parser.add_argument('--ort-archive', type=Path, help='local SDK archive, or auto to forget a saved override')
    parser.add_argument('--ort-sha256', help='SHA-256 of --ort-archive')
    args = parser.parse_args(argv)
    preferences = read_json(state_directory(ROOT) / 'preferences.json')
    args.reset_ort = str(args.ort_archive) == 'auto'
    if args.reset_ort:
        if args.ort_sha256:
            parser.error('--ort-archive auto does not take --ort-sha256')
        args.ort_archive = None
    if bool(args.ort_archive) != bool(args.ort_sha256):
        parser.error('--ort-archive and --ort-sha256 must be supplied together')
    args.profile = args.profile or preferences.get('profile', 'sim')
    args.jobs = args.jobs if args.jobs is not None else preferences.get('jobs', 2)
    if args.profile not in ('sim', 'onboard', 'offboard'):
        parser.error('Invalid saved profile; select --profile explicitly')
    if not isinstance(args.jobs, int) or args.jobs < 1 or (args.stage and args.from_stage):
        parser.error('Use positive --jobs and either --stage or --from-stage')
    if not args.reset_ort and not args.ort_archive and preferences.get('ort_archive'):
        args.ort_archive = Path(preferences['ort_archive'])
        args.ort_sha256 = preferences['ort_sha256']
    selected = args.stage or STAGES
    if args.from_stage:
        selected = STAGES[STAGES.index(args.from_stage):]
    if args.profile != 'sim':
        selected = [stage for stage in selected if stage not in {'scene', 'sim'}]
    if args.profile == 'offboard':
        selected = [stage for stage in selected if stage != 'artifacts']
    return args, selected, preferences


class Transcript:
    def __init__(self, console, log):
        self.console, self.log = console, log

    def write(self, text):
        self.console.write(text)
        self.log.write(text)

    def flush(self):
        self.console.flush()
        self.log.flush()


def choose_distro(preferences):
    requested = os.environ.get('ROS_DISTRO', '')
    saved = preferences.get('ros_distro', '')
    if not requested and saved and (ROS_ROOT / saved / 'setup.bash').is_file():
        requested = saved
    return select_distro(requested)


def execute(args, selected, preferences, progress):
    distro = None
    if args.system or any(stage in selected for stage in ('ros', 'doctor')):
        distro = choose_distro(preferences)
        os.environ['ROS_DISTRO'] = distro
    preferences.update(profile=args.profile, jobs=args.jobs)
    if distro:
        preferences['ros_distro'] = distro
    if args.reset_ort:
        preferences.pop('ort_archive', None)
        preferences.pop('ort_sha256', None)
    if args.ort_archive:
        preferences.update(ort_archive=str(args.ort_archive.resolve()), ort_sha256=args.ort_sha256)
    write_json(state_directory(ROOT) / 'preferences.json', preferences)
    if args.profile == 'sim' and 'deps' in selected and sys.version_info < (3, 10):
        raise ValueError('Simulation setup requires Python 3.10+ (Humble/Jazzy). '
                         'Foxy is supported for --profile onboard or offboard.')
    progress('system/setup Python')
    python = bootstrap(args.system, distro)
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    environment['PATH'] = str(ROOT / '.venv/bin') + os.pathsep + os.environ['PATH']
    for stage in selected:
        progress(stage)
        if stage == 'sources':
            run([python, 'scripts/sources.py', 'import'], env=environment)
        elif stage == 'deps':
            if args.profile == 'sim':
                run([python, '-m', 'pip', 'install', '-r', 'requirements-setup.txt'])
                sdk_setup(args.jobs)
                version = json.loads((ROOT / 'dependencies.lock.json').read_text())['mujoco']['version']
                mujoco = ROOT / '.deps' / ('mujoco-' + version)
                dependency('mujoco', ['bash', 'unitree_mujoco/scripts/setup_mujoco.sh',
                           '--install-dir', mujoco], mujoco,
                           ['include/mujoco/mujoco.h', 'simulate/simulate.cc', 'lib/libmujoco.so'])
            if args.profile in {'sim', 'onboard'}:
                setup_ort(args)
        elif stage == 'artifacts':
            run([python, 'scripts/artifacts.py', '--lock', ROOT / 'artifacts.lock.json'])
        elif stage == 'scene':
            run([python, 'scripts/scenes.py'])
        elif stage == 'sim':
            deps = json.loads((ROOT / 'dependencies.lock.json').read_text())
            pins = repositories(ROOT)
            prepare_build(ROOT, 'sim', dict(native_identity(), simulator=pins['unitree_mujoco']['version'],
                          sdk=deps['unitree_sdk2']['revision'], mujoco=deps['mujoco']['version']),
                          ['unitree_mujoco/simulate/build'])
            run(['cmake', '-S', 'unitree_mujoco/simulate', '-B', 'unitree_mujoco/simulate/build',
                 '-Dunitree_sdk2_DIR=' + str(ROOT / '.deps/sdk-install/lib/cmake/unitree_sdk2'),
                 '-DMUJOCO_ROOT=' + str(ROOT / '.deps' / ('mujoco-' + deps['mujoco']['version'])),
                 '-DCMAKE_BUILD_TYPE=Release', '-DBUILD_TESTING=ON'])
            run(['cmake', '--build', 'unitree_mujoco/simulate/build', '-j', str(args.jobs)])
        elif stage == 'ros':
            prepare_build(ROOT, 'ros', build_inputs(distro, args.profile),
                          ['cyclonedds_ws/build', 'cyclonedds_ws/install', 'cyclonedds_ws/log'])
            build = ['/usr/bin/colcon', 'build', '--symlink-install', '--executor', 'sequential',
                     '--parallel-workers', str(args.jobs), '--packages-select']
            os.environ['CMAKE_BUILD_PARALLEL_LEVEL'] = str(args.jobs)
            cmake = ['--cmake-args', '-DCMAKE_BUILD_TYPE=Release',
                     '-DPython3_EXECUTABLE=/usr/bin/python3', '-DPYTHON_EXECUTABLE=/usr/bin/python3']
            ros_command(build + ['unitree_go', 'unitree_hg', 'unitree_api'] + cmake)
            packages = ['cdr_tcp_bridge', 'vision_encoders', 'cpp_control', 'sledgehammer']
            ort = str(ROOT / 'cyclonedds_ws/src/vision_encoders/thirdparty/onnxruntime')
            runtime = 'OFF' if args.profile == 'offboard' else 'ON'
            flags = ['-DCPP_CONTROL_BUILD_RUNTIME=' + runtime,
                     '-DVISION_ENCODERS_BUILD_RUNTIME=' + runtime,
                     '-DSLEDGEHAMMER_BUILD_RUNTIME=' + runtime]
            if runtime == 'ON':
                flags += ['-DONNXRUNTIME_ROOT=' + ort, '-DONNXRUNTIME_ROOT_DIR=' + ort]
            ros_command(build + packages + cmake + flags, overlay=True)
            write_json(ROOT / 'cyclonedds_ws/install/vibe_build.json', identity(distro, runtime == 'ON'))
        else:
            run(['/usr/bin/python3', 'scripts/doctor.py', '--profile', args.profile])
    print('\nCompleted stages: ' + ', '.join(selected))
    print('ONNX exports stay in ignored artifacts/.')
    if args.profile == 'sim' and 'doctor' in selected:
        print('Sample scenes: ' + str((ROOT / 'generated').resolve()))
        print('Direct simulator and ROS commands: README.md#usage')


def main():
    global LOCK_FD
    args, selected, preferences = parse_args()
    if args.plan:
        print(' -> '.join(selected))
        return 0
    state = state_directory(ROOT)
    with locked(state / 'install.lock') as descriptor:
        LOCK_FD = descriptor
        logs = state / 'logs'
        logs.mkdir(parents=True, exist_ok=True)
        name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + str(os.getpid()) + '.log'
        path = logs / name
        console, errors = sys.stdout, sys.stderr
        with path.open('w', buffering=1) as log:
            sys.stdout, sys.stderr = Transcript(console, log), Transcript(errors, log)
            stage = 'preflight'
            def progress(value):
                nonlocal stage
                stage = value
                write_json(state / 'progress.json', {'stage': stage, 'status': 'running', 'log': str(path)})
                print('\n[' + stage + ']', flush=True)
            try:
                print('Installation log: ' + str(path), flush=True)
                execute(args, selected, preferences, progress)
                write_json(state / 'progress.json', {'stage': stage, 'status': 'complete', 'log': str(path)})
                return 0
            except (OSError, ValueError, KeyError, subprocess.CalledProcessError, KeyboardInterrupt) as error:
                write_json(state / 'progress.json', {'stage': stage, 'status': 'failed', 'log': str(path)})
                print('\nSetup stopped at {}: {}'.format(stage, error), file=sys.stderr)
                print('Retry: ./install.sh ' + shlex.join(sys.argv[1:]), file=sys.stderr)
                print('Log: ' + str(path), file=sys.stderr)
                return 1
            finally:
                sys.stdout, sys.stderr = console, errors
                LOCK_FD = None


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        print('Setup stopped: ' + str(error), file=sys.stderr)
        sys.exit(1)
