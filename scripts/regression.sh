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
python3 scripts/experiment.py repose-v9.3
ctest --test-dir unitree_mujoco/simulate/build --output-on-failure
cyclonedds_ws/build/cpp_control/deploy_selftest \
  artifacts/models/repose-v9.3/model_59999.onnx
cyclonedds_ws/build/cpp_control/repose_planner_selftest \
  --config cyclonedds_ws/src/cpp_control/config/repose_planner/g1_sim_v9_3.yaml \
  --table artifacts/data/sys1_clips.npz \
  --library artifacts/data/sys1_library.npz \
  --frames artifacts/data/retargeted_motions \
  --approach artifacts/data/sys1_walk/walk_forward_amateur_001__A001/motion.npz
ros2 run vision_encoders cuda_provider_check
python3 - <<'PY'
from pathlib import Path
import hashlib
import json
lock = json.loads(Path('artifacts.lock.json').read_text())
for name, spec in lock['files'].items():
    data = (Path('artifacts') / name).read_bytes()
    assert len(data) == spec['bytes'] and hashlib.sha256(data).hexdigest() == spec['sha256'], name
print('PASS: all', len(lock['files']), 'frozen artifact hashes match')
PY
echo "Automated regression passed; manual joystick gate remains separate."
