# testing

Run from the workspace on Ubuntu 22.04 / ROS Humble. Automated checks establish
build, data, rendering and ROS startup compatibility; joystick task completion
and onboard/offboard behavior require the operator runs below.

## automated

```bash
source setup_local.sh
bash scripts/regression.sh
python3 tests/sample_launch_smoke.py
python3 tests/planner_graph_smoke.py
python3 tests/planner_console_smoke.py
python3 tests/runtime_recovery_smoke.py  # also included in regression.sh
```

The regression checks sample hashes and channels, repeatable scene generation,
all four policy inference paths, Repose/UoLM contacts, rendering each sample,
CUDA, and the frozen V9.3 planner. Its native 15-second `kd=5` check protects the
robot, cube, contacts and 2 ms timestep that fixed the damping regression.
It also plays every sample clip through the tracker using synthetic gamepad and
ROS `/joy` inputs on loopback domain 96 with remapped test topics. This checks
RB → L1 → A, premature/stale-token entry rejection, retry, RB reset and Y damping;
it does not simulate balance or establish task completion. Run just this check
with `python3 tests/motion_path_smoke.py` (`--sample walk` selects one sample).

The sample launch smoke loads each reference through the actual ROS tracker
launch on loopback domain 95. It sends no joystick or robot state. The planner
graph and console tests use domains 93/94 and verify QoS, disconnect handling,
console input and terminal restoration. Run them separately from manual tests.

The recovery smoke uses loopback domain 97 and a local synthetic camera. It
checks fragmented frames, silent/partial-frame timeouts, camera server restart,
and prompt Ctrl-C during reads and retries in all three camera consumers.
Synthetic state goes only to the planner's remapped input. A separate tracker
launch receives no state/joystick input; stopping its telemetry server must
leave commands flowing, while stopping the launch must close its children.

Package checks:

```bash
cd cyclonedds_ws
colcon test --packages-select cdr_tcp_bridge vision_encoders cpp_control sledgehammer
colcon test-result --verbose
```

Bridge and planner runtime tests pass. The encoder and cpp_control packages have
pre-existing lint failures; a successful focused regression does not mean the
entire colcon lint suite is green.

## manual samples

The operator reported all four samples working in simulation on 2026-10-13.
Dodge is outside this release check.

Follow the two direct commands in [README](../README.md#without-planner).
Restart simulator and tracker between samples; set the same `sample` in both
terminals. The scene, motion and policy paths follow that selection.

| Sample | Observe |
|---|---|
| `walk` | Grail sample0 crossing the two curbs from its recorded start |
| `parkour` | OmRe sample0 climbing from the 56 mm starting deck |
| `repose` | Two consecutive cube frontflips, starting 1 m ahead |
| `uolm` | Suitcase interaction using the supplied contact/object sidecars |

For each: **Y** settles without vibration, **RB** stands, **L1** prepares the
reference, **A** starts it. Record falls, interventions and motion completion.
Sample0 is the selected Grail example; its exact identity in the earlier hardware
trial has not been established.

## manual planner

Use the three [planner commands](../README.md#with-planner-cube-repose), which
select `generated/repose/g1_repose.xml`. **RB** stands/disarms, **A** arms, **Y**
damps. Select the target in the console before arming. Exercise targets 0–5,
a fresh trial, and an approach case.

The tracker refuses A until planner status is fresh. Losing a previously seen
heartbeat for one second shuts down tracker and encoder; this is process shutdown,
not an active damping command. Validate command-loss behavior on the target robot.
The planner stops references when low-state or controller status becomes stale.

Hardware acceptance also includes topic QoS, camera/encoder reconnect, bridge
disconnect and onboard/offboard command-loss checks. Simulator results do not
establish hardware acceptance.

## clean build replay

The sample checkpoint rebuilt the SDK, simulator and ROS packages in an isolated
checkout and fresh venv, with no assets package. It passed the same regression.
Sources came from the exact local review commits, models and the MuJoCo download
were reused, and ONNX Runtime was downloaded. Fresh-OS `--system` provisioning and
public availability of every review pin remain separate publication checks.

## evidence

The runtime recovery build passed the full automated regression, sample launches,
planner graph/console checks and focused cpp_control/sledgehammer CTests.
Recovery and regression logs are under `.migration/runtime-recovery/`; manual
task completion and hardware acceptance remain separate.

Current sample-build logs are under `.migration/samples-*`. Earlier phase results
remain in [build progress](build_progress.md) and [migration history](migration.md).
Policy bytes are checked separately from numerical/closed-loop behavior; native
MuJoCo and the training simulator need not produce bit-identical trajectories.
