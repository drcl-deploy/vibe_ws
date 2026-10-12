# ViBe parity checkpoint

The intended big-cube mass is **0.62369 kg**, as confirmed by the user. The
published training reference (`ed4ee6c`) incorrectly specifies 1.5 kg. The local
`~/drcl_projects/vibe` branch `fix/repose-deployment-mass` corrects that constant
and README branding. It has not been pushed. The ONNX artifacts are unchanged.

## Fixed and tested

- Simulation renders at native 112 x 63 by default, with the reference 42.5-degree
  vertical FOV, position and quaternion. Width/height remain configurable for
  other exports. The encoder preserves incoming pixels and only resizes when
  the manifest requires it. The old intermediate resize is an explicit override.
- RGB-D intrinsics scale `fx` and `fy` independently. The real TCP/PNG test covers
  both native and legacy 640 x 480 renders with a differently proportioned depth
  plane, checking headers, PNG dimensions and focal lengths.
- The generated Repose scene uses an invisible box collider and six massless,
  noncolliding colored faces, matching public `vibe.assets.repose` exactly for
  mass, inertia, geometry, RGBA and contact settings after the mass correction.
  It uses the public play floor color and task timestep/solver settings. Robot
  visual groups are converted in a generated copy, preserving robot dynamics.
- Use `--camera_textures 0 --camera_visual_groups 1` with this scene: the camera
  draws groups 0/2, with textures and shadows disabled. Generic object scenes
  retain texture support. The [runbook](testing.md) supplies the full command.
- The CUDA encoder disables TF32 on ONNX Runtime 1.18+ to honor fp32 export
  precision. The runtime documents that control in its
  [CUDA provider options](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html#use_tf32).
  Older JetPack/ORT retains its supported API and still needs target-specific
  numerical validation; no Orin result is claimed here.
- README and release prose use **ViBe**; paths/repositories use **vibe**.
  Existing task IDs such as `Vibe-Repose-BigCubeFloor-ImgFeat-Ext` are preserved.

The scene's options come from the public Repose task (`timestep=0.005`,
`iterations=10`, `ls_iterations=20`) and its pinned
[mjlab 1.4.0 defaults](https://github.com/mujocolab/mjlab/blob/v1.4.0/src/mjlab/sim/sim.py).
This is a separate behavior checkpoint, not a claim that the old scene is
unchanged: cube friction changes from `(0.6, 0.6, 0.0001)` to the public builder's
`(1.0, 0.005, 0.0001)`, inertia is computed without the old XML rounding, timestep
changes from 0.002 to 0.005, and integration/solver/appearance settings align
with the reference. The Phase 1 baseline remains commit `75cbb03`.

## Evidence

| Check | Result |
|---|---|
| Assets package suite | 10 passed; existing host SciPy/NumPy compatibility warning |
| MuJoCo 3.3.6 model and real OpenGL/TCP stream tests | 2 passed |
| Generated Repose scene on actual 3.3.6 stream server | native and 640 x 480 checks passed |
| Compiled cube vs corrected public Python builder | exact array equality for tested properties |
| Native encoder images | all 8 published input frames byte-identical to source PNG pixels |
| CUDA encoder vs CPU ONNX reference | max patch error 4.4107437e-6; max CLS error 4.1723251e-7 |
| V9.3 planner and policy self-tests | passed; planner zero failures |
| Existing ROS package suites | runtime suites pass; known lint suites still fail |

The numerical threshold stayed at 1e-4. Before disabling TF32, a seeded frame
failed with max patch error 0.0028199. The unchanged frame passed after the fix,
then the eight-frame gate passed. The published geometry builder comparison ran
under the available training environment (Python MuJoCo 3.8.1); actual generated
scene loading/rendering also passed on deployment's compiled MuJoCo 3.3.6.

Evidence lives in `.migration/parity/`. Re-run the CUDA comparison in a fresh
shell with the host's Python ONNX Runtime, OpenCV and ROS dependencies installed:

```bash
cd ~/vibe_ws
source setup_local.sh
ROS_DOMAIN_ID=93 python3 tests/integration/encoder_parity.py \
  --model-path "$PWD/artifacts/encoders/theia-tiny.onnx" \
  --node-path "$PWD/cyclonedds_ws/install/vision_encoders/lib/vision_encoders/encoder_node" \
  --log-dir "$PWD/.migration/parity/recheck"
```

## Remaining limits and release work

These checks establish specific camera, cube and encoder contracts. They do not
prove pixel-identical whole scenes across OpenGL/MuJoCo Warp, identical robot
models/dynamics, identical C++ observation assembly on real trajectories, or
bit-for-bit closed-loop behavior. Lighting/backend/runtime differences and the
full public checkpoint-to-ONNX export gate still need evaluation. The user has
deferred the physical-joystick rollout to the end.

The assets revisions differ because the deployment branch includes the colored
cube fix; the older public assets pin has a generic wood cube. Public Repose
builds its own primitive cube, so blindly changing assets revisions is not a
parity fix. The new generator is tested against that actual primitive builder.

**The release is not complete.** Phase 1 and these corrective automated gates
are done. Still pending: Phase 2 artifact descriptor/path wiring; Phase 3
resumable installer and clean-machine dependencies; Phase 4 planner extraction;
Phase 5 frozen planner payload; Phase 6 final launch flows and deployment gates.
Module fixes are kept on separate branches and pinned by `sources.repos`.
The workspace snapshot is a development checkpoint, not a completed release.
