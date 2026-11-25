import { readFile } from "node:fs/promises";
import { parseArgs } from "node:util";
import { checkDimensions, measureStl, parseExpectation } from "../measure.mjs";

function byAxis(values) {
  return Object.fromEntries(["x", "y", "z"].map((axis, index) => [axis, values[index]]));
}

try {
  const { values, positionals } = parseArgs({
    options: { unit: { type: "string" }, expect: { type: "string" } },
    allowPositionals: true,
  });
  if (positionals.length !== 1 || !["mm", "m"].includes(values.unit) || !values.expect) {
    throw new Error("Usage: node scripts/check_stl.mjs model.stl --unit mm|m --expect expected.json");
  }
  const { expected, tolerance } = parseExpectation(await readFile(values.expect, "utf8"));
  const source = await readFile(positionals[0]);
  const buffer = source.buffer.slice(source.byteOffset, source.byteOffset + source.byteLength);
  const { spans, format } = measureStl(buffer);
  const check = checkDimensions(spans, values.unit, expected, tolerance);
  const passed = check.within.every(Boolean);
  console.log(JSON.stringify({
    status: passed ? "pass" : "fail",
    format,
    coordinate_unit: values.unit,
    dimensions_mm: byAxis(check.mm),
    expected_mm: byAxis(expected),
    tolerance_mm: tolerance,
    deviation_mm: byAxis(check.delta),
    within_tolerance: byAxis(check.within),
    scale_hint: check.scale,
  }, null, 2));
  process.exitCode = passed ? 0 : 1;
} catch (error) {
  console.log(JSON.stringify({ status: "invalid", error: error.message }, null, 2));
  process.exitCode = 2;
}
