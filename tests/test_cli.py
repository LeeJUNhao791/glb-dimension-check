import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_glb.py"


class CheckGLB(unittest.TestCase):
    def run_cli(self, path, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(path), *args],
            capture_output=True, text=True, check=False,
        )

    def run_modified_box(self, edit, *args):
        raw = (ROOT / "examples/correct.glb").read_bytes()
        (length,) = struct.unpack_from("<I", raw, 12)
        json_end = 20 + length
        model = json.loads(raw[20:json_end])
        edit(model)
        metadata = json.dumps(model).encode()
        metadata += b" " * (-len(metadata) % 4)
        chunks = struct.pack("<I4s", len(metadata), b"JSON") + metadata + raw[json_end:]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "box.glb"
            path.write_bytes(struct.pack("<4sII", b"glTF", 2, 12 + len(chunks)) + chunks)
            return self.run_cli(path, *args)

    def test_correct_dimensions(self):
        result = self.run_cli(ROOT / "examples/correct.glb", "--expected-mm", "120", "80", "40")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "pass")
        self.assertNotIn("diagnosis", report)
        for axis, expected in zip("xyz", (120, 80, 40)):
            self.assertAlmostEqual(report["dimensions_mm"][axis], expected, places=4)

    def test_scale_error(self):
        result = self.run_cli(ROOT / "examples/1000x-too-large.glb", "--expected-mm", "120", "80", "40")
        self.assertEqual(result.returncode, 1, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "fail")
        self.assertAlmostEqual(report["dimensions_mm"]["x"], 120000, places=2)
        self.assertAlmostEqual(report["deviation_mm"]["x"], 119880, places=2)
        self.assertEqual(report["diagnosis"]["type"], "unit_scale")
        self.assertEqual(report["diagnosis"]["scale_factor"], 1000)
        self.assertEqual(report["diagnosis"]["out_of_tolerance_axes"], ["x", "y", "z"])

    def test_inverse_scale_error(self):
        result = self.run_cli(ROOT / "examples/correct.glb", "--expected-mm", "120000", "80000", "40000")
        self.assertEqual(result.returncode, 1, result.stderr)
        diagnosis = json.loads(result.stdout)["diagnosis"]
        self.assertEqual(diagnosis["type"], "unit_scale")
        self.assertEqual(diagnosis["scale_factor"], 0.001)

    def test_swapped_axes_still_fail(self):
        def rotate_box(model):
            model["nodes"][0]["rotation"] = [0, 0, 2 ** -0.5, 2 ** -0.5]

        result = self.run_modified_box(rotate_box, "--expected-mm", "120", "80", "40")
        self.assertEqual(result.returncode, 1, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["diagnosis"]["type"], "axis_permutation")
        self.assertEqual(report["diagnosis"]["out_of_tolerance_axes"], ["x", "y"])
        self.assertEqual(report["diagnosis"]["axis_mapping"], {"x": "y", "y": "x", "z": "z"})

    def test_single_axis_out_of_tolerance(self):
        result = self.run_cli(ROOT / "examples/correct.glb", "--expected-mm", "110", "80", "40")
        self.assertEqual(result.returncode, 1, result.stderr)
        diagnosis = json.loads(result.stdout)["diagnosis"]
        self.assertEqual(diagnosis["type"], "axis_mismatch")
        self.assertEqual(diagnosis["out_of_tolerance_axes"], ["x"])
        self.assertNotIn("scale_factor", diagnosis)
        self.assertNotIn("axis_mapping", diagnosis)

    def test_required_unlit_material_does_not_change_dimensions(self):
        extension = "KHR_materials_unlit"

        def add_unlit_material(model):
            model["extensionsUsed"] = [extension]
            model["extensionsRequired"] = [extension]
            model["materials"] = [{"extensions": {extension: {}}}]
            model["meshes"][0]["primitives"][0]["material"] = 0

        baseline = self.run_cli(ROOT / "examples/correct.glb")
        self.assertEqual(baseline.returncode, 0, baseline.stderr)
        result = self.run_modified_box(add_unlit_material)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), json.loads(baseline.stdout))

    def test_geometry_extension_remains_unsupported(self):
        def mark_draco(model):
            model["extensionsUsed"] = ["KHR_draco_mesh_compression"]

        result = self.run_modified_box(mark_draco)
        self.assertEqual(result.returncode, 2)
        self.assertIn("KHR_draco_mesh_compression", result.stderr)

    def test_other_required_material_extension_remains_unsupported(self):
        extension = "KHR_materials_clearcoat"

        def add_clearcoat_material(model):
            model["extensionsUsed"] = [extension]
            model["extensionsRequired"] = [extension]
            model["materials"] = [{"extensions": {extension: {}}}]
            model["meshes"][0]["primitives"][0]["material"] = 0

        result = self.run_modified_box(add_clearcoat_material)
        self.assertEqual(result.returncode, 2)
        self.assertIn(extension, result.stderr)

    def test_measure_only_uses_transformed_referenced_vertices(self):
        result = self.run_cli(ROOT / "examples/measure-only.glb")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "measured")
        self.assertNotIn("diagnosis", report)
        for axis, expected in zip("xyz", (141.421356, 70.710678, 40)):
            self.assertAlmostEqual(report["dimensions_mm"][axis], expected, places=4)

    def test_unsupported_extension(self):
        result = self.run_cli("example.obj")
        self.assertEqual(result.returncode, 2)
        self.assertIn("static .glb", result.stderr)

    def test_invalid_container(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.glb"
            path.write_bytes(b"glTF")
            result = self.run_cli(path)
        self.assertEqual(result.returncode, 2)
        self.assertIn("GLB header", result.stderr)


if __name__ == "__main__":
    unittest.main()
