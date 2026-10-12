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
