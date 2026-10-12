# Release build progress

The operator joystick gate is deferred to the end at the user's request.

## Phase 2 — artifact wiring

- One experiment descriptor selects unchanged exporter policy/encoder pairs.
- The independent tracker launch accepts explicit ONNX and manifest paths;
  legacy artifact selection remains supported.
- New deployments no longer require an encoder model copy inside its package.
- Validation: 11 workspace tests; both simulator camera tests; real policy
  inference; V9.3 planner with original frames and walk, zero failures; CUDA
  provider load; all 63 frozen file hashes; explicit and legacy launch construction.
- No runtime C++ changed in this phase. Evidence: `.migration/phase2/`.
- ONNX files remain ignored. Local export inputs are supported; optional HF
  distribution is under discussion and no model files have been uploaded.

## Phase 3 — automated setup

- Added resumable source/dependency/scene/simulator/ROS/doctor stages and explicit
  sim/onboard/offboard profiles. System package installation is an optional
  `--system` step; an existing ROS installation remains a prerequisite.
- Found SDK commit `29935ddcea461c26004978e95ed85d7e0452ea4f`: its headers and
  all three x86 runtime libraries match the tested `/opt` installation exactly.
  The simulator now uses this workspace-local SDK and pinned MuJoCo 3.3.6.
- Asset generation uses an isolated Python environment. Both G1 camera/floor
  and Repose cube scenes are generated and their absolute paths printed.
- Artifact import preserves exporter pairs and validates their compatibility;
  optional HF fetch requires full commit revisions and SHA-256 hashes. No
  ONNX files are tracked or uploaded.
- Validation: installer dependency stage and focused simulator/ROS builds;
  doctor; 16 workspace tests; two camera tests; V9.3 and policy smoke checks;
  CUDA provider; all 63 hashes. Runtime RPATH resolves only the selected SDK
  and MuJoCo trees. Evidence: `.migration/phase3/`.
- Clean-checkout replay and final operator flows are reserved for Phase 6.

## Phase 4 — planner extraction

- Planner sources, headers, configurations, utilities, documentation and self-tests
  now belong to sledgehammer. cpp_control exports its shared deployment libraries
  and retains tracker/control implementations and ROS interface names.
- Legacy planner launch names forward to the optional sledgehammer package.
- All 17 C++ algorithm/header/test files compare exactly after only include-path
  normalization. Tracker and shared utility implementations were not changed.
- Fresh cpp_control products replace archived pre-extraction build/install trees.
- Validation: 16 workspace tests; camera tests; real-policy smoke; V9.3 using
  original retargeted frames and walk (zero failures); CUDA; 63 file hashes;
  all eight sledgehammer CTests. cpp_control retains its failing lint suites.
- Evidence and rollback products: `.migration/phase4/`.

## Phase 5 — frozen planner payload

- sledgehammer owns four NPZ files: clips, library, baked frames and approach walk
  (10.9 MB total), installed with the ROS package and independently checksummed.
- V9.3 defaults to the baked loader. All four arrays match the Phase 0 snapshot
  byte-for-byte, including all 10,980 rows and their contact commands.
- This check exposed a relocation omission: the motion copies lacked sibling
  contact files, silently zeroing 1,249 contact values. Earlier smoke-test passes
  did not establish complete data parity. Sidecars were restored before baking;
  no planner algorithm changed. Their provenance hashes accompany the bundle.
- Validation: V9.3 with the packaged baked frames and walk, zero failures;
  all nine sledgehammer CTests; 16 workspace tests; both camera tests; real-policy
  smoke; CUDA provider; 63 historical and four packaged payload hashes.
- Evidence: `.migration/phase5/`. The operator gate remains deferred.

## Phase 6 — final workflows and release validation

- Two terminals launch a tracker experiment; the optional frozen planner uses
  a third terminal. Imported exports resolve by name; the README and setup/test
  guides now describe the implemented workflows.
- A separate planner launch owns only its node. The workspace tracker supervisor
  waits for V9.3 status and shuts down the launch on heartbeat loss. This preserves
  process shutdown behavior; it does not invent a robot damping transition.
- The planner now rejects stale controller status as well as stale low-state.
  This lifecycle fix is separate from the unchanged algorithm extraction.
- Development-checkout validation: 18 workspace tests; both camera tests; real-policy and V9.3
  data checks; CUDA provider; installed data hashes; launch argument resolution;
  isolated domain-93 QoS, arming/status loss, low-state loss, disarmed reconnect
  and planner-loss supervision tests. No joystick events or control nodes were
  used in that isolated graph test.
- Fresh public clone `/tmp/vibe-release-replay` completed every installer stage
  on the existing ROS host, then repeated source import/build/doctor successfully.
  No prebuilt workspace products or training dataset were copied into that clone.
  The four frozen model files were supplied locally because ONNX publication is
  pending; the normal exporter import also passed twice with unchanged bytes.
- Fresh-build regression: 18 workspace tests, both real camera tests, V9.3 with
  packaged data, real-policy smoke, CUDA, four model hashes and four data hashes
  all pass. The isolated disconnect graph also passes from this checkout.
- Fresh runtime/library paths and CMake caches contain no references to either
  earlier workspace or `/opt/unitree_robotics`. System ROS, graphics and host
  NVIDIA libraries remain shared prerequisites; this is not a clean-OS test.
- Final focused package result: 961 entries, 0 errors, 853 lint failures, 57
  skips. All nine sledgehammer tests and bridge runtime tests pass. Existing
  cpp_control/vision_encoders lint failures are preserved, not waived.
- Root ownership audit covers 201 tracked paths: no child sources, ONNX, NPZ,
  generated scenes or build trees. Published dependency pins are fetchable.
  Original workspace commits and working-tree statuses still match Phase 0.
- All six implementation phases are complete. Physical joystick rollout,
  clean-OS provisioning and onboard/offboard hardware validation remain open.
- Hugging Face ONNX publication is pending. Local exporter imports are usable;
  no policy/encoder binaries have been committed or uploaded.

## Direct ROS workflow revision

The operator requested native executable/ROS commands instead of a runtime script
API. Work is isolated on `refactor/direct-ros-workflow` (workspace/controller)
and `docs/direct-ros-workflow` (planner documentation).

- Removed `run.sh`, its Python dispatcher/supervisor, named experiment descriptors,
  descriptor resolution and the export import API. Exports are used directly.
- Retained installation, pinned downloads and checks as setup/test utilities.
- Moved the existing one-second planner heartbeat guard into the C++ tracker.
  It starts independently, refuses arming until status arrives, and exits on
  subsequent heartbeat loss; ROS launch stops its encoder/bridge siblings.
- README usage now shows the simulator executable, `ros2 launch cpp_control`,
  and `ros2 launch sledgehammer` explicitly. Earlier phase notes above record
  the superseded workflow, not another supported runtime entry point.
- The joystick is visible at `/dev/input/js0`; the operator rollout is pending.
- Validation: focused Humble build passed; 14 workspace tests; both camera
  tests; real-policy inference; CUDA; V9.3 with zero failures; all 63 historical
  and four packaged data hashes. Native tracker/encoder shutdown was exercised
  on isolated domain 93 with no joystick input. All nine planner tests pass;
  cpp_control retains its existing lint failures. Logs: `.migration/direct-ros-workflow/`.
- This revision is committed on the local review branches; the operator can
  test the built checkout before publishing or merging them.
