#!/usr/bin/env python3
import sys
import os
import argparse
import json

# --- Silence FreeCAD noisy output ------------------------------------------
class _SuppressStdout:
    def __enter__(self):
        self._old_stdout = sys.stdout
        sys.stdout = open(os.devnull, "w")
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._old_stdout

class _SuppressStderr:
    def __enter__(self):
        self._old_stderr = sys.stderr
        sys.stderr = open(os.devnull, "w")
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stderr.close()
        sys.stderr = self._old_stderr

# Import FreeCAD quietly
with _SuppressStdout(), _SuppressStderr():
    try:
        import FreeCAD
        import Part
        import Mesh
        import MeshPart
        import Import
    except Exception as e:
        print(json.dumps({"success": False, "error": f"FreeCAD import failed: {str(e)}"}))
        sys.exit(1)


def get_mesh_info(mesh):
    return {
        "points": mesh.CountPoints,
        "facets": mesh.CountFacets,
        "edges": mesh.CountEdges,
        "solid": mesh.isSolid(),
        "non_manifolds": mesh.hasNonManifolds(),
        "self_intersections": mesh.hasSelfIntersections(),
        "volume": mesh.Volume if mesh.isSolid() else None,
        "area": mesh.Area,
    }


def repair_mesh(mesh):
    fixes = []

    pts_before = mesh.CountPoints
    mesh.removeDuplicatedPoints()
    if mesh.CountPoints < pts_before:
        fixes.append("Removed duplicated points")

    fac_before = mesh.CountFacets
    mesh.removeDuplicatedFacets()
    if mesh.CountFacets < fac_before:
        fixes.append("Removed duplicated facets")

    if mesh.hasSelfIntersections():
        mesh.fixSelfIntersections()
        fixes.append("Fixed self-intersections")

    mesh.fixDegenerations()
    fixes.append("Fixed degenerations")

    if mesh.hasNonManifolds():
        mesh.removeNonManifolds()
        fixes.append("Removed non-manifolds")

    mesh.fillupHoles()
    fixes.append("Filled holes")

    mesh.harmonizeNormals()
    fixes.append("Harmonized normals")

    return mesh, fixes


def convert_stl_to_step(input_path, output_path, tolerance=0.01, repair=True, info_only=False):
    result = {
        "success": False,
        "input": input_path,
        "output": output_path,
        "tolerance": tolerance,
    }

    try:
        if not os.path.exists(input_path):
            result["error"] = "Input file not found"
            return result

        mesh = Mesh.Mesh()
        mesh.read(input_path)

        if mesh.CountFacets == 0:
            result["error"] = "STL contains no geometry"
            return result

        result["mesh_info_before"] = get_mesh_info(mesh)

        if info_only:
            result["success"] = True
            return result

        if repair:
            mesh, fixes = repair_mesh(mesh)
            result["repairs"] = fixes
            result["mesh_info_after"] = get_mesh_info(mesh)

        doc = FreeCAD.newDocument("CONVERT")

        shape = Part.Shape()
        shape.makeShapeFromMesh(mesh.Topology, tolerance)

        try:
            solid = Part.makeSolid(shape)
            final_shape = solid
            result["is_solid"] = True
        except:
            final_shape = shape
            result["is_solid"] = False

        obj = doc.addObject("Part::Feature", "Converted")
        obj.Shape = final_shape

        Import.export([obj], output_path)

        if not os.path.exists(output_path):
            result["error"] = "STEP export failed"
            return result

        result["output_size"] = os.path.getsize(output_path)
        result["success"] = True

        FreeCAD.closeDocument("CONVERT")

    except Exception as e:
        result["error"] = str(e)

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--tolerance", type=float, default=0.01)
    parser.add_argument("--repair", action="store_true", default=True)
    parser.add_argument("--no-repair", action="store_false", dest="repair")
    parser.add_argument("--info", action="store_true")

    args = parser.parse_args()

    result = convert_stl_to_step(
        args.input,
        args.output,
        args.tolerance,
        args.repair,
        args.info
    )

    # ONLY PRINT JSON. NO OTHER OUTPUT.
    sys.stdout = sys.__stdout__
    print(json.dumps(result))

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
