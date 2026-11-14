const form = document.querySelector("#check-form");
const controls = document.querySelector("#controls");
const fileInput = document.querySelector("#file");
const dropZone = document.querySelector("#drop-zone");
const status = document.querySelector("#status");
const report = document.querySelector("#report");
const preview = document.querySelector("#preview");
const download = document.querySelector("#download");
let worker;
let svgUrl;

function clearReport(message = "") {
  report.hidden = true;
  if (svgUrl) URL.revokeObjectURL(svgUrl);
  svgUrl = undefined;
  preview.removeAttribute("src");
  download.removeAttribute("href");
  delete status.dataset.result;
  status.textContent = message;
}

function runInWorker(bytes, values) {
  return new Promise((resolve, reject) => {
    worker ??= new Worker("./demo/check-worker.js", { type: "module" });
    worker.onmessage = ({ data }) => {
      if (data.error) reject(new Error(data.error));
      else resolve(data);
    };
    worker.onerror = () => {
      worker.terminate();
      worker = undefined;
      reject(new Error("The browser checker could not start. Reload the page and try again."));
    };
    worker.postMessage({ bytes, values }, [bytes]);
  });
}

async function check(filename, readBytes) {
  if (controls.disabled) return;
  clearReport("Checking " + filename + "…");
  if (!/\.glb$/i.test(filename)) {
    status.dataset.result = "error";
    status.textContent = "Choose a static .glb file.";
    return;
  }
  const values = ["x", "y", "z", "tolerance"].map(name => form.elements[name].value);
  controls.disabled = true;
  try {
    const { result, svg } = await runInWorker(await readBytes(), values);
    const hint = result.diagnosis?.hint;
    status.dataset.result = result.status;
    status.textContent = result.status.toUpperCase() + " · " + filename + (hint ? " · " + hint : "");
    svgUrl = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
    preview.src = svgUrl;
    preview.alt = ["X", "Y", "Z"].map(axis => {
      const key = axis.toLowerCase();
      const actual = Number(result.dimensions_mm[key].toPrecision(7));
      return axis + " measured " + actual + " mm, expected " + result.expected_mm[key] + " mm";
    }).join(". ");
    download.href = svgUrl;
    report.hidden = false;
  } catch (error) {
    status.dataset.result = "error";
    status.textContent = error.message;
  } finally {
    controls.disabled = false;
  }
}

function checkLocal(event) {
  event.preventDefault();
  const file = fileInput.files[0];
  if (file) check(file.name, () => file.arrayBuffer());
  else clearReport("Choose or drop a .glb file, or try a sample.");
}

form.addEventListener("submit", checkLocal);
form.addEventListener("input", () => clearReport("Ready to check."));

for (const button of document.querySelectorAll("[data-example]")) {
  button.addEventListener("click", () => {
    form.reset();
    const filename = button.dataset.example;
    check(filename, async () => {
      const response = await fetch("./examples/" + filename);
      if (!response.ok) throw new Error("The sample GLB could not be loaded.");
      return response.arrayBuffer();
    });
  });
}

dropZone.addEventListener("dragover", event => {
  event.preventDefault();
  if (!controls.disabled) dropZone.classList.add("dragging");
});
dropZone.addEventListener("dragleave", event => {
  if (!dropZone.contains(event.relatedTarget)) dropZone.classList.remove("dragging");
});
dropZone.addEventListener("drop", event => {
  event.preventDefault();
  dropZone.classList.remove("dragging");
  if (controls.disabled) return;
  if (event.dataTransfer.files.length === 1) {
    fileInput.files = event.dataTransfer.files;
    clearReport("Ready to check.");
  } else {
    fileInput.value = "";
    clearReport("Drop one static .glb file at a time.");
  }
});
