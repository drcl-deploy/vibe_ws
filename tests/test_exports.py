"""Check explicit exporter pairs without introducing a runtime descriptor."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from doctor import check_exports


class ExportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.policy = root / 'policy.onnx'
        self.encoder = root / 'encoder.onnx'
        self.pm = dict(schema='vibe.onnx.v1', inputs=[
            dict(name='kv_tokens__img_tokens', shape=[21, 192]), dict(name='q_cls', shape=[192])])
        self.em = dict(schema='vision.onnx.v1', outputs=dict(
            patch_tokens=dict(num=21, dim=192), cls_token=dict(dim=192)))
        self.policy.write_bytes(b'policy fixture')
        self.encoder.write_bytes(b'encoder fixture')

    def check(self):
        self.policy.with_suffix('.manifest.json').write_text(json.dumps(self.pm))
        self.encoder.with_suffix('.manifest.json').write_text(json.dumps(self.em))
        check_exports(self.policy, self.encoder)

    def test_explicit_export_pair(self):
        self.check()

    def test_incompatible_token_grid(self):
        self.em['outputs']['patch_tokens']['num'] = 28
        with self.assertRaisesRegex(ValueError, 'patch-token'):
            self.check()

    def test_missing_cls(self):
        del self.em['outputs']['cls_token']
        with self.assertRaisesRegex(ValueError, 'CLS'):
            self.check()

    def test_missing_export(self):
        self.encoder.unlink()
        with self.assertRaises(FileNotFoundError):
            self.check()
