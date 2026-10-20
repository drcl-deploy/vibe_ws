# vibe_ws agent guide

## Start here

- Work in this checkout, normally `/home/loki/vibe_ws`, with the session's working
  directory and writable scope set here. Do not modify `/home/loki/unitree_ros2`
  or the internal training/assets checkouts during release work.
- The root repository is `drcl-deploy/vibe_ws`, branch `main`. Inspect its diff
  before editing; preserve the user's manual README changes.
- Module directories are independent Git repositories, ignored by the root.
  `sources.repos` pins their exact commits. Check module status separately and
  commit changes in their owning repository; never stage their source trees here.
- Read `README.md` for current commands, then `docs/setup.md` and
  `docs/testing.md`. `docs/migration.md` and most of `docs/build_progress.md` are
  historical: old wrappers, paths and pending gates there may be superseded.

## Code map

| Location | Responsibility |
|---|---|
| Root scripts and locks | Fetch pinned sources/dependencies/exports, generate scenes, build and validate |
| `unitree_mujoco/` | Native G1 simulation, robot XML, joystick input and camera TCP stream |
| `cyclonedds_ws/src/vision_encoders/` | Camera frames to patch/CLS tokens through the frozen ONNX encoder |
| `cyclonedds_ws/src/cpp_control/` | Manifest-driven ViBe tracker, motion playback, robot control and controller interfaces |
| `cyclonedds_ws/src/cdr_tcp_bridge/` | Serialized ROS telemetry over TCP for offboard viewing/recording |
| `cyclonedds_ws/src/sledgehammer/` | Frozen Repose V9.3 planner, planner messages, target console and four packaged NPZ files |
| `data/sample/` | Four small reference motions, required sidecars and scene geometry |

`install.sh --system` runs `scripts/install.py`: sources, deps, artifacts, scene,
sim, ros, doctor. `scripts/scenes.py` composes sample geometry with Unitree's G1.
`setup_local.sh` / `setup.sh` only select the ROS/network/artifact environment.
Runtime usage stays direct: simulator executable + tracker ROS launch; the
optional planner adds one ROS launch. Do not reintroduce runtime wrapper APIs.

## Contracts to preserve

- Sample names are `walk`, `parkour`, `repose`, `uolm`. One `sample` shell variable
  selects `generated/$sample/scene.xml`, `data/sample/$sample/motion.npz` and
  `models/$sample/policy.onnx`. Do not require a separate policy-name lookup.
- Local policies are `artifacts/models/<sample>/policy.onnx` with
  `policy.manifest.json`; all four use `artifacts/encoders/theia-tiny.onnx` and
  its manifest. `artifacts.lock.json` maps these names to immutable HF files.
  Keep model/manifest bytes and source provenance unchanged; no ONNX in GitHub.
- `setup_local.sh` sets `VIBE_ASSET_ROOT` to `artifacts/`; set
  `VIBE_ARTIFACT_ROOT` before sourcing to override it. Launch paths can be
  absolute. Same-stem manifests are discovered beside ONNX files by default;
  `policy_manifest` / `encoder_manifest` can point elsewhere.
- The public workspace has no internal `assets` or training-repository
  dependency. Keep motion contact/object sidecars with their reference. Repose
  uses two consecutive cube frontflips; UoLM uses the suitcase example.
- Generated scenes live at `$XDG_DATA_HOME/vibe/scenes/<checkout>/`, default
  `~/.local/share/vibe/scenes/`, with an ignored `generated` symlink. Regenerate
  after moving the checkout; preserve hand edits under separate filenames.
- G1 comes from `unitree_mujoco/unitree_robots/g1/g1_29dof_with_camera.xml`.
  Preserve native 2 ms dynamics, actuator/contact settings, 42.5-degree camera,
  112x63 imagery and the 0.62369 kg cube. Both cube examples start 1 m ahead;
  the planner has its own `generated/repose/g1_repose.xml`. Do not restore the
  earlier 5 ms/terrain changes that caused heavy Y-damping vibration.
- The tracker, MotionReference and ControllerStatus stay in cpp_control. The
  frozen Repose planner, its NPZ data, PlannerStatus, CubeObservation and
  CalibrationState belong in sledgehammer. Planner liveness uses std_msgs/Empty
  on /vibe/planner/heartbeat, emitted from the same planner tick as status.
  Never delete `lok-i/planners-level3` or other legacy
  branches, or merge compatibility branches, without explicit instructions.
- Preserve Foxy/Humble compatibility, snake_case ROS/YAML names and existing
  formatting. Use `vibe` / `ViBe`, not `Vibe`, in new prose; retain exported IDs.
- README style: commands first, short comments, tables afterward, minimal notes.
  Put detail in docs. Keep the existing `stream_vibes.sh` attention command.

## Validation

Use focused builds for changed modules, followed by their relevant tests.
For workspace files/exports:

```bash
source setup_local.sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
python3 scripts/doctor.py
```

For runtime, artifact wiring or scene changes, use the established regression:

```bash
bash scripts/regression.sh <checkpoint-name>
python3 tests/sample_launch_smoke.py
python3 tests/sample_launch_smoke.py --task-launches  # when task launch names/wiring change
python3 tests/repose_message_smoke.py  # when message ownership or replay changes
python3 tests/planner_graph_smoke.py
python3 tests/planner_console_smoke.py  # when planner/console behavior changes
```

The regression includes V9.3, four policy inference/render checks, native damping,
CUDA and isolated motion playback. Tests use separate DDS domains; keep them
separate from manual runs. Documentation-only edits need link/syntax/diff checks,
not another full runtime regression. Hardware acceptance requires explicit
onboard/offboard checks, including QoS and disconnect behavior.

## Handoff: 2026-10-13

- All six implementation phases and the direct-launch revision are implemented.
  The user reported all four samples and the planner working in simulation.
  Dodge is outside this release's sample checks.
- Latest changes align local policy names with samples and simplify README,
  including the user's prose edits. HF paths, hashes, model contents and sample
  payloads are unchanged. Existing local policy pairs were moved to the new names.
- Validation passed after renaming: 19 workspace tests, 2 simulator CTests,
  four policy/camera checks, native damping, CUDA, V9.3, all four motion-playback
  checks through both gamepad/ROS inputs, sample launches and planner disconnect
  checks. Logs: `.migration/sample-artifact-names/` (local, ignored).
- Fresh HF download and repeat verification passed for all 10 policy/encoder
  files. Actual launches outside `artifacts/` passed with adjacent manifests and
  explicitly located manifests, including paths with spaces. These were startup
  checks without robot state/joystick input, not hardware rollout tests.
- All five module checkouts were clean and matched `sources.repos` at handoff.
  The root release PR is merged. Module PRs below were still OPEN when checked:
  [cpp_control #7](https://github.com/drcl-deploy/cpp_control/pull/7) (base `master`),
  [vision_encoders #7](https://github.com/drcl-deploy/vision_encoders/pull/7),
  [unitree_mujoco #4](https://github.com/lok-i/unitree_mujoco/pull/4),
  [sledgehammer #1](https://github.com/drcl-deploy/sledgehammer/pull/1).
- HF exports were published for review at
  [lkrajan/vibe discussion #1](https://huggingface.co/lkrajan/vibe/discussions/1).
  The lock pins commit `ff79137d921d0124fea5877e01d1065f10e852a3`; original
  checkpoints and `v0.1.0` were not changed. Recheck review status before updating pins.

## Remaining release work

- On 2026-10-20, standalone SONIC gained the existing ViBe L1 prep path in
  cpp_control `fix/sonic-prep` (`872ee90`). Both trackers share the arm-reference
  ramp and reject manual clip entry until prep completes; planner/stand-reactive
  behavior stays unchanged. Workspace sources.repos pins that branch commit.
  The full local regression, four sample launches, planner graph and standalone
  gamepad/ROS-joy prep checks passed. The operator accepted R1 → L1 → A walking
  in simulation and on G1; the native Foxy ROS build also completed successfully.
  The G1's portable deploy.yaml is now tracked; its workspace
  Git author/committer is configured locally as lok-i. README includes hardware
  RGB/depth camera commands and onboard/offboard sourcing for telemetry.
  Release PRs: vision_encoders #9 → cpp_control #10 → vibe_ws #6. Refresh the
  two review-branch pins to actual merged default-branch commits before merging
  the workspace. Onboard audit: all five module pins match and source trees are
  clean; the ignored ORT source has exactly the two published encoder patches.
  Generated CTest logs were preserved under the ignored installer cache.

- On 2026-10-19, the G1 Orin NX completed the full native ONNX Runtime 1.15.1
  CUDA 11.4 SDK build/install, all shared-library dependency checks, and the
  native CUDA provider-load check. Encoder PR #9 contains two localized fixes
  for disabled flash attention; workspace PR #6 pins that review branch.
  Evidence: .migration/jetpack5-ort-build/native-sdk-build.log. Native ROS build,
  model inference and hardware rollout acceptance remain pending. After the
  battery swap the robot clock was January 1970, with NTP active but unsynced;
  correct it before HTTPS downloads. The completed SDK recovery session is
  available as tmux vibe-sdk-recovery on unitree@gilfoyle.

- Installer retries and upgrades now reconcile the current locks through the
  existing install.sh command. Clean managed module pins advance automatically;
  older release pins and artifacts can be recognized from committed lock history.
  Unknown commits, edits, ignored-file collisions and custom exports stay intact.
  Receipts/logs live in .cache/vibe-install; artifact receipts stay with artifacts.
  Profile, ROS selection, job count and custom SDK archive persist between runs.
  Changed build identities rotate generated outputs to previous/; matching inputs
  retain partial builds. Incomplete owned SDKs/venvs recover on rerun. The first
  receipt-aware run rebuilds previously unrecorded generated outputs once.
- Installer validation includes 47 workspace tests, complete normal installation,
  incremental retry with all 463 object timestamps retained, fresh offboard
  installation/retry without CUDA or runtime executables, installed legacy replay,
  bridge tests, the full runtime regression and sample/planner launch checks.
  Evidence: .migration/installer-retry/ and .migration/installer-retry-regression/.
  Native JetPack source build and onboard/offboard hardware acceptance remain pending.
- README operator/gamepad and restart notes were removed at the user's request;
  detailed controls remain in docs/testing.md and future demo links are planned.

- The approved package-boundary cleanup renames only the branch-added Grail/OmRe
  wrappers to g1_vibe_walk / g1_vibe_parkour. Generic ViBe, standalone SONIC and
  every master path remain. The cpp_control README and new docs/vibe.md replace
  the five stale branch-added ViBe notes; workspace README commands are unchanged.
- Repose messages moved byte-for-byte to sledgehammer; the tracker uses a standard
  heartbeat with the existing freshness/timeout logic. Bridge profiles and all
  consumers use the new names. Bundled replay/validation readers accept old bag
  names; this does not add live ROS aliases for legacy types.
- SLEDGEHAMMER_BUILD_RUNTIME=OFF supplies offboard messages/tools without CUDA or
  planner binaries. Clean normal/offboard builds, 13 type-support imports, legacy
  bag replay, full regression, both sample-launch paths and planner graph/console
  checks passed. Logs: .migration/package-boundary/. Final native ARM CUDA and
  five-case manual acceptance remain pending.
- On 2026-10-14, encoder #7, sledgehammer #1/#4, simulator #4 and bridge #2
  landed in main. Their checkouts and sources.repos now use the merged commits.
  Encoder #6 was closed as superseded: #7 already includes its CUDA runtime
  changes. Sledgehammer #3 had landed in its old parent branch after #1 merged;
  #4 brings that exact tested tree onto main. Do not remove the legacy branches.
- cpp_control #8 also merged on 2026-10-14 as `e6ea520` on master. Its checkout
  and source pin now use that merge commit; its tree is identical to the reviewed
  `dad4031`. All five modules now use merged main/master commits. Only the
  workspace PR #3 remains for the user's final review.
- ROS build/install/log, simulator build, and Unitree SDK build/install outputs
  were deleted for the user's fresh README installation. Downloaded SDKs,
  artifacts, setup venv and regression evidence remain. All five module source
  trees match the tested release versions; 25 workspace and three encoder setup
  tests passed. The user subsequently reported the fresh README installation
  and simulation working. Later cpp_control edits only adjusted its README:
  preserve the standalone workflow, add a brief ViBe install note and launch
  template. Workspace README commands remain unchanged.

- The approved planner cleanup (`adc7456`, included in the current cpp_control
  pin) removes only the unused `sonic_kinematic` integration
  and four cpp_control Repose forwarding launches. Manual reference-based
  walking, yaw, active stand, standalone SONIC, external planner interfaces and
  README commands are unchanged. All 92 master paths are preserved; the original
  terminal attention viewer and previously removed tracked Python files were
  restored. Never broaden this into removing the working walking/yaw features.
- Clean cpp_control build/install, sledgehammer rebuild, standalone SONIC
  stand/clip startup, restored viewer, full regression, sample launches, planner
  graph/console and focused CTests passed. Logs: `.migration/planner-cleanup/`.
  The user's five-case README retest after this cleanup is pending.
- User is reviewing workspace #3 after merging all five modules.
  Fresh-OS provisioning and onboard/offboard validation are still pending.
- The final cpp_control review was [PR #8](https://github.com/drcl-deploy/cpp_control/pull/8),
  now merged into `master`, superseding #7. Research branches remain intact. Encoder #7 and
  sledgehammer #1 include their merged recovery PRs. The message-ownership
  companions are now on sledgehammer and cdr_tcp_bridge main.
  Workspace [PR #3](https://github.com/drcl-deploy/vibe_ws/pull/3)
  pins the matching commits.
- Installation portability changes support explicit/unique Foxy/Humble/Jazzy
  selection, OS Python for ROS tools, and a bounded ARM ONNX Runtime source build
  matched to JetPack CUDA/cuDNN. Foxy simulation setup remains unsupported.
- Offboard now builds cpp_control/vision_encoders messages and viewing tools with
  runtime targets disabled. A fresh isolated x86/Humble offboard build passed
  all 12 bridge Python/C++ type-support imports without an ONNX/CUDA SDK. Doctor
  checks these imports and sim/onboard CUDA-provider loading. Native ARM and
  fresh-OS/hardware acceptance remain pending.
- Portability validation passed 25 workspace tests, three environment tests,
  three SDK setup tests, normal ROS build, full runtime regression, sample launch
  and planner graph/console checks. Logs: `.migration/portability/`.
- Camera TCP reads/shutdown now have bounded waits, with encoder/planner recovery
  checks passing in simulation. Hardware reconnect acceptance is still pending.
- cpp_control/vision_encoders retain known lint failures (853 in the recorded
  package run). Root CI now targets `main` and runs the offboard installer and
  tests on x86/ARM with Humble/Jazzy. It does not cover native CUDA installation.
  Passing focused checks does not make the full package lint suite green.
