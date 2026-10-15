"""Protect user exports and enforce immutable download locks."""

import hashlib
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


class ArtifactUpgradeTest(unittest.TestCase):
    setUp = ArtifactTest.setUp

    def lock(self, payload):
        sha = hashlib.sha256(payload).hexdigest()
        self.lock_path = self.root / 'lock.json'
        self.lock_path.write_text(json.dumps(dict(schema='vibe.hf_artifacts.v1', files={
            'model.onnx': dict(repo_id='fixture/model', revision='a' * 40,
                               path='model.onnx', sha256=sha, bytes=len(payload))})))
        return sha

    def fetch_payload(self, payload):
        import io
        from unittest.mock import patch
        self.lock(payload)
        with patch('artifacts.urllib.request.urlopen', return_value=io.BytesIO(payload)):
            artifacts.fetch(self.lock_path, self.target.parent)

    def test_managed_export_updates_then_verified_retry_needs_no_network(self):
        from unittest.mock import patch
        self.fetch_payload(b'old release')
        self.fetch_payload(b'new released bytes')
        self.assertEqual(self.target.read_bytes(), b'new released bytes')
        with patch('artifacts.urllib.request.urlopen', side_effect=AssertionError('unnecessary download')):
            artifacts.fetch(self.lock_path, self.target.parent)

    def test_interrupted_upgrade_preserves_old_export_and_same_command_recovers(self):
        import io
        from unittest.mock import patch
        self.fetch_payload(b'old release')
        self.lock(b'new release')
        class Interrupted(io.BytesIO):
            def read(self, size=-1):
                if self.tell():
                    raise OSError('connection interrupted')
                return super().read(3)
        with patch('artifacts.urllib.request.urlopen', return_value=Interrupted(b'new release')):
            with self.assertRaisesRegex(OSError, 'interrupted'):
                artifacts.fetch(self.lock_path, self.target.parent)
        self.assertEqual(self.target.read_bytes(), b'old release')
        with patch('artifacts.urllib.request.urlopen', return_value=io.BytesIO(b'new release')):
            artifacts.fetch(self.lock_path, self.target.parent)
        self.assertEqual(self.target.read_bytes(), b'new release')

    def test_modified_managed_export_blocks_update_without_losing_user_bytes(self):
        from unittest.mock import patch
        self.fetch_payload(b'released')
        self.target.write_bytes(b'my local export')
        self.lock(b'new release')
        with patch('artifacts.urllib.request.urlopen', side_effect=AssertionError('preflight should stop')):
            with self.assertRaisesRegex(ValueError, 'left untouched'):
                artifacts.fetch(self.lock_path, self.target.parent)
        self.assertEqual(self.target.read_bytes(), b'my local export')

    def test_complete_pending_download_is_reused_after_interruption(self):
        from unittest.mock import patch
        self.fetch_payload(b'old release')
        sha = self.lock(b'new release')
        receipt = self.target.parent / '.vibe-artifacts.json'
        value = json.loads(receipt.read_text())
        value['pending'] = {'relative': 'model.onnx', 'sha256': sha}
        receipt.write_text(json.dumps(value))
        (self.target.parent / ('.vibe-' + sha + '.partial')).write_bytes(b'new release')
        with patch('artifacts.urllib.request.urlopen', side_effect=AssertionError('already downloaded')):
            artifacts.fetch(self.lock_path, self.target.parent)
        self.assertEqual(self.target.read_bytes(), b'new release')

    def test_previous_committed_artifact_lock_adopts_old_files_without_a_receipt(self):
        import io
        import subprocess
        from unittest.mock import patch
        self.lock(b'old release')
        old_lock = self.root / 'artifacts.lock.json'
        self.lock_path.rename(old_lock)
        self.lock_path = old_lock
        self.target.parent.mkdir()
        self.target.write_bytes(b'old release')
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        subprocess.run(['git', '-C', str(self.root), 'add', 'artifacts.lock.json'], check=True)
        subprocess.run(['git', '-C', str(self.root), '-c', 'user.name=Test',
                        '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'previous release'], check=True)
        self.lock(b'new release')
        self.lock_path.rename(old_lock)
        self.lock_path = old_lock
        with patch('artifacts.urllib.request.urlopen', return_value=io.BytesIO(b'new release')):
            artifacts.fetch(self.lock_path, self.target.parent)
        self.assertEqual(self.target.read_bytes(), b'new release')


if __name__ == '__main__':
    unittest.main()
