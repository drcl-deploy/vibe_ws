#!/bin/bash
echo "Setup unitree ros2 environment with default interface"
source /opt/ros/foxy/setup.bash

# Resolve the repository from this file so it works from any checkout path.
UNITREE_ROS2_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${UNITREE_ROS2_ROOT}/cyclonedds_ws/install/setup.bash"

export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

# Models and data the packages read but do not track: checkpoints, motion
# libraries, clip tables. Same path on every box — rsync into <root>/vibe on
# the Orin and every config string stays identical.
export UNITREE_ROS2_ROOT
export VIBE_ASSET_ROOT="${UNITREE_ROS2_ROOT}/vibe"
