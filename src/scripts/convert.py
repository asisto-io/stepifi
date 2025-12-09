#!/usr/bin/env python3
"""
STL to STEP Converter with Mesh Repair

This script converts STL files to STEP format using FreeCAD's libraries.
It includes optional mesh repair and quality improvements.

Usage:
    python3 convert.py <input.stl> <output.step> [--tolerance=0.01] [--repair] [--info]
"""

import sys
import os
import argparse
import json

# FreeCAD imports
try:
    import FreeCAD
    import Part
    import Mesh
    import MeshPart
    import Import
except ImportError as e:
    print(json.dumps({
        "success": False,
        "error": f"FreeCAD import failed: {str(e)}",
        "stage": "import"
    }))
    sys.exit(1)


def get_mesh_info(mesh):
    """Extract mesh statistics."""
    return {
        "points": mesh.CountPoints,
        "facets": mesh.CountFacets,
        "edges": mesh.CountEdges,
        "is_solid": mesh.isSolid(),
        "has_non_manifolds": mesh.hasNonManifolds(),
        "has_self_intersections": mesh.hasSelfIntersections(),
        "volume": mesh.Volume if mesh.isSolid() else None,
        "area": mesh.Area,
    }


def repair_mesh(mesh):
    """
    Attempt to repair common mesh issues.
    Returns the repaired mesh and a report of fixes applied.
    """
    repairs = []
    
    # Remove duplicate points
    points_before = mesh.CountPoints
    mesh.removeDuplicatedPoints()
    if mesh.CountPoints < points_before:
        repairs.append(f"Removed {points_before - mesh.CountPoints} duplicate points")
    
    # Remove duplicate facets
    facets_before = mesh.CountFacets
    mesh.removeDuplicatedFacets()
    if mesh.CountFacets < facets_before:
        repairs.append(f"Removed {facets_before - mesh.CountFacets} duplicate facets")
    
    # Fix self-intersections
    if mesh.hasSelfIntersections():
        mesh.fixSelfIntersections()
        if not mesh.hasSelfIntersections():
            repairs.append("Fixed self-intersections")
    
    # Fix degenerated facets
    mesh.fixDegenerations()
    repairs.append("Fixed degenerations")
    
    # Fix non-manifold edges
    if mesh.hasNonManifolds():
        mesh.removeNonManifolds()
        if not mesh.hasNonManifolds():
            repairs.append("Removed non-manifold geometry")
    
    # Fill holes
    mesh.fillupHoles()
    repairs.append("Filled holes")
    
    # Harmonize normals
    mesh.harmonizeNormals()
    repairs.append("Harmonized normals")
    
    return mesh, repairs


def convert_stl_to_step(input_path, output_path, tolerance=0.01, repair=True, info_only=False):
    """
    Convert an STL file to STEP format.
    
    Args:
        input_path: Path to input STL file
        output_path: Path for output STEP file
        tolerance: Tolerance for mesh to shape conversion (smaller = more accurate, slower)
        repair: Whether to attempt mesh repair before conversion
        info_only: Only return mesh info, don't convert
    
    Returns:
        dict with success status and conversion details
    """
    result = {
        "success": False,
        "input": input_path,
        "output": output_path,
        "tolerance": tolerance,
    }
    
    try:
        # Validate input file
        if not os.path.exists(input_path):
            result["error"] = f"Input file not found: {input_path}"
            result["stage"] = "validation"
            return result
        
        # Read STL file
        mesh = Mesh.Mesh()
        mesh.read(input_path)
        
        if mesh.CountFacets == 0:
            result["error"] = "STL file contains no geometry"
            result["stage"] = "read"
            return result
        
        # Get initial mesh info
        result["mesh_info_before"] = get_mesh_info(mesh)
        
        # If only info requested, return now
        if info_only:
            result["success"] = True
            return result
        
        # Repair mesh if requested
        if repair:
            mesh, repairs = repair_mesh(mesh)
            result["repairs"] = repairs
            result["mesh_info_after"] = get_mesh_info(mesh)
        
        # Create a new FreeCAD document
        doc = FreeCAD.newDocument("STLtoSTEP")
        
        # Convert mesh to shape
        shape = Part.Shape()
        shape.makeShapeFromMesh(mesh.Topology, tolerance)
        
        # Create a solid if possible
        try:
            solid = Part.makeSolid(shape)
            final_shape = solid
            result["is_solid"] = True
        except Exception:
            # If we can't make a solid, use the shell
            final_shape = shape
            result["is_solid"] = False
        
        # Add to document
        obj = doc.addObject("Part::Feature", "ConvertedMesh")
        obj.Shape = final_shape
        
        # Export to STEP
        Import.export([obj], output_path)
        
        # Verify output was created
        if os.path.exists(output_path):
            result["success"] = True
            result["output_size"] = os.path.getsize(output_path)
        else:
            result["error"] = "STEP file was not created"
            result["stage"] = "export"
        
        # Cleanup
        FreeCAD.closeDocument("STLtoSTEP")
        
    except Exception as e:
        result["error"] = str(e)
        result["stage"] = "conversion"
        
        # Try to cleanup on error
        try:
            FreeCAD.closeDocument("STLtoSTEP")
        except:
            pass
    
    return result


def main():
    parser = argparse.ArgumentParser(description="Convert STL to STEP with optional mesh repair")
    parser.add_argument("input", help="Input STL file path")
    parser.add_argument("output", help="Output STEP file path")
    parser.add_argument("--tolerance", type=float, default=0.01,
                        help="Conversion tolerance (default: 0.01)")
    parser.add_argument("--repair", action="store_true", default=True,
                        help="Repair mesh before conversion (default: True)")
    parser.add_argument("--no-repair", action="store_false", dest="repair",
                        help="Skip mesh repair")
    parser.add_argument("--info", action="store_true",
                        help="Only show mesh info, don't convert")
    
    args = parser.parse_args()
    
    result = convert_stl_to_step(
        args.input,
        args.output,
        tolerance=args.tolerance,
        repair=args.repair,
        info_only=args.info
    )
    
    # Output JSON result
    print(json.dumps(result, indent=2))
    
    # Exit with appropriate code
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
