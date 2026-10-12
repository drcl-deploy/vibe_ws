#!/usr/bin/env python3
"""Check an installed workspace without starting control nodes."""

import argparse
import json
from pathlib import Path
import subprocess

from experiment import ROOT, load


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=['sim', 'onboard', 'offboard'], default='sim')
    parser.add_argument('--experiment', default='repose-v9.3')
    parser.add_argument('--build-only', action='store_true')
    args = parser.parse_args()
    failures = []
    required = ['cyclonedds_ws/install/setup.bash',
                'cyclonedds_ws/install/cdr_tcp_bridge/lib/cdr_tcp_bridge/cdr_tcp_bridge']
    if args.profile in {'sim', 'onboard'}:
        required += ['cyclonedds_ws/install/vision_encoders/lib/vision_encoders/encoder_node',
                     'cyclonedds_ws/install/cpp_control/lib/cpp_control/g1_vibe_sonic_node']
    if args.profile == 'sim':
        required += ['unitree_mujoco/simulate/build/unitree_mujoco', 'generated/repose/g1_repose.xml']
    for relative in required:
        if not (ROOT / relative).is_file():
            failures.append('Missing: ' + relative)
        else:
            print('OK ' + relative)
    if args.profile == 'sim' and (ROOT / required[-2]).is_file():
        result = subprocess.run(['ldd', str(ROOT / required[-2])], capture_output=True, text=True)
        if result.returncode or 'not found' in result.stdout:
            failures.append('Simulator has unresolved libraries: ' + result.stdout)
    if not args.build_only and args.profile != 'offboard':
        try:
            selected = load(args.experiment)
            print('OK policy: ' + selected['policy'])
            print('OK encoder: ' + selected['encoder'])
        except (OSError, ValueError, KeyError) as error:
            failures.append('Artifacts: ' + str(error))
    for failure in failures:
        print('FAIL ' + failure)
    if failures:
        raise SystemExit(1)
    print('Automated file checks passed. Run scripts/regression.sh for runtime checks.')
    print('Manual joystick rollout and hardware validation remain operator gates.')


if __name__ == '__main__':
    main()
