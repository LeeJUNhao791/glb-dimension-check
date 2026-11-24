from pathlib import Path

from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer
from OCP.StlAPI import StlAPI_Writer
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt


LENGTH_MM = 64.0
WIDTH_MM = 40.0
THICKNESS_MM = 6.0
HOLE_DIAMETER_MM = 4.5
HOLE_PITCH_X_MM = 48.0
HOLE_PITCH_Y_MM = 24.0
OPENING_X_MM = 20.0
OPENING_Y_MM = 12.0


def gen_step():
    origin = gp_Pnt(-LENGTH_MM / 2, -WIDTH_MM / 2, 0)
    plate = BRepPrimAPI_MakeBox(origin, LENGTH_MM, WIDTH_MM, THICKNESS_MM).Shape()
    cutter_height = THICKNESS_MM + 2
    opening_corner = gp_Pnt(-OPENING_X_MM / 2, -OPENING_Y_MM / 2, -1)
    opening = BRepPrimAPI_MakeBox(opening_corner, OPENING_X_MM, OPENING_Y_MM, cutter_height).Shape()
    plate = BRepAlgoAPI_Cut(plate, opening).Shape()
    for x in (-HOLE_PITCH_X_MM / 2, HOLE_PITCH_X_MM / 2):
        for y in (-HOLE_PITCH_Y_MM / 2, HOLE_PITCH_Y_MM / 2):
            axis = gp_Ax2(gp_Pnt(x, y, -1), gp_Dir(0, 0, 1))
            hole = BRepPrimAPI_MakeCylinder(axis, HOLE_DIAMETER_MM / 2, cutter_height).Shape()
            plate = BRepAlgoAPI_Cut(plate, hole).Shape()
    if not BRepCheck_Analyzer(plate).IsValid():
        raise RuntimeError("Invalid mounting plate solid")
    return plate


if __name__ == "__main__":
    part = gen_step()
    path = Path(__file__)
    step_writer = STEPControl_Writer()
    if step_writer.Transfer(part, STEPControl_AsIs) != IFSelect_RetDone:
        raise RuntimeError("Could not transfer mounting plate to STEP")
    step_path = path.with_suffix(".step")
    if step_writer.Write(str(step_path)) != IFSelect_RetDone:
        raise RuntimeError("Could not write mounting plate STEP")
    # The STEP writer pads some lines. Keep the text export clean for Git.
    step_lines = step_path.read_text(encoding="ascii").splitlines()
    step_path.write_text("\n".join(line.rstrip() for line in step_lines) + "\n", encoding="ascii", newline="\n")

    BRepMesh_IncrementalMesh(part, 0.02, False, 0.05)
    stl_writer = StlAPI_Writer()
    stl_writer.ASCIIMode = False
    if not stl_writer.Write(part, str(path.with_suffix(".stl"))):
        raise RuntimeError("Could not write mounting plate STL")
