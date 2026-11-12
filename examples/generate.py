"""Regenerate the three original GLB examples using only Python."""

import json
import math
import struct
from pathlib import Path


def write_glb(name, positions, indices, root_transform):
    vertices = b"".join(struct.pack("<3f", *point) for point in positions)
    faces = struct.pack(f"<{len(indices)}H", *indices)
    data = vertices + faces
    model = {
        "asset": {"version": "2.0", "generator": "GLB Dimension Check examples"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"children": [1], **root_transform}, {"mesh": 0, "translation": [0.1, 0, 0]}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
        "buffers": [{"byteLength": len(data)}],
        "bufferViews": [
            {"buffer": 0, "byteLength": len(vertices), "target": 34962},
            {"buffer": 0, "byteOffset": len(vertices), "byteLength": len(faces), "target": 34963},
        ],
        "accessors": [
            {
                "bufferView": 0, "componentType": 5126, "count": len(positions), "type": "VEC3",
                "min": [min(axis) for axis in zip(*positions)],
                "max": [max(axis) for axis in zip(*positions)],
            },
            {"bufferView": 1, "componentType": 5123, "count": len(indices), "type": "SCALAR"},
        ],
    }
    metadata = json.dumps(model, separators=(",", ":")).encode()
    metadata += b" " * (-len(metadata) % 4)
    data += b"\0" * (-len(data) % 4)
    chunks = struct.pack("<I4s", len(metadata), b"JSON") + metadata
    chunks += struct.pack("<I4s", len(data), b"BIN\0") + data
    Path(__file__).with_name(name).write_bytes(struct.pack("<4sII", b"glTF", 2, 12 + len(chunks)) + chunks)


if __name__ == "__main__":
    box = [
        (0, 0, 0), (0.12, 0, 0), (0.12, 0.08, 0), (0, 0.08, 0),
        (0, 0, 0.04), (0.12, 0, 0.04), (0.12, 0.08, 0.04), (0, 0.08, 0.04),
    ]
    faces = [
        0, 2, 1, 0, 3, 2, 4, 5, 6, 4, 6, 7, 0, 1, 5, 0, 5, 4,
        1, 2, 6, 1, 6, 5, 2, 3, 7, 2, 7, 6, 3, 0, 4, 3, 4, 7,
    ]
    write_glb("correct.glb", box, faces, {})
    write_glb("1000x-too-large.glb", box, faces, {"scale": [1000, 1000, 1000]})
    write_glb(
        "measure-only.glb",
        [(0, 0, 0), (0.1, 0, 0.04), (0, 0.1, 0.04), (1, 1, 1)],
        [0, 1, 2],
        {"rotation": [0, 0, math.sin(math.pi / 8), math.cos(math.pi / 8)]},
    )
