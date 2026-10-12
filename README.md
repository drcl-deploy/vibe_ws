# vibe_ws

[![Project](https://img.shields.io/badge/Project-Page-brightgreen)](https://lok-i.github.io/vibe-control/)
[![Training](https://img.shields.io/badge/Training-vibe-blue)](https://github.com/lok-i/vibe)

ROS 2 deployment for **ViBe**: vision-conditioned whole-body trackers on the Unitree G1.
Training and ONNX export live in [vibe](https://github.com/lok-i/vibe).

## install

Tested on Ubuntu 22.04 / ROS Humble with NVIDIA CUDA. Source import requires Git,
Git LFS, Python with PyYAML, and vcstool.

```bash
git clone https://github.com/drcl-deploy/vibe_ws && cd vibe_ws
python3 scripts/sources.py import    # pinned module repositories
python3 scripts/sources.py check
```

build steps and host dependencies: [docs/migration.md](docs/migration.md#rebuild-this-host-checkpoint).

The installer and downloadable deployment bundles are still being packaged.
The example below requires the built workspace and local V9.3 artifacts;
cloning alone does not fetch the models or planner data.

## usage

### Repose · V9.3

Run from the workspace root in each terminal, with an Xbox-compatible gamepad connected.

```bash
# generate the G1 + cube scene once; prints the simulator's XML path
PYTHONPATH=assets/src python3 -m assets.repose_scene \
  --robot-xml unitree_mujoco/unitree_robots/g1/g1_29dof_with_camera.xml \
  --out-dir generated/repose
```

```bash
# terminal 1 — simulator
unitree_mujoco/simulate/build/unitree_mujoco -r g1 -i 1 -n lo \
  -s "$PWD/generated/repose/g1_repose.xml" --use_joystick 1 \
  --camera_width 112 --camera_height 63 --camera_fps 50 \
  --camera_depth_width 112 --camera_depth_height 63 \
  --camera_textures 0 --camera_visual_groups 1
```

```bash
# terminal 2 — encoder, tracker and planner
source setup_local.sh
ros2 launch cpp_control g1_repose_planner.launch.py \
  artifact_dir:="$PWD/artifacts/models/repose-v9.3" \
  planner_config:="$PWD/cyclonedds_ws/src/cpp_control/config/repose_planner/g1_sim_v9_3.yaml" \
  env:=sim camera_ip:=127.0.0.1 enable_bridge:=true goal_color:=4
```

| control | action |
|---|---|
| **RB** | enter stand; disarm an active rollout |
| **A** | arm the planner from stand |
| `goal_color` | `0` red · `1` orange · `2` green · `3` yellow · `4` blue · `5` pink |

The current launch starts the planner inside `cpp_control`. Its move to
[sledgehammer](https://github.com/drcl-deploy/sledgehammer) is pending;
the tracker stays in `cpp_control`.

### artifacts

```text
artifacts/
  models/repose-v9.3/     policy ONNX + manifest
  encoders/              encoder ONNX + manifest
  data/                  current V9.3 planner tables and motion frames
generated/repose/        generated G1 + cube XML
```

`setup_local.sh` selects loopback / DDS domain 1 and prints the resolved paths.
`VIBE_ASSET_ROOT` defaults to `artifacts/`; set `VIBE_ARTIFACT_ROOT` before sourcing
to use another directory. Keep each ONNX file and its matching manifest together.

export compatibility: [docs/compatibility.md](docs/compatibility.md).

### test

automated checks and joystick regression: [docs/migration.md](docs/migration.md#automated-regression).
camera, cube and encoder parity results: [docs/parity.md](docs/parity.md).
The live joystick regression is still pending.

## modules

| repo | owns |
|---|---|
| [cpp_control](https://github.com/drcl-deploy/cpp_control) | tracker and robot control |
| [vision_encoders](https://github.com/drcl-deploy/vision_encoders) | CUDA image encoding |
| [unitree_mujoco](https://github.com/lok-i/unitree_mujoco) | simulator and G1 model |
| [assets](https://github.com/drcl-deploy/assets) | objects and scene generation |
| [cdr_tcp_bridge](https://github.com/lok-i/cdr_tcp_bridge) | onboard/offboard telemetry |
| [sledgehammer](https://github.com/drcl-deploy/sledgehammer) | optional frozen cube planner; extraction pending |

source pins: [sources.repos](sources.repos). Release progress: [docs/migration.md](docs/migration.md#remaining-phases).
