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
rerun `--stage scene` after moving the workspace. Paths printed during setup:

```text
generated/g1/g1.xml                 G1 camera + floor
generated/repose/g1_repose.xml      G1 camera + colored cube
```

MuJoCo 3.3.6 and the exact tested Unitree SDK live under `.deps/`. ONNX Runtime
is installed under the encoder package's ignored dependency directory. CUDA
user-space libraries may come from the host or the encoder setup's pinned wheels;
the host NVIDIA driver remains a prerequisite. Scene generation uses `.venv/`.

## artifacts

```text
artifacts/                         ignored, local deployment inputs
  models/<hash>/                   policy ONNX + manifest
  encoders/<hash>/                 encoder ONNX + manifest
  experiments/<name>.yaml          selection of those two exports
cyclonedds_ws/src/sledgehammer/data/  versioned planner NPZ payload
```

`artifacts/` is a storage location, not a modified export format. Import checks
policy/encoder token shapes and copies both pairs unchanged. A same-name import
with identical inputs is repeatable; different inputs need a new name.

```bash
python3 scripts/artifacts.py import --name my-run --task-family perloco \
  --policy /path/to/policy.onnx --encoder /path/to/encoder.onnx
./run.sh tracker my-run --motion /path/to/motion.npz
```

Keep the motion's contact/object sidecars alongside it. Set `VIBE_ARTIFACT_ROOT`
to select another storage root. `VIBE_ASSET_ROOT` is the compatibility alias set
by the environment scripts. Explicit YAML paths resolve name ambiguity.

The tracked `experiments/repose-v9.3.yaml` selects the exact historical regression
exports; `artifacts.lock.json` records their hashes. A fresh export can be used
under another experiment name, but is not automatically that frozen baseline.

If pre-exported models are published on Hugging Face, the intended release unit
is the policy, matching encoder and both manifests. `scripts/artifacts.py fetch
--lock <file>` accepts only immutable HF commit IDs and SHA-256 checksums. No
published ONNX download lock exists yet, and installation does not upload files.

## profiles

```bash
./install.sh --profile onboard     # no simulator/scene build
./install.sh --profile offboard    # telemetry bridge build only
```

For onboard operation, set `VIBE_ROBOT_INTERFACE` to the robot-facing interface
and source `setup.sh`; `VIBE_PROFILE=onboard ./run.sh tracker <experiment>` uses
that profile. Offboard setup uses `VIBE_ROBOT_HOST` and `source setup.sh offboard`.
See the bridge package documentation for telemetry-client launch options.

Simulation uses domain 1 on loopback, onboard uses domain 0 on the explicit robot
interface, and offboard telemetry uses domain 71. The simulator wrappers always
select loopback. Foxy-compatible interfaces are preserved, but only the Humble
simulation build has been exercised here; Jetson/Foxy hardware gates remain open.
