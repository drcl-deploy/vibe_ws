# vibe_ws

[![Project](https://img.shields.io/badge/Project-Page-brightgreen)](https://lok-i.github.io/vibe-control/)
[![Training](https://img.shields.io/badge/Training-vibe-blue)](https://github.com/lok-i/vibe)

deployment workspace for **ViBe** trackers to `unitree_mujoco` and the Unitree G1 hardware

## requirements

- Ubuntu 22.04 + ROS 2 Humble (tested)
- NVIDIA GPU with a working driver (`nvidia-smi`)
- Git + Git LFS

## install

From a fresh shell, choose simulation or hardware:

```bash
git clone https://github.com/drcl-deploy/vibe_ws
cd vibe_ws

# simulation
./install.sh --system --profile sim

# hardware (system packages already installed)
./install.sh --profile onboard --jobs 4
```

To sync module sources and rebuild ROS packages, choose simulation or hardware:

```bash
git pull --ff-only
./install.sh --stage sources

# simulation
./install.sh --stage ros --profile sim

# hardware
./install.sh --stage ros --profile onboard --jobs 4
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

#### start simulation or hardware camera (terminal 1; choose one)

```bash
# simulation
sample=walk  # walk | parkour | repose | uolm
./unitree_mujoco/simulate/build/unitree_mujoco \
  -s "$PWD/generated/$sample/scene.xml"
```

```bash
# hardware
sudo -v && \
  /usr/bin/python3 cyclonedds_ws/src/vision_encoders/scripts/camera_streamer.py -v
```

#### start encoder + tracker (terminal 2)

```bash
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

#### start simulation or hardware camera (terminal 1; choose one)

```bash
# simulation
./unitree_mujoco/simulate/build/unitree_mujoco \
  -s "$PWD/generated/repose/g1_repose.xml"
```

```bash
# hardware
sudo -v && \
  /usr/bin/python3 cyclonedds_ws/src/vision_encoders/scripts/camera_streamer.py --depth -v
```

#### start encoder + tracker (terminal 2)

```bash
ros2 launch cpp_control g1_vibe_sonic.launch.py \
  policy_path:=models/repose/policy.onnx \
  encoder_path:=encoders/theia-tiny.onnx \
  planner:=true \
  stand_yaw_teleop:=true stand_walk_teleop:=true \
  stand_walk_motion:="$PWD/cyclonedds_ws/install/sledgehammer/share/sledgehammer/data/sys1_walk/walk_forward_amateur_001__A001/motion.npz"
```

#### start planner + console (terminal 3)

```bash
ros2 launch sledgehammer planner.launch.py env:=sim  # hardware: env:=real
```

- **console:** **0–5** or **r/o/g/y/b/p** target · **R** new trial · **q** quit. Select a target before arming.

### attention viewer

to visualize the **learnt attention maps** , run in another terminal:

```bash
# simulation
source setup_local.sh
bash cyclonedds_ws/src/cpp_control/scripts/vibe/stream_vibes.sh
```

```bash
# hardware: offboard workstation
export VIBE_ROBOT_HOST="<robot-ip-or-hostname>"  # G1 onboard PC default: 192.168.123.164
source setup.sh offboard
bash cyclonedds_ws/src/cpp_control/scripts/vibe/stream_vibes.sh
```

start the controller first; its launch starts the telemetry bridge.

## docs

- [Setup & hardware deployment](docs/setup.md)
- [Samples & motion files](data/sample/README.md)
- [Testing](docs/testing.md)
- [Export compatibility](docs/compatibility.md)
- [Pinned dependencies](sources.repos)
