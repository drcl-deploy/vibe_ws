# climb_16/level_1.00 — build sheet

`Vibe-PerLoco-OmRe-AdaptSonic-ImgFeat-Ext` · grid row 0 col 0 · frame `start`

**Stand the robot at (0, 0), pelvis 860 mm up, facing +X, then start the controller.** SONIC has no global root state — the reference is replayed relative to wherever the robot is when tracking begins — so this pose IS the datum and the tile origin is a number the policy never sees.

z=0 is the ground and every part sits ON it (base z = 0). Millimetres. The robot walks **+X**; parts are listed in the order it meets them.

## cut list

| part | cut L x W x H | as-built @5mm | centre X | centre Y | yaw deg | top |
|---|---|---|---:|---:|---:|---:|
| #1 | 3708 x 3708 x 56 | 3710 x 3710 x 55 | 1694 | -123 | -26.25 | 56 |
| #0 | 704 x 1187 x 356 | 705 x 1185 x 355 | 1912 | 59 | +168.21 | 356 |

- course length (along +X): **2537 mm** · width to clear (across): **4781 mm**
- clear gaps between parts: overlap mm
- `render_z_scale` = 0.75  — obstacle height is PINNED here and does NOT follow the level row; build the number in this table, never the clip's own z_scale.
- dropped: nothing

## elevation

```
                                                     #####################
                                                     #####################
                                                     #####################
                                                     #####################
                                                     #####################
                                                     #####################
############################################################################
----------------------------------------------------------------------------
-0.28                                                                 +2.25
robot walks +X (left to right), m
```

## notes

- Colour is free: training randomizes terrain hue every run (`vibe.core.env_cfgs.apply_render_domain`). The one constraint that carries to reality is that the parts stay visually SEPARABLE from the ground.
- Yaw names the part's SHORT axis (`orcs...terrain_spec.box_from_vertices` picks the short edge as local X), so the long axis sits at yaw + 90 deg.
- Provenance: `data/terrain_motions/omni/climb_16/level_1.00`
