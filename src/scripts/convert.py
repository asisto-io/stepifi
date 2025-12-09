#!/usr/bin/env python3
"""
DIAGNOSTIC STL → STEP CONVERTER
THIS VERSION ALWAYS OUTPUTS VALID JSON AND FULL TRACEBACKS.
"""

import sys
import os
import argparse
import json
import traceback

# FreeCAD imports
try:
    import FreeCAD
    import Part
    import Mesh
    import MeshPart
    import Import
except Exception as e:
    print(json.dumps({
        "success": False,
        "stage": "freecad_import",
        "error": str(e),
        "trace": traceback.format_exc()
    }))
    sys.exit(1)


def json_out(obj):
    """Always print clean JSON and exit."""
    print(json.dumps(obj, indent=2))
    sys.exit(0 if obj.get("success", False) else 1)


def convert_stl_to_step(input_path, output_path, tolerance, repair):
    result = {
        "success": False,
        "stage": "init",
        "input": input_path,
        "output": output_path,
        "tolerance": tolerance,
        "repair": repair,
        "steps": []
    }

    def log(step):
        result["steps"].append(step)

    try:
        # Validate file exists
        if not os.path.exists(input_path):
            result["error"] = "Input STL does not exist"
            result["stage"] = "validation"
            return result

        log("Reading STL mesh…")
        mesh = Mesh.Mesh()
        mesh.read(input_path)

        if mesh.CountFacets == 0:
            result["error"] = "Mesh has 0 facets"
            result["stage"] = "empty_mesh"
            return result

        result["mesh_stats"] = {
            "points": mesh.CountPoints,
            "facets": mesh.CountFacets,
            "edges": mesh.CountEdges,
            "isSolid": mesh.isSolid()
        }

        # Attempt mesh repair
        if repair:
            log("Running mesh repair…")
            try:
                mesh.removeDuplicatedPoints()
                mesh.removeDuplicatedFacets()
                mesh.fixSelfIntersections()
                mesh.fixDegenerations()
                mesh.removeNonManifolds()
                mesh.fillupHoles()
                mesh.harmonizeNormals()
            except Exception as e:
                result["mesh_repair_error"] = str(e)
                result["mesh_repair_trace"] = traceback.format_exc()

        # Create document
        log("Creating FreeCAD document…")
        doc = FreeCAD.newDocument("Diag")

        # Convert to shape
        log("Converting mesh → shape…")
        try:
            shape = Part.Shape()
            shape.makeShapeFromMesh(mesh.Topology, tolerance)
        except Exception as e:
            result["stage"] = "mesh_to_shape_fail"
            result["error"] = str(e)
            result["trace"] = traceback.format_exc()
            return result

        # Convert to solid
        log("Converting shape → solid if possible…")
        try:
            solid = Part.makeSolid(shape)
            final_shape = solid
            result["solid"] = True
        except Exception as e:
            log("Solid conversion FAILED, using shell instead.")
            final_shape = shape
            result["solid"] = False
            result["solid_error"] = str(e)
            result["solid_trace"] = traceback.format_exc()

        # Add object to document
        log("Adding shape to FreeCAD document…")
        obj = doc.addObject("Part::Feature", "Converted")
        obj.Shape = final_shape

        # Export STEP
        log("Exporting STEP file…")
        try:
            Import.export([obj], output_path)
        except Exception as e:
            result["stage"] = "step_export_fail"
            result["error"] = str(e)
            result["trace"] = traceback.format_exc()
            return result

        # Validate STEP file
        if not os.path.exists(output_path):
            result["stage"] = "step_missing"
            result["error"] = "STEP file was not created"
            return result

        size = os.path.getsize(output_path)
        if size == 0:
            result["stage"] = "step_empty"
            result["error"] = "STEP file is zero bytes"
            return result

        result["success"] = True
        result["stage"] = "complete"
        result["output_size"] = size
        return result

    except Exception as e:
        result["stage"] = "fatal"
        result["error"] = str(e)
        result["trace"] = traceback.format_exc()
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--tolerance", type=float, default=0.01)
    parser.add_argument("--repair", action="store_true", default=True)
    parser.add_argument("--no-repair", action="store_false", dest="repair")
    args = parser.parse_args()

    result = convert_stl_to_step(
        args.input,
        args.output,
        args.tolerance,
        args.repair
    )
    json_out(result)


if __name__ == "__main__":
    main()
