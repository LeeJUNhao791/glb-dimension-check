"""Check the STL and Y-up GLB exports against one CAD-axis dimension contract."""

import argparse
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile


CHECKERS = Path(__file__).resolve().parent / "checkers"
STL_CHECKER = CHECKERS / "mesh-guard" / "scripts" / "check_stl.mjs"
GLB_CHECKER = CHECKERS / "glb-dimension-check" / "scripts" / "check_glb.py"
STATUS = ("pass", "fail", "invalid")


def check_asset(asset, command):
    try:
        result = subprocess.run(command, capture_output=True, encoding="utf-8", errors="replace")
    except OSError as error:
        return {**asset, "status": "invalid", "error": str(error)}

    try:
        raw = json.loads(result.stdout)
    except (ValueError, RecursionError):
        raw = {}
    if result.returncode not in (0, 1) or raw.get("status") != STATUS[result.returncode]:
        error = raw.get("error") or result.stderr.strip()
        return {
            **asset, "status": "invalid",
            "error": error.splitlines()[-1] if error else f"Unexpected checker response (exit {result.returncode}).",
        }

    axes = asset["source_axes"]
    child_within = raw.get("within_tolerance")
    if child_within is None:
        child_failed = raw.get("diagnosis", {}).get("out_of_tolerance_axes", [])
        child_within = {axis: axis not in child_failed for axis in "xyz"}
    within = {axis: child_within[source] for axis, source in axes.items()}
    return {
        **asset, "status": raw["status"],
        "dimensions_mm": {axis: raw["dimensions_mm"][source] for axis, source in axes.items()},
        "deviation_mm": {axis: raw["deviation_mm"][source] for axis, source in axes.items()},
        "within_tolerance": within,
        "out_of_tolerance_axes": [axis for axis, passed in within.items() if not passed],
    }


def aggregate(args):
    stl = {
        "file": args.stl, "role": "manufacturing_mesh", "coordinate_unit": args.stl_unit,
        "source_axes": dict(zip("xyz", "xyz")),
    }
    glb = {
        "file": args.glb, "role": "preview_asset", "coordinate_unit": "m",
        "source_axes": dict(zip("xyz", "xzy")),
    }
    report = {"contract": args.expect, "axis_frame": "cad", "assets": {"stl": stl, "glb": glb}}
    with tempfile.TemporaryDirectory() as directory:
        contract = Path(directory) / "expected.json"
        try:
            # Both measurements use the same snapshot of the user's contract.
            contract.write_bytes(Path(args.expect).read_bytes())
            read_expectation = runpy.run_path(str(GLB_CHECKER))["read_expectation"]
            expected, tolerance = read_expectation(contract)
        except (OSError, ValueError, RecursionError) as error:
            for asset in report["assets"].values():
                asset.update(status="invalid", error="Dimension contract could not be read.")
            return 2, {**report, "status": "invalid", "error": str(error)}

        report["expected_mm"] = dict(zip("xyz", expected))
        report["tolerance_mm"] = tolerance
        report["assets"]["stl"] = check_asset(stl, [
            "node", str(STL_CHECKER), "--unit", args.stl_unit, "--expect", str(contract),
            "--", args.stl,
        ])
        # glTF rotates CAD +Y to GLB -Z. Spans are unchanged by the sign.
        x, y, z = expected
        report["assets"]["glb"] = check_asset(glb, [
            sys.executable, str(GLB_CHECKER), "--expected-mm", str(x), str(z), str(y),
            "--tolerance-mm", str(tolerance), "--", args.glb,
        ])

    code = max(STATUS.index(asset["status"]) for asset in report["assets"].values())
    return code, {**report, "status": STATUS[code]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expect", required=True, help="JSON dimension contract in CAD X/Y/Z and mm.")
    parser.add_argument("--stl", required=True, help="Z-up STL exported in CAD axes.")
    parser.add_argument("--stl-unit", required=True, choices=("mm", "m"), help="STL coordinate unit.")
    parser.add_argument("--glb", required=True, help="Y-up GLB exported in meters from Z-up CAD.")
    code, report = aggregate(parser.parse_args())
    print(json.dumps(report, indent=2, allow_nan=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
