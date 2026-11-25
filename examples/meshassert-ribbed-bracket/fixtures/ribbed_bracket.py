"""Export the original ribbed bracket and a taller GLB control with OpenCascade."""

from pathlib import Path

from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism
from OCP.IFSelect import IFSelect_RetDone
from OCP.Message import Message_ProgressRange
from OCP.RWGltf import RWGltf_CafWriter
from OCP.RWMesh import RWMesh_CoordinateSystem_Yup, RWMesh_CoordinateSystem_Zup
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer
from OCP.StlAPI import StlAPI_Writer
from OCP.TCollection import TCollection_AsciiString, TCollection_ExtendedString
from OCP.TDocStd import TDocStd_Document
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.XCAFApp import XCAFApp_Application
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from OCP.collections import IndexedDataMap_TCollection_AsciiString_TCollection_AsciiString
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Vec


WIDTH_MM = 57
DEPTH_MM = 29
HEIGHT_MM = 35
BASE_THICKNESS_MM = 5
WALL_THICKNESS_MM = 6
BORE_RADIUS_MM = 4
FIXTURES = Path(__file__).resolve().parent


def make_bracket(height):
    base = BRepPrimAPI_MakeBox(WIDTH_MM, DEPTH_MM, BASE_THICKNESS_MM).Shape()
    upright = BRepPrimAPI_MakeBox(WIDTH_MM, WALL_THICKNESS_MM, height).Shape()

    rib_profile = BRepBuilderAPI_MakePolygon()
    for point in ((7, 5, 4), (7, 22, 4), (7, 5, 25)):
        rib_profile.Add(gp_Pnt(*point))
    rib_profile.Close()
    rib_face = BRepBuilderAPI_MakeFace(rib_profile.Wire()).Face()
    rib = BRepPrimAPI_MakePrism(rib_face, gp_Vec(5, 0, 0)).Shape()

    with_upright = BRepAlgoAPI_Fuse(base, upright).Shape()
    with_rib = BRepAlgoAPI_Fuse(with_upright, rib).Shape()
    bore_axis = gp_Ax2(gp_Pnt(35, -1, 23), gp_Dir(0, 1, 0))
    bore = BRepPrimAPI_MakeCylinder(bore_axis, BORE_RADIUS_MM, WALL_THICKNESS_MM + 2).Shape()
    cut = BRepAlgoAPI_Cut(with_rib, bore)
    cut.SimplifyResult()
    bracket = cut.Shape()

    solids = TopExp_Explorer(bracket, TopAbs_SOLID)
    if not solids.More() or not BRepCheck_Analyzer(bracket).IsValid():
        raise RuntimeError("Bracket is not a valid solid")
    solid = solids.Current()
    solids.Next()
    if solids.More():
        raise RuntimeError("Bracket contains more than one solid")
    return solid


def gen_step():
    return make_bracket(HEIGHT_MM)


def write_step(solid, path):
    writer = STEPControl_Writer()
    if writer.Transfer(solid, STEPControl_AsIs) != IFSelect_RetDone or writer.Write(str(path)) != IFSelect_RetDone:
        raise RuntimeError(f"Could not write {path}")
    lines = path.read_text(encoding="ascii").splitlines()
    path.write_text("\n".join(line.rstrip() for line in lines) + "\n", encoding="ascii", newline="\n")


def write_stl(solid, path):
    BRepMesh_IncrementalMesh(solid, 0.02, False, 0.05)
    writer = StlAPI_Writer()
    writer.ASCIIMode = False
    if not writer.Write(solid, str(path)):
        raise RuntimeError(f"Could not write {path}")


def write_glb(solid, path):
    BRepMesh_IncrementalMesh(solid, 0.02, False, 0.05)
    XCAFApp_Application.GetApplication_s()
    document = TDocStd_Document(TCollection_ExtendedString("BinXCAF"))
    XCAFDoc_DocumentTool.SetLengthUnit_s(document, 0.001)
    XCAFDoc_DocumentTool.ShapeTool_s(document.Main()).AddShape(solid, False)

    writer = RWGltf_CafWriter(TCollection_AsciiString(str(path)), True)
    coordinates = writer.ChangeCoordinateSystemConverter()
    coordinates.SetInputCoordinateSystem(RWMesh_CoordinateSystem_Zup)
    coordinates.SetOutputCoordinateSystem(RWMesh_CoordinateSystem_Yup)
    coordinates.SetInputLengthUnit(0.001)
    coordinates.SetOutputLengthUnit(1.0)
    metadata = IndexedDataMap_TCollection_AsciiString_TCollection_AsciiString()
    if not writer.Perform(document, metadata, Message_ProgressRange()):
        raise RuntimeError(f"Could not write {path}")


if __name__ == "__main__":
    nominal = gen_step()
    write_step(nominal, FIXTURES / "ribbed_bracket.step")
    write_stl(nominal, FIXTURES / "ribbed_bracket.stl")
    write_glb(gen_step(), FIXTURES / "ribbed_bracket.glb")
    write_glb(make_bracket(HEIGHT_MM + 2), FIXTURES / "ribbed_bracket_tall.glb")
