# GLB Dimension Check

Measure the real-world dimensions encoded in a static GLB. Compare the scene's
X, Y, and Z dimensions with your reference measurements to catch scale mistakes
before handing off a model for web 3D or AR.

静态 GLB 尺寸验收工具。读取场景的 X、Y、Z 轴尺寸，按毫米与预期尺寸比较。

## Quick start

Use Python 3.8 or newer. The script uses only the Python standard library.

```sh
python scripts/check_glb.py examples/correct.glb --expected-mm 120 80 40
```

Use `--expected-mm X Y Z` in scene-axis order. The check passes when all three
axes are within `--tolerance-mm`, which defaults to 0.1 mm. The JSON report
includes measured dimensions, expected dimensions, and signed deviations in
millimeters. Omit `--expected-mm` to measure only.

| Exit code | Meaning |
| --- | --- |
| 0 | `pass` or `measured` |
| 1 | `fail`. At least one axis exceeded the tolerance. |
| 2 | Unsupported input, invalid geometry, or command-line error. |

## Three reproducible examples

```sh
python scripts/check_glb.py examples/correct.glb --expected-mm 120 80 40
python scripts/check_glb.py examples/1000x-too-large.glb --expected-mm 120 80 40
python scripts/check_glb.py examples/measure-only.glb
```

| Example | Expected result |
| --- | --- |
| [correct.glb](examples/correct.glb) | `pass`. Approximately 120 × 80 × 40 mm. |
| [1000x-too-large.glb](examples/1000x-too-large.glb) | `fail`. A parent scale of 1000 produces approximately 120,000 × 80,000 × 40,000 mm. |
| [measure-only.glb](examples/measure-only.glb) | `measured`. A rotated triangle produces approximately 141.421 × 70.711 × 40 mm. An unreferenced vertex in the position buffer does not affect the result. |

Regenerate the included GLB files with `python examples/generate.py`. Run the
CLI checks with `python -B -m unittest discover -s tests -v`.

## Supported inputs

The script accepts static GLB 2.0 files with a single embedded binary buffer and
standard float32 vertex positions. It reads the default scene, or the first
scene when the file has no default. It applies parent and child transforms,
including matrix and translation/rotation/scale transforms. It measures the
world-axis extent of the mesh vertices used by the scene. A rotated model's
measured envelope may differ from its drawing dimensions.

Animations, skinning, morph targets, compressed or quantized geometry, and
required glTF extensions are outside this version's scope. For other formats
such as separate `.gltf`, OBJ, FBX, STL, and STEP, export a static GLB first
and verify the export units.

## Use as an Agent Skill

Clone or copy this repository into a skill directory named
`glb-dimension-check`. An [Agent Skills](https://agentskills.io/specification)
client can load [SKILL.md](SKILL.md). Try asking it to check a GLB against
120 × 80 × 40 mm in X/Y/Z order.

The unit conversion follows the
[glTF 2.0 specification](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#coordinate-system-and-units).

## License

[MIT](LICENSE)
