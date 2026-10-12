#!/usr/bin/env bash
set -eo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$root/scripts/environment.sh" "${VIBE_PROFILE:-sim}"
exec python3 "$root/scripts/run.py" "$@"
