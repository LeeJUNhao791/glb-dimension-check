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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="Path to a static GLB 2.0 file.")
    parser.add_argument("--expected-mm", nargs=3, type=nonnegative_mm, metavar=("X", "Y", "Z"))
    parser.add_argument("--tolerance-mm", type=nonnegative_mm, default=0.1, help="Per-axis tolerance (default: 0.1).")
    args = parser.parse_args()
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
    print(json.dumps(report, indent=2))
    return int(report["status"] == "fail")


if __name__ == "__main__":
    sys.exit(main())
