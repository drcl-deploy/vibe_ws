#!/usr/bin/env python3
"""Check an installed workspace without starting control nodes."""

import argparse
import json
import hashlib
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def check_samples(root=ROOT):
    folder = root / 'data/sample'
    manifest = json.loads((folder / 'samples.json').read_text())
    for relative, expected in manifest['files'].items():
        if hashlib.sha256((folder / relative).read_bytes()).hexdigest() != expected:
            raise ValueError('Sample differs from its recorded source: ' + relative)
    return manifest['samples']


def check_exports(policy, encoder):
    """Check the two explicit exporter pairs without creating a descriptor."""
    metadata = []
    for path in [policy, encoder]:
        path = Path(path).expanduser().resolve(strict=True)
        if path.suffix != '.onnx' or not path.is_file():
            raise ValueError('Expected an ONNX file: ' + str(path))
        metadata.append(json.loads(path.with_suffix('.manifest.json').read_text()))
    pm, em = metadata
    if pm.get('schema') != 'vibe.onnx.v1' or em.get('schema') != 'vision.onnx.v1':
        raise ValueError('Unsupported policy or encoder manifest schema')
    ports = {port['name']: port['shape'] for port in pm['inputs']}
    tokens = em['outputs']['patch_tokens']
    if ports.get('kv_tokens__img_tokens') != [tokens['num'], tokens['dim']]:
        raise ValueError('Policy and encoder patch-token shapes differ')
    if 'q_cls' in ports and ports['q_cls'] != [em['outputs'].get('cls_token', {}).get('dim')]:
        raise ValueError('Policy and encoder CLS shapes differ')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=['sim', 'onboard', 'offboard'], default='sim')
    artifacts = Path(os.environ.get('VIBE_ARTIFACT_ROOT', os.environ.get('VIBE_ASSET_ROOT', ROOT / 'artifacts')))
    parser.add_argument('--policy', type=Path, help='check one export instead of all sample policies')
    parser.add_argument('--encoder', type=Path, default=artifacts / 'encoders/theia-tiny.onnx')
    parser.add_argument('--build-only', action='store_true')
    args = parser.parse_args()
    failures = []
    samples = {}
    try:
        samples = check_samples()
        print('OK four sample payloads and source hashes')
    except (OSError, ValueError, KeyError) as error:
        failures.append('Samples: ' + str(error))
    required = ['cyclonedds_ws/install/setup.bash',
                'cyclonedds_ws/install/cdr_tcp_bridge/lib/cdr_tcp_bridge/cdr_tcp_bridge']
    if args.profile in {'sim', 'onboard'}:
        required += ['cyclonedds_ws/install/vision_encoders/lib/vision_encoders/encoder_node',
                     'cyclonedds_ws/install/cpp_control/lib/cpp_control/g1_vibe_sonic_node',
                     'cyclonedds_ws/install/sledgehammer/lib/sledgehammer/g1_repose_planner_node']
    if args.profile == 'sim':
        required += ['unitree_mujoco/simulate/build/unitree_mujoco', 'generated/repose/g1_repose.xml']
        required += ['generated/' + name + '/scene.xml' for name in samples]
    for relative in required:
        if not (ROOT / relative).is_file():
            failures.append('Missing: ' + relative)
        else:
            print('OK ' + relative)
    simulator = ROOT / 'unitree_mujoco/simulate/build/unitree_mujoco'
    if args.profile == 'sim' and simulator.is_file():
        result = subprocess.run(['ldd', str(simulator)], capture_output=True, text=True)
        if result.returncode or 'not found' in result.stdout:
            failures.append('Simulator has unresolved libraries: ' + result.stdout)
    if args.profile != 'offboard':
        share = ROOT / 'cyclonedds_ws/install/sledgehammer/share/sledgehammer'
        try:
            for name, spec in json.loads((share / 'data.lock.json').read_text())['files'].items():
                payload = (share / name).read_bytes()
                if len(payload) != spec['bytes'] or hashlib.sha256(payload).hexdigest() != spec['sha256']:
                    failures.append('Planner data differs from its lock: ' + name)
            print('OK frozen planner data checked against installed lock')
        except (OSError, ValueError, KeyError) as error:
            failures.append('Planner data: ' + str(error))
    if not args.build_only and args.profile != 'offboard':
        try:
            policies = [args.policy] if args.policy else [artifacts / spec['policy'] for spec in samples.values()]
            for policy in policies:
                check_exports(policy, args.encoder)
                print('OK policy: ' + str(policy))
            print('OK encoder: ' + str(args.encoder))
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
