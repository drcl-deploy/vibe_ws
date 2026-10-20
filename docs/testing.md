# testing

Run from the workspace on Ubuntu 22.04 / ROS Humble. Automated checks establish
build, data, rendering and ROS startup compatibility; joystick task completion
and onboard/offboard behavior require the operator runs below.

## automated

```bash
source setup_local.sh
bash scripts/regression.sh
python3 tests/sample_launch_smoke.py
python3 tests/sample_launch_smoke.py --task-launches  # walk / parkour / repose / uolm wrappers
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
Add `--sonic` to check standalone SONIC with the bundled walking reference,
including staged-clip invalidation and prep resets on X/B/Y.

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

Installation checks:

```bash
/usr/bin/python3 -m unittest discover -s tests -v
/usr/bin/python3 -m unittest discover -s cyclonedds_ws/src/vision_encoders/tests -p test_setup.py -v
/usr/bin/python3 -m unittest discover -s cyclonedds_ws/src/cpp_control/tests -p test_ros_environment.py -v
/usr/bin/python3 scripts/doctor.py --profile onboard  # or sim / offboard
/usr/bin/python3 tests/repose_message_smoke.py  # from a sourced workspace
```

Doctor loads the bridge profiles' Python and C++ message libraries, checks Python
runtime dependencies, and loads the CUDA provider for sim/onboard. `--build-only`
skips these imports and model checks. CI runs the actual offboard installer in
Humble/Jazzy containers on x86 and ARM runners. It does not exercise JetPack CUDA
or replace native onboard acceptance.

Installer tests exercise clean pinned upgrades, local-work preservation, failed
clones, interrupted artifact/SDK installation, incomplete setup venvs and build
rotation interrupted between moves. They check that unchanged retries retain
completed objects, changed inputs retire obsolete installed messages, and saved
onboard/offboard profiles survive a plain rerun. CI repeats `./install.sh` after
the fresh offboard install and checks that its build cache and profile survive.

The message smoke checks that Repose types are installed only in sledgehammer,
their fields match the former cpp_control schemas, and the installed replay tools
read old type names from an actual SQLite bag. Frozen CDR fixtures were captured
from cpp_control `0c4da22` before migrating the definitions. The planner graph
check verifies that its standard heartbeat keeps the tracker alive, and that
heartbeat loss still stops tracker/encoder even while detailed status continues.

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

Use the three [planner commands](../README.md#with-planner-cube-repose-only), which
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

On 2026-10-20, the operator confirmed standalone SONIC walking with the shared
R1/RB → L1 → A prep path in simulation and on the G1. The native Foxy ROS build
completed successfully. This acceptance covers standalone walking/prep; the four
ViBe task rollouts on hardware remain separate checks.

The package-boundary cleanup rebuilt cpp_control and sledgehammer from empty
build/install directories. The legacy bag checks, all four generic and named
sample launches, full runtime regression, planner graph/console and focused
controller/planner/bridge CTests passed. A separate clean offboard build loaded
all 13 required message types and replayed legacy data without an ONNX/CUDA SDK
or controller/encoder/planner executables. Evidence: `.migration/package-boundary/`.

The tracker retains the same planner-entry and one-second timeout behavior;
its liveness subscription now uses `std_msgs/msg/Empty` independently of Repose
telemetry. The operator's five-case manual retest and hardware acceptance remain
separate from these automated checks.

The portability changes passed 25 workspace tests, three ROS environment tests,
and three SDK setup tests, including archive extraction with nested source-build
headers and custom dependency paths. The normal Humble build and a fresh isolated
offboard build both passed doctor. The offboard checkout had no ONNX/CUDA SDK;
all 12 bridge message types loaded through Python and C++ typesupport.
Removing a C++ typesupport library made doctor fail as intended. The installed
live viewer and both Repose diagnostic viewers started with the setup venv active
and stopped cleanly on Ctrl-C. Controller, nine planner, and three bridge CTests
passed as well.

The full runtime regression, four sample launches and planner graph/console
checks passed after the installation changes. Logs are under
`.migration/portability/`. These are x86/Humble results; native ARM source builds,
fresh-OS provisioning, and hardware operation still require target-host checks.

The planner cleanup rebuilt cpp_control from empty build/install directories and
rebuilt sledgehammer against it. The full regression, sample launches, planner
graph/console checks, controller deploy self-test and all nine planner CTests
passed. Standalone SONIC startup/shutdown passed with its default stand and an
explicit motion clip on isolated DDS, without robot state or joystick input.
The clean install excludes the retired kinematic planner and cpp_control Repose
redirects; the original terminal attention viewer is installed and callable.

All 92 paths tracked on cpp_control's `master` remain present. Across this cleanup,
112 protected runtime/configuration/README/data files retain identical hashes,
including manual walking and yaw. Logs are under `.migration/planner-cleanup/`.
The operator's repeat of the five README cases on this cleaned build is pending.

The runtime recovery build passed the full automated regression, sample launches,
planner graph/console checks and focused cpp_control/sledgehammer CTests.
Recovery and regression logs are under `.migration/runtime-recovery/`. The
operator also confirmed all four README samples and the planner working in
simulation on 2026-10-13. Hardware acceptance remains pending.

Current sample-build logs are under `.migration/samples-*`. Earlier phase results
remain in [build progress](build_progress.md) and [migration history](migration.md).
Policy bytes are checked separately from numerical/closed-loop behavior; native
MuJoCo and the training simulator need not produce bit-identical trajectories.
