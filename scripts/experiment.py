#!/usr/bin/env python3
"""Resolve deployment inputs; the exporter owns model and manifest contents."""

import argparse
import json
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FAMILIES = {'repose', 'uolm', 'perloco', 'dodge'}


def pair(path, artifact_root):
    """Return absolute ONNX/sidecar paths and parsed metadata."""
    path = Path(path).expanduser()
    if not path.is_absolute():
        path = artifact_root / path
    path = path.resolve(strict=True)
    if path.suffix != '.onnx' or not path.is_file():
        raise ValueError('Expected an ONNX file: ' + str(path))
    manifest = path.with_suffix('.manifest.json')
    metadata = json.loads(manifest.read_text())
    return str(path), str(manifest), metadata


def load(name, root=ROOT, artifact_root=None):
    """Load a descriptor and validate policy/encoder shape compatibility."""
    root = Path(root)
    artifact_root = Path(artifact_root or os.environ.get(
        'VIBE_ARTIFACT_ROOT', os.environ.get('VIBE_ASSET_ROOT', root / 'artifacts')))
    path = Path(name).expanduser()
    if not path.is_file():
        candidates = [root / 'experiments' / (str(name) + '.yaml'),
                      artifact_root / 'experiments' / (str(name) + '.yaml')]
        existing = [candidate for candidate in candidates if candidate.is_file()]
        if len(existing) > 1:
            raise ValueError('Ambiguous experiment name; use an explicit YAML path: ' + str(name))
        if not existing:
            raise FileNotFoundError('Experiment not found; import your policy and encoder exports: ' + str(name))
        path = existing[0]
    data = yaml.safe_load(path.read_text())
    allowed = {'schema', 'task_family', 'policy', 'encoder', 'scene', 'goal_color',
               'planner', 'motion'}
    if not isinstance(data, dict) or set(data) - allowed:
        raise ValueError('Unknown experiment fields: ' + str(path))
    if data.get('schema') != 'vibe.experiment.v1':
        raise ValueError('Expected experiment schema vibe.experiment.v1')
    if data.get('task_family') not in FAMILIES:
        raise ValueError('Unsupported task_family: ' + str(data.get('task_family')))
    if data.get('planner') not in {None, 'v9.3'}:
        raise ValueError('Only the frozen v9.3 planner is supported')
    policy, policy_manifest, pm = pair(data['policy'], artifact_root)
    encoder, encoder_manifest, em = pair(data['encoder'], artifact_root)
    if pm.get('schema') != 'vibe.onnx.v1' or em.get('schema') != 'vision.onnx.v1':
        raise ValueError('Unsupported policy or encoder manifest schema')
    task = pm.get('task_id', '').lower()
    if data['task_family'] not in task:
        raise ValueError('Policy task_id does not match task_family')
    ports = {port['name']: port['shape'] for port in pm['inputs']}
    tokens = em['outputs']['patch_tokens']
    if ports.get('kv_tokens__img_tokens') != [tokens['num'], tokens['dim']]:
        raise ValueError('Policy and encoder patch-token shapes differ')
    if 'q_cls' in ports and ports['q_cls'] != [em['outputs'].get('cls_token', {}).get('dim')]:
        raise ValueError('Policy and encoder CLS shapes differ')
    goal = data.get('goal_color', 0)
    if type(goal) is not int or not 0 <= goal <= 5:
        raise ValueError('goal_color must be an integer in 0..5')
    if data.get('scene', 'g1') not in {'g1', 'repose'}:
        raise ValueError('scene must be g1 or repose')
    return dict(data, policy=policy, policy_manifest=policy_manifest,
                encoder=encoder, encoder_manifest=encoder_manifest,
                encoder_tag=em['tag'], goal_color=goal,
                descriptor=str(path.resolve()))


def tracker_arguments(experiment):
    """Arguments accepted by cpp_control's independent tracker launch."""
    fields = {'policy_path': 'policy', 'policy_manifest': 'policy_manifest',
              'encoder_path': 'encoder', 'encoder_manifest': 'encoder_manifest',
              'expected_task_family': 'task_family', 'goal_color': 'goal_color'}
    return [f'{argument}:={experiment[key]}' for argument, key in fields.items()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('experiment', nargs='?', default='repose-v9.3')
    args = parser.parse_args()
    print(json.dumps(load(args.experiment), indent=2))


if __name__ == '__main__':
    main()
