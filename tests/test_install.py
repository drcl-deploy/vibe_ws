import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from ros_env import check_overlay, identity, select_distro
import check_runtime
import install as installer


class InstallationDependencyTest(unittest.TestCase):
    def test_profiles_require_only_their_available_system_dependencies(self):
        for distro in ['foxy', 'humble', 'jazzy']:
            for profile in ['sim', 'onboard', 'offboard']:
                with self.subTest(distro=distro, profile=profile):
                    packages = installer.system_packages(distro, profile)
                    self.assertIn('python3-venv', packages)
                    self.assertIn('ros-' + distro + '-rosbag2', packages)
                    for graphics in ['libglfw3-dev', 'libgl1-mesa-dev']:
                        self.assertEqual(graphics in packages, profile == 'sim')
                    for viewer in ['python3-matplotlib', 'python3-pyqt5']:
                        self.assertEqual(viewer in packages, profile != 'onboard')
                    self.assertEqual('ros-' + distro + '-rosbag2-py' in packages,
                                     profile != 'onboard' and distro != 'foxy')

    def test_doctor_checks_bag_replay_only_where_it_is_available_and_used(self):
        for distro in ['foxy', 'humble', 'jazzy']:
            for profile in ['sim', 'onboard', 'offboard']:
                with self.subTest(distro=distro, profile=profile):
                    modules = check_runtime.runtime_modules(profile, distro)
                    for runtime in ['numpy', 'cv2', 'rclpy', 'yaml']:
                        self.assertIn(runtime, modules)
                    self.assertEqual('PyQt5.QtCore' in modules, profile != 'onboard')
                    self.assertEqual('rosbag2_py' in modules,
                                     profile != 'onboard' and distro != 'foxy')

    def test_foxy_onboard_preflight_reports_only_missing_setup_dependency(self):
        installed = set(installer.system_packages('foxy', 'onboard')) - {'python3-venv'}
        probe = subprocess.CompletedProcess([], 1, stdout=''.join(
            name + ' installed\n' for name in sorted(installed)))
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(installer, 'ROOT', Path(directory)), \
             patch.object(installer, 'choose_distro', return_value='foxy'), \
             patch.object(installer.subprocess, 'run', return_value=probe), \
             patch.dict(os.environ, {'ROS_DISTRO': 'foxy'}):
            args, stages, preferences = installer.parse_args(['--profile', 'onboard', '--jobs', '1'])
            with self.assertRaisesRegex(ValueError,
                    r'^Missing system packages: python3-venv\. Run ./install.sh --system --profile onboard\.$'):
                installer.execute(args, stages, preferences, lambda stage: None)


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
