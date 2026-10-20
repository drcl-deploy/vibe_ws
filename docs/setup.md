# setup

Ubuntu 22.04 / ROS Humble is the tested target; setup also accepts Ubuntu 24.04 /
ROS Jazzy. Install ROS and the NVIDIA driver (JetPack on Jetson),
then run `./install.sh --system` from a fresh shell. Without `--system`, setup
assumes the system packages are already installed.

The installer honors `ROS_DISTRO`. In a fresh shell it selects the only installed
Foxy/Humble/Jazzy distribution; if several are installed, set `ROS_DISTRO`
explicitly. `--system` works in any argument position and `--plan` never installs
packages. ROS and viewer tools use `/usr/bin/python3`; `.venv` is for setup tools.
Later runs remember the selected profile, job limit, ROS distribution and any
custom ONNX Runtime archive. Explicit arguments and `ROS_DISTRO` override them.
Use `--ort-archive auto` to return from a saved custom SDK to automatic selection.

## retry and update

```bash
./install.sh                 # retry or verify the current release

# update an existing checkout
git pull --ff-only
./install.sh
```

Healthy dependencies and verified artifacts are reused. Interrupted compilation
keeps completed objects; incomplete installer-owned SDKs and the setup venv are
preserved aside and rebuilt. Downloads and new source checkouts are prepared
before publishing them to their final paths. A failed model update leaves the
previous model intact.

The source stage advances clean managed repositories to `sources.repos` pins.
A clean checkout from an older installer can be adopted when the update is a
fast-forward from the expected remote, or its exact pin appears in the
workspace's committed lock history. Local edits, independent commits and
custom exports stop setup with their paths; they are never reset or overwritten.
Model updates replace only files matching a recorded or previously locked checksum.
An existing unknown incomplete directory is left for the operator to inspect.

Build inputs include source pins, SDK identity, ROS/Python/architecture and
profile. When these change, setup moves the affected generated build/install
outputs aside, preventing obsolete installed files from surviving an upgrade.
The same inputs reuse the current build, including a partially completed one.
The first run of this installer adopts existing sources/artifacts and rebuilds
unrecorded generated outputs once.

Receipts, failure details and logs live under `.cache/vibe-install/`; preserved
outputs are in its `previous/` directory. Artifact ownership is recorded in
`artifacts/.vibe-artifacts.json`, or beside the chosen custom artifact root.
Retain these receipts for future upgrades. Each failure prints the stage, log
path and retry command. Only one installer can run in a checkout at a time.

Use `--system` again if a release needs additional OS packages. Setup checks
system requirements and doctor verifies the completed installation. Updating
the workspace itself remains the explicit `git pull` above.

If APT stops with `EXPKEYSIG`, repair the host's ROS repository signing keys using
the [ROS migration guide](https://discourse.ros.org/t/ros-signing-key-migration-guide/43937).
Running without `--system` skips APT and reports any missing system packages;
it still requires `python3-venv` for the setup environment.

## stages

```bash
./install.sh --plan
./install.sh --stage sources
./install.sh --stage deps
./install.sh --stage artifacts
./install.sh --stage scene
./install.sh --stage sim
./install.sh --stage ros
./install.sh --stage doctor
./install.sh --from-stage scene --jobs 2
```

The full command runs these in order. Stage selectors are optional tools for
development and diagnosis; ordinary retries use the full command. MuJoCo 3.3.6
and the Unitree SDK live in `.deps/`.

Shell setup still rejects incompatible installed overlays. Run the installer to
prepare the selected profile, then source its setup script in a fresh terminal.

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

Simulation and onboard setup download the four sample policy pairs and shared
112×63 Theia-tiny encoder pair from [lkrajan/vibe](https://huggingface.co/lkrajan/vibe)
into ignored `artifacts/`. `artifacts.lock.json` pins the HF commit, remote paths,
SHA-256 hashes and sizes. Matching local files are reused; different local exports
are left untouched and stop the download. Offboard setup skips model downloads.

Policies live at `artifacts/models/<sample>/policy.onnx`, with a matching
`policy.manifest.json`. Sample names match `data/sample/`: `walk`, `parkour`,
`repose`, `uolm`. The shared encoder stays at `artifacts/encoders/theia-tiny.onnx`.

For custom [exports](https://github.com/lok-i/vibe/blob/main/docs/export.md),
pass absolute `policy_path` and `encoder_path` values to the tracker launch.
Each ONNX file loads its matching `.manifest.json` beside it by default.
Use `policy_manifest` / `encoder_manifest` for manifests stored elsewhere.

`setup_local.sh` sets `VIBE_ASSET_ROOT` to `artifacts/`. Set `VIBE_ARTIFACT_ROOT`
before sourcing to use another model directory. Relative launch paths resolve
there; use absolute paths for `data/sample/.../motion.npz`.

```bash
python3 scripts/doctor.py  # all sample exports + installed build + sample hashes
python3 scripts/doctor.py --policy /path/to/policy.onnx --encoder /path/to/encoder.onnx
```

To fetch or verify only the sample exports:

```bash
python3 scripts/artifacts.py --lock artifacts.lock.json
```

The lock currently references the published deployment review commit. The original
HF `v0.1.0` tag remains the checkpoint-only release.

## optional telemetry

The tracker launch starts the bridge server by default. A server exit or an
offboard client disconnect leaves the encoder and tracker running. Ctrl-C on
the tracker launch still closes all its children.

To run the server in its own terminal, add `enable_bridge:=false` to the tracker
launch, then run:

```bash
source setup_local.sh  # setup.sh onboard on the robot
ros2 run cdr_tcp_bridge bridge_server.sh
```

The README's `stream_vibes.sh` command starts the offboard client and viewer.

## onboard and offboard

```bash
./install.sh --system --profile onboard --jobs 2  # tracker, encoder, planner and bridge
./install.sh --system --profile offboard          # bridge, messages and viewer tools; no CUDA
```

Onboard: set `VIBE_ROBOT_INTERFACE`, source `setup.sh onboard`, then use the direct
ROS launch with `env:=real` for the planner. Offboard: set `VIBE_ROBOT_HOST` and
source `setup.sh offboard`.

For three onboard terminals with the environment already sourced, install
`tmuxp` and run from the workspace root:

```bash
tmuxp load deploy.yaml
```

The session defaults to `eth0`; export `VIBE_ROBOT_INTERFACE` first to select
another interface. Each pane runs `source setup.sh onboard`.

Offboard builds cpp_control, vision_encoders and sledgehammer interfaces/tools
with their runtime targets disabled. It includes Repose telemetry and calibration
message support without compiling a controller, encoder or planner executable.

Onboard setup excludes simulator graphics and desktop viewer dependencies.
CLI bag recording is included in every profile. Python bag replay is checked
only for sim/offboard on Humble/Jazzy: standard Foxy has no `rosbag2_py` package,
so its offboard profile supports live viewing and CLI recording without Python
bag replay.

Simulation uses DDS domain 1 on loopback, onboard domain 0 on the selected
interface, and offboard telemetry domain 71. Foxy retains onboard/offboard support
and its older CycloneDDS interface syntax; simulation setup requires Humble/Jazzy
and Python 3.10+. Foxy and Jetson hardware acceptance are separate from the Humble
simulation checks.

## ARM and ONNX Runtime

The x86 installer downloads the pinned ONNX Runtime GPU SDK and supplies missing
CUDA runtime libraries locally. ARM setup uses JetPack's CUDA/cuDNN and builds a
pinned native SDK with a local CMake 3.28.4 toolchain. `--jobs` limits compilation;
use `--jobs 1` on a memory-constrained robot. Orin/Xavier GPU architectures are
detected from the device tree; another supported device needs
`VISION_ENCODERS_CUDA_ARCHITECTURES` set explicitly.

| Host libraries | ARM ONNX Runtime |
|---|---|
| CUDA 11 + cuDNN 8 | 1.15.1 |
| CUDA 12 + cuDNN 8 | 1.18.0 |
| CUDA 12 + cuDNN 9 | 1.22.0 |

Install JetPack development libraries before source builds. Set `CUDA_HOME` or
`CUDNN_HOME` if they are outside `/usr/local/cuda` and `/usr`. Other library pairs
fail early; setup does not replace JetPack's libraries. ORT 1.22 also requires
GCC 11.1 or newer. A validated local GPU SDK can avoid the source build:

```bash
./install.sh --system --profile onboard \
  --ort-archive /path/to/onnxruntime-sdk.tgz --ort-sha256 <sha256>
```

Installation finishes by checking viewer imports, bridge message libraries and
(for sim/onboard) CUDA-provider loading, without starting control nodes. Native
Jetson build/inference and onboard/offboard communication still need target-host
acceptance; architecture-selection tests do not establish that acceptance.
