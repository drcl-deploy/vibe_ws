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
        self.temp = tempfile.TemporaryDirectory()
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


if __name__ == '__main__':
    unittest.main()
