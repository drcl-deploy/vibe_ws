"""Validate the shipped references and scene inputs without training dependencies."""

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from doctor import check_samples
from scenes import generate


class SampleTest(unittest.TestCase):
    def test_reference_channels_and_object_sidecars(self):
        samples = check_samples()
        self.assertEqual(set(samples), {'walk', 'parkour', 'repose', 'uolm'})
        for name in samples:
            folder = ROOT / 'data/sample' / name
            with np.load(folder / 'motion.npz', allow_pickle=False) as motion:
                frames = len(motion['joint_pos'])
                self.assertEqual(motion['joint_pos'].shape, (frames, 29))
                self.assertEqual(float(motion['fps'][0]), 50)
                for key in ['joint_pos', 'joint_vel', 'body_pos_w', 'body_quat_w',
                            'body_lin_vel_w', 'body_ang_vel_w']:
                    self.assertEqual(motion[key].shape[0], frames)
                    self.assertTrue(np.isfinite(motion[key]).all())
            if name in {'repose', 'uolm'}:
                with np.load(folder / 'object_motion.npz', allow_pickle=False) as obj:
                    self.assertEqual(obj['obj_pos_w'].shape, (frames, 3))
                    self.assertEqual(obj['obj_quat_w'].shape, (frames, 4))
                    np.testing.assert_array_equal(obj['obj_pos_w'][0], samples[name]['object_start']['pos'])
                with np.load(folder / 'contact_matrix.npz', allow_pickle=False) as contacts:
                    self.assertIn('body_names', contacts)
                    matrix = contacts['matrix']
                    self.assertEqual(matrix.shape[0], frames)
                    self.assertTrue(np.isin(matrix, [0, 1]).all())
                    self.assertTrue(matrix.any())

    def test_portable_generation_and_selected_start(self):
        # A copied checkout with no assets package or training data reachable by path.
        import shutil
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'checkout'
            root.mkdir()
            shutil.copytree(ROOT / 'data/sample', root / 'data/sample')
            robot_dir = root / 'unitree_mujoco/unitree_robots/g1'
            robot_dir.mkdir(parents=True)
            source = ROOT / 'unitree_mujoco/unitree_robots/g1/g1_29dof_with_camera.xml'
            shutil.copyfile(source, robot_dir / source.name)
            with patch.dict('os.environ', XDG_DATA_HOME=str(Path(temp) / 'share')):
                paths = generate(root)
                before = {str(p): p.read_bytes() for p in (root / 'generated').rglob('*.xml')}
                self.assertEqual(paths, generate(root))
                self.assertEqual(before, {str(p): p.read_bytes() for p in (root / 'generated').rglob('*.xml')})
            specs = check_samples(root)
            for name, spec in specs.items():
                folder = root / 'generated' / name
                robot = ET.parse(folder / 'robot.xml')
                pelvis = robot.find("worldbody/body[@name='pelvis']")
                position = [float(x) for x in pelvis.get('pos').split()]
                np.testing.assert_allclose(position[:2], spec['robot_start']['xy'])
                self.assertAlmostEqual(position[2], .793 + spec['robot_start']['ground_z'])
                if name in {'walk', 'parkour'}:
                    self.assertEqual((folder / 'terrain.xml').read_bytes(),
                                     (root / 'data/sample' / name / 'terrain.xml').read_bytes())
                scene = ET.parse(folder / 'scene.xml')
                self.assertEqual(scene.find('option').get('timestep'), '0.002')
                for include in scene.findall('include'):
                    self.assertTrue((folder / include.get('file')).is_file())
                for p in folder.glob('*.xml'):
                    self.assertNotIn('/home/loki/', p.read_text())
            planner = ET.parse(root / 'generated/repose/g1_repose.xml')
            self.assertEqual(planner.find("worldbody/body[@name='cube']").get('pos'), '1.0 0.0 0.3')
            sample = ET.parse(root / 'generated/repose/scene.xml')
            np.testing.assert_allclose([float(x) for x in sample.find("worldbody/body[@name='cube']").get('pos').split()],
                                       specs['repose']['object_start']['pos'])


if __name__ == '__main__':
    unittest.main()
