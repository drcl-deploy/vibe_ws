# setup

The tested target is Ubuntu 22.04 / ROS Humble with an NVIDIA GPU. Install ROS
and the NVIDIA driver first. `./install.sh --system` installs the remaining apt
dependencies and builds this workspace. Without `--system`, it assumes those
system packages already exist. Run from a fresh shell without another ROS overlay.

## stages

```bash
./install.sh --plan
./install.sh --stage sources
./install.sh --stage deps
./install.sh --stage scene
./install.sh --stage sim
./install.sh --stage ros
./install.sh --stage doctor
./install.sh --from-stage scene --jobs 2
```

The full command runs these in order. Sources are pinned commits; an existing
dirty or mismatched checkout stops setup without resetting local work. Dependency
scripts reuse verified downloads. Generated scenes contain local absolute paths:
rerun `--stage scene` after moving the workspace. XML files live in
`$XDG_DATA_HOME/vibe/scenes/<checkout>/` (default `~/.local/share/vibe/scenes/`).
Each checkout gets its own directory, avoiding stale mesh paths between clones.
`generated/` is an ignored symlink, so the direct launch commands stay the same.
Setup prints the resolved paths; inspect them with `realpath generated/repose/g1_repose.xml`.
Regeneration replaces generated XML; keep experimental edits under a different filename.
The first migration preserves the existing directory's other files. Launch shortcuts:

```text
generated/g1/g1.xml                 G1 camera + floor
generated/repose/g1_repose.xml      G1 camera + colored cube
```

MuJoCo 3.3.6 and the exact tested Unitree SDK live under `.deps/`. ONNX Runtime
is installed under the encoder package's ignored dependency directory. CUDA
user-space libraries may come from the host or the encoder setup's pinned wheels;
the host NVIDIA driver remains a prerequisite. Scene generation uses `.venv/`.

## artifacts

Keep policy and encoder exports unchanged, each beside its `.manifest.json`.
The ROS launch takes `policy_path:=...` and `encoder_path:=...` directly. Relative
paths resolve under `VIBE_ASSET_ROOT`; absolute paths can point at the training
repo's exports without copying or registering them.

```text
artifacts/                          ignored local exports
  models/repose-v9.3/                frozen policy ONNX + manifest
  encoders/                         encoder ONNX + manifest
cyclonedds_ws/src/sledgehammer/data/  versioned planner NPZ payload
```

`setup_local.sh` sets `VIBE_ASSET_ROOT` to the workspace's `artifacts/`. Set
`VIBE_ARTIFACT_ROOT` before sourcing to select another storage root. Preserve
motion contact/object sidecars beside any `motion.npz` you pass to the tracker.

`artifacts.lock.json` records the historical V9.3 model hashes. A fresh export
can use the same launch directly, but is not automatically that frozen baseline.
Check an explicit pair without starting nodes:

```bash
python3 scripts/doctor.py --policy /path/to/policy.onnx --encoder /path/to/encoder.onnx
```

Hugging Face publication is pending. The setup-only downloader accepts a lock
with immutable HF revisions and SHA-256 hashes:

```bash
python3 scripts/artifacts.py --lock /path/to/published-lock.json
```

No published ONNX download lock exists yet. Installation does not upload files.

## profiles

```bash
./install.sh --profile onboard     # no simulator/scene build
./install.sh --profile offboard    # telemetry bridge build only
```

For onboard operation, set `VIBE_ROBOT_INTERFACE` to the robot-facing interface
and source `setup.sh onboard`; then use the same `ros2 launch cpp_control`
command shown in the README. For the planner, select `env:=real`. Offboard setup uses `VIBE_ROBOT_HOST` and `source setup.sh offboard`.
See the bridge package documentation for telemetry-client launch options.

Simulation uses domain 1 on loopback, onboard uses domain 0 on the explicit robot
interface, and offboard telemetry uses domain 71. The documented simulator command selects loopback. Foxy-compatible interfaces are preserved, but only the Humble
simulation build has been exercised here; Jetson/Foxy hardware gates remain open.
