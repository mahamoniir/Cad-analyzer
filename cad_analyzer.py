from __future__ import annotations

import math
import traceback
from pathlib import Path
from collections import Counter
from datetime import datetime
from typing import Any

from ezdxf.addons import odafc


# ============================================================
# GENERAL SERIALIZATION HELPERS
# ============================================================

def safe_value(value: Any, depth: int = 0) -> Any:
    """
    Convert ezdxf/Python values into JSON-safe values.
    """

    if depth > 10:
        return str(value)

    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        if isinstance(value, float):
            if math.isnan(value) or math.isinf(value):
                return str(value)
        return value

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, dict):
        result = {}
        for key, val in value.items():
            result[str(key)] = safe_value(val, depth + 1)
        return result

    if isinstance(value, (list, tuple, set)):
        return [safe_value(item, depth + 1) for item in value]

    # ezdxf vectors and similar objects
    if hasattr(value, "x") and hasattr(value, "y"):
        result = {
            "x": safe_value(value.x, depth + 1),
            "y": safe_value(value.y, depth + 1),
        }
        if hasattr(value, "z"):
            result["z"] = safe_value(value.z, depth + 1)
        return result

    # DXF tag-like object
    if hasattr(value, "code") and hasattr(value, "value"):
        return {
            "code": safe_value(value.code, depth + 1),
            "value": safe_value(value.value, depth + 1),
        }

    # Try iterable objects
    try:
        if not isinstance(value, (str, bytes)):
            return [safe_value(item, depth + 1) for item in value]
    except Exception:
        pass

    return str(value)


def safe_get_dxf_attribute(entity, attribute_name: str, default=None):
    """
    Safely read an optional DXF attribute.
    """
    try:
        if entity.dxf.hasattrib(attribute_name):
            return safe_value(entity.dxf.get(attribute_name))
    except Exception:
        pass
    return default


# ============================================================
# DXF ATTRIBUTE EXTRACTION
# ============================================================

def extract_dxf_attributes(entity) -> dict:
    """
    Read all supported DXF attributes of an entity.
    """
    result = {}
    try:
        attribute_names = entity.dxfattribs()
        for name in attribute_names:
            try:
                value = entity.dxf.get(name)
                result[name] = safe_value(value)
            except Exception as error:
                result[name] = {"error": str(error)}
    except Exception as error:
        result["_error"] = str(error)
    return result


# ============================================================
# XDATA
# ============================================================

def extract_xdata(entity) -> dict:
    """
    Read extended data attached to an entity.
    """
    result = {}
    try:
        if not entity.has_xdata:
            return result

        appids = []
        try:
            appids = list(entity.get_xdata_appids())
        except Exception:
            pass

        for appid in appids:
            try:
                tags = entity.get_xdata(appid)
                result[appid] = safe_value(list(tags))
            except Exception as error:
                result[appid] = {"error": str(error)}
    except Exception as error:
        result["_error"] = str(error)
    return result


# ============================================================
# EXTENSION DICTIONARY
# ============================================================

def extract_extension_dictionary(entity) -> dict:
    result = {}
    try:
        if not entity.has_extension_dict:
            return result

        extension_dict = entity.get_extension_dict()
        for key, value in extension_dict.items():
            try:
                result[str(key)] = {
                    "handle": safe_get_dxf_attribute(value, "handle"),
                    "type": value.dxftype(),
                }
            except Exception as error:
                result[str(key)] = {"error": str(error)}
    except Exception as error:
        result["_error"] = str(error)
    return result


# ============================================================
# ENTITY-SPECIFIC GEOMETRY
# ============================================================

def extract_entity_geometry(entity) -> dict:
    entity_type = entity.dxftype()
    result = {}

    if entity_type == "LINE":
        result = {
            "start": safe_value(entity.dxf.start),
            "end": safe_value(entity.dxf.end),
        }

    elif entity_type == "POINT":
        result = {"location": safe_value(entity.dxf.location)}

    elif entity_type == "CIRCLE":
        result = {
            "center": safe_value(entity.dxf.center),
            "radius": safe_value(entity.dxf.radius),
        }

    elif entity_type == "ARC":
        result = {
            "center": safe_value(entity.dxf.center),
            "radius": safe_value(entity.dxf.radius),
            "start_angle": safe_value(entity.dxf.start_angle),
            "end_angle": safe_value(entity.dxf.end_angle),
        }

    elif entity_type == "ELLIPSE":
        result = {
            "center": safe_value(entity.dxf.center),
            "major_axis": safe_value(entity.dxf.major_axis),
            "ratio": safe_value(entity.dxf.ratio),
            "start_param": safe_value(entity.dxf.start_param),
            "end_param": safe_value(entity.dxf.end_param),
        }

    elif entity_type == "LWPOLYLINE":
        points = []
        try:
            for point in entity.get_points():
                points.append({
                    "x": safe_value(point[0]),
                    "y": safe_value(point[1]),
                    "start_width": safe_value(point[2]),
                    "end_width": safe_value(point[3]),
                    "bulge": safe_value(point[4]),
                })
        except Exception as error:
            result["points_error"] = str(error)

        result.update({
            "closed": safe_value(entity.closed),
            "elevation": safe_get_dxf_attribute(entity, "elevation"),
            "thickness": safe_get_dxf_attribute(entity, "thickness"),
            "points": points,
        })

    elif entity_type == "POLYLINE":
        vertices = []
        try:
            for vertex in entity.vertices:
                vertices.append({
                    "handle": safe_get_dxf_attribute(vertex, "handle"),
                    "attributes": extract_dxf_attributes(vertex),
                })
        except Exception as error:
            result["vertices_error"] = str(error)

        result.update({
            "is_3d_polyline": entity.is_3d_polyline(),
            "is_polygon_mesh": entity.is_polygon_mesh(),
            "is_poly_face_mesh": entity.is_poly_face_mesh(),
            "closed": safe_get_dxf_attribute(entity, "flags"),
            "vertices": vertices,
        })

    elif entity_type == "SPLINE":
        result = {
            "degree": safe_get_dxf_attribute(entity, "degree"),
            "flags": safe_get_dxf_attribute(entity, "flags"),
            "control_points": safe_get_dxf_attribute(entity, "control_points"),
            "fit_points": safe_get_dxf_attribute(entity, "fit_points"),
            "knots": safe_get_dxf_attribute(entity, "knots"),
            "weights": safe_get_dxf_attribute(entity, "weights"),
        }

    elif entity_type == "TEXT":
        result = {
            "text": safe_get_dxf_attribute(entity, "text"),
            "insert": safe_get_dxf_attribute(entity, "insert"),
            "height": safe_get_dxf_attribute(entity, "height"),
            "rotation": safe_get_dxf_attribute(entity, "rotation"),
            "style": safe_get_dxf_attribute(entity, "style"),
            "width": safe_get_dxf_attribute(entity, "width"),
            "oblique": safe_get_dxf_attribute(entity, "oblique"),
        }

    elif entity_type == "MTEXT":
        result = {
            "text": safe_get_dxf_attribute(entity, "text"),
            "insert": safe_get_dxf_attribute(entity, "insert"),
            "char_height": safe_get_dxf_attribute(entity, "char_height"),
            "rotation": safe_get_dxf_attribute(entity, "rotation"),
            "style": safe_get_dxf_attribute(entity, "style"),
            "attachment_point": safe_get_dxf_attribute(entity, "attachment_point"),
        }

    elif entity_type == "INSERT":
        result = {
            "block_name": safe_get_dxf_attribute(entity, "name"),
            "insert": safe_get_dxf_attribute(entity, "insert"),
            "rotation": safe_get_dxf_attribute(entity, "rotation"),
            "xscale": safe_get_dxf_attribute(entity, "xscale"),
            "yscale": safe_get_dxf_attribute(entity, "yscale"),
            "zscale": safe_get_dxf_attribute(entity, "zscale"),
            "attribs": [],
        }
        try:
            for attrib in entity.attribs:
                result["attribs"].append({
                    "tag": safe_get_dxf_attribute(attrib, "tag"),
                    "text": safe_get_dxf_attribute(attrib, "text"),
                    "insert": safe_get_dxf_attribute(attrib, "insert"),
                    "rotation": safe_get_dxf_attribute(attrib, "rotation"),
                    "layer": safe_get_dxf_attribute(attrib, "layer"),
                })
        except Exception as error:
            result["attributes_error"] = str(error)

    elif entity_type == "HATCH":
        result = {
            "pattern_name": safe_get_dxf_attribute(entity, "pattern_name"),
            "solid_fill": safe_get_dxf_attribute(entity, "solid_fill"),
            "associative": safe_get_dxf_attribute(entity, "associative"),
            "elevation": safe_get_dxf_attribute(entity, "elevation"),
            "extrusion": safe_get_dxf_attribute(entity, "extrusion"),
            "boundary_paths": [],
        }
        try:
            for path in entity.paths:
                result["boundary_paths"].append({
                    "type": path.path_type_flags,
                    "is_polyline": path.is_polyline,
                    "is_edge_path": path.is_edge_path,
                    "data": safe_value(path),
                })
        except Exception as error:
            result["boundary_paths_error"] = str(error)

    elif entity_type == "DIMENSION":
        result = {
            "dimension_type": safe_get_dxf_attribute(entity, "dimtype"),
            "text": safe_get_dxf_attribute(entity, "text"),
            "insert": safe_get_dxf_attribute(entity, "defpoint"),
            "defpoint2": safe_get_dxf_attribute(entity, "defpoint2"),
            "defpoint3": safe_get_dxf_attribute(entity, "defpoint3"),
            "defpoint4": safe_get_dxf_attribute(entity, "defpoint4"),
            "actual_measurement": safe_get_dxf_attribute(entity, "actual_measurement"),
            "dimension_style": safe_get_dxf_attribute(entity, "dimstyle"),
        }

    elif entity_type == "3DFACE":
        result = {
            "vtx0": safe_get_dxf_attribute(entity, "vtx0"),
            "vtx1": safe_get_dxf_attribute(entity, "vtx1"),
            "vtx2": safe_get_dxf_attribute(entity, "vtx2"),
            "vtx3": safe_get_dxf_attribute(entity, "vtx3"),
        }

    elif entity_type == "MESH":
        result = {
            "version": safe_get_dxf_attribute(entity, "version"),
            "subdivision_levels": safe_get_dxf_attribute(entity, "subdivision_levels"),
            "vertices": safe_get_dxf_attribute(entity, "vertices"),
            "edges": safe_get_dxf_attribute(entity, "edges"),
            "faces": safe_get_dxf_attribute(entity, "faces"),
        }

    elif entity_type in ["SOLID", "TRACE"]:
        result = {
            "vtx0": safe_get_dxf_attribute(entity, "vtx0"),
            "vtx1": safe_get_dxf_attribute(entity, "vtx1"),
            "vtx2": safe_get_dxf_attribute(entity, "vtx2"),
            "vtx3": safe_get_dxf_attribute(entity, "vtx3"),
        }

    elif entity_type == "LEADER":
        result = {
            "vertices": safe_get_dxf_attribute(entity, "vertices"),
            "annotation": safe_get_dxf_attribute(entity, "annotation"),
            "style": safe_get_dxf_attribute(entity, "dimstyle"),
        }

    elif entity_type == "VIEWPORT":
        result = {
            "center": safe_get_dxf_attribute(entity, "center"),
            "width": safe_get_dxf_attribute(entity, "width"),
            "height": safe_get_dxf_attribute(entity, "height"),
            "view_center_point": safe_get_dxf_attribute(entity, "view_center_point"),
            "view_direction_vector": safe_get_dxf_attribute(entity, "view_direction_vector"),
            "view_target_point": safe_get_dxf_attribute(entity, "view_target_point"),
        }

    elif entity_type == "IMAGE":
        result = {
            "insert": safe_get_dxf_attribute(entity, "insert"),
            "image_size": safe_get_dxf_attribute(entity, "image_size"),
            "u_pixel": safe_get_dxf_attribute(entity, "u_pixel"),
            "v_pixel": safe_get_dxf_attribute(entity, "v_pixel"),
        }

    return result


# ============================================================
# ENTITY READER
# ============================================================

def read_entity(entity) -> dict:
    return {
        "type": entity.dxftype(),
        "handle": safe_get_dxf_attribute(entity, "handle"),
        "owner": safe_get_dxf_attribute(entity, "owner"),
        "layer": safe_get_dxf_attribute(entity, "layer"),
        "color": safe_get_dxf_attribute(entity, "color"),
        "true_color": safe_get_dxf_attribute(entity, "true_color"),
        "linetype": safe_get_dxf_attribute(entity, "linetype"),
        "lineweight": safe_get_dxf_attribute(entity, "lineweight"),
        "dxf_attributes": extract_dxf_attributes(entity),
        "geometry": extract_entity_geometry(entity),
        "xdata": extract_xdata(entity),
        "extension_dictionary": extract_extension_dictionary(entity),
    }


# ============================================================
# ENTITY SPACE ANALYSIS
# ============================================================

def analyze_entity_space(entity_space, name: str) -> dict:
    entity_counts = Counter()
    layer_counts = Counter()
    entities = []
    errors = []

    for index, entity in enumerate(entity_space):
        entity_type = "UNKNOWN"
        try:
            entity_type = entity.dxftype()
            entity_counts[entity_type] += 1

            layer = safe_get_dxf_attribute(entity, "layer", "NO_LAYER")
            layer_counts[str(layer)] += 1

            entity_data = read_entity(entity)
            entity_data["space_index"] = index
            entities.append(entity_data)

        except Exception as error:
            errors.append({
                "index": index,
                "type": entity_type,
                "error": str(error),
                "traceback": traceback.format_exc(),
            })

    return {
        "name": name,
        "entity_count": sum(entity_counts.values()),
        "entity_counts": dict(sorted(entity_counts.items())),
        "layer_counts": dict(sorted(layer_counts.items())),
        "errors": errors,
        "entities": entities,
    }


# ============================================================
# HEADER ANALYSIS
# ============================================================

def analyze_header(doc) -> dict:
    result = {}
    try:
        for key, value in doc.header.items():
            result[key] = safe_value(value)
    except Exception as error:
        result["_error"] = str(error)
    return result


# ============================================================
# TABLE ANALYZER
# ============================================================

def analyze_table(table, table_name: str) -> dict:
    result = {"name": table_name, "count": 0, "entries": []}
    try:
        for entry in table:
            result["count"] += 1
            result["entries"].append({
                "name": safe_get_dxf_attribute(entry, "name"),
                "handle": safe_get_dxf_attribute(entry, "handle"),
                "dxf_attributes": extract_dxf_attributes(entry),
            })
    except Exception as error:
        result["_error"] = str(error)
    return result


# ============================================================
# LAYERS
# ============================================================

def analyze_layers(doc) -> dict:
    result = {"count": 0, "layers": []}
    try:
        for layer in doc.layers:
            result["count"] += 1
            result["layers"].append({
                "name": safe_get_dxf_attribute(layer, "name"),
                "handle": safe_get_dxf_attribute(layer, "handle"),
                "color": safe_get_dxf_attribute(layer, "color"),
                "linetype": safe_get_dxf_attribute(layer, "linetype"),
                "flags": safe_get_dxf_attribute(layer, "flags"),
                "is_off": safe_value(layer.is_off()),
                "is_frozen": safe_value(layer.is_frozen()),
                "is_locked": safe_value(layer.is_locked()),
                "dxf_attributes": extract_dxf_attributes(layer),
            })
    except Exception as error:
        result["_error"] = str(error)
    return result


# ============================================================
# BLOCK ANALYSIS
# ============================================================

def analyze_blocks(doc) -> dict:
    result = {"count": 0, "blocks": []}
    try:
        for block in doc.blocks:
            result["count"] += 1
            block_entity_counts = Counter()
            entities = []
            block_error = None

            try:
                for entity in block:
                    block_entity_counts[entity.dxftype()] += 1
                    entities.append(read_entity(entity))
            except Exception as error:
                block_error = str(error)

            block_data = {
                "name": safe_value(block.name),
                "block_record": safe_value(getattr(block, "block_record", None)),
                "entity_count": sum(block_entity_counts.values()),
                "entity_counts": dict(sorted(block_entity_counts.items())),
                "entities": entities,
            }
            if block_error:
                block_data["error"] = block_error

            result["blocks"].append(block_data)
    except Exception as error:
        result["_error"] = str(error)
    return result


# ============================================================
# BLOCK REFERENCE SUMMARY
# ============================================================

def analyze_block_references(doc) -> dict:
    result = {
        "total_insert_entities": 0,
        "references_by_block": {},
        "references": [],
    }
    try:
        for entity in doc.query("INSERT"):
            result["total_insert_entities"] += 1
            block_name = safe_get_dxf_attribute(entity, "name", "UNKNOWN")
            result["references_by_block"][block_name] = (
                result["references_by_block"].get(block_name, 0) + 1
            )

            reference = {
                "handle": safe_get_dxf_attribute(entity, "handle"),
                "block_name": block_name,
                "insert": safe_get_dxf_attribute(entity, "insert"),
                "rotation": safe_get_dxf_attribute(entity, "rotation"),
                "xscale": safe_get_dxf_attribute(entity, "xscale"),
                "yscale": safe_get_dxf_attribute(entity, "yscale"),
                "zscale": safe_get_dxf_attribute(entity, "zscale"),
                "layer": safe_get_dxf_attribute(entity, "layer"),
                "attributes": [],
            }

            try:
                for attrib in entity.attribs:
                    reference["attributes"].append({
                        "tag": safe_get_dxf_attribute(attrib, "tag"),
                        "text": safe_get_dxf_attribute(attrib, "text"),
                        "insert": safe_get_dxf_attribute(attrib, "insert"),
                        "layer": safe_get_dxf_attribute(attrib, "layer"),
                    })
            except Exception:
                pass

            result["references"].append(reference)
    except Exception as error:
        result["_error"] = str(error)
    return result


# ============================================================
# LAYOUT ANALYSIS
# ============================================================

def analyze_layouts(doc) -> dict:
    result = {"layout_names": [], "layouts": []}
    try:
        layout_names = doc.layout_names()
        result["layout_names"] = list(layout_names)

        for layout_name in layout_names:
            layout = doc.layout(layout_name)
            result["layouts"].append(analyze_entity_space(layout, layout_name))
    except Exception as error:
        result["_error"] = str(error)
    return result


# ============================================================
# APPID ANALYSIS
# ============================================================

def analyze_appids(doc) -> dict:
    result = {"count": 0, "appids": []}
    try:
        for appid in doc.appids:
            result["count"] += 1
            result["appids"].append({
                "name": safe_get_dxf_attribute(appid, "name"),
                "handle": safe_get_dxf_attribute(appid, "handle"),
                "attributes": extract_dxf_attributes(appid),
            })
    except Exception as error:
        result["_error"] = str(error)
    return result


# ============================================================
# ENTITY DATABASE ANALYSIS
# ============================================================

def analyze_entity_database(doc) -> dict:
    counts = Counter()
    total = 0
    errors = []

    try:
        for handle, entity in doc.entitydb.items():
            try:
                total += 1
                counts[entity.dxftype()] += 1
            except Exception as error:
                errors.append({"handle": str(handle), "error": str(error)})
    except Exception as error:
        return {"error": str(error)}

    return {
        "total_entities": total,
        "entity_type_counts": dict(sorted(counts.items())),
        "errors": errors,
    }


# ============================================================
# OBJECTS SECTION
# ============================================================

def analyze_objects(doc) -> dict:
    counts = Counter()
    objects = []
    errors = []

    try:
        for obj in doc.objects:
            try:
                object_type = obj.dxftype()
                counts[object_type] += 1
                objects.append({
                    "type": object_type,
                    "handle": safe_get_dxf_attribute(obj, "handle"),
                    "owner": safe_get_dxf_attribute(obj, "owner"),
                    "attributes": extract_dxf_attributes(obj),
                })
            except Exception as error:
                errors.append({"error": str(error), "traceback": traceback.format_exc()})
    except Exception as error:
        errors.append({"error": str(error), "traceback": traceback.format_exc()})

    return {
        "object_count": sum(counts.values()),
        "object_type_counts": dict(sorted(counts.items())),
        "errors": errors,
        "objects": objects,
    }


# ============================================================
# DOCUMENT ANALYSIS
# ============================================================

def analyze_document(doc, source_file: Path, progress=None) -> dict:
    """
    Run the full analysis pipeline against an already-loaded ezdxf document.

    `progress`, if given, is a callable(str) used to report stage updates
    (e.g. to stream status to a web client).
    """

    def report_progress(message: str):
        if progress:
            progress(message)

    report_progress("Analyzing document...")

    report = {
        "analysis_metadata": {
            "analysis_time": datetime.now().isoformat(),
            "source_file": str(source_file),
            "source_file_size_bytes": source_file.stat().st_size if source_file.exists() else None,
        },
        "file_information": {
            "dxf_version": safe_value(doc.dxfversion),
            "acad_release": safe_value(doc.acad_release),
            "encoding": safe_value(doc.encoding),
            "filename": safe_value(getattr(doc, "filename", None)),
        },
        "header": analyze_header(doc),
        "tables": {
            "layers": analyze_layers(doc),
            "linetypes": analyze_table(doc.linetypes, "linetypes"),
            "text_styles": analyze_table(doc.styles, "text_styles"),
            "dimension_styles": analyze_table(doc.dimstyles, "dimension_styles"),
            "ucs": analyze_table(doc.ucs, "ucs"),
            "views": analyze_table(doc.views, "views"),
            "viewports": analyze_table(doc.viewports, "viewports"),
        },
        "appids": analyze_appids(doc),
        "modelspace": None,
        "layouts": None,
        "blocks": None,
        "block_references": None,
        "objects": None,
        "entity_database": None,
    }

    report_progress("Analyzing modelspace...")
    report["modelspace"] = analyze_entity_space(doc.modelspace(), "MODELSPACE")

    report_progress("Analyzing layouts...")
    report["layouts"] = analyze_layouts(doc)

    report_progress("Analyzing blocks...")
    report["blocks"] = analyze_blocks(doc)

    report_progress("Analyzing block references...")
    report["block_references"] = analyze_block_references(doc)

    report_progress("Analyzing objects...")
    report["objects"] = analyze_objects(doc)

    report_progress("Analyzing entity database...")
    report["entity_database"] = analyze_entity_database(doc)

    return report


# ============================================================
# SUMMARY REPORT
# ============================================================

def create_summary(report: dict) -> str:
    lines = []
    lines.append("CAD ANALYSIS SUMMARY")
    lines.append("=" * 80)
    lines.append("")

    file_info = report.get("file_information", {})
    lines.append(f"DXF Version: {file_info.get('dxf_version')}")
    lines.append(f"AutoCAD Release: {file_info.get('acad_release')}")
    lines.append("")

    lines.append("HEADER")
    lines.append("-" * 80)
    header = report.get("header", {})
    important_header_values = [
        "$ACADVER", "$DWGCODEPAGE", "$INSUNITS", "$MEASUREMENT",
        "$EXTMIN", "$EXTMAX", "$LIMMIN", "$LIMMAX",
        "$UCSNAME", "$ANGBASE", "$AUNITS", "$LUNITS",
    ]
    for key in important_header_values:
        if key in header:
            lines.append(f"{key}: {header[key]}")
    lines.append("")

    layers = report["tables"]["layers"]
    lines.append(f"LAYERS: {layers.get('count', 0)}")
    lines.append("-" * 80)
    for layer in layers.get("layers", []):
        lines.append(
            f"{layer.get('name')} | Color: {layer.get('color')} | "
            f"Off: {layer.get('is_off')} | Frozen: {layer.get('is_frozen')} | "
            f"Locked: {layer.get('is_locked')}"
        )
    lines.append("")

    modelspace = report["modelspace"]
    lines.append("MODELSPACE")
    lines.append("-" * 80)
    lines.append(f"Total Entities: {modelspace.get('entity_count', 0)}")
    lines.append("")
    for entity_type, count in modelspace.get("entity_counts", {}).items():
        lines.append(f"{entity_type}: {count}")
    lines.append("")

    lines.append("ENTITIES BY LAYER")
    lines.append("-" * 80)
    for layer, count in modelspace.get("layer_counts", {}).items():
        lines.append(f"{layer}: {count}")
    lines.append("")

    blocks = report["blocks"]
    lines.append(f"BLOCK DEFINITIONS: {blocks.get('count', 0)}")
    lines.append("-" * 80)
    for block in blocks.get("blocks", []):
        lines.append(
            f"{block.get('name')} | Entities: {block.get('entity_count')} | "
            f"Types: {block.get('entity_counts')}"
        )
    lines.append("")

    references = report["block_references"]
    lines.append(f"BLOCK INSERTS: {references.get('total_insert_entities', 0)}")
    lines.append("-" * 80)
    for block_name, count in references.get("references_by_block", {}).items():
        lines.append(f"{block_name}: {count}")
    lines.append("")

    objects = report["objects"]
    lines.append(f"OBJECTS: {objects.get('object_count', 0)}")
    lines.append("-" * 80)
    for object_type, count in objects.get("object_type_counts", {}).items():
        lines.append(f"{object_type}: {count}")
    lines.append("")

    entity_db = report["entity_database"]
    lines.append(f"ENTITY DATABASE TOTAL: {entity_db.get('total_entities', 0)}")
    lines.append("")

    return "\n".join(lines)


# ============================================================
# PUBLIC ENTRY POINT (used by the Flask app)
# ============================================================

class CADAnalysisError(Exception):
    """Raised when a DWG file cannot be loaded or analyzed."""


def analyze_dwg_file(source_path: Path, progress=None) -> tuple[dict, str]:
    """
    Load a DWG file through the ODA File Converter and run the full
    analysis pipeline against it.

    Returns (report_dict, summary_text).
    Raises CADAnalysisError on failure (missing ODA converter, corrupt
    file, unsupported version, etc.) with a human-readable message.
    """

    source_path = Path(source_path)

    if not source_path.exists():
        raise CADAnalysisError(f"File not found: {source_path}")

    if progress:
        progress("Loading DWG through ODA File Converter...")

    try:
        doc = odafc.readfile(source_path)
    except Exception as error:
        raise CADAnalysisError(
            "Failed to load DWG. Make sure the ODA File Converter is "
            f"installed and the file is a valid DWG. Details: {error}"
        ) from error

    try:
        report = analyze_document(doc, source_path, progress=progress)
        summary = create_summary(report)
    except Exception as error:
        raise CADAnalysisError(f"Analysis failed: {error}") from error

    return report, summary
