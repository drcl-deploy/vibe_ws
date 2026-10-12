# ViBe workspace

Deploy exported ViBe policies on the Unitree G1 with ROS 2 and Unitree MuJoCo.
The workspace composes independently versioned simulator, assets, controller,
encoder and transport repositories. The optional frozen Repose V9.3 planner
will ship separately as [sledgehammer](https://github.com/drcl-deploy/sledgehammer).

This checkout is under staged release migration. The one-command installer and
final tracker quick start are not yet implemented. Phase 1 and the automated
camera/scene parity fixes are complete; Phases 2–6 remain. Current evidence, build
instructions and remaining gates are in [the migration record](docs/migration.md).

## Sources

With Git, Git LFS, Python 3 with PyYAML, and vcstool installed:

```bash
git clone https://github.com/drcl-deploy/vibe_ws.git
cd vibe_ws
python3 scripts/sources.py import
python3 scripts/sources.py check
```

`sources.repos` pins exact commits. Import creates missing repositories and
refuses changed or mismatched existing checkouts; it never resets local work.
Unitree ROS interfaces are inherited from the tested Unitree workspace in this
repository's history. Child implementations remain in their own repositories.

## Layout

```text
assets/                         simulation objects and scene-generation tools
unitree_mujoco/                  simulator and G1 model
cyclonedds_ws/src/
  unitree/                      Unitree ROS messages (tracked here)
  cpp_control/                  tracker and controller
  vision_encoders/              CUDA vision encoder
  cdr_tcp_bridge/               optional onboard/offboard telemetry
  sledgehammer/                 reserved for planner extraction
artifacts/                      local ONNX exports and processed data
generated/                      generated object models and scenes
profiles/                       sim, onboard and offboard environments
```

## Environment after building

```bash
source setup_local.sh
```

Simulation uses DDS domain 1 and loopback. `VIBE_ASSET_ROOT` points at
`artifacts/`; `VIBE_ARTIFACT_ROOT` optionally selects another artifact root.
The environment script prints resolved addresses and paths.

Onboard/offboard environment profiles are explicit, but hardware validation is
still pending:

```bash
export VIBE_ROBOT_INTERFACE=enp3s0  # replace with the actual robot interface
source setup.sh onboard

# On the offboard machine:
export VIBE_ROBOT_HOST=192.168.123.10  # replace with the actual onboard host
source setup.sh offboard
```

The main release target is tracker deployment. Dodge-specific simulation is
deferred; controller support remains available. The legacy combined V9.3
launch remains the migration regression until planner extraction is validated.
