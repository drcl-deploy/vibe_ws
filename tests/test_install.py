import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from ros_env import check_overlay, identity, select_distro


class InstallationSelectionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def add_ros(self, distro):
        folder = self.root / distro
        folder.mkdir()
        (folder / 'setup.bash').write_text('export ROS_DISTRO=' + distro + '\n')

    def test_each_distribution_is_discovered_in_a_fresh_shell(self):
        for distro in ['foxy', 'humble', 'jazzy']:
            with self.subTest(distro=distro):
                self.add_ros(distro)
                self.assertEqual(select_distro('', self.root), distro)
                (self.root / distro / 'setup.bash').unlink()

    def test_ambiguous_selection_requires_explicit_distribution(self):
        self.add_ros('humble')
        self.add_ros('jazzy')
        with self.assertRaisesRegex(ValueError, 'explicitly'):
            select_distro('', self.root)
        self.assertEqual(select_distro('jazzy', self.root), 'jazzy')

    def test_missing_selection_does_not_fall_back(self):
        self.add_ros('humble')
        with self.assertRaisesRegex(ValueError, 'Missing ROS'):
            select_distro('jazzy', self.root)
        with self.assertRaisesRegex(ValueError, 'ROS_DISTRO'):
            select_distro('invalid', self.root)

    def test_overlay_cannot_mix_distribution_or_profile(self):
        install = self.root / 'install'
        install.mkdir()
        marker = install / 'vibe_build.json'
        marker.write_text(json.dumps(identity('humble', runtime=True)))
        check_overlay(self.root, 'humble', runtime=True)
        for distro, runtime in [('jazzy', True), ('humble', False)]:
            with self.subTest(distro=distro, runtime=runtime):
                with self.assertRaisesRegex(ValueError, 'different ROS'):
                    check_overlay(self.root, distro, runtime)

    def test_legacy_overlay_underlay_is_checked(self):
        install = self.root / 'install'
        install.mkdir()
        (install / 'setup.bash').write_text('COLCON_CURRENT_PREFIX="/opt/ros/foxy"\n')
        with self.assertRaisesRegex(ValueError, 'foxy, not jazzy'):
            check_overlay(self.root, 'jazzy')

    def test_plan_is_read_only_even_with_system_anywhere_in_arguments(self):
        env = dict(os.environ, ROS_DISTRO='jazzy', PYTHONDONTWRITEBYTECODE='1')
        for args in [ ['--system', '--profile', 'offboard', '--plan'],
                      ['--profile', 'offboard', '--plan', '--system'] ]:
            result = subprocess.run([str(ROOT / 'install.sh')] + args,
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), 'sources -> deps -> ros -> doctor')


if __name__ == '__main__':
    unittest.main()
