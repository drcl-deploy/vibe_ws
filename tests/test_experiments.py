"""Reject incompatible exports before launching robot-facing processes."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import yaml

SPEC = importlib.util.spec_from_file_location(
    'experiment', Path(__file__).resolve().parents[1] / 'scripts/experiment.py')
experiment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(experiment)


class ExperimentTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'experiments').mkdir()
        (self.root / 'artifacts').mkdir()
        self.descriptor = dict(schema='vibe.experiment.v1', task_family='repose',
                               policy='agent.onnx', encoder='encoder.onnx')
        self.policy = dict(schema='vibe.onnx.v1', task_id='Vibe-Repose-Example',
                           inputs=[dict(name='kv_tokens__img_tokens', shape=[21, 192]),
                                   dict(name='q_cls', shape=[192])])
        self.encoder = dict(schema='vision.onnx.v1', tag='theia-tiny',
                            outputs=dict(patch_tokens=dict(num=21, dim=192),
                                         cls_token=dict(dim=192)))
        for name in ['agent.onnx', 'encoder.onnx']:
            (self.root / 'artifacts' / name).write_bytes(b'test export')

    def load(self):
        (self.root / 'experiments/test.yaml').write_text(yaml.safe_dump(self.descriptor))
        for name, manifest in [('agent', self.policy), ('encoder', self.encoder)]:
            (self.root / 'artifacts' / (name + '.manifest.json')).write_text(json.dumps(manifest))
        return experiment.load('test', self.root, self.root / 'artifacts')

    def test_explicit_paths_without_package_model_copy(self):
        loaded = self.load()
        self.assertEqual(loaded['policy'], str(self.root / 'artifacts/agent.onnx'))
        self.assertIn('encoder_path:=' + loaded['encoder'], experiment.tracker_arguments(loaded))

    def test_imported_experiment_discovered_by_name(self):
        self.load()
        target = self.root / 'artifacts/experiments'
        target.mkdir()
        (self.root / 'experiments/test.yaml').rename(target / 'local.yaml')
        loaded = experiment.load('local', self.root, self.root / 'artifacts')
        self.assertEqual(loaded['task_family'], 'repose')

    def test_ambiguous_name_requires_explicit_path(self):
        self.load()
        target = self.root / 'artifacts/experiments'
        target.mkdir()
        (target / 'test.yaml').write_text((self.root / 'experiments/test.yaml').read_text())
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            experiment.load('test', self.root, self.root / 'artifacts')

    def test_wrong_camera_token_grid(self):
        self.encoder['outputs']['patch_tokens']['num'] = 28
        with self.assertRaisesRegex(ValueError, 'patch-token'):
            self.load()

    def test_missing_cls(self):
        del self.encoder['outputs']['cls_token']
        with self.assertRaisesRegex(ValueError, 'CLS'):
            self.load()

    def test_task_mismatch(self):
        self.descriptor['task_family'] = 'dodge'
        with self.assertRaisesRegex(ValueError, 'task_id'):
            self.load()

    def test_unknown_field(self):
        self.descriptor['encodre'] = 'typo'
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            self.load()

    def test_missing_export(self):
        (self.root / 'artifacts/agent.onnx').unlink()
        with self.assertRaises(FileNotFoundError):
            self.load()


if __name__ == '__main__':
    unittest.main()
