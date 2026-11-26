# Contributing

Keep each change focused and describe what changes for a user. For a bug,
include a synthetic or redistributable GLB, the command, expected result, and
actual result. Include the reference X/Y/Z dimensions, units, and tolerance
when reporting a dimension mismatch.

## Setup and checks

Use Python 3.8 or newer; the CLI and tests use only the standard library.
Run from the repository root:

```sh
python -B -m unittest discover -s tests -v
```

CI runs this suite on Python 3.8 and 3.14. For a CLI or measurement change,
also run these sample commands separately and record their exit codes:

```sh
python scripts/check_glb.py examples/correct.glb --expect examples/expected.json
python scripts/check_glb.py examples/1000x-too-large.glb --expect examples/expected.json
python scripts/check_glb.py examples/measure-only.glb
```

Expect `pass` / exit `0`, `fail` / exit `1` with a `unit_scale` diagnosis, and
`measured` / exit `0`, respectively. Invalid inputs return exit `2`.

For browser changes, follow the [browser demo steps](README.md#browser-demo)
with both built-in samples. Check expectation import and SVG/JSON downloads
against the CLI report. Record browser checks separately from the test suite.

## Dimension-checking scope

The checker measures the world-axis extent of vertices used by a static GLB
scene after node transforms, converting meters to millimeters. Reference
dimensions follow the exported GLB X/Y/Z order; rotation can change its bounds.
See [Supported inputs](README.md#supported-inputs) for format restrictions.

Keep measurement, tolerance comparison, and diagnostic hints distinct. A hint
does not repair the model, and a passing extent check does not verify internal
features, mesh quality, manufacturing accuracy, or AR behavior. Add a focused
regression test when changing parsing or measurement behavior, and report the
checks you actually ran in the pull request.
