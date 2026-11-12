import json
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

    def test_correct_dimensions(self):
        result = self.run_cli(ROOT / "examples/correct.glb", "--expected-mm", "120", "80", "40")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "pass")
        for axis, expected in zip("xyz", (120, 80, 40)):
            self.assertAlmostEqual(report["dimensions_mm"][axis], expected, places=4)

    def test_scale_error(self):
        result = self.run_cli(ROOT / "examples/1000x-too-large.glb", "--expected-mm", "120", "80", "40")
        self.assertEqual(result.returncode, 1, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "fail")
        self.assertAlmostEqual(report["dimensions_mm"]["x"], 120000, places=2)
        self.assertAlmostEqual(report["deviation_mm"]["x"], 119880, places=2)

    def test_measure_only_uses_transformed_referenced_vertices(self):
        result = self.run_cli(ROOT / "examples/measure-only.glb")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "measured")
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
