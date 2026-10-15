"""Retry the actual recovery boundaries without downloading SDKs or starting ROS."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import install as installer
from install_state import locked, prepare_build, read_json, state_directory, write_json


class RecoveryTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='installer retry ')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        patcher = patch.object(installer, 'ROOT', self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.outputs = ['cyclonedds_ws/build', 'cyclonedds_ws/install']
        self.inputs = {'profile': 'onboard', 'revision': 'old'}

    def output(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def test_retry_keeps_completed_objects_and_upgrade_removes_obsolete_installed_types(self):
        prepare_build(self.root, 'ros', self.inputs, self.outputs)
        obj = self.output('cyclonedds_ws/build/completed.o', 'completed object')
        stale = self.output('cyclonedds_ws/install/cpp_control/msg/PlannerStatus.py', 'old type')
        prepare_build(self.root, 'ros', self.inputs, self.outputs)
        self.assertEqual(obj.read_text(), 'completed object')
        prepare_build(self.root, 'ros', dict(self.inputs, revision='new'), self.outputs)
        self.assertFalse(obj.exists())
        self.assertFalse(stale.exists())
        preserved = list((state_directory(self.root) / 'previous').rglob('PlannerStatus.py'))
        self.assertEqual(len(preserved), 1)
        self.assertEqual(preserved[0].read_text(), 'old type')
        # A failed new compilation must not trigger another clean rotation.
        new_obj = self.output('cyclonedds_ws/build/new.o', 'partial new build')
        prepare_build(self.root, 'ros', dict(self.inputs, revision='new'), self.outputs)
        self.assertEqual(new_obj.read_text(), 'partial new build')

    def test_interrupted_directory_rotation_finishes_once_on_retry(self):
        prepare_build(self.root, 'ros', self.inputs, self.outputs)
        self.output('cyclonedds_ws/build/completed.o', 'old object')
        self.output('cyclonedds_ws/install/old.txt', 'old install')
        rename = Path.rename
        def interrupted(path, destination):
            if path == self.root / 'cyclonedds_ws/install':
                raise OSError('power cut between moves')
            return rename(path, destination)
        updated = dict(self.inputs, profile='offboard')
        with patch.object(Path, 'rename', interrupted):
            with self.assertRaisesRegex(OSError, 'power cut'):
                prepare_build(self.root, 'ros', updated, self.outputs)
        prepare_build(self.root, 'ros', updated, self.outputs)
        self.assertFalse((self.root / 'cyclonedds_ws/build').exists())
        self.assertFalse((self.root / 'cyclonedds_ws/install').exists())
        backups = state_directory(self.root) / 'previous'
        self.assertEqual(len(list(backups.iterdir())), 1)
        self.assertEqual(len(list(backups.rglob('old.txt'))), 1)
        self.assertNotIn('moving', read_json(state_directory(self.root) / 'builds.json')['ros'])

    def test_generated_symlink_outside_checkout_is_never_rotated(self):
        outside = self.root / 'outside'
        outside.mkdir()
        target = self.root / 'cyclonedds_ws'
        target.mkdir()
        (target / 'build').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            prepare_build(self.root, 'ros', self.inputs, self.outputs)
        self.assertTrue((target / 'build').is_symlink())
        self.assertTrue(outside.exists())

    def test_pending_sdk_recovers_but_an_unrecognized_incomplete_directory_is_preserved(self):
        target = self.root / '.deps/sdk'
        def interrupted(*args, **kwargs):
            self.output('.deps/sdk/partial.txt', 'incomplete install')
            raise subprocess.CalledProcessError(1, ['setup-helper'])
        with patch.object(installer, 'run', interrupted):
            with self.assertRaises(subprocess.CalledProcessError):
                installer.dependency('sdk', ['setup-helper'], target, ['header.h'])
        def finish(*args, **kwargs):
            self.output('.deps/sdk/header.h', 'complete SDK')
        with patch.object(installer, 'run', finish):
            installer.dependency('sdk', ['setup-helper'], target, ['header.h'])
        self.assertEqual((target / 'header.h').read_text(), 'complete SDK')
        self.assertFalse((target / 'partial.txt').exists())
        self.assertEqual(len(list((state_directory(self.root) / 'previous').rglob('partial.txt'))), 1)
        unknown = self.root / '.deps/unrecognized'
        self.output('.deps/unrecognized/notes.txt', 'my work')
        with self.assertRaisesRegex(ValueError, 'left untouched'):
            installer.dependency('unknown', ['setup-helper'], unknown, ['header.h'])
        self.assertEqual((unknown / 'notes.txt').read_text(), 'my work')

    def test_profile_jobs_and_archive_are_remembered_without_plan_writes(self):
        preferences = {'profile': 'onboard', 'jobs': 1,
                       'ort_archive': '/path with spaces/sdk.tgz', 'ort_sha256': 'a' * 64}
        path = state_directory(self.root) / 'preferences.json'
        write_json(path, preferences)
        before = path.read_bytes()
        args, stages, _ = installer.parse_args(['--plan'])
        self.assertEqual(args.profile, 'onboard')
        self.assertEqual(args.jobs, 1)
        self.assertEqual(str(args.ort_archive), '/path with spaces/sdk.tgz')
        self.assertEqual(stages, ['sources', 'deps', 'artifacts', 'ros', 'doctor'])
        args, stages, _ = installer.parse_args(['--plan', '--profile', 'offboard', '--jobs', '3'])
        self.assertEqual(args.jobs, 3)
        self.assertEqual(stages, ['sources', 'deps', 'ros', 'doctor'])
        args, _, _ = installer.parse_args(['--plan', '--ort-archive', 'auto'])
        self.assertIsNone(args.ort_archive)
        self.assertIsNone(args.ort_sha256)
        self.assertEqual(path.read_bytes(), before)

    def test_stage_failure_records_log_and_same_command_retry(self):
        def fail(args, selected, preferences, progress):
            progress('ros')
            print('compiler details retained')
            raise subprocess.CalledProcessError(2, ['compile'])
        out, err = io.StringIO(), io.StringIO()
        with patch.object(sys, 'argv', ['install.py', '--stage', 'ros']), \
             patch.object(installer, 'execute', fail), redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(installer.main(), 1)
        self.assertIn('Setup stopped at ros', err.getvalue())
        self.assertIn('Retry: ./install.sh --stage ros', err.getvalue())
        record = read_json(state_directory(self.root) / 'progress.json')
        self.assertEqual(record['status'], 'failed')
        log = Path(record['log']).read_text()
        self.assertIn('compiler details retained', log)
        self.assertIn('Setup stopped at ros', log)
        # The failed installer must release the workspace lock.
        with locked(state_directory(self.root) / 'install.lock'):
            pass

    def test_parallel_installers_are_rejected_without_modifying_the_receipt(self):
        path = state_directory(self.root) / 'install.lock'
        with locked(path):
            with self.assertRaisesRegex(ValueError, 'Another installer'):
                with locked(path):
                    self.fail('lock was not enforced')

    def test_incomplete_venv_cannot_install_setup_packages_into_system_python(self):
        # A killed `python -m venv` can leave bin/python but no pyvenv.cfg.
        self.output('.venv/notes.txt', 'preserve these files')
        (self.root / '.venv/bin').mkdir()
        (self.root / '.venv/bin/python').symlink_to('/usr/bin/python3')
        commands = []
        def setup(command, **kwargs):
            commands.append([str(value) for value in command])
            if command[:3] == ['/usr/bin/python3', '-m', 'venv']:
                subprocess.run([str(value) for value in command], check=True)
        with patch.object(installer, 'run', setup):
            python = installer.bootstrap(False, None)
        prefix = subprocess.check_output([str(python), '-c', 'import sys; print(sys.prefix)'], text=True).strip()
        self.assertEqual(Path(prefix), self.root / '.venv')
        self.assertTrue((self.root / '.venv/pyvenv.cfg').is_file())
        self.assertTrue(any('-m' in command and 'pip' in command for command in commands))
        for command in commands:
            if 'pip' in command:
                self.assertEqual(command[0], str(self.root / '.venv/bin/python'))
        self.assertEqual(len(list((state_directory(self.root) / 'previous').rglob('notes.txt'))), 1)

    def test_simulator_stage_does_not_require_ros_or_an_encoder_sdk(self):
        self.output('sources.repos', 'repositories:\n  unitree_mujoco:\n    version: simulator-pin\n')
        self.output('dependencies.lock.json', json.dumps({
            'unitree_sdk2': {'revision': 'sdk-pin'}, 'mujoco': {'version': '9.9.9'}}))
        args, _, preferences = installer.parse_args(['--stage', 'sim'])
        commands = []
        with patch.object(installer, 'bootstrap', return_value=self.root / '.venv/bin/python'), \
             patch.object(installer, 'select_distro', side_effect=AssertionError('ROS is not needed')), \
             patch.object(installer, 'native_identity', return_value={'architecture': 'fixture', 'compiler': 'fixture'}), \
             patch.object(installer, 'run', side_effect=lambda command, **kwargs: commands.append(command)):
            installer.execute(args, ['sim'], preferences, lambda stage: None)
        self.assertEqual(len(commands), 2)
        self.assertEqual(commands[0][:3], ['cmake', '-S', 'unitree_mujoco/simulate'])
        self.assertEqual(commands[1][:2], ['cmake', '--build'])
        self.assertIn('-DMUJOCO_ROOT=' + str(self.root / '.deps/mujoco-9.9.9'), commands[0])

    def test_saved_ros_is_reused_when_available_and_detected_again_after_an_os_upgrade(self):
        import os
        import ros_env
        ros_root = self.root / 'ros'
        for name in ['humble', 'jazzy']:
            folder = ros_root / name
            folder.mkdir(parents=True)
            (folder / 'setup.bash').touch()
        with patch.object(installer, 'ROS_ROOT', ros_root), \
             patch.object(installer, 'select_distro', side_effect=lambda value: ros_env.select_distro(value, ros_root)), \
             patch.dict(os.environ, {'ROS_DISTRO': ''}):
            self.assertEqual(installer.choose_distro({'ros_distro': 'humble'}), 'humble')
            (ros_root / 'humble/setup.bash').unlink()
            self.assertEqual(installer.choose_distro({'ros_distro': 'humble'}), 'jazzy')
            with patch.dict(os.environ, {'ROS_DISTRO': 'humble'}):
                with self.assertRaisesRegex(ValueError, 'Missing ROS'):
                    installer.choose_distro({'ros_distro': 'jazzy'})


if __name__ == '__main__':
    unittest.main()
