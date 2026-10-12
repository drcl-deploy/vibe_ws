# testing

The automated migration gates pass on Ubuntu 22.04 / ROS Humble. The physical
joystick rollout and onboard/offboard hardware checks remain pending. See
[build progress](build_progress.md) for phase-by-phase evidence and known limits.

## automated

```bash
source setup_local.sh
python3 -m unittest discover -s tests -v
python3 scripts/doctor.py --experiment repose-v9.3
bash scripts/regression.sh
python3 tests/planner_graph_smoke.py
cd cyclonedds_ws
colcon test --packages-select cdr_tcp_bridge vision_encoders cpp_control sledgehammer
colcon test-result --verbose
```

The frozen regression checks real policy inference, CUDA provider availability,
both simulator camera tests, V9.3 planning over packaged frames/walk, four model
hashes and four packaged NPZ hashes. Historical dataset hashes are also checked
when present; a fresh checkout does not need the retargeted dataset.

The graph smoke uses loopback domain 93, test low-state/controller-status messages,
and a dummy supervised process. It checks QoS compatibility, disarmed startup,
controller and low-state loss, disarmed reconnect, and planner loss. It launches
no tracker, sends no joystick events and is not a closed-loop control test.

Bridge runtime tests and all nine planner tests pass. cpp_control and
vision_encoders retain pre-existing lint-suite failures; the full colcon result
is not green. No hardware validation is inferred from simulation or file checks.

## operator gate

Attach the physical gamepad and use the three-terminal V9.3 flow:

```bash
./run.sh sim repose-v9.3
./run.sh tracker repose-v9.3 --with-planner
./run.sh planner repose-v9.3
```

Use the established simulator/gamepad startup sequence, then **RB** for nominal
stand and **A** to arm. Verify **RB** disarms and re-arming starts a fresh episode.
Repeat the same scene reset for colors 0–5 (pass the same `--goal-color` to both
tracker and planner), including an approach case. Record duration, falls,
interventions and planner/controller telemetry. No success-rate threshold has
been invented in place of these measurements.

The tracker wrapper waits for a V9.3 planner heartbeat before starting. Losing
that heartbeat for one second stops its whole launch, matching the former
combined launch's process shutdown. This is not a commanded damping transition;
verify the platform's command-loss behavior in the operator/hardware gate.
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
