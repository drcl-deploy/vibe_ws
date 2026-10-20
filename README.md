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

To sync updated module pins:

```bash
git pull --ff-only
./install.sh --stage sources
```

> [!NOTE]
> For [custom models](docs/setup.md#policy-and-encoder-exports), use absolute paths or place it under `artifacts/`.

## usage

run from the workspace root in each terminal, with a gamepad connected.
Source the matching environment in each ROS terminal:

```bash
# simulation
source setup_local.sh
```

```bash
# hardware
export VIBE_ROBOT_INTERFACE=eth0
source setup.sh onboard
```

### without planner

```bash
# terminal 1: simulator
sample=walk  # walk | parkour | repose | uolm
./unitree_mujoco/simulate/build/unitree_mujoco \
  -s "$PWD/generated/$sample/scene.xml"
```

```bash
# terminal 1: hardware camera (instead of the simulator)
sudo -v
/usr/bin/python3 cyclonedds_ws/src/vision_encoders/scripts/camera_streamer.py -v
```

```bash
# terminal 2: encoder + tracker
sample=walk  # walk | parkour | repose | uolm
ros2 launch cpp_control g1_vibe_sonic.launch.py \
  policy_path:="models/$sample/policy.onnx" \
  encoder_path:=encoders/theia-tiny.onnx \
  motion_path:="$PWD/data/sample/$sample/motion.npz"
```

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
# terminal 1: hardware camera (instead of the simulator)
sudo -v
/usr/bin/python3 cyclonedds_ws/src/vision_encoders/scripts/camera_streamer.py --depth -v
```

```bash
# terminal 2: encoder + tracker
ros2 launch cpp_control g1_vibe_sonic.launch.py \
  policy_path:=models/repose/policy.onnx \
  encoder_path:=encoders/theia-tiny.onnx \
  planner:=true \
  stand_yaw_teleop:=true stand_walk_teleop:=true \
  stand_walk_motion:="$PWD/cyclonedds_ws/install/sledgehammer/share/sledgehammer/data/sys1_walk/walk_forward_amateur_001__A001/motion.npz"
```

```bash
# terminal 3: planner + console
ros2 launch sledgehammer planner.launch.py env:=sim  # hardware: env:=real
```

- **console:** **0–5** or **r/o/g/y/b/p** target · **R** new trial · **q** quit. Select a target before arming.

to visualize the **learnt attention maps** , run in another terminal:
```bash
source setup_local.sh
bash cyclonedds_ws/src/cpp_control/scripts/vibe/stream_vibes.sh
```

```bash
# hardware: offboard workstation
export VIBE_ROBOT_HOST=gilfoyle
source setup.sh offboard
bash cyclonedds_ws/src/cpp_control/scripts/vibe/stream_vibes.sh
```

Start the controller first; its launch starts the telemetry bridge.

## docs

- [Setup & hardware deployment](docs/setup.md)
- [Samples & motion files](data/sample/README.md)
- [Testing](docs/testing.md)
- [Export compatibility](docs/compatibility.md)
- [Pinned dependencies](sources.repos)
