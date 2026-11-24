# Mesh Guard mounting plate trial

This original mounting plate was designed for a downstream GitHub Actions trial. [Drawing MP-001 Rev A](drawing.svg) defines the overall X/Y/Z dimensions as 64 × 40 × 6 mm, with ±0.20 mm on each axis. [expected.json](expected.json) records those drawing dimensions. The STL export uses millimetre coordinates.

The plate has four through holes and a central clearance opening. Mesh Guard checks the axis-aligned outer dimensions. The hole diameters, positions and opening dimensions are additional drawing features outside this check's scope.

The first PR run uses the nominal export. The second run changes only the plate's X dimension to 65 mm while retaining the same workflow, units, drawing and expectation file. The comparison step should fail and the workflow should still upload its JSON report.

Install `cadquery-ocp-novtk==8.0.1.1.0` and run `python examples/mesh-guard-mounting-plate/mounting_plate.py` from the repository root to regenerate the STEP and STL in this directory.
