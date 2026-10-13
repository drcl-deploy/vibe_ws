# setup

Ubuntu 22.04 / ROS Humble is the tested target. Install ROS and the NVIDIA driver,
then run `./install.sh --system` from a fresh shell. Without `--system`, setup
assumes the system packages are already installed.

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

The full command runs these in order. Sources are pinned commits. Existing dirty
or mismatched repositories stop setup without resetting local work. Verified
dependencies are reused; MuJoCo 3.3.6 and the Unitree SDK live in `.deps/`.

## samples and scenes

The Git checkout includes `data/sample/{walk,parkour,repose,uolm}`: one reference
per policy, terrain or object geometry, and required sidecars. See the
[sample notes](../data/sample/README.md). No training checkout or `assets` package
is needed.

```bash
python3 scripts/scenes.py  # regenerate all scenes; prints scene + motion paths
realpath generated/walk/scene.xml
```

Generated XML lives in `$XDG_DATA_HOME/vibe/scenes/<checkout>/`, defaulting to
`~/.local/share/vibe/scenes/`. `generated/` is an ignored symlink. Each checkout
gets its own output so mesh paths cannot leak between clones. Regenerate after
moving the workspace; save hand-edited scenes under different filenames.

`generated/<sample>/scene.xml` starts each task at its reference placement.
`generated/repose/g1_repose.xml` retains the tested planner's separate start.
The G1 still comes from `unitree_mujoco/unitree_robots/g1/g1_29dof_with_camera.xml`.
Setup preserves the native 2 ms dynamics and 42.5 degree camera.

## policy and encoder exports

Place unchanged ONNX exports and their matching `.manifest.json` files under
`artifacts/`. The README lists paths for the four samples. All use the shared
112×63 Theia-tiny encoder. Policies and encoders are excluded from Git.

`setup_local.sh` sets `VIBE_ASSET_ROOT` to `artifacts/`. Set `VIBE_ARTIFACT_ROOT`
before sourcing to use another model directory. Relative launch paths resolve
there; use absolute paths for `data/sample/.../motion.npz`.

```bash
python3 scripts/doctor.py  # all sample exports + installed build + sample hashes
python3 scripts/doctor.py --policy /path/to/policy.onnx --encoder /path/to/encoder.onnx
```

ONNX publication on Hugging Face is a separate release step; installation does
not download models yet. `artifacts.lock.json` records the tested local exports.
The existing setup downloader accepts a future lock with immutable HF revisions:
`python3 scripts/artifacts.py --lock /path/to/published-lock.json`.

## onboard and offboard

```bash
./install.sh --profile onboard  # tracker, encoder, planner and bridge
./install.sh --profile offboard # telemetry bridge only
```

Onboard: set `VIBE_ROBOT_INTERFACE`, source `setup.sh onboard`, then use the direct
ROS launch with `env:=real` for the planner. Offboard: set `VIBE_ROBOT_HOST` and
source `setup.sh offboard`.

Simulation uses DDS domain 1 on loopback, onboard domain 0 on the selected
interface, and offboard telemetry domain 71. Foxy interfaces remain supported;
Jetson/Foxy hardware validation is separate from the Humble simulation checks.
