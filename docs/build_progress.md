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
