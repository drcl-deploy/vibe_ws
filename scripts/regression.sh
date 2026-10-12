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
cyclonedds_ws/build/cpp_control/deploy_selftest \
  artifacts/models/repose-v9.3/model_59999.onnx
cyclonedds_ws/build/sledgehammer/repose_planner_selftest \
  --config cyclonedds_ws/src/sledgehammer/config/repose_planner/g1_sim_v9_3.yaml \
  --table cyclonedds_ws/src/sledgehammer/data/sys1_clips.npz \
  --frames cyclonedds_ws/src/sledgehammer/data/sys1_bundle.npz \
  --approach cyclonedds_ws/src/sledgehammer/data/sys1_walk/walk_forward_amateur_001__A001/motion.npz
ros2 run vision_encoders cuda_provider_check
python3 - <<'PY'
from pathlib import Path
import hashlib
import json
lock = json.loads(Path('artifacts.lock.json').read_text())
checked = 0
for name, spec in lock['files'].items():
    path = Path('artifacts') / name
    if name.startswith('data/') and not path.exists():
        continue  # historical retargeted inputs are replaced by the frozen package bundle
    data = path.read_bytes()
    checked += 1
    assert len(data) == spec['bytes'] and hashlib.sha256(data).hexdigest() == spec['sha256'], name
print('PASS:', checked, 'baseline artifact hashes match (4 model files required)')
pkg = Path('cyclonedds_ws/src/sledgehammer')
for name, spec in json.loads((pkg / 'data.lock.json').read_text())['files'].items():
    data = (pkg / name).read_bytes()
    assert len(data) == spec['bytes'] and hashlib.sha256(data).hexdigest() == spec['sha256'], name
print('PASS: all 4 frozen planner data hashes match')
PY
echo "Automated regression passed; manual joystick gate remains separate."
