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
