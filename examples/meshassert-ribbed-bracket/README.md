# MeshAssert CAD export verification

RB-001 Rev A is a self-authored L-bracket with one triangular reinforcing rib and one horizontal through-bore. The drawing datum is the lower rear-left corner. All dimensions are in millimetres.

| CAD axis | Drawing dimension | Nominal span |
| --- | --- | ---: |
| X | Width from left to right | 57 mm |
| Y | Depth from rear to front | 29 mm |
| Z | Height from base to top of upright | 35 mm |

The acceptance tolerance is ±0.15 mm on each overall span. The base is 5 mm thick and the rear upright extends 6 mm along Y. The 8 mm through-bore runs along Y at X = 35 mm and Z = 23 mm. The rib extends along X from 7 to 12 mm. Its profile is defined in [the CAD source](fixtures/ribbed_bracket.py). MeshAssert measures overall spans. Geometry features are specified here for identification.

OpenCascade writes [STEP](fixtures/ribbed_bracket.step) and a Z-up [STL](fixtures/ribbed_bracket.stl) in millimetres. It exports the [nominal GLB](fixtures/ribbed_bracket.glb) from a separate copy of the CAD solid in Y-up axes and metres. The [taller GLB](fixtures/ribbed_bracket_tall.glb) comes from raising the upright to 37 mm before export. Both cases use the same STL and [drawing contract](fixtures/expected.json). GLB coordinates are mapped from X/Z/Y spans to CAD X/Y/Z.

## Run the check

From this directory, with Python 3.11 and Node.js 22:

~~~sh
python -B meshassert.py --expect fixtures/expected.json --stl fixtures/ribbed_bracket.stl --stl-unit mm --glb fixtures/ribbed_bracket.glb
python -B meshassert.py --expect fixtures/expected.json --stl fixtures/ribbed_bracket.stl --stl-unit mm --glb fixtures/ribbed_bracket_tall.glb
~~~

The first command exits 0 and both assets pass. The second exits 1 and reports only CAD Z outside tolerance for the taller GLB. The STL still passes. The branch workflow runs both commands as separate jobs and uploads each JSON report even when the check fails. The negative job intentionally fails the workflow.

Regenerate the files with Python 3.11 and the pinned OpenCascade bindings:

~~~sh
uv run --python 3.11 --with cadquery-ocp-novtk==8.0.1.1.0 python fixtures/ribbed_bracket.py
~~~

## Checker provenance

The MeshAssert adapter is copied verbatim from the mounting plate pilot. Its checker copies retain the original MIT notices.

- Mesh Guard measurement module and STL CLI at [811a795e0f382cde7e89a2c887b292aec64d4529](https://github.com/LeeJUNhao791/mesh-guard/tree/811a795e0f382cde7e89a2c887b292aec64d4529). [MIT license](checkers/mesh-guard/LICENSE)
- GLB Dimension Check CLI at [18ceb7485c43fde4f16a3ac1b394dfd29a9db105](https://github.com/LeeJUNhao791/glb-dimension-check/tree/18ceb7485c43fde4f16a3ac1b394dfd29a9db105). [MIT license](checkers/glb-dimension-check/LICENSE)
