# ViBe export compatibility

The training/export reference is [lok-i/vibe](https://github.com/lok-i/vibe).
Deployment does not import the training environment or the internal `assets`
package. The four frozen examples in `data/sample/` are sufficient to construct
their native simulator scenes.

## exports

`artifacts/` is a storage root. Keep ONNX and `.manifest.json` pairs unchanged:
input ports, joint order, history, action scaling and encoder preprocessing come
from the exporter. Absolute paths are supported; the directory name is not an
export contract.

`artifacts.lock.json` pins the HF revision, paths and hashes of four policy pairs
and the shared encoder pair. Setup downloads those exact bytes into `artifacts/`,
using `models/<sample>/policy.onnx` and `policy.manifest.json` locally. Original
checkpoint filenames remain in the HF paths; model and manifest contents are unchanged.
Their source checkpoints match ViBe's v0.1.0 release; the four ONNX exports retain
their historical exporter revisions. They have passed ONNX/manifest checks,
encoder shape checks and native C++ inference. A fresh public-export numerical
and closed-loop check has not been rerun for these four files.

The older PerLoco `AdaptSonic` task names are accepted by the tracker. The sample
names `walk` and `parkour` do not change these task IDs. All four samples use
112×63 images and the same Theia-tiny encoder. Dodge's separate 112×64 export
remains optional and has no packaged sample environment.

## transfer conventions

These are the existing runtime conventions for the four released samples.
The manifests and named source files remain authoritative; this table adds no
configuration format. Source paths identify the owning module.

| Area | Convention and source |
|---|---|
| Camera | All four policies use 112×63 Theia-tiny input. The native head camera has 42.5° vertical FOV; its mount is in `unitree_mujoco/unitree_robots/g1/g1_29dof_with_camera.xml`. Encoder normalization is baked into ONNX; the node preserves native pixels and resizes only when needed. Real RGB-D intrinsics travel per plane on the camera wire; the planner's mount/palette calibration is in `sledgehammer/config/repose_planner/g1_real_v9_3.yaml`. Real-camera calibration still needs onboard validation. |
| Coordinates | G1 motor/action order is MJ order; sample NPZ and typed reference rows use IsaacLab order. `cpp_control/include/common/g1/joint_orders.hpp` owns the mapping. Quaternions are wxyz. `MotionClock` heading-aligns the reference on engage; root twist is expressed in the reference anchor frame. UoLM's object goal stays in the canonical clip frame. See cpp_control's `docs/motion.md`. |
| History/reset | Port history lengths come from the policy manifest. `HistoryTerm` writes oldest to newest and backfills with the first observation after reset. A cold engage resets histories/actions; a planner reference swap within policy mode retains histories. Implementation: `cpp_control/include/common/obs_terms.hpp` and `src/tasks/tracker/g1_sonic.cpp`. |
| Cadence | Released policy manifests specify 20 ms (50 Hz), matching tracker `control_dt`. The tracker currently warns on mismatch and runs at configured `control_dt`; it does not reject it. Reference playback advances by that configured period. Native MuJoCo dynamics stay at 2 ms; the two periods serve different purposes. |
| Actuation | Policy output maps to `q = default_joint_pos + scale * action`, with stiffness/damping from the manifest. The Unitree backend sends these as motor position/PD commands. The native simulator computes PD torque from them in `unitree_mujoco/simulate/src/unitree_sdk2_bridge.h`. Hardware timing and command-loss behavior require onboard acceptance. |
| Failure response | Camera connection/frame reads time out after two seconds and reconnect; shutdown and retry waits check cancellation every 100 ms. Stale vision refuses new policy entry but only warns during an active policy. Planner heartbeat loss shuts down the tracker after one second without issuing active damping. The planner stops references on stale controller/robot state; the tracker itself has no robot-state timeout. Telemetry server/client loss leaves control running. |

## extending the workspace

- A new checkpoint within a supported task family uses the existing direct
  launch with its policy/encoder paths and manifests; no path-specific C++ is
  needed.
- New task semantics belong in cpp_control's task profile and observation
  bindings. Keep robot/backend handling in the robot layer; exported IDs and
  existing task contracts stay compatible.
- A new planner runs separately and exchanges `MotionReference` and
  `ControllerStatus`. With `planner:=true`, publish `std_msgs/msg/Empty` on
  `/vibe/planner/heartbeat` from the planner tick. Detailed Repose status and
  observation types belong to sledgehammer. Keep the algorithm independently testable, following
  sledgehammer's planner/core split.

The bundled experiment/calibration replay tools accept bags recorded with the
former `cpp_control/msg/{PlannerStatus,CubeObservation,CalibrationState}` names.
Their message fields are unchanged; only ownership moved to sledgehammer.
This does not alias old type names for live ROS publishers or `ros2 bag play`.

## scenes and references

`data/sample/samples.json` records source revisions, reference identities, start
placement, policy paths and hashes. Motion arrays and contact/object sidecars are
copied unchanged. Terrain dimensions are unchanged; Grail uses sample0's offset
and heading within the exported terrain frame. UoLM keeps its canonical object
frame because the policy consumes the clip-final object goal in that frame.

The checked-in cube scene retains mass 0.62369 kg, inertia 0.0386285, native
contacts and the six-color palette. The robot comes from the pinned Unitree model
with a 42.5 degree camera. Native 2 ms Euler integration is deliberate: copying
the training simulator's timestep previously caused unstable SDK damping.

The Repose clip scene starts from the reference's object pose. The planner scene
retains its separate tested start and frozen data in `sledgehammer`; it does not
read the old `artifacts/data/` dataset.

File hashes establish byte identity. Scene/damping comparisons protect the native
baseline. Neither establishes complete training/native closed-loop equivalence.
See [testing](testing.md) and the earlier [parity audit](parity.md).
