#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$root"
if [[ "${1:-}" == --help || "${1:-}" == -h || "${1:-}" == --plan ]]; then
  exec python3 scripts/install.py "$@"
fi
if [[ "${1:-}" == --system ]]; then
  shift
  distro="${ROS_DISTRO:-humble}"
  [[ "$distro" == humble || "$distro" == foxy ]] || { echo 'Use ROS Humble or Foxy.' >&2; exit 2; }
  sudo apt-get update
  sudo apt-get install -y build-essential cmake git git-lfs curl pkg-config \
    python3-venv python3-pip python3-colcon-common-extensions \
    python3-numpy python3-yaml python3-opencv \
    libyaml-cpp-dev libopencv-dev libboost-program-options-dev libglfw3-dev \
    libgl1-mesa-dev libfmt-dev libeigen3-dev zlib1g-dev \
    "ros-$distro-rmw-cyclonedds-cpp" "ros-$distro-rosidl-generator-dds-idl" \
    "ros-$distro-ros2launch" "ros-$distro-ament-cmake-gtest" \
    "ros-$distro-ament-lint-auto" "ros-$distro-ament-lint-common"
fi
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --disable-pip-version-check \
  'PyYAML==6.0.2' 'vcstool==0.3.0'
exec .venv/bin/python scripts/install.py "$@"
