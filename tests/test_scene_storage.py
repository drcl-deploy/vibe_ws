"""Scene files stay inspectable outside the checkout without cross-checkout reuse."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from scenes import scene_directory


class SceneStorageTest(unittest.TestCase):
    def test_migration_preserves_files_and_separates_checkouts(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / 'one/vibe_ws'
            existing = root / 'generated/repose'
            existing.mkdir(parents=True)
            (existing / 'hand-edited.xml').write_text('local work')
            with patch.dict(os.environ, XDG_DATA_HOME=str(base / 'share')):
                output = scene_directory(root)
                self.assertTrue((root / 'generated').is_symlink())
                self.assertEqual((output / 'repose/hand-edited.xml').read_text(), 'local work')
                self.assertEqual(scene_directory(root), output)
                other = base / 'two/vibe_ws'
                other.mkdir(parents=True)
                self.assertNotEqual(scene_directory(other), output)

    def test_relocated_checkout_does_not_overwrite_old_scenes(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / 'before'
            root.mkdir()
            with patch.dict(os.environ, XDG_DATA_HOME=str(base / 'share')):
                output = scene_directory(root)
                (output / 'note').write_text('keep')
                moved = base / 'after'
                root.rename(moved)
                new_output = scene_directory(moved)
                self.assertNotEqual(new_output, output)
                self.assertEqual((new_output / 'note').read_text(), 'keep')
                self.assertEqual((output / 'note').read_text(), 'keep')
