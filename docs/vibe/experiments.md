# Vibe experiment commands

The Vibe task launches own both `encoder_node` and `g1_vibe_sonic_node`. Do not
start a second encoder or controller for the same experiment. The camera and
telemetry bridge remain separate processes.

## Real robot

Run the camera streamer onboard first:

```bash
cd ~/unitree_ros2
python3 cyclonedds_ws/src/vision_encoders/scripts/camera_streamer.py
```

In a sourced onboard terminal, start exactly one task. The launch starts the
Theia Tiny encoder and then its controller:

```bash
cd ~/unitree_ros2
source setup.sh

# UOLM
ros2 launch cpp_control g1_vibe_uolm.launch.py \
  artifact_dir:=/home/loki/drcl_projects/vibe/logs/rsl_rl/vibe_uolm/wandb_checkpoints/xhej6sbd

# PerLoco Grail
ros2 launch cpp_control g1_vibe_perloco_grail.launch.py \
  artifact_dir:=/home/loki/drcl_projects/vibe/logs/rsl_rl/vibe_perloco_grail/wandb_checkpoints/0uetimde

# PerLoco OmRe
ros2 launch cpp_control g1_vibe_perloco_omre.launch.py \
  artifact_dir:=/home/loki/drcl_projects/vibe/logs/rsl_rl/vibe_perloco_omre/wandb_checkpoints/bc7sz47j

# Dodge
ros2 launch cpp_control g1_vibe_dodge.launch.py \
  artifact_dir:=/home/loki/drcl_projects/vibe/logs/rsl_rl/vibe_dodge/wandb_checkpoints/wm8wjywv
```

For UOLM or PerLoco, stage the motion after the task is running:

```bash
publish-motion /path/to/motion.npz
```

Start the telemetry server in another sourced onboard terminal:

```bash
cd ~/unitree_ros2
source setup.sh
ros2 run cdr_tcp_bridge bridge_server.sh
```

On the offboard computer, open a completely fresh terminal at the repository
root. No manual ROS or workspace sourcing is needed:

```bash
cd ~/unitree_ros2

# Live encoder-frame + attention viewer
bash cyclonedds_ws/src/cpp_control/scripts/vibe/stream_vibes.sh

# The same viewer plus a timestamped bag
bash cyclonedds_ws/src/cpp_control/scripts/vibe/stream_vibes.sh record
```

Bags are written under `~/unitree_ros2/bags/` with names such as
`15Aug2026_16_34`. The real bridge client resolves `gilfoyle-rth`, currently
`192.168.0.177`.

## Simulation

Start the configured G1 simulator, which supplies the camera TCP stream:

```bash
cd ~/unitree_ros2/unitree_mujoco/simulate/build
./unitree_mujoco
```

Start one Vibe task in another terminal using the same task commands above:

```bash
cd ~/unitree_ros2
source setup_local.sh
export ROS_DOMAIN_ID=1
ros2 launch cpp_control g1_vibe_uolm.launch.py \
  artifact_dir:=/home/loki/drcl_projects/vibe/logs/rsl_rl/vibe_uolm/wandb_checkpoints/xhej6sbd
```

Start the simulation-side bridge server:

```bash
cd ~/unitree_ros2
source setup_local.sh
export ROS_DOMAIN_ID=1
ros2 run cdr_tcp_bridge bridge_server.sh -p bind_address:=127.0.0.1
```

Finally, stream or stream-and-record from a fresh terminal:

```bash
cd ~/unitree_ros2
bash cyclonedds_ws/src/cpp_control/scripts/vibe/stream_vibes.sh --deployed_in sim
bash cyclonedds_ws/src/cpp_control/scripts/vibe/stream_vibes.sh record --deployed_in sim
```

## Controls and shutdown

- UOLM and PerLoco: `RB` stand, `L1` prep, `A` run.
- Dodge: `A` or `RB` engages its nominal reactive reference.
- If the controller prints `STALE VISION TOKENS`, press `Y` for damping if the
  experiment requires it.
- Stop the task launch before starting a different experiment. `Ctrl-C` stops
  both the controller and its encoder.
- Stop `stream_vibes.sh` with `Ctrl-C` or close its viewer; recording is closed
  with the bridge and viewer.
