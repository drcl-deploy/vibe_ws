#!/usr/bin/env python3
"""Load installed dependencies without creating ROS nodes or sending commands."""

import argparse
import ctypes
import importlib
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=['sim', 'onboard', 'offboard'], required=True)
    args = parser.parse_args()
    from ament_index_python.packages import get_package_prefix, get_package_share_directory
    from rclpy.type_support import check_for_type_support
    from rosidl_runtime_py.utilities import get_message
    import yaml

    modules = ['numpy', 'cv2', 'rclpy', 'yaml', 'rosbag2_py']
    if args.profile != 'onboard':
        modules += ['PyQt5.QtCore', 'matplotlib.backends.backend_qt5agg']
    for module in modules:
        importlib.import_module(module)
    print('OK ROS Python runtime dependencies')

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
