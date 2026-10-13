# vibe_ws

[![Project](https://img.shields.io/badge/Project-Page-brightgreen)](https://lok-i.github.io/vibe-control/)
[![Training](https://img.shields.io/badge/Training-vibe-blue)](https://github.com/lok-i/vibe)

deployment workspace for **ViBe** trackers to `unitree_mujoco` and the Unitree G1 hardware

## requirements

- Ubuntu 22.04 + ROS 2 Humble (tested)
- NVIDIA GPU with a working driver (`nvidia-smi`)
- Git + Git LFS

## install

From a fresh shell:

```bash
git clone https://github.com/drcl-deploy/vibe_ws
cd vibe_ws
./install.sh --system  # fetch, generate scenes, build
```

> [!NOTE]
> For [custom models](docs/setup.md#policy-and-encoder-exports), use absolute paths or place it under `artifacts/`.

## usage

Run from the workspace root in each terminal, with a gamepad connected.

### without planner

```bash
# terminal 1: simulator
sample=walk  # walk | parkour | repose | uolm
./unitree_mujoco/simulate/build/unitree_mujoco \
  -s "$PWD/generated/$sample/scene.xml"
```

```bash
# terminal 2: encoder + tracker
source setup_local.sh
sample=walk  # walk | parkour | repose | uolm
ros2 launch cpp_control g1_vibe_sonic.launch.py \
  policy_path:="models/$sample/policy.onnx" \
  encoder_path:=encoders/theia-tiny.onnx \
  motion_path:="$PWD/data/sample/$sample/motion.npz"
```

- **RB** stand → **L1** prep → **A** run · **Y** damping.
- Use the same `sample` in both terminals; the scene, motion and policy follow it.

| Sample | Demo |
|---|---|
| `walk` | Grail curbs |
| `parkour` | OmRe climb |
| `repose` | Double cube frontflip |
| `uolm` | Suitcase |

### with planner (cube repose only)

```bash
# terminal 1: simulator + cube
./unitree_mujoco/simulate/build/unitree_mujoco \
  -s "$PWD/generated/repose/g1_repose.xml"
```

```bash
# terminal 2: encoder + tracker
source setup_local.sh
ros2 launch cpp_control g1_vibe_sonic.launch.py \
  policy_path:=models/repose/policy.onnx \
  encoder_path:=encoders/theia-tiny.onnx \
  planner:=true \
  stand_yaw_teleop:=true stand_walk_teleop:=true \
  stand_walk_motion:="$PWD/cyclonedds_ws/install/sledgehammer/share/sledgehammer/data/sys1_walk/walk_forward_amateur_001__A001/motion.npz"
```

```bash
# terminal 3: planner + console
source setup_local.sh
ros2 launch sledgehammer planner.launch.py env:=sim
```

- **Gamepad:** **RB** stand/disarm · **A** arm · **Y** damping.
- **Console:** **0–5** or **r/o/g/y/b/p** target · **R** new trial · **q** quit. Select a target before arming.
- Restart the tracker after restarting the planner.

to visualize the **learnt attention maps** , run in another terminal:
```bash
source setup_local.sh
bash cyclonedds_ws/src/cpp_control/scripts/vibe/stream_vibes.sh
```

## docs

- [Setup & hardware deployment](docs/setup.md)
- [Samples & motion files](data/sample/README.md)
- [Testing](docs/testing.md)
- [Export compatibility](docs/compatibility.md)
- [Pinned dependencies](sources.repos)
