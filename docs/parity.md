# ViBe parity and native simulation

The intended big-cube mass is **0.62369 kg**. The published training reference
(`ed4ee6c`) says 1.5 kg; the local `~/drcl_projects/vibe` branch
`fix/repose-deployment-mass` corrects that constant and has not been pushed.
Policy and encoder ONNX files remain unchanged.

## Native physics regression and correction

The first joystick test exposed persistent vibration in **Y** damping mode.
The earlier scene-parity change had copied training's 5 ms timestep and solver
settings into the native SDK simulator. Its bridge computes motor PD torques
explicitly; copying those options did not preserve the tested native behavior.
The earlier loading, rendering and planner checks did not exercise damping.

The generated Repose scene now restores the Phase 0 native settings:

| Setting | Native V9.3 |
|---|---|
| Timestep / integrator | 0.002 s / Euler |
| Solver / iterations / line search | Newton / 100 / 50 |
| Cube mass / principal inertia | 0.62369 kg / 0.0386285 kg m² |
| Cube friction | `(0.6, 0.6, 0.0001)` |
| Ground | original flat grid floor and lighting; no heightfield |

The source remains `unitree_mujoco/unitree_robots/g1/g1_29dof_with_camera.xml`.
Generation copies it with absolute mesh paths and remaps visual groups; robot
joint damping, armature, actuators and contacts remain unchanged. The camera
retains the approved 42.5-degree FOV. Six noncolliding colored cube faces remain
for the camera; the cube's physical properties follow the native baseline.

Using the simulator's exact MuJoCo **3.3.6** library, a deterministic 15-second
test applies Y's `kd=5` damping law. Over its final five seconds:

| Scene | Joint speed RMS | Peak joint speed |
|---|---|---|
| Frozen Phase 0 | 0.0152809 rad/s | 0.0813374 rad/s |
| Previous 5 ms scene | 10.4636 rad/s | 40.8747 rad/s |
| Restored native scene | 0.0152809 rad/s | 0.0813374 rad/s |

The restored scene's `qpos` and `qvel` match Phase 0 at every tested step (maximum
difference **0**). This is an offline damping trajectory, with per-step torque
refresh; it does not test asynchronous SDK/DDS scheduling or policy rollouts.
`scripts/regression.sh` now checks native robot/contact settings and settling
against the pinned C++ MuJoCo library. The frozen Phase 0 comparison is additional
local evidence in `.migration/native-scene-dynamics/`.

## Camera and encoder checks retained

- Native 112 × 63 rendering, 42.5-degree vertical FOV and reference camera pose.
  The encoder preserves incoming pixels unless its manifest requires resizing.
- RGB-D intrinsics scale `fx` and `fy` independently. Real OpenGL/TCP tests cover
  native and 640 × 480 rendering with a differently proportioned depth plane.
- `--camera_textures 0 --camera_visual_groups 1` selects groups 0/2 and disables
  camera textures/shadows. Viewer floor appearance and policy-camera rendering
  are distinct; no whole-scene pixel identity is claimed.
- CUDA encoding disables TF32 on ONNX Runtime 1.18+ for fp32 exports. The prior
  eight-frame comparison preserved source image bytes and measured maximum
  patch/CLS errors of 4.4107437e-6 / 4.1723251e-7 against CPU ONNX inference,
  below the unchanged 1e-4 threshold. Evidence: `.migration/parity/`.

The previous claim of exact public cube/contact/solver parity is superseded by
the native physics correction above. Training and native SDK simulation have
different control/integration arrangements. Artifact compatibility does not
establish bit-identical closed-loop trajectories across those backends.

All six implementation phases are recorded in [build progress](build_progress.md).
The operator must restart the simulator to load regenerated XML and rerun the
joystick gate. Clean-OS provisioning, onboard/offboard validation, fresh-public-
export numerical comparison and optional Hugging Face publication remain open.
