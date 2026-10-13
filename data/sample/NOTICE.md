# Sample provenance

The frozen files were extracted from the internal ViBe data/asset checkouts at the
revisions recorded in `samples.json`. Paths there retain the original dataset
identities. Motion arrays are unchanged; machine-local XML mesh paths and terrain
provenance paths were made portable.

- `walk`: [GRAIL](https://huggingface.co/datasets/nvidia/PhysicalAI-Robotics-Locomanipulation-GRAIL/blob/main/README.md)
  terrain-curb reference and ViBe's exported `curb_111` build sheet. The upstream
  card lists CC BY-NC 4.0 for these original trajectories/procedural terrains.
- `parkour`: [OmniRetarget](https://huggingface.co/datasets/omniretarget/OmniRetarget_Dataset/blob/main/README.md)
  robot-terrain reference and ViBe's exported `climb_16` build sheet. The dataset
  card lists MIT; this clip comes from its in-house robot-terrain subset.
- `repose`: custom cube-frontflip reference and the tested native scene, extracted
  from the internal `assets` generator.
- `uolm`: [OMOMO](https://github.com/lijiaman/omomo_release)-derived suitcase
  reference, visual mesh and convex decomposition;
  material/texture and object XML copied from the internal `assets` output.

`LICENSE.assets` preserves the assets project's original-code license. Third-party
motions, meshes and textures retain their upstream terms; that license does not
relicense them. The upstream assets notice does not yet document the redistribution
terms of the OMOMO family. Resolve that provenance record before publishing the
new sample bundle; local build and testing do not publish these files.
