# Workspace migration guidelines

- Work in this workspace. Do not modify `/home/loki/unitree_ros2` during migration.
- `sources.repos` pins independent repositories. Commit module changes from
  their own repository; never absorb their source trees into the root commit.
- The Repose tracker remains in `cpp_control`; only its planner moves to
  `sledgehammer`. Preserve V9.3 behavior during extraction.
- Keep downloaded models/data in ignored `artifacts/`, generated scenes in
  `$XDG_DATA_HOME/vibe/scenes/` (default `~/.local/share/vibe/scenes/`) with an ignored
  `generated` symlink per checkout, and local migration evidence in ignored `.migration/`.
- Preserve ROS Foxy/Humble compatibility, snake_case ROS topics/YAML keys,
  two-space C++ indentation and the inherited formatting conventions.
- Use focused colcon builds/tests. Run the V9.3 regression after each phase;
  distinguish automated validation from the operator joystick gate.
- Hardware-facing changes require an explicit onboard/offboard smoke test,
  including QoS and disconnect behavior, before claiming hardware validation.
- Do not merge compatibility branches or delete development branches unless
  requested. Keep upstream sync and behavioral changes separate from packaging.
- See `docs/migration.md` and `.migration/phase0/PHASE0.md` for phase boundaries,
  baseline details and known lint failures. Do not silently waive pending gates.
