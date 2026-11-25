#!/usr/bin/env python3
"""Measure the world-axis dimensions of a static GLB 2.0 scene."""

import argparse
import json
import math
import struct
import sys
from itertools import permutations
from pathlib import Path


IDENTITY = ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))
DEFAULT_TOLERANCE_MM = 0.1
INDEX_FORMATS = {5121: "B", 5123: "H", 5125: "I"}
GEOMETRY_EXTENSIONS = {
    "EXT_mesh_gpu_instancing", "EXT_meshopt_compression", "KHR_meshopt_compression",
    "KHR_draco_mesh_compression", "KHR_mesh_quantization",
}


def read_glb(path):
    if path.suffix.lower() != ".glb":
        raise ValueError("Input must be a static .glb file.")
    raw = path.read_bytes()
    if len(raw) < 20:
        raise ValueError("Incomplete GLB header or JSON chunk header.")
    magic, version, length = struct.unpack_from("<4sII", raw)
    if (magic, version, length) != (b"glTF", 2, len(raw)):
        raise ValueError("Invalid GLB header. Expected GLB 2.0 with matching file length.")

    chunks = {}
    offset = 12
    while offset < length:
        size, kind = struct.unpack_from("<I4s", raw, offset)
        start = offset + 8
        end = start + size
        if size % 4 or end > length or (offset == 12 and kind != b"JSON"):
            raise ValueError("Invalid GLB chunk layout.")
        if kind in (b"JSON", b"BIN\0"):
            if kind in chunks:
                raise ValueError("Duplicate GLB chunk.")
            chunks[kind] = memoryview(raw)[start:end]
        offset = end

    model = json.loads(bytes(chunks[b"JSON"]).decode("utf-8"))
    if model["asset"]["version"] != "2.0":
        raise ValueError("Expected a glTF 2.0 asset.")
    if model.get("animations") or model.get("skins"):
        raise ValueError("Animations and skins are outside the static GLB scope.")
    unsupported = GEOMETRY_EXTENSIONS.intersection(model.get("extensionsUsed", []))
    unsupported.update(
        extension for extension in model.get("extensionsRequired", [])
        if extension != "KHR_materials_unlit"
    )
    if unsupported:
        raise ValueError(f"Unsupported glTF extensions: {', '.join(sorted(unsupported))}.")

    buffers = model.get("buffers", [])
    if len(buffers) != 1 or "uri" in buffers[0] or b"BIN\0" not in chunks:
        raise ValueError("Expected a single geometry buffer embedded in the GLB BIN chunk.")
    data = chunks[b"BIN\0"]
    byte_length = buffers[0]["byteLength"]
    if not 0 < byte_length <= len(data) <= byte_length + 3:
        raise ValueError("GLB BIN length does not match its buffer declaration.")
    return model, data[:byte_length]


def entry(items, index):
    if type(index) is not int or not 0 <= index < len(items):
        raise ValueError(f"Out-of-range glTF index: {index!r}.")
    return items[index]


def read_view(model, data, view_id, offset, count, format_code, *, interleaved=False):
    view = entry(model["bufferViews"], view_id)
    if view["buffer"] != 0:
        raise ValueError("Geometry must use the embedded GLB buffer.")
    start = view.get("byteOffset", 0)
    length = view["byteLength"]
    layout = struct.Struct("<" + format_code)
    stride = view.get("byteStride", layout.size)
    if stride < layout.size or ("byteStride" in view and not interleaved):
        raise ValueError("Invalid geometry stride.")
    if not (0 <= start <= start + length <= len(data) and offset >= 0 and count > 0):
        raise ValueError("Invalid geometry buffer range.")
    if offset + (count - 1) * stride + layout.size > length:
        raise ValueError("Geometry accessor exceeds its buffer view.")
    return [layout.unpack_from(data, start + offset + i * stride) for i in range(count)]


def read_accessor(model, data, accessor_id, *, position=False):
    accessor = entry(model["accessors"], accessor_id)
    component = accessor["componentType"]
    count = accessor["count"]
    sparse = accessor.get("sparse")
    if type(count) is not int or count < 1 or accessor.get("normalized"):
        raise ValueError("Invalid geometry accessor.")
    if position:
        if accessor["type"] != "VEC3" or component != 5126:
            raise ValueError("Expected float32 VEC3 positions.")
        format_code = "3f"
        zero = (0.0, 0.0, 0.0)
    else:
        if accessor["type"] != "SCALAR" or component not in INDEX_FORMATS:
            raise ValueError("Expected unsigned scalar vertex indices.")
        format_code = INDEX_FORMATS[component]
        zero = (0,)
    if "bufferView" in accessor:
        values = read_view(
            model, data, accessor["bufferView"], accessor.get("byteOffset", 0),
            count, format_code, interleaved=position,
        )
    else:
        values = None  # An absent base buffer represents zero-initialized elements.
    if sparse is not None:
        indices = sparse["indices"]
        overrides = sparse["values"]
        sparse_count = sparse["count"]
        if not 1 <= sparse_count <= count:
            raise ValueError("Invalid sparse accessor count.")
        locations = read_view(
            model, data, indices["bufferView"], indices.get("byteOffset", 0),
            sparse_count, INDEX_FORMATS[indices["componentType"]],
        )
        replacements = read_view(
            model, data, overrides["bufferView"], overrides.get("byteOffset", 0),
            sparse_count, format_code,
        )
        if values is None:
            values = {}
        previous = -1
        for (index,), replacement in zip(locations, replacements):
            if not previous < index < count:
                raise ValueError("Invalid sparse accessor indices.")
            values[index] = replacement
            previous = index
    if isinstance(values, list):
        return values
    return SparseValues(count, zero, values or {})


class SparseValues:
    """Read implicit zeros without allocating the full accessor."""

    def __init__(self, count, zero, overrides):
        self.count = count
        self.zero = zero
        self.overrides = overrides

    def __len__(self):
        return self.count

    def __getitem__(self, index):
        if not 0 <= index < self.count:
            raise IndexError(index)
        return self.overrides.get(index, self.zero)


def node_matrix(node):
    if "matrix" in node:
        matrix = node["matrix"]
        return tuple(tuple(matrix[4 * col + row] for col in range(4)) for row in range(4))
    tx, ty, tz = node.get("translation", (0, 0, 0))
    sx, sy, sz = node.get("scale", (1, 1, 1))
    x, y, z, w = node.get("rotation", (0, 0, 0, 1))
    return (
        ((1 - 2 * (y * y + z * z)) * sx, 2 * (x * y - z * w) * sy, 2 * (x * z + y * w) * sz, tx),
        (2 * (x * y + z * w) * sx, (1 - 2 * (x * x + z * z)) * sy, 2 * (y * z - x * w) * sz, ty),
        (2 * (x * z - y * w) * sx, 2 * (y * z + x * w) * sy, (1 - 2 * (x * x + y * y)) * sz, tz),
        (0, 0, 0, 1),
    )


def measure_mm(model, data):
    scene = entry(model["scenes"], model.get("scene", 0))
    pending = [(node, IDENTITY) for node in scene.get("nodes", [])]
    visited = set()
    low = [math.inf] * 3
    high = [-math.inf] * 3
    while pending:
        node_id, parent = pending.pop()
        node = entry(model["nodes"], node_id)
        if node_id in visited:
            raise ValueError("The selected scene is not a tree of nodes.")
        visited.add(node_id)
        columns = tuple(zip(*node_matrix(node)))
        world = tuple(
            tuple(sum(a * b for a, b in zip(row, column)) for column in columns)
            for row in parent
        )
        pending.extend((child, world) for child in node.get("children", []))
        if "mesh" not in node:
            continue
        mesh = entry(model["meshes"], node["mesh"])
        for primitive in mesh["primitives"]:
            if primitive.get("targets"):
                raise ValueError("Morph targets are outside the static GLB scope.")
            positions = read_accessor(model, data, primitive["attributes"]["POSITION"], position=True)
            if "indices" in primitive:
                indices = read_accessor(model, data, primitive["indices"])
                vertices = (entry(positions, index) for (index,) in indices)
            else:
                vertices = iter(positions)
            for x, y, z in vertices:
                for axis, (a, b, c, translation) in enumerate(world[:3]):
                    value = a * x + b * y + c * z + translation
                    if not math.isfinite(value):
                        raise ValueError("Non-finite vertex or scene transform.")
                    low[axis] = min(low[axis], value)
                    high[axis] = max(high[axis], value)
    dimensions = [(maximum - minimum) * 1000 for minimum, maximum in zip(low, high)]
    if not all(map(math.isfinite, dimensions)):
        raise ValueError("No finite mesh bounds found in the selected scene.")
    return dimensions


def nonnegative_mm(text):
    value = float(text)
    if value < 0 or not math.isfinite(value):
        raise argparse.ArgumentTypeError("Enter a finite, nonnegative value in millimeters.")
    return value


def contract_mm(value, field):
    message = f"{field} must be a finite, nonnegative JSON number in millimeters."
    if type(value) not in (int, float):
        raise ValueError(message)
    try:
        return nonnegative_mm(value)
    except (argparse.ArgumentTypeError, OverflowError):
        raise ValueError(message) from None


def read_expectation(path):
    try:
        contract = json.loads(path.read_text(encoding="utf-8-sig"))
    except UnicodeDecodeError:
        raise ValueError("Expected UTF-8 text.") from None
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON: {error}") from None

    if not isinstance(contract, dict):
        raise ValueError("Expected a JSON object.")
    for field in contract:
        if field not in ("expected_mm", "tolerance_mm"):
            raise ValueError(f"Unknown field {field!r}.")

    expected = contract.get("expected_mm")
    if not isinstance(expected, dict):
        raise ValueError("expected_mm must be an object with x, y, and z fields.")
    for axis in expected:
        if axis not in ("x", "y", "z"):
            field = f"expected_mm.{axis}"
            raise ValueError(f"Unknown field {field!r}.")

    return (
        [contract_mm(expected.get(axis), f"expected_mm.{axis}") for axis in "xyz"],
        contract_mm(contract.get("tolerance_mm", DEFAULT_TOLERANCE_MM), "tolerance_mm"),
    )


def diagnose_mismatch(dimensions, expected, tolerance, axes):
    diagnosis = {"type": "axis_mismatch", "out_of_tolerance_axes": axes}
    if len(axes) == 1:
        return diagnosis

    for factor in (1000, 0.001):
        if all(
            reference > 0
            and math.isclose(actual / reference, factor, rel_tol=0, abs_tol=factor * 0.01)
            for actual, reference in zip(dimensions, expected)
        ):
            return {
                **diagnosis,
                "type": "unit_scale",
                "scale_factor": factor,
                "hint": "Check the export units (meters versus millimeters).",
            }

    expected_by_axis = dict(zip("xyz", expected))
    for order in permutations("xyz"):
        if all(
            abs(actual - expected_by_axis[axis]) <= tolerance
            for actual, axis in zip(dimensions, order)
        ):
            return {
                **diagnosis,
                "type": "axis_permutation",
                "axis_mapping": dict(zip("xyz", order)),
                "hint": "Check the model orientation and the order of the expected axes.",
            }
    return diagnosis


def svg_number(value, signed=False):
    if value == 0:
        return "0"
    sign = "+" if signed else ""
    if abs(value) < 0.001 or abs(value) >= 1e9:
        return format(value, f"{sign}.4g")
    return format(value, f"{sign},.3f").rstrip("0").rstrip(".")


def render_svg(report):
    status = report["status"]
    badge, ink = {
        "pass": ("#dcfce7", "#166534"),
        "fail": ("#fee2e2", "#991b1b"),
        "measured": ("#dbeafe", "#1e40af"),
    }[status]
    diagnosis = report.get("diagnosis", {})
    failed_axes = diagnosis.get("out_of_tolerance_axes", ())
    rows = []
    for axis, y in zip("xyz", (157, 201, 245)):
        rows.append(f'    <g data-axis="{axis}">')
        rows.append(f'      <text x="40" y="{y}" font-weight="700">{axis.upper()}</text>')
        for field, x in (("dimensions_mm", 264), ("expected_mm", 420), ("deviation_mm", 598)):
            value = report.get(field, {}).get(axis)
            is_deviation = field == "deviation_mm"
            color = "#991b1b" if is_deviation and axis in failed_axes else "#17253a"
            if value is None:
                label, data = "—", ""
            else:
                label = svg_number(value, signed=is_deviation)
                data = f' data-value-mm="{value}"'
            rows.append(
                f'      <text data-field="{field}"{data} x="{x}" y="{y}" fill="{color}" '
                f'text-anchor="end" font-family="Consolas, monospace">{label}</text>'
            )
        rows.append("    </g>")
    table = "\n".join(rows)
    footer = "Measurement only"
    if "tolerance_mm" in report:
        footer = f'Per-axis tolerance ±{svg_number(report["tolerance_mm"])} mm'
    if diagnosis.get("type") == "unit_scale":
        footer += f' · Check export units (×{svg_number(diagnosis["scale_factor"])})'

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="640" height="308" viewBox="0 0 640 308"
     role="img" aria-labelledby="card-title">
  <title id="card-title">GLB Dimension Check · {status.upper()}</title>
  <rect x="0.5" y="0.5" width="639" height="307" rx="16" fill="#ffffff" stroke="#cbd5e1"/>
  <g font-family="Arial, sans-serif" fill="#17253a">
    <text x="24" y="45" font-size="26" font-weight="700">GLB Dimension Check</text>
    <text x="24" y="66" font-size="13" fill="#475569">World-axis dimensions in millimeters</text>
    <rect x="492" y="23" width="124" height="36" rx="18" fill="{badge}"/>
    <text id="status" x="554" y="46" text-anchor="middle" font-size="14" font-weight="700" fill="{ink}">{status.upper()}</text>
    <rect x="24" y="88" width="592" height="174" rx="10" fill="#f8fafc" stroke="#e2e8f0"/>
    <path d="M24 130H616 M24 174H616 M24 218H616" fill="none" stroke="#e2e8f0"/>
    <g font-size="13" font-weight="700" fill="#475569">
      <text x="40" y="114">Axis</text>
      <g text-anchor="end">
        <text x="264" y="114">Measured</text>
        <text x="420" y="114">Expected</text>
        <text x="598" y="114">Deviation</text>
      </g>
    </g>
    <g font-size="17">
{table}
    </g>
    <text x="24" y="287" font-size="13" fill="#475569">{footer}</text>
  </g>
</svg>
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="Path to a static GLB 2.0 file.")
    parser.add_argument("--expected-mm", nargs=3, type=nonnegative_mm, metavar=("X", "Y", "Z"))
    parser.add_argument("--tolerance-mm", type=nonnegative_mm, help="Per-axis tolerance (default: 0.1).")
    parser.add_argument("--expect", type=Path, metavar="PATH", help="Read expected dimensions and tolerance from JSON.")
    parser.add_argument("--svg", type=Path, metavar="PATH", help="Write an SVG card for the JSON report.")
    args = parser.parse_args()
    if args.expect is not None:
        if args.expected_mm is not None:
            parser.error("--expect cannot be combined with --expected-mm.")
        if args.tolerance_mm is not None:
            parser.error("--expect cannot be combined with --tolerance-mm.")
        try:
            args.expected_mm, args.tolerance_mm = read_expectation(args.expect)
        except (OSError, ValueError, RecursionError) as error:
            print(f"Expectation file {args.expect}: {error}", file=sys.stderr)
            return 2
    elif args.tolerance_mm is None:
        args.tolerance_mm = DEFAULT_TOLERANCE_MM
    try:
        dimensions = measure_mm(*read_glb(args.file))
    except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError, OverflowError, struct.error) as error:
        print(f"GLB check error: {error}", file=sys.stderr)
        return 2
    report = {"status": "measured", "dimensions_mm": dict(zip("xyz", dimensions))}
    if args.expected_mm is not None:
        deviation = [actual - expected for actual, expected in zip(dimensions, args.expected_mm)]
        axes = [axis for axis, value in zip("xyz", deviation) if abs(value) > args.tolerance_mm]
        report.update(
            status="fail" if axes else "pass",
            expected_mm=dict(zip("xyz", args.expected_mm)),
            deviation_mm=dict(zip("xyz", deviation)),
            tolerance_mm=args.tolerance_mm,
        )
        if axes:
            report["diagnosis"] = diagnose_mismatch(
                dimensions, args.expected_mm, args.tolerance_mm, axes,
            )
    if args.svg is not None:
        try:
            if args.svg.exists():
                if args.svg.samefile(args.file):
                    raise ValueError("SVG output must differ from the input GLB.")
                if args.expect is not None and args.svg.samefile(args.expect):
                    raise ValueError("SVG output must differ from the input expectation file.")
            args.svg.write_bytes(render_svg(report).encode("utf-8"))
        except (OSError, ValueError) as error:
            print(f"Cannot write SVG: {error}", file=sys.stderr)
            return 2
    print(json.dumps(report, indent=2))
    return int(report["status"] == "fail")


if __name__ == "__main__":
    sys.exit(main())
