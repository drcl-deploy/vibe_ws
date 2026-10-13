# vibe_ws

[![Project](https://img.shields.io/badge/Project-Page-brightgreen)](https://lok-i.github.io/vibe-control/)
[![Training](https://img.shields.io/badge/Training-vibe-blue)](https://github.com/lok-i/vibe)

Deploy **ViBe** trackers on the Unitree G1.

## requirements

- Ubuntu 22.04 + ROS 2 Humble (tested).
- NVIDIA GPU with a working driver (`nvidia-smi`).
- Git + Git LFS.

## install

From a fresh shell:

```bash
git clone https://github.com/drcl-deploy/vibe_ws
cd vibe_ws
./install.sh --system  # fetch, generate scenes, build
```

> [!NOTE]
> Samples are included in `data/sample/`. Setup downloads the matching policies,
> shared encoder and manifests from [Hugging Face](https://huggingface.co/lkrajan/vibe) into `artifacts/`.
> For your own [exports](https://github.com/lok-i/vibe/blob/main/docs/export.md), keep each `.onnx`
> beside its `.manifest.json`; absolute paths work too.

## usage

Run from `~/vibe_ws` in each terminal, with the gamepad connected.

### without planner

| Sample | Policy under `artifacts/` |
|---|---|
| `walk` · Grail curbs | `models/perloco-grail/model_14999.onnx` |
| `parkour` · OmRe climb | `models/perloco-omre/model_14999.onnx` |
| `repose` · double cube frontflip | `models/repose/model_59999.onnx` |
| `uolm` · suitcase | `models/uolm/model_24999.onnx` |

```bash
# terminal 1: simulator
sample=walk  # walk | parkour | repose | uolm
./unitree_mujoco/simulate/build/unitree_mujoco -r g1 \
  -s "$PWD/generated/$sample/scene.xml" \
  --camera_fps 50 --camera_textures 0 --camera_visual_groups 1
```

```bash
# terminal 2: encoder + tracker
source setup_local.sh
sample=walk
ros2 launch cpp_control g1_vibe_sonic.launch.py \
  policy_path:=models/perloco-grail/model_14999.onnx \
  encoder_path:=encoders/theia-tiny.onnx \
  motion_path:="$PWD/data/sample/$sample/motion.npz"
```

> [!NOTE]
> **RB** stand → **L1** prep → **A** run · **Y** damping.
>
> Match `sample` in both terminals and select its policy from the table.
> Keep the motion sidecars together. [Sample details](data/sample/README.md).

### with planner for cube-repose

```bash
# terminal 1: simulator + cube
./unitree_mujoco/simulate/build/unitree_mujoco -r g1 \
  -s "$PWD/generated/repose/g1_repose.xml" \
  --camera_fps 50 --camera_textures 0 --camera_visual_groups 1
```

```bash
# terminal 2: encoder + tracker
source setup_local.sh
ros2 launch cpp_control g1_vibe_sonic.launch.py \
  policy_path:=models/repose/model_59999.onnx \
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

> [!NOTE]
> **Gamepad:** **RB** stand/disarm · **A** arm · **Y** damping.
>
> **Console:** **0–5** or **r/o/g/y/b/p** target · **R** new trial · **q** quit.
> Select a target here before arming; it updates both nodes.
>
> SSH/tmux onboard: `source setup.sh onboard`, then launch with `env:=real`.
> Restart the tracker after restarting the planner.

## docs

- [Setup & deployment](docs/setup.md)
- [Testing](docs/testing.md)
- [Export compatibility](docs/compatibility.md)
- [Pinned dependencies](sources.repos)
