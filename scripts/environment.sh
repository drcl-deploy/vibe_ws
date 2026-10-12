#!/usr/bin/env bash
# Sourced by the root setup scripts; never starts nodes or changes the host.
_vibe_setup_environment() {
  local profile=${1:-sim}
  local root distro domain_id interface camera_address bridge_address bridge_domain_id
  root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
  case "$profile" in
    sim|onboard|offboard) ;;
    *) echo "Unknown profile '$profile': use sim, onboard, or offboard." >&2; return 1 ;;
  esac
  source "$root/profiles/$profile.env" || return 1
  if [[ -z "$interface" ]]; then
    echo 'Set VIBE_ROBOT_INTERFACE to the robot-facing network interface.' >&2
    return 1
  fi
  if [[ ! "$interface" =~ ^[a-zA-Z0-9_.:-]+$ ]]; then
    echo 'Invalid network interface name.' >&2
    return 1
  fi
  if [[ -z "$camera_address" || -z "$bridge_address" ]]; then
    echo 'Set VIBE_ROBOT_HOST to the onboard camera/bridge host.' >&2
    return 1
  fi
  distro=${ROS_DISTRO:-}
  if [[ -z "$distro" ]]; then
    if [[ -f /opt/ros/humble/setup.bash ]]; then distro=humble;
    elif [[ -f /opt/ros/foxy/setup.bash ]]; then distro=foxy; fi
  fi
  case "$distro" in
    humble|foxy) ;;
    *) echo 'This workspace supports ROS Humble or Foxy.' >&2; return 1 ;;
  esac
  if [[ ! -f "/opt/ros/$distro/setup.bash" || ! -f "$root/cyclonedds_ws/install/setup.bash" ]]; then
    echo "ROS $distro or the workspace overlay is missing; build the workspace first." >&2
    return 1
  fi
  source "/opt/ros/$distro/setup.bash" || return 1
  source "$root/cyclonedds_ws/install/setup.bash" || return 1
  export VIBE_WORKSPACE_ROOT="$root"
  export UNITREE_ROS2_ROOT="$root"  # Existing package compatibility.
  export VIBE_ASSET_ROOT="${VIBE_ARTIFACT_ROOT:-$root/artifacts}"
  export VIBE_PROFILE="$profile"
  export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
  export ROS_DOMAIN_ID="$domain_id"
  export VIBE_CAMERA_ADDRESS="$camera_address"
  export VIBE_BRIDGE_ADDRESS="$bridge_address"
  export BRIDGE_ROS_DOMAIN_ID="$bridge_domain_id"
  export CYCLONEDDS_URI="<CycloneDDS><Domain><General><Interfaces><NetworkInterface name=\"$interface\" priority=\"default\" multicast=\"default\" /></Interfaces></General></Domain></CycloneDDS>"
  unset ROS_LOCALHOST_ONLY
  echo "ViBe $profile: DDS domain $domain_id, interface $interface"
  echo "Artifacts: $VIBE_ASSET_ROOT"
  echo "Camera: $camera_address:5555; bridge: $bridge_address:5556 (offboard domain $bridge_domain_id)"
}

if _vibe_setup_environment "${1:-sim}"; then
  unset -f _vibe_setup_environment
  return 0
else
  unset -f _vibe_setup_environment
  return 1
fi
