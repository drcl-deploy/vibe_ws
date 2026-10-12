# testing

The automated gates run on Ubuntu 22.04 / ROS Humble. The first operator run
exposed unstable damping in the generated scene; the native physics correction
now has a settling regression. The operator rerun and hardware checks remain pending. See
[build progress](build_progress.md) for phase-by-phase evidence and known limits.

## automated

```bash
source setup_local.sh
python3 -m unittest discover -s tests -v
python3 scripts/doctor.py
bash scripts/regression.sh
python3 tests/planner_graph_smoke.py
cd cyclonedds_ws
colcon test --packages-select cdr_tcp_bridge vision_encoders cpp_control sledgehammer
colcon test-result --verbose
```

The frozen regression checks real policy inference, CUDA provider availability,
both simulator camera tests, a 15-second native `kd=5` damping simulation,
V9.3 planning over packaged frames/walk, four model
hashes and four packaged NPZ hashes. Historical dataset hashes are also checked
when present; a fresh checkout does not need the retargeted dataset.

The graph smoke uses loopback domain 93. It first checks planner QoS and stale
state/controller gates using test messages. It then removes those publishers
and starts the actual cpp_control tracker/encoder launch to verify that the
native heartbeat check shuts down both processes when the planner exits.
No joystick events are sent, no physical robot is connected, and no closed-loop
control result is claimed. Run this separately from the operator experiment.

Bridge runtime tests and all nine planner tests pass. cpp_control and
vision_encoders retain pre-existing lint-suite failures; the full colcon result
is not green. No hardware validation is inferred from simulation or file checks.

## fresh-checkout replay

The published workspace was cloned into `/tmp/vibe-release-replay` and completed
all installer stages on the same ROS host. Sources and runtime dependencies were
downloaded; scenes and binaries were built there. A second source/build/doctor
pass verified resumability. Only the four frozen model files were supplied from
local storage; no historical retargeted dataset or previous build was reused.

All 18 workspace tests, both camera tests, V9.3, policy inference, CUDA, file
hashes and the isolated disconnect graph passed. Package results reproduce the
known lint failures. Runtime and build paths contain neither earlier workspace.
Fresh OS provisioning and `--system` apt installation were not executed here.

## operator gate

Attach the physical gamepad and run the three direct commands in
[README.md](../README.md#repose--v93): the simulator executable, the cpp_control
ROS launch, and the sledgehammer ROS launch. Each command runs in its own terminal.

After restarting the simulator with the regenerated scene, press **Y** and
check that the fallen robot settles without persistent vibration. The offline
check uses the same damping torque law but does not exercise DDS/thread timing.

Use the established simulator/gamepad startup sequence, then **RB** for nominal
stand and **A** to arm. Verify **RB** disarms and re-arming starts a fresh episode.
Repeat the same scene reset for colors 0–5 (pass the same `goal_color:=` to both
tracker and planner), including an approach case. Record duration, falls,
interventions and planner/controller telemetry. No success-rate threshold has
been invented in place of these measurements.

The tracker starts independently and refuses **A** until planner status is fresh.
After a planner has connected, one second without status shuts down the C++
tracker; its ROS launch then stops the encoder and bridge. This retains process
shutdown without a wrapper and is not a commanded damping transition. Verify
the platform's command-loss behavior in the operator/hardware gate.
The planner stops reference publication when controller status or low-state is
stale. A stalled camera retains the original V9.3 behavior: depleted visual
evidence requests a nominal stand at an act boundary.

Hardware acceptance also requires onboard/offboard topic QoS, camera/encoder
reconnect, bridge disconnect and command-loss checks on the actual platform.

## parity

Phase 5 found that the initial relocation had copied motion files without their
contact sidecars. The old loader silently zero-filled 1,249 values; its smoke
tests did not detect that. The source sidecars were restored and all four baked
arrays now match the Phase 0 snapshot byte-for-byte. sledgehammer's locked bundle
ships those contacts directly, without needing the training dataset checkout.

Model byte identity is checked separately from numerical inference and behavior.
Public ViBe export compatibility does not promise bit-identical trajectories
across MuJoCo Warp, native MuJoCo and different inference providers.
