# ViBe export compatibility

The training/export reference is [lok-i/vibe](https://github.com/lok-i/vibe).
Deployment does not import the training environment or the internal `assets`
package. The four frozen examples in `data/sample/` are sufficient to construct
their native simulator scenes.

## exports

`artifacts/` is a storage root. Keep ONNX and `.manifest.json` pairs unchanged:
input ports, joint order, history, action scaling and encoder preprocessing come
from the exporter. Absolute paths are supported; the directory name is not an
export contract.

`artifacts.lock.json` pins the HF revision, paths and hashes of four policy pairs
and the shared encoder pair. Setup downloads those exact bytes into `artifacts/`,
using `models/<sample>/policy.onnx` and `policy.manifest.json` locally. Original
checkpoint filenames remain in the HF paths; model and manifest contents are unchanged.
Their source checkpoints match ViBe's v0.1.0 release; the four ONNX exports retain
their historical exporter revisions. They have passed ONNX/manifest checks,
encoder shape checks and native C++ inference. A fresh public-export numerical
and closed-loop check has not been rerun for these four files.

The older PerLoco `AdaptSonic` task names are accepted by the tracker. The sample
names `walk` and `parkour` do not change these task IDs. All four samples use
112×63 images and the same Theia-tiny encoder. Dodge's separate 112×64 export
remains optional and has no packaged sample environment.

## scenes and references

`data/sample/samples.json` records source revisions, reference identities, start
placement, policy paths and hashes. Motion arrays and contact/object sidecars are
copied unchanged. Terrain dimensions are unchanged; Grail uses sample0's offset
and heading within the exported terrain frame. UoLM keeps its canonical object
frame because the policy consumes the clip-final object goal in that frame.

The checked-in cube scene retains mass 0.62369 kg, inertia 0.0386285, native
contacts and the six-color palette. The robot comes from the pinned Unitree model
with a 42.5 degree camera. Native 2 ms Euler integration is deliberate: copying
the training simulator's timestep previously caused unstable SDK damping.

The Repose clip scene starts from the reference's object pose. The planner scene
retains its separate tested start and frozen data in `sledgehammer`; it does not
read the old `artifacts/data/` dataset.

File hashes establish byte identity. Scene/damping comparisons protect the native
baseline. Neither establishes complete training/native closed-loop equivalence.
See [testing](testing.md) and the earlier [parity audit](parity.md).
