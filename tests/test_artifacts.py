"""Protect user exports and enforce immutable download locks."""

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import artifacts


class ArtifactTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.write_bytes(b'unchanged export bytes')
        self.target = self.root / 'artifacts/model.onnx'

    def test_copy_is_exact_and_idempotent(self):
        sha = artifacts.digest(self.source)
        artifacts.checked_copy(self.source, self.target, sha)
        artifacts.checked_copy(self.source, self.target, sha)
        self.assertEqual(self.source.read_bytes(), self.target.read_bytes())

    def test_different_local_export_is_preserved(self):
        self.target.parent.mkdir()
        self.target.write_bytes(b'my local export')
        with self.assertRaisesRegex(ValueError, 'left untouched'):
            artifacts.checked_copy(self.source, self.target, artifacts.digest(self.source))
        self.assertEqual(self.target.read_bytes(), b'my local export')

    def test_bad_checksum_never_publishes_partial_file(self):
        with self.assertRaisesRegex(ValueError, 'checksum'):
            artifacts.checked_copy(self.source, self.target, '0' * 64)
        self.assertFalse(self.target.exists())
        self.assertEqual(list(self.target.parent.iterdir()), [])

    def test_floating_hf_revision_rejected_before_network(self):
        lock = self.root / 'lock.json'
        lock.write_text(json.dumps(dict(schema='vibe.hf_artifacts.v1', files={
            'model.onnx': dict(revision='main', sha256='0' * 64)})))
        with self.assertRaisesRegex(ValueError, 'full commit'):
            artifacts.fetch(lock, self.root / 'artifacts')

    def test_download_cannot_escape_storage_root(self):
        lock = self.root / 'lock.json'
        lock.write_text(json.dumps(dict(schema='vibe.hf_artifacts.v1', files={'../outside': {}})))
        with self.assertRaisesRegex(ValueError, 'escapes'):
            artifacts.fetch(lock, self.root / 'artifacts')


if __name__ == '__main__':
    unittest.main()
