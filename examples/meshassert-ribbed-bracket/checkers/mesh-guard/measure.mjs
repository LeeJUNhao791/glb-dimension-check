const number = "([+-]?(?:\\d+(?:\\.\\d*)?|\\.\\d+)(?:e[+-]?\\d+)?)";
const vector = [number, number, number].join("\\s+");
const vertex = "\\s+vertex\\s+" + vector;
const facetPattern = "\\s*facet\\s+normal\\s+" + vector + "\\s+outer\\s+loop"
  + vertex.repeat(3) + "\\s+endloop\\s+endfacet(?=\\s)";
const invalidStl = "Invalid or truncated STL.";

function readBinary(view, include) {
  if (view.byteLength < 84) return false;
  const count = view.getUint32(80, true);
  if (view.byteLength !== 84 + count * 50) return false;

  for (let base = 84; base < view.byteLength; base += 50) {
    for (let offset = base; offset < base + 48; offset += 12) {
      const x = view.getFloat32(offset, true);
      const y = view.getFloat32(offset + 4, true);
      const z = view.getFloat32(offset + 8, true);
      requireFinite(x, y, z);
      if (offset !== base) include(x, y, z);
    }
  }
  return true;
}

function readAscii(buffer, include) {
  let source;
  try {
    source = new TextDecoder("utf-8", { fatal: true }).decode(buffer);
  } catch {
    throw new Error(invalidStl);
  }

  const header = /^\s*solid(?:[ \t]+[^\r\n\0]*)?(?:\r\n?|\n)/i.exec(source);
  if (!header) throw new Error(invalidStl);

  const facet = new RegExp(facetPattern, "iy");
  let offset = header[0].length;
  facet.lastIndex = offset;
  for (let match; (match = facet.exec(source)) !== null;) {
    const coords = match.slice(1).map(Number);
    requireFinite(...coords);
    for (let vertex = 3; vertex < coords.length; vertex += 3) {
      include(coords[vertex], coords[vertex + 1], coords[vertex + 2]);
    }
    offset = facet.lastIndex;
  }

  const footer = /\s*endsolid(?:[ \t]+[^\r\n\0]*)?\s*$/iy;
  footer.lastIndex = offset;
  if (!footer.test(source)) throw new Error(invalidStl);
}

function requireFinite(...values) {
  if (!values.every(Number.isFinite)) throw new Error("STL geometry must have finite coordinates and dimensions.");
}

export function measureStl(buffer) {
  const min = [Infinity, Infinity, Infinity];
  const max = [-Infinity, -Infinity, -Infinity];

  function include(x, y, z) {
    min[0] = Math.min(min[0], x);
    min[1] = Math.min(min[1], y);
    min[2] = Math.min(min[2], z);
    max[0] = Math.max(max[0], x);
    max[1] = Math.max(max[1], y);
    max[2] = Math.max(max[2], z);
  }

  // The byte count distinguishes binary STL even when its header starts with "solid".
  const binary = readBinary(new DataView(buffer), include);
  if (!binary) readAscii(buffer, include);
  if (min[0] === Infinity) throw new Error("Invalid STL. No triangles found.");
  const spans = min.map((value, axis) => max[axis] - value);
  requireFinite(...spans);
  return { format: binary ? "Binary" : "ASCII", spans };
}

export function checkDimensions(spans, unit, expected, tolerance = 0.1) {
  if (unit !== "mm" && unit !== "m") {
    throw new Error("Choose the STL coordinate unit.");
  }
  const mm = spans.map(value => value * (unit === "m" ? 1000 : 1));
  requireFinite(...mm);
  if (!expected) return { mm };

  if (expected.length !== spans.length || !expected.every(value => Number.isFinite(value) && value >= 0)) {
    throw new Error("Enter all three expected dimensions as nonnegative numbers, or leave all three blank.");
  }
  if (!Number.isFinite(tolerance) || tolerance < 0) {
    throw new Error("Enter a nonnegative tolerance.");
  }

  const delta = mm.map((actual, axis) => actual - expected[axis]);
  const within = mm.map((actual, axis) =>
    actual >= expected[axis] - tolerance && actual <= expected[axis] + tolerance
  );
  const ratios = mm.map((actual, axis) => actual / expected[axis]);
  const scale = within.every(Boolean) ? null : [1000, 0.001].find(factor =>
    ratios.every(ratio => ratio >= factor * 0.95 && ratio <= factor * 1.05)
  ) ?? null;
  return { mm, delta, within, scale };
}

export function parseExpectation(source) {
  const contract = JSON.parse(source.replace(/^\uFEFF/, ""));
  if (!contract || typeof contract !== "object" || Array.isArray(contract)) {
    throw new Error("Expected a JSON object.");
  }
  for (const field of Object.keys(contract)) {
    if (!["expected_mm", "tolerance_mm"].includes(field)) {
      throw new Error("Unknown field " + field + ".");
    }
  }
  const expected = contract.expected_mm;
  if (!expected || typeof expected !== "object" || Array.isArray(expected)) {
    throw new Error("expected_mm must be an object with x, y, and z fields.");
  }
  const axes = ["x", "y", "z"];
  for (const axis of Object.keys(expected)) {
    if (!axes.includes(axis)) throw new Error("Unknown field expected_mm." + axis + ".");
  }
  const values = axes.map(axis => {
    const value = expected[axis];
    if (!Number.isFinite(value) || value < 0) {
      throw new Error("expected_mm." + axis + " must be a finite, nonnegative JSON number in millimeters.");
    }
    return value;
  });
  const tolerance = Object.hasOwn(contract, "tolerance_mm") ? contract.tolerance_mm : 0.1;
  if (!Number.isFinite(tolerance) || tolerance < 0) {
    throw new Error("tolerance_mm must be a finite, nonnegative JSON number in millimeters.");
  }
  return { expected: values, tolerance };
}
