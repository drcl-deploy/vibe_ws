# curb_111/level_0.00 — build sheet

`Vibe-PerLoco-Grail-AdaptSonic-ImgFeat-Ext` · grid row 0 col 4 · frame `start`

**Stand the robot at (0, 0), pelvis 782 mm up, facing +X, then start the controller.** SONIC has no global root state — the reference is replayed relative to wherever the robot is when tracking begins — so this pose IS the datum and the tile origin is a number the policy never sees.

The terrain is placed on the clips' MEAN start pose. Per clip the true start deviates by up to **14.8°** — over a 1.5 m course that is metres of lateral error, so either mark one start footprint per clip from the table below, or re-export with `--anchor-clip <name>` for the one you are running.

| clip | start X (mm) | start Y (mm) | start yaw (deg) |
|---|---:|---:|---:|
| `sample0` | -102 | +22 | +14.8 |
| `sample1` | -156 | +37 | -0.9 |
| `sample2` | +53 | +20 | -0.6 |
| `sample3` | +41 | +19 | -3.8 |
| `sample4` | +54 | +18 | -3.8 |
| `sample5` | -71 | -64 | -14.0 |
| `sample6` | +40 | -22 | +6.5 |
| `sample7` | +152 | -47 | -2.7 |
| `sample8` | -11 | +17 | +4.5 |

z=0 is the ground and every part sits ON it (base z = 0). Millimetres. The robot walks **+X**; parts are listed in the order it meets them.

## cut list

| part | cut L x W x H | as-built @5mm | centre X | centre Y | yaw deg | top |
|---|---|---|---:|---:|---:|---:|
| #0 | 486 x 1200 x 232 | 485 x 1200 x 230 | 879 | 211 | +1.30 | 232 |
| #1 | 230 x 1200 x 141 | 230 x 1200 x 140 | 1435 | 61 | +1.30 | 141 |

- course length (along +X): **922 mm** · width to clear (across): **1232 mm**
- clear gaps between parts: 205 mm
- `render_z_scale` = None
- dropped: nothing

## elevation

```
#######################################
#######################################
#######################################                ###################
#######################################                ###################
#######################################                ###################
----------------------------------------------------------------------------
+0.62                                                                 +1.55
robot walks +X (left to right), m
```

## notes

- Colour is free: training randomizes terrain hue every run (`vibe.core.env_cfgs.apply_render_domain`). The one constraint that carries to reality is that the parts stay visually SEPARABLE from the ground.
- Yaw names the part's SHORT axis (`orcs...terrain_spec.box_from_vertices` picks the short edge as local X), so the long axis sits at yaw + 90 deg.
- Provenance: `data/terrain_motions/grail/curb_111/level_0.00`
