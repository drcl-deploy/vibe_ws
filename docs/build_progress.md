# Release build progress

Current usage is in the root README; entries below preserve the earlier build
history. The user reported the corrected cube/planner workflow working and,
on 2026-10-13, all four standalone samples (walk, parkour, repose, uolm) working
in simulation. Dodge is outside the release check; onboard validation is separate.

## Self-contained samples — 2026-10-12

- Ship walk (Grail sample0), parkour (OmRe sample0), repose (frontflip sample1)
  and uolm (suitcase sample1), totaling about 9.3 MB of inputs. Required contact
  and object sidecars are byte-identical to their source files.
- Removed the workspace assets checkout, source pin, editable package and its
  unused Python dependencies. The independent internal training checkout stays
  intact. Preserved the unpublished assets fix in an external Git bundle.
- One standard-library scene script composes all four examples. The planner's
  separate cube start remains unchanged; the deterministic 15-second damping
  trajectory has maximum qpos/qvel difference 0 against the saved baseline.
- Removed verified obsolete artifacts/data copies, the old /tmp release replay,
  and the duplicate temporary Dodge export. Active policies/encoders remain
  ignored; the sample payload is tracked directly in this repository.
- Complete installer passes after cleanup. All 18 workspace tests, four policy
  inference checks, sample camera renders, Repose/UoLM contact checks, CUDA and
  V9.3 pass. Four isolated sample ROS launches and both planner graph/console
  checks pass. No joystick input was synthesized.
- An isolated /tmp replay built a new venv, SDK, simulator and ROS packages and
  passed the regression without assets. Exact local review commits supplied the
  sources; model files and the MuJoCo vendor download were reused. ONNX Runtime
  was downloaded anew. This is a clean build replay, not verification that all
  review pins are already published or that fresh-OS apt provisioning passes.
- Package tests reproduce 853 existing lint failures in cpp_control and
  vision_encoders (961 tests, 57 skipped, no test errors). Bridge/planner runtime
  tests pass. These independent source repositories were not modified.
- Evidence: .migration/samples-before, samples-scenes, samples-clean,
  samples-replay and the samples-{launch,graph,console,package-*}.log files.


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


## Native scene dynamics correction

- The operator found heavy vibration under Y damping. Earlier parity work had
  changed the timestep from 2 to 5 ms, integration/solver settings, cube contacts
  and floor appearance. Previous automated checks had missed dynamic settling.
- Restored Phase 0 native physics, cube inertia/friction and the original flat
  grid floor/lighting. Kept the 0.62369 kg cube, colored visual faces and 42.5°
  camera; no controller gains or G1 actuators changed.
- A 15-second MuJoCo 3.3.6 `kd=5` simulation reproduces the regression: final
  joint-speed RMS 10.4636 rad/s before the fix, 0.0152809 after it. Restored
  qpos/qvel match Phase 0 at every step with maximum difference zero.
- Added compiled native robot/contact/damping checks to the routine regression.
  The deterministic test does not cover DDS scheduling or closed-loop inference.
- Generated scenes now live under `~/.local/share/vibe/scenes/<checkout>/`
  (honoring XDG_DATA_HOME), with the ignored `generated` shortcut retaining the
  direct executable commands. Setup prints the actual file paths. Storage tests
  cover preservation of local files and separation of relocated/copied checkouts.
- Evidence and pre-fix XML: `.migration/native-scene-dynamics/`. Restart the
  running simulator to load the repaired scene, then repeat the joystick gate.
- Validation: 16 workspace tests, 10 assets tests, the native damping check,
  both simulator camera tests and the generated scene's actual RGB-D stream
  pass. Policy inference, CUDA provider, V9.3 (zero failures), all 63 historical
  hashes and four planner payload hashes pass. Assets' Python tests use host
  MuJoCo 3.3.5; all native dynamics and stream checks use pinned C++ 3.3.6.
- The original unitree_ros2 checkout is untouched. Fixes are committed locally
  on the workspace review branch and assets' `fix/native-scene-dynamics` branch.


## Default planner console and two usage paths

- README usage now starts with adapter tracking (two terminals), followed by
  cube Repose with the planner (three terminals). Both show direct executable
  and ROS commands.
- `ros2 launch sledgehammer planner.launch.py env:=sim` opens the existing
  console in the invoking terminal by default. `env:=real` uses the same TTY
  path for onboard SSH/tmux. Color keys publish on the existing shared target
  topic; initial blue remains explicit in the tracker command.
- Both planner log streams stay in the ROS launch log while the console draws.
  q/Ctrl-C stop planner and console together and restore terminal settings.
  `console:=false` supports unattended launches; a missing TTY also skips the UI.
- Validation: focused Humble build and all nine sledgehammer package tests pass,
  including V9.3 with frozen data. The PTY smoke passes sim/real launches,
  numeric/named colors, R, q/Ctrl-C cleanup and headless startup on isolated DDS
  domain 94. It sends no joystick, low-state or controller commands; this is
  terminal/ROS validation, not onboard hardware acceptance.
- Evidence: `.migration/planner-console/`. Changes are committed locally.


## Standalone motion entry correction

- The operator's walk clip loaded and completed L1 prep, but A cleared the prep
  flag before the base handler rechecked it. The tracker then refused entry and
  restored nominal stand. Keep completed prep until the base accepts the clip;
  a refused token-freshness check leaves prep retryable. Startup now prints the
  loaded motion path, frame count, FPS and joint-order mapping.
- Reproduced the failure before changing C++. The new regression runs all four
  sample references to their final frame with both Unitree gamepad and ROS Joy
  inputs, and checks early-A rejection, stale-token retry, RB reset and Y damping.
  It runs on loopback domain 96 with remapped test topics and synthetic state and
  tokens; it does not establish robot balance or task success.
- Focused Humble build and both cpp_control runtime package tests pass. The full
  workspace regression passes, including V9.3, native damping/rendering and all
  payload hashes; the planner QoS/disconnect graph test also passes. Existing
  package lint failures remain outside this focused runtime check.
- Evidence: `.migration/motion-path-before/` and `.migration/motion-path-fix/`.
  Restart terminal 2 and repeat RB → L1 → A with the same README commands.


## Double-frontflip Repose sample

- Replaced `cube_frontflip/sample1` with the original `sample3` and matching
  contact/object sidecars: 384 frames at 50 Hz, two consecutive forward tips.
  All source arrays remain byte-identical; recorded hashes were updated.
- Restored the standalone cube to the earlier native start: position
  `(1.0, 0.0, 0.3)`, identity orientation. The previous sample's closer pose came
  from its recording. The planner scene is byte-identical to its prior version.
- The reference rotations from the restored blue-up start go blue → orange →
  pink, so README now uses `goal_color:=5` for the standalone sample.
- All 19 workspace tests, native dynamics/rendering, four clip playback checks
  through both joystick paths, CUDA and V9.3 pass. Evidence:
  `.migration/repose-double/`; previous scene/manifest: `.migration/repose-double-before/`.
  Synthetic playback does not establish physical task completion. Restart both
  simulator and tracker for the operator's double-flip check.
