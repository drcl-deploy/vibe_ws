#!/bin/bash
echo "Setup unitree ros2 environment"
if [[ -n "${ROS_DISTRO:-}" && -f "/opt/ros/${ROS_DISTRO}/setup.bash" ]]; then
  source "/opt/ros/${ROS_DISTRO}/setup.bash"
elif [[ -f /opt/ros/humble/setup.bash ]]; then
  source /opt/ros/humble/setup.bash
else
  source /opt/ros/foxy/setup.bash
fi

# Resolve the repository from this file so it works from any checkout path.
UNITREE_ROS2_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${UNITREE_ROS2_ROOT}/cyclonedds_ws/install/setup.bash"

export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

# Models and data the packages read but do not track: checkpoints, motion
# libraries, clip tables. Same path on every box — rsync into <root>/vibe on
# the Orin and every config string stays identical.
export UNITREE_ROS2_ROOT
export VIBE_ASSET_ROOT="${UNITREE_ROS2_ROOT}/vibe"
export ROS_DOMAIN_ID=0
unset ROS_LOCALHOST_ONLY
export VIBE_BRIDGE_ADDRESS=gilfoyle-rth
export VIBE_CAMERA_ADDRESS=127.0.0.1
export BRIDGE_ROS_DOMAIN_ID=71
export CYCLONEDDS_URI='<CycloneDDS><Domain><General><Interfaces>
                            <NetworkInterface name="lo" priority="default" multicast="default" />
                        </Interfaces></General></Domain></CycloneDDS>'
