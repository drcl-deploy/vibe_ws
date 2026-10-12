# vibe_ws

[![Project](https://img.shields.io/badge/Project-Page-brightgreen)](https://lok-i.github.io/vibe-control/)
[![Training](https://img.shields.io/badge/Training-vibe-blue)](https://github.com/lok-i/vibe)

ROS 2 deployment for **ViBe**: vision-conditioned whole-body trackers on the Unitree G1.
Training and ONNX export live in [vibe](https://github.com/lok-i/vibe).

## install

Ubuntu 22.04 / ROS Humble, an NVIDIA driver, and Git LFS. Start in a fresh shell.

```bash
git clone https://github.com/drcl-deploy/vibe_ws && cd vibe_ws
./install.sh --system
```

Fetches pinned modules, installs dependencies, generates the scenes and builds
the simulator and ROS packages. Generated XML paths are printed. ROS must already
be installed. XML lives in `~/.local/share/vibe/scenes/<checkout>/`, linked as
`generated/` here. Resume stages and onboard setup: [docs/setup.md](docs/setup.md).

### models

Use the policy and matching encoder from [vibe's exporter](https://github.com/lok-i/vibe/blob/main/docs/export.md).
Keep each `.onnx` beside its `.manifest.json`; pass their paths directly to ROS.
The commands below use the frozen Repose files already present on this machine:

```text
artifacts/models/repose-v9.3/model_59999.onnx
artifacts/models/repose-v9.3/model_59999.manifest.json
artifacts/encoders/theia-tiny.onnx
artifacts/encoders/theia-tiny.manifest.json
```

`artifacts/` is ignored by Git. Exports can live elsewhere—absolute paths work too.
Pre-exported Hugging Face downloads are pending publication.

## usage

Run from `~/vibe_ws` in each terminal, with an Xbox-compatible gamepad connected.

### Repose · V9.3

Terminal 1 — simulator:

```bash
./unitree_mujoco/simulate/build/unitree_mujoco -r g1 -i 1 -n lo \
  -s "$PWD/generated/repose/g1_repose.xml" --use_joystick 1 \
  --camera_width 112 --camera_height 63 --camera_fps 50 \
  --camera_depth_width 112 --camera_depth_height 63 \
  --camera_textures 0 --camera_visual_groups 1
```

Terminal 2 — encoder + tracker:

```bash
source setup_local.sh
ros2 launch cpp_control g1_vibe_sonic.launch.py \
  policy_path:=models/repose-v9.3/model_59999.onnx \
  encoder_path:=encoders/theia-tiny.onnx \
  planner:=true goal_color:=4 \
  stand_yaw_teleop:=true stand_walk_teleop:=true \
  stand_walk_motion:="$PWD/cyclonedds_ws/install/sledgehammer/share/sledgehammer/data/sys1_walk/walk_forward_amateur_001__A001/motion.npz"
```

Terminal 3 — planner:

```bash
source setup_local.sh
ros2 launch sledgehammer planner.launch.py env:=sim goal_color:=4
```

| control | action |
|---|---|
| **Y** | damping |
| **RB** | enter stand; disarm an active rollout |
| **A** | arm from stand, once the planner is available |
| `goal_color` | `0` red · `1` orange · `2` green · `3` yellow · `4` blue · `5` pink |

Set the same `goal_color` in terminals 2 and 3. The tracker exits if a connected
planner stops publishing status for one second; ROS launch then stops the encoder
and bridge. Restart terminal 2 explicitly after restarting the planner.

### tracker only

Use the simulator above and start only the encoder + tracker in terminal 2:

```bash
source setup_local.sh
ros2 launch cpp_control g1_vibe_sonic.launch.py \
  policy_path:=/path/to/policy.onnx encoder_path:=/path/to/encoder.onnx \
  motion_path:=/path/to/motion.npz
```

For Repose, UoLM and PerLoco (OmRe/Grail): **RB** stand, **L1** prep, **A** run.
Keep the motion's contact/object sidecars beside it. For the generic G1 floor
scene, use `generated/g1/g1.xml` in terminal 1 and omit the two Repose render flags.
Dodge remains loadable, with no dedicated task scene in this release.

### test

```bash
python3 scripts/doctor.py
bash scripts/regression.sh
```

These defaults check the frozen Repose files above. Automated checks and the
joystick gate: [docs/testing.md](docs/testing.md). Camera/cube alignment:
[docs/parity.md](docs/parity.md). Export contracts: [docs/compatibility.md](docs/compatibility.md).

## modules

| repo | owns |
|---|---|
| [cpp_control](https://github.com/drcl-deploy/cpp_control) | tracker and robot control |
| [vision_encoders](https://github.com/drcl-deploy/vision_encoders) | CUDA image encoding |
| [unitree_mujoco](https://github.com/lok-i/unitree_mujoco) | simulator and G1 model |
| [assets](https://github.com/drcl-deploy/assets) | objects and scene generation |
| [cdr_tcp_bridge](https://github.com/lok-i/cdr_tcp_bridge) | onboard/offboard telemetry |
| [sledgehammer](https://github.com/drcl-deploy/sledgehammer) | optional frozen planner and NPZ data |

Source pins: [sources.repos](sources.repos). Build checkpoints:
[docs/build_progress.md](docs/build_progress.md).
