#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$root"
# ROS binary packages use the OS Python ABI, regardless of an active venv/Conda.
exec /usr/bin/python3 scripts/install.py "$@"
