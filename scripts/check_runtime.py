#!/usr/bin/env python3
"""Load installed dependencies without creating ROS nodes or sending commands."""

import argparse
import ctypes
import importlib
from pathlib import Path
import subprocess

from ros_env import select_distro


def runtime_modules(profile, distro):
    modules = ['numpy', 'cv2', 'rclpy', 'yaml']
    if profile != 'onboard':
        modules += ['PyQt5.QtCore', 'matplotlib.backends.backend_qt5agg']
        if distro != 'foxy':
            modules.append('rosbag2_py')
    return modules


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=['sim', 'onboard', 'offboard'], required=True)
    args = parser.parse_args()
    distro = select_distro()
    from ament_index_python.packages import get_package_prefix, get_package_share_directory
    from rclpy.type_support import check_for_type_support
    from rosidl_runtime_py.utilities import get_message
    import yaml

    for module in runtime_modules(args.profile, distro):
        importlib.import_module(module)
    print('OK ROS Python runtime dependencies')
    if distro == 'foxy' and args.profile != 'onboard':
        print('NOTE Python bag replay requires Humble/Jazzy; Foxy supports live viewing and ROS bag CLI recording.')

    config = Path(get_package_share_directory('cdr_tcp_bridge')) / 'config'
    types = set()
    # Calibration labels are recorded by the offboard viewer, not the TCP bridge.
    types.add('sledgehammer/msg/CalibrationState')
    for name in ['full.yaml', 'repose_calibration.yaml']:
        for channel in yaml.safe_load((config / name).read_text())['channels']:
            types.add(channel['type'])
    libraries = []  # Keep the loaded C++ typesupport handles alive during this check.
    for name in sorted(types):
        check_for_type_support(get_message(name))
        package = name.split('/')[0]
        path = Path(get_package_prefix(package)) / 'lib' / ('lib' + package + '__rosidl_typesupport_cpp.so')
        libraries.append(ctypes.CDLL(str(path)))
    print('OK bridge Python/C++ type support for {} message types'.format(len(types)))

    if args.profile != 'offboard':
        prefix = Path(get_package_prefix('vision_encoders'))
        subprocess.run([str(prefix / 'lib/vision_encoders/cuda_provider_check')], check=True)


if __name__ == '__main__':
    main()
