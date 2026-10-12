# Public ViBe compatibility

The training/export reference is [lok-i/vibe](https://github.com/lok-i/vibe),
commit `ed4ee6c581af9a7effcb53ee219d10784a839ca3`. A separate reference checkout
is at `~/drcl_projects/vibe`; deployment must not import that Python environment
or depend on that local directory. The revision is an audit reference, not a
runtime source in `sources.repos`.

## Artifact boundary

`artifacts/` is a storage root. Copy the exporter outputs unchanged, retaining
the `.onnx` and matching `.manifest.json` pair. Public ViBe permits an explicit
export output directory; its default `exports/` name is not a runtime contract.
Do not rewrite the embedded manifests, input ports, history layout, joint order,
action scaling, or encoder preprocessing to accommodate deployment paths.

`artifacts.lock.json` hashes the current V9.3 migration snapshot. It does not
claim those files were exported by the public revision above. Their embedded
producer revisions are `902a211` (policy) and `4d92bf0` (encoder). A future
published bundle must record the checkpoint hash, exporter/dependency revisions,
export options, output hashes and parity verdict. Re-exporting the same weights
need not produce byte-identical ONNX files: provenance metadata also changes.

The public Repose release manifest names the same source run `vbp/repose/011pgzbh`
and checkpoint iteration 59999. That identity alone does not establish equality
between a fresh public export and the frozen deployment ONNX.

The optional planner's complete NPZ payload now belongs to `sledgehammer`.
V9.3 uses its installed baked frames. Phase 5 restored missing contact sidecars
from the relocation inputs and verified all four arrays byte-for-byte against
the Phase 0 snapshot; see [testing.md](testing.md#parity).

## Checks performed on the frozen snapshot

- All 63 entries in `artifacts.lock.json` match SHA-256 and include actual local
  copies of all 56 required retargeted motion files.
- Both ONNX files pass the ONNX checker and embedded/sidecar manifest equality.
- Public `src/vibe/export/agent/onnx_agent.py` loads the existing policy directly
  with CPU ONNX Runtime. Its seven ports satisfy shape/term-width checks; seeded
  input buffers survive term assembly exactly; actions and joint targets are finite.
- The encoder accepts BGR HWC uint8 `[1,63,112,3]`, emitting finite fp32 patch
  tokens `[1,21,192]` and CLS `[1,192]`, matching the public export contract.

These checks establish artifact/loader compatibility, not checkpoint-to-ONNX
numerical equivalence, complete C++ observation equivalence, or closed-loop parity.

## Differences found in the Phase 1 snapshot

The camera, cube and encoder issues below have since received local fixes;
see [parity.md](parity.md) for exact checks and remaining limits. The public
clone now carries a local correction to `BIG_CUBE_MASS = 0.62369`; the
published reference at `ed4ee6c` still says 1.5 kg until that fix is published.

| Area | Public reference | Frozen deployment baseline |
|---|---|---|
| Head camera | 112 x 63, vertical FOV 42.5 degrees | 640 x 480, vertical FOV 42.5 degrees, then resize |
| Camera pose | quaternion rounded to `(0.6533,0.2706,-0.2706,-0.6533)` | more precise quaternion; not byte-identical |
| Rendering | explicit geometry groups 0/2, shadows disabled | default MuJoCo visualization options |
| Big cube | primitive collider, mass 1.5 kg, six colored shell geoms | mass 0.62369 kg, colored cube-map material |
| Assets revision | `90e226008bda5edc9c07ca3eb69f9f79c4603de1` | `cc719481812cb6a5ba4c3299b36b7397314c3712` |
| Motion dataset | `e635ed670162c8b4cc91dd6247d4f3b47368ab3c` | same revision |

Resizing a 4:3 render to 16:9 does not restore the horizontal field of view of
the training camera. Match projection, preprocessing, rendering and scene physics
explicitly before claiming simulation compatibility. The public assets pin alone
does not fix Repose: public Repose constructs its colored cube in
`src/vibe/assets/repose.py`, while that assets revision's generic cube is wood.

First finish the relocated V9.3 baseline; then compare a public export and the
deployment node on identical recorded observations, histories, reference frames
and images. Compare actions and final joint targets using recorded provider,
precision and tolerances. Run the public exporter's two-world gate and the fixed
operator regression after aligning scene/camera behavior. Keep those changes in
a separate checkpoint so relocation regressions remain distinguishable.

Exact file bytes are enforceable with hashes. Literal bit-for-bit trajectories
across different simulators/providers are not a defensible release promise:
public ViBe's `docs/export.md` itself notes MuJoCo Warp nondeterminism and FSQ
token sensitivity. Record numerical tolerances and observed behavior separately.
