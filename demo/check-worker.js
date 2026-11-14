const runtimeURL = "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs";
let checker;

async function loadChecker() {
  const [{ loadPyodide }, response] = await Promise.all([
    import(runtimeURL),
    fetch("../scripts/check_glb.py"),
  ]);
  if (!response.ok) throw new Error("The Python checker could not be loaded.");
  const pyodide = await loadPyodide();
  pyodide.FS.writeFile("check_glb.py", await response.text());
  const run = pyodide.runPython(`
import io
import json
import sys
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from check_glb import main

def check(x, y, z, tolerance):
    output, errors = io.StringIO(), io.StringIO()
    sys.argv = ["check_glb.py", "input.glb", "--expected-mm", x, y, z,
                "--tolerance-mm", tolerance, "--svg", "result.svg"]
    try:
        with redirect_stdout(output), redirect_stderr(errors):
            code = main()
    except SystemExit as error:
        code = error.code
    if code == 2:
        return json.dumps({"error": errors.getvalue().strip()})
    return json.dumps({
        "result": json.loads(output.getvalue()),
        "svg": Path("result.svg").read_text(encoding="utf-8"),
    })

check
`);
  return { pyodide, run };
}

self.onmessage = async ({ data: { bytes, values } }) => {
  checker ??= loadChecker().catch(() => {
    checker = undefined;
    throw new Error("The Python runtime could not load. Check your connection to jsDelivr and try again.");
  });
  try {
    const { pyodide, run } = await checker;
    pyodide.FS.writeFile("input.glb", new Uint8Array(bytes));
    try {
      self.postMessage(JSON.parse(run(...values)));
    } finally {
      pyodide.FS.unlink("input.glb");
      if (pyodide.FS.analyzePath("result.svg").exists) pyodide.FS.unlink("result.svg");
    }
  } catch (error) {
    self.postMessage({ error: error.message });
  }
};
