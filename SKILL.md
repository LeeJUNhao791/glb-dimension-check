---
name: glb-dimension-check
description: Measure static GLB 2.0 model dimensions and compare them with expected real-world dimensions. Use for physical scale checks, asset handoffs, and suspected Blender or AR export unit errors.
license: MIT
---

# GLB Dimension Check

Run [scripts/check_glb.py](scripts/check_glb.py) on the user's static GLB with
Python 3.8 or newer. Use the absolute path to the script when running from
another directory.

```sh
python scripts/check_glb.py model.glb --expected-mm 120 80 40
```

- Map expected dimensions to the scene's X, Y, and Z axes in millimeters. Ask
  which axis corresponds to each dimension when the order is ambiguous.
- For a measurement without a reference, omit `--expected-mm` and report the
  measured axes. Use `--tolerance-mm` if the user supplies a per-axis tolerance.
  The default is 0.1 mm.
- Read the JSON status and report each measured dimension, its expected value,
  and signed deviation when available. Exit 0 means pass or measurement only.
  Exit 1 means at least one axis exceeds tolerance. Exit 2 means input or usage
  error.
- On a mismatch, report the out-of-tolerance axes in `diagnosis`. Treat
  `unit_scale` and `axis_permutation` as clues about export units or input axis
  order. The check uses the original X/Y/Z order.
- For unsupported inputs, report the script's error and request a static
  GLB 2.0 export with embedded, uncompressed float32 geometry.

The measurement is the scene's world-axis bounding box. It describes the
exported geometry. See [README.md](README.md) for supported inputs and examples.
