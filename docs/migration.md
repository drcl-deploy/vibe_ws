# Release migration checkpoint

Phase 1 has passed its automated relocation gates on Ubuntu 22.04 / ROS Humble.
The operator joystick regression is deferred to the end at the user's request.
No live rollout, hardware test, or full release acceptance is claimed.

The original `~/unitree_ros2` source checkout is preserved. All new source,
builds, artifacts, generated scenes and logs live under `~/vibe_ws`.
The root inherits tested workspace commit
`8d0066efecac04706598305fe4010a68c1234631`; independent module revisions are in
`sources.repos`. All five pins are advertised by their public remotes.
The camera hotfix is published on `lok-i/unitree_mujoco:fix/vibe-camera-fov`
at `5d35e648f2348cbfed4accd541873db620392224`; it is not merged into main.

## Scope and dependencies

- `artifacts.lock.json` records the byte-identical V9.3 migration payload:
  policy, encoder, clip/library tables, walking motion and 56 retargeted files.
  These are local copies, not links into the training or original workspace.
- `artifacts/` is compatible with public Vibe's exporter conventions. See
  [the compatibility audit](compatibility.md) for contract checks and the separate
  camera, renderer and cube-physics alignment work required for public parity.
- The encoder temporarily retains an ignored `models/` copy for its legacy tag
  lookup. Both installed files match the canonical files in `artifacts/encoders`.
  Phase 2 removes that duplicate discovery path.
- Both Unitree message packages and custom ROS packages were built here. The
  build does not source the old workspace or its installed message packages.
- Shared host dependencies remain: ROS Humble, system development libraries,
  Unitree SDK2 at `/opt/unitree_robotics`, MuJoCo 3.3.6 under `~/.mujoco`, and
  NVIDIA user-space libraries. ONNX Runtime GPU 1.22.0 has been copied into this
  workspace. This is not yet a clean-machine installer.
- Unitree SDK2 reports version 2.0.0 but its source commit is not established.
  Local binary hashes and runtime versions are recorded in
  `.migration/phase1/runtime_inventory.json`; establish a reproducible SDK source
  pin in Phase 3. Do not confuse SDK DDS libraries with ROS's CycloneDDS overlay.
- Source import requires Git/LFS, Python with PyYAML and vcstool. Object generation
  currently uses host NumPy/trimesh/Pillow/platformdirs; the host SciPy/NumPy pair
  emits a compatibility warning. A tested isolated generation environment is
  still required for the installer.

## Rebuild this host checkpoint

Use a fresh shell with no other ROS workspace sourced. These commands assume
the host dependencies above are already present; they are not an installer.

```bash
cd ~/vibe_ws
python3 scripts/sources.py check
source /opt/ros/humble/setup.bash
export CMAKE_BUILD_PARALLEL_LEVEL=2
cd cyclonedds_ws
colcon build --symlink-install --executor sequential \
  --packages-select unitree_go unitree_hg unitree_api \
  --cmake-args -DCMAKE_BUILD_TYPE=Release
source install/setup.bash
colcon build --symlink-install --executor sequential \
  --packages-select cdr_tcp_bridge vision_encoders cpp_control \
  --cmake-args -DCMAKE_BUILD_TYPE=Release \
  -DONNXRUNTIME_ROOT="$PWD/src/vision_encoders/thirdparty/onnxruntime" \
  -DONNXRUNTIME_ROOT_DIR="$PWD/src/vision_encoders/thirdparty/onnxruntime"
cd ..
cmake -S unitree_mujoco/simulate -B unitree_mujoco/simulate/build \
  -DMUJOCO_ROOT="$HOME/.mujoco/mujoco-3.3.6" \
  -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON
cmake --build unitree_mujoco/simulate/build -j2
```

Generate the scene locally. The generator prints its output, and the last line
prints the absolute path used by the simulator command below.

```bash
PYTHONPATH=assets/src python3 -m assets.cli generate --object cube \
  --no-decompose --output-root generated/assets
PYTHONPATH=assets/src python3 -m assets.omni_objects.generate_uolm_scene_xmls \
  --robot-xml unitree_mujoco/unitree_robots/g1/g1_29dof_with_camera.xml \
  --object cube --model hull --generated-root generated/assets \
  --out-dir generated/scenes
realpath generated/scenes/g1_29dof_with_camera_cube.xml
```

Generated XML contains absolute paths into this workspace. Regenerate after
moving it. No generated scene, model binary or build tree belongs in root Git.

## Automated regression

```bash
cd ~/vibe_ws
source setup_local.sh
python3 -m unittest discover -s tests -v
ctest --test-dir unitree_mujoco/simulate/build --output-on-failure
cyclonedds_ws/build/cpp_control/deploy_selftest \
  artifacts/models/repose-v9.3/model_59999.onnx
cyclonedds_ws/build/cpp_control/repose_planner_selftest \
  --config cyclonedds_ws/src/cpp_control/config/repose_planner/g1_sim_v9_3.yaml \
  --table artifacts/data/sys1_clips.npz \
  --library artifacts/data/sys1_library.npz \
  --frames artifacts/data/retargeted_motions \
  --approach artifacts/data/sys1_walk/walk_forward_amateur_001__A001/motion.npz
ros2 run vision_encoders cuda_provider_check
cd cyclonedds_ws
colcon test --packages-select cdr_tcp_bridge vision_encoders cpp_control
colcon test-result --verbose
```

Results: source-import protections 5/5; simulator camera test 1/1; policy
inference and V9.3 planner self-tests pass; CUDA provider loads; all 63 artifact
hashes and installed encoder copies match. CTest outcomes match Phase 0 exactly:
bridge 3 pass; encoder 2 pass / 4 lint suites fail; controller 12 pass / 6 lint
suites fail. Aggregate colcon result: 1175 entries, 1048 failures, 74 skipped,
including duplicate wrapper/per-diagnostic reporting. Full package tests are
not green. Logs and `results.json` are in `.migration/phase1/`.

## Deferred operator regression

No joystick was attached at this checkpoint. The user will perform this gate
at the end. Do not replace it with synthetic `/joy` events.

Simulator terminal:

```bash
cd ~/vibe_ws
unitree_mujoco/simulate/build/unitree_mujoco -r g1 -i 1 -n lo \
  -s "$PWD/generated/scenes/g1_29dof_with_camera_cube.xml" --use_joystick 1
```

ROS terminal (legacy combined planner launch until extraction):

```bash
cd ~/vibe_ws
source setup_local.sh
ros2 launch cpp_control g1_repose_planner.launch.py \
  artifact_dir:="$PWD/artifacts/models/repose-v9.3" \
  planner_config:="$PWD/cyclonedds_ws/src/cpp_control/config/repose_planner/g1_sim_v9_3.yaml" \
  env:=sim camera_ip:=127.0.0.1 enable_bridge:=true goal_color:=4
```

Use the same reset for colors 0–5, record planner/controller telemetry, falls,
duration and interventions, and include disarm/re-arm plus an approach case.
The initial measurements are still pending; no success-rate threshold has been
invented. Keep each phase's source/artifact pins to allow replaying these gates.

## Remaining phases

2. Introduce one experiment descriptor and explicit policy/encoder paths;
   preserve the public manifests and old launch compatibility.
3. Add resumable installation, pinned SDK/runtime acquisition, generation,
   focused builds, doctor and printed launch commands. Resolve public camera/
   scene alignment as a separately measured behavior change.
4. Extract only the planner to `sledgehammer`; the tracker remains in
   `cpp_control`. Preserve topics, messages and shutdown/disconnect semantics.
5. Freeze the complete planner payload there and validate baked-frame equivalence.
6. Finish two-terminal tracker / three-terminal planner workflows and run
   clean-machine, operator and explicit onboard/offboard QoS/disconnect gates.

The checkpoint commit preserves root scripts and locks; child sources remain
at their own pinned commits. For rollback, use a separate checkout of the
checkpoint and import its pins, keeping the current work intact. Local artifact
bytes are reproducible from the recorded snapshot; remote distribution is still
to be finalized before release.
