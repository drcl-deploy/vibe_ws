"""Source import must preserve existing work and obey immutable pins."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/sources.py'


class SourceImportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='source retry ')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.remote = self.base / 'remote'
        self.root = self.base / 'workspace'
        self.remote.mkdir()
        self.root.mkdir()
        self.git(self.remote, 'init', '-q')
        (self.remote / 'file').write_text('baseline\n')
        self.git(self.remote, 'add', 'file')
        self.git(self.remote, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                 'commit', '-qm', 'baseline')
        self.sha = self.git(self.remote, 'rev-parse', 'HEAD').strip()
        self.pin = {'type': 'git', 'url': str(self.remote), 'version': self.sha}
        self.write_pins({'module': self.pin})

    def git(self, path, *args):
        return subprocess.check_output(['git', '-C', str(path), *args], text=True)

    def write_pins(self, repos):
        (self.root / 'sources.repos').write_text(yaml.safe_dump({'repositories': repos}))

    def invoke(self, action, success=True):
        result = subprocess.run(['python3', str(SCRIPT), action, '--root', str(self.root)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def test_fresh_import_is_idempotent(self):
        self.invoke('check', False)
        self.invoke('import')
        self.invoke('import')
        self.invoke('check')
        self.assertEqual(self.git(self.root / 'module', 'rev-parse', 'HEAD').strip(), self.sha)

    def test_dirty_checkout_blocks_all_imports_without_overwriting(self):
        self.invoke('import')
        path = self.root / 'module/file'
        path.write_text('user edit\n')
        self.write_pins({'module': self.pin, 'other': self.pin})
        self.invoke('import', False)
        self.assertEqual(path.read_text(), 'user edit\n')
        self.assertFalse((self.root / 'other').exists())

    def test_mismatched_head_is_not_reset(self):
        self.invoke('import')
        path = self.root / 'module'
        self.git(path, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                 'commit', '--allow-empty', '-qm', 'local work')
        before = self.git(path, 'rev-parse', 'HEAD')
        self.invoke('import', False)
        self.assertEqual(self.git(path, 'rev-parse', 'HEAD'), before)

    def test_non_repo_directory_is_preserved(self):
        path = self.root / 'module'
        path.mkdir()
        (path / 'notes').write_text('local notes')
        self.invoke('import', False)
        self.assertEqual((path / 'notes').read_text(), 'local notes')

    def test_path_escape_is_rejected(self):
        self.write_pins({'../escape': self.pin})
        self.invoke('import', False)
        self.assertFalse((self.base / 'escape').exists())
        (self.root / 'module').symlink_to(self.remote, target_is_directory=True)
        self.write_pins({'module': self.pin})
        self.invoke('import', False)


class SourceUpgradeTest(unittest.TestCase):
    setUp = SourceImportTest.setUp
    git = SourceImportTest.git
    write_pins = SourceImportTest.write_pins
    invoke = SourceImportTest.invoke

    def next_commit(self):
        (self.remote / 'file').write_text('next release\n')
        self.git(self.remote, 'add', 'file')
        self.git(self.remote, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                 'commit', '-qm', 'next release')
        return self.git(self.remote, 'rev-parse', 'HEAD').strip()

    def test_managed_source_upgrades_and_retries_without_resetting_a_branch(self):
        self.invoke('import')
        module = self.root / 'module'
        self.git(module, 'switch', '-qc', 'my-release')
        new = self.next_commit()
        self.write_pins({'module': dict(self.pin, version=new)})
        self.invoke('import')
        self.invoke('import')
        self.assertEqual(self.git(module, 'rev-parse', 'HEAD').strip(), new)
        self.assertEqual(self.git(module, 'branch', '--show-current').strip(), 'my-release')
        self.assertEqual((module / 'file').read_text(), 'next release\n')

    def test_old_installer_checkout_is_adopted_only_when_fast_forward_is_safe(self):
        # An existing user predates receipts; the clean old release is on main.
        self.git(self.root, 'clone', '-q', str(self.remote), 'module')
        new = self.next_commit()
        self.write_pins({'module': dict(self.pin, version=new)})
        self.invoke('import')
        self.assertEqual(self.git(self.root / 'module', 'rev-parse', 'HEAD').strip(), new)

    def test_dirty_second_module_blocks_every_update(self):
        self.write_pins({'module': self.pin, 'other': self.pin})
        self.invoke('import')
        (self.root / 'other/file').write_text('local experiment\n')
        new = self.next_commit()
        self.write_pins({'module': dict(self.pin, version=new), 'other': self.pin})
        self.invoke('import', False)
        self.assertEqual(self.git(self.root / 'module', 'rev-parse', 'HEAD').strip(), self.sha)
        self.assertEqual((self.root / 'other/file').read_text(), 'local experiment\n')

    def test_pin_rollback_keeps_the_previous_branch(self):
        self.invoke('import')
        new = self.next_commit()
        self.write_pins({'module': dict(self.pin, version=new)})
        self.invoke('import')
        self.git(self.root / 'module', 'switch', '-qc', 'keep-my-release')
        self.write_pins({'module': self.pin})
        self.invoke('import')
        self.assertEqual(self.git(self.root / 'module', 'rev-parse', 'keep-my-release').strip(), new)
        self.assertEqual(self.git(self.root / 'module', 'rev-parse', 'HEAD').strip(), self.sha)

    def test_failed_clone_never_exposes_a_partial_source_and_retry_recovers(self):
        bad = dict(self.pin, version='0' * 40)
        self.write_pins({'module': bad})
        self.invoke('import', False)
        self.assertFalse((self.root / 'module').exists())
        self.write_pins({'module': self.pin})
        self.invoke('import')
        self.assertEqual((self.root / 'module/file').read_text(), 'baseline\n')

    def test_ignored_local_export_is_not_overwritten_by_a_new_tracked_file(self):
        (self.remote / '.gitignore').write_text('local.onnx\n')
        self.git(self.remote, 'add', '.gitignore')
        self.git(self.remote, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                 'commit', '-qm', 'ignore local models')
        ignored_release = self.git(self.remote, 'rev-parse', 'HEAD').strip()
        self.write_pins({'module': dict(self.pin, version=ignored_release)})
        self.invoke('import')
        (self.root / 'module/local.onnx').write_text('my custom model')
        (self.remote / 'local.onnx').write_text('new packaged model')
        self.git(self.remote, 'add', '-f', 'local.onnx')
        self.git(self.remote, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                 'commit', '-qm', 'package a model')
        updated = self.git(self.remote, 'rev-parse', 'HEAD').strip()
        self.write_pins({'module': dict(self.pin, version=updated)})
        self.invoke('import', False)
        self.assertEqual((self.root / 'module/local.onnx').read_text(), 'my custom model')
        self.assertEqual(self.git(self.root / 'module', 'rev-parse', 'HEAD').strip(), ignored_release)

    def test_old_release_pin_can_cross_a_squash_merge_without_receipts(self):
        self.git(self.root, 'init', '-q')
        self.git(self.root, 'add', 'sources.repos')
        self.git(self.root, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                 'commit', '-qm', 'previous workspace release')
        self.git(self.root, 'clone', '-q', str(self.remote), 'module')
        module = self.root / 'module'
        branch = self.git(module, 'branch', '--show-current').strip()
        self.git(self.remote, 'checkout', '--orphan', 'squashed-release')
        (self.remote / 'file').write_text('squashed new release\n')
        self.git(self.remote, 'add', 'file')
        self.git(self.remote, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                 'commit', '-qm', 'squashed release')
        new = self.git(self.remote, 'rev-parse', 'HEAD').strip()
        self.write_pins({'module': dict(self.pin, version=new)})
        self.git(self.root, 'add', 'sources.repos')
        self.git(self.root, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                 'commit', '-qm', 'next workspace release')
        self.invoke('import')
        self.assertEqual(self.git(module, 'rev-parse', 'HEAD').strip(), new)
        self.assertEqual(self.git(module, 'rev-parse', branch).strip(), self.sha)
        self.assertEqual((module / 'file').read_text(), 'squashed new release\n')


if __name__ == '__main__':
    unittest.main()
