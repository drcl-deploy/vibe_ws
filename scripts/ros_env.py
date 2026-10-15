"""ROS selection and build identity shared by installation and shell setup."""

import argparse
import json
import os
from pathlib import Path
import platform
import re
import shlex
import sys

SUPPORTED = ('foxy', 'humble', 'jazzy')
ROS_ROOT = Path('/opt/ros')


def select_distro(requested=None, ros_root=ROS_ROOT):
    requested = os.environ.get('ROS_DISTRO', '') if requested is None else requested
    if requested:
        if requested not in SUPPORTED:
            raise ValueError('ROS_DISTRO must be foxy, humble or jazzy')
        if not (ros_root / requested / 'setup.bash').is_file():
            raise ValueError('Missing ROS setup: ' + str(ros_root / requested / 'setup.bash'))
        return requested
    installed = [name for name in SUPPORTED if (ros_root / name / 'setup.bash').is_file()]
    if len(installed) != 1:
        raise ValueError('Set ROS_DISTRO explicitly; installed supported distributions: '
                         + (', '.join(installed) or 'none (install ROS first)'))
    return installed[0]


def identity(distro, runtime=True):
    return {'ros_distro': distro, 'architecture': platform.machine(),
            'python': '{}.{}'.format(*sys.version_info[:2]), 'runtime': runtime}


def check_overlay(workspace, distro, runtime=None):
    workspace = Path(workspace)
    marker = workspace / 'install/vibe_build.json'
    if marker.exists():
        recorded = json.loads(marker.read_text())
        expected = identity(distro)
        keys = ['ros_distro', 'architecture', 'python']
        if runtime is not None:
            expected['runtime'] = runtime
            keys.append('runtime')
        if any(recorded.get(key) != expected[key] for key in keys):
            raise ValueError('Existing build belongs to a different ROS/Python/architecture '
                             'or runtime profile. Move cyclonedds_ws/build and install aside '
                             'and rebuild; local files were not removed.')
    # Also protect older installs which predate the identity marker.
    setup = workspace / 'install/setup.bash'
    if setup.exists():
        parents = set(re.findall(r'/opt/ros/([^/\s"\']+)', setup.read_text()))
        if parents and parents != {distro}:
            raise ValueError('Workspace overlay was built against ' + ', '.join(sorted(parents))
                             + ', not ' + distro + '; move build/install aside and rebuild.')


def shell_command(command, distro, workspace=None):
    script = 'set -e; source ' + shlex.quote(str(ROS_ROOT / distro / 'setup.bash')) + '; '
    if workspace is not None:
        check_overlay(workspace, distro)
        # The selected ROS underlay is already sourced. Do not re-import old parents.
        script += 'source ' + shlex.quote(str(Path(workspace) / 'install/local_setup.bash')) + '; '
    return ['bash', '--noprofile', '--norc', '-c', script + shlex.join(map(str, command))]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path)
    args = parser.parse_args()
    distro = select_distro()
    if args.workspace:
        check_overlay(args.workspace, distro)
    print(distro)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
