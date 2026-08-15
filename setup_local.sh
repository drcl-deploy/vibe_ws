#!/bin/bash
echo "Setup unitree ros2 simulation environment"
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
UNITREE_SIM_CONFIG="${UNITREE_ROS2_ROOT}/unitree_mujoco/simulate/config.yaml"
VIBE_SIM_DOMAIN_ID=1
if [[ -f "${UNITREE_SIM_CONFIG}" ]]; then
  VIBE_CONFIG_DOMAIN_ID="$(awk '$1 == "domain_id:" {print $2; exit}' "${UNITREE_SIM_CONFIG}")"
  if [[ "${VIBE_CONFIG_DOMAIN_ID}" =~ ^[0-9]+$ ]]; then
    VIBE_SIM_DOMAIN_ID="${VIBE_CONFIG_DOMAIN_ID}"
  fi
fi
export ROS_DOMAIN_ID="${VIBE_SIM_DOMAIN_ID}"
unset VIBE_CONFIG_DOMAIN_ID VIBE_SIM_DOMAIN_ID
unset ROS_LOCALHOST_ONLY
export VIBE_BRIDGE_ADDRESS=127.0.0.1
export VIBE_CAMERA_ADDRESS=127.0.0.1
export BRIDGE_ROS_DOMAIN_ID=71
export CYCLONEDDS_URI='<CycloneDDS><Domain><General><Interfaces>
                            <NetworkInterface name="lo" priority="default" multicast="default" />
                        </Interfaces></General></Domain></CycloneDDS>'
echo "Simulation DDS: domain ${ROS_DOMAIN_ID}, interface lo"
