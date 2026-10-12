#!/usr/bin/env bash
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo 'Use: source setup.sh onboard|offboard' >&2
  exit 1
fi
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/scripts/environment.sh" "${1:-onboard}"
