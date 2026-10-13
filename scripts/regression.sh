#!/usr/bin/env bash
set -eo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
source setup_local.sh
phase="${1:-recheck}"
[[ "$phase" =~ ^[a-zA-Z0-9_-]+$ ]] || exit 2
mkdir -p ".migration/$phase"
exec > >(tee ".migration/$phase/regression.log") 2>&1
export PYTHONDONTWRITEBYTECODE=1
python3 -m unittest discover -s tests -v
python3 scripts/doctor.py
# Compile against the exact MuJoCo used by the simulator, not a Python wheel.
c++ -std=c++17 -O2 tests/integration/native_scene_check.cpp \
  -I.deps/mujoco-3.3.6/include -L.deps/mujoco-3.3.6/lib \
  "-Wl,-rpath,$root/.deps/mujoco-3.3.6/lib" -lmujoco \
  -o ".migration/$phase/native_scene_check"
".migration/$phase/native_scene_check" \
  unitree_mujoco/unitree_robots/g1/g1_29dof_with_camera.xml \
  generated/repose/g1_repose_robot.xml generated/repose/g1_repose.xml
ctest --test-dir unitree_mujoco/simulate/build --output-on-failure
python3 - <<'PY'
from pathlib import Path
import json
import os
import subprocess
root = Path.cwd()
artifacts = Path(os.environ.get('VIBE_ARTIFACT_ROOT', root / 'artifacts'))
samples = json.loads(Path('data/sample/samples.json').read_text())['samples']
for name, spec in samples.items():
    command = ['cyclonedds_ws/build/cpp_control/deploy_selftest', str(artifacts / spec['policy'])]
    motion = root / 'data/sample' / name / 'motion.npz'
    if motion.with_name('contact_matrix.npz').exists():
        command += ['--motion', str(motion)]
    subprocess.run(command, check=True)
    subprocess.run(['unitree_mujoco/simulate/build/camera_stream_test',
                    str(root / 'generated' / name / 'scene.xml')], check=True)
PY
cyclonedds_ws/build/sledgehammer/repose_planner_selftest \
  --config cyclonedds_ws/src/sledgehammer/config/repose_planner/g1_sim_v9_3.yaml \
  --table cyclonedds_ws/src/sledgehammer/data/sys1_clips.npz \
  --frames cyclonedds_ws/src/sledgehammer/data/sys1_bundle.npz \
  --approach cyclonedds_ws/src/sledgehammer/data/sys1_walk/walk_forward_amateur_001__A001/motion.npz
ros2 run vision_encoders cuda_provider_check
python3 tests/motion_path_smoke.py --logs ".migration/$phase/motion-path"
python3 - <<'PY'
from pathlib import Path
import hashlib
import json
lock = json.loads(Path('artifacts.lock.json').read_text())
checked = 0
for name, spec in lock['files'].items():
    path = Path('artifacts') / name
    data = path.read_bytes()
    checked += 1
    assert len(data) == spec['bytes'] and hashlib.sha256(data).hexdigest() == spec['sha256'], name
print('PASS:', checked, 'sample policy/encoder hashes match')
pkg = Path('cyclonedds_ws/src/sledgehammer')
for name, spec in json.loads((pkg / 'data.lock.json').read_text())['files'].items():
    data = (pkg / name).read_bytes()
    assert len(data) == spec['bytes'] and hashlib.sha256(data).hexdigest() == spec['sha256'], name
print('PASS: all 4 frozen planner data hashes match')
PY
echo "Automated regression passed; manual joystick gate remains separate."
