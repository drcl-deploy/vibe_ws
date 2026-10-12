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

Fetches pinned modules, installs runtime dependencies, generates the scenes, and
builds the simulator and ROS packages. The generated XML paths are printed.
ROS itself must already be installed. Resume stages and onboard setup:
[docs/setup.md](docs/setup.md).

### exports

Export a policy and its matching encoder using
[vibe's exporter](https://github.com/lok-i/vibe/blob/main/docs/export.md), then import them:

```bash
python3 scripts/artifacts.py import --name repose --task-family repose \
  --policy /path/to/model.onnx --encoder /path/to/theia-tiny.onnx
```

Keep each ONNX beside its exporter-generated `.manifest.json`. Import preserves
their bytes in ignored `artifacts/`; no models are stored in this Git repository.
Pre-exported Hugging Face downloads are pending publication. Local exports work now.

## usage

Run from the workspace root in each terminal, with an Xbox-compatible gamepad.

```bash
# terminal 1 — simulator
./run.sh sim repose

# terminal 2 — encoder + tracker
./run.sh tracker repose --motion /path/to/motion.npz
```

The same tracker flow supports Repose, UoLM and PerLoco (OmRe/Grail); select the
corresponding exports with `--task-family repose|uolm|perloco`. Preserve any
motion companion files beside `motion.npz`. Dodge remains loadable, with no
dedicated task scene in this release.

### sledgehammer · V9.3

The optional frozen cube planner supplies the motion. Use three terminals:

```bash
./run.sh sim repose                       # terminal 1
./run.sh tracker repose --with-planner    # terminal 2; waits for terminal 3
./run.sh planner repose                   # terminal 3
```

| control | action |
|---|---|
| **RB** | enter stand; disarm an active rollout |
| **A** | arm the planner from stand |
| `--goal-color` | `0` red · `1` orange · `2` green · `3` yellow · `4` blue · `5` pink |

Use the same experiment and goal color in the tracker and planner terminals.
Planner loss stops the supervised tracker launch; restart it explicitly.
For this machine's frozen reference exports, use `repose-v9.3` as the experiment.

### test

```bash
python3 scripts/doctor.py --experiment repose
bash scripts/regression.sh                 # requires the frozen V9.3 model files
```

Automated checks, current results and the final joystick gate:
[docs/testing.md](docs/testing.md). Camera/cube alignment:
[docs/parity.md](docs/parity.md). Export contracts:
[docs/compatibility.md](docs/compatibility.md).

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
