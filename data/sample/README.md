# samples

One fixed example per policy. These files arrive with the Git checkout; no
training checkout or `assets` package is required.

| Folder | Source reference | Scene |
|---|---|---|
| `walk` | Grail `curb_111/level_0.00/sample0` | Two curbs, robot at sample0's recorded offset/yaw |
| `parkour` | OmniRetarget `climb_16/level_1.00/sample0` | Climb from the 56 mm deck |
| `repose` | `custom/cube_frontflip/sample3` | Double frontflip; cube 1 m ahead |
| `uolm` | OMOMO `sub1_suitcase_010/sample1` | Suitcase with the original convex decomposition |

`motion.npz` is the reference. Keep `contact_matrix.npz` and `object_motion.npz`
beside it where provided. PerLoco's two references have no object-contact sidecars.
The Repose and UoLM sidecars carry real contacts and object trajectories.

```bash
python3 scripts/scenes.py  # from the workspace root
```

Each `scene.xml` is an input to this setup step. Run the generated
`generated/<sample>/scene.xml` with the simulator. Robot meshes come from
`unitree_mujoco`, and all other required geometry is included here.
The script prints the resolved scene and reference paths.

The terrain XML and dimensions match the exported build sheets. Grail's sheet
lists nine starts; this example uses sample0, not their mean. OmRe includes its
starting deck. The sheets also list rounded construction dimensions; the simulator
uses the exact exported geometry, not the rounded column.

The standalone and planner scenes both start the cube 1 m ahead, blue up.
The sample retains its original object sidecar. The planner uses
`generated/repose/g1_repose.xml` and its own library in `sledgehammer`.

To adapt an example, replace its motion and required sidecars together, supply the
matching geometry/start pose in `samples.json`, and regenerate. That file records
the original source revisions and SHA-256 hashes; update them deliberately when
changing a sample. Policy/encoder files belong in `artifacts/`.

See [NOTICE.md](NOTICE.md) for sources. The selected Grail clip is a release
example; which of the nine clips was used in the earlier hardware trial is unknown.
