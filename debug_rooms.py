"""
Standalone room-detection diagnostic.

Run from your project root (F:\\LuxSCale-Cad\\LuxScaleCADAnalyzer):

    python debug_rooms.py

This prints:
  - detected $INSUNITS and the resulting unit_scale (this is the first
    thing to check — if unit_scale looks wrong for this file, everything
    downstream will be wrong too)
  - every candidate closed-loop room found in the DWG, including the ones
    currently filtered out as "too small," with area/layer/matched label
  - the world-space extents of every top-level INSERT block once
    exploded, so we can see if any block's geometry lands far outside the
    main house's coordinate range
  - final detected rooms and doors

Paste the FULL output back so the detection thresholds / block handling
can be tuned against real numbers instead of guesses.
"""

import sys
from pathlib import Path

# Make sure cad_analyzer package is importable when run from project root.
sys.path.insert(0, str(Path(__file__).parent))

from cad_analyzer.dwg_reader import DWGReader

DWG_PATH = "data/input/Two-story-house-410202.dwg"


# =============================================================
# INSERT EXTENT DIAGNOSTIC
# =============================================================

def print_insert_extents(reader):
    """Print the world-space bounding box of each top-level INSERT's
    exploded contents, compared against a baseline of everything NOT
    inside any INSERT. Used to find a block whose geometry lands far
    outside the main house (wrong offset/scale), which would blow up
    the total drawing bbox and break both the canvas autofit and the
    outer-envelope container filter.

    Uses reader.raw_entities (top-level, pre-flatten) for the baseline
    and iterates top-level INSERTs directly, since reader.entities has
    already had non-door INSERTs exploded into their children."""
    print("\n--- TOP-LEVEL INSERT WORLD-SPACE EXTENTS ---")

    xs, ys = [], []
    for entity in reader.raw_entities:
        etype = entity.dxftype()
        if etype == "LINE":
            try:
                start = entity.dxf.start
                end = entity.dxf.end
                p1 = reader._scale_point(float(start.x), float(start.y))
                p2 = reader._scale_point(float(end.x), float(end.y))
                xs += [p1[0], p2[0]]
                ys += [p1[1], p2[1]]
            except Exception:
                pass
        elif etype in ("LWPOLYLINE", "POLYLINE"):
            for p in reader.extract_polyline(entity):
                xs.append(p[0])
                ys.append(p[1])

    if xs and ys:
        print(
            f"  BASELINE (non-block top-level geometry, meters): "
            f"x=[{min(xs):.2f}, {max(xs):.2f}]  y=[{min(ys):.2f}, {max(ys):.2f}]"
        )
    else:
        print("  BASELINE: no non-block LINE/POLYLINE geometry found at top level")

    for entity in reader.raw_entities:
        if entity.dxftype() != "INSERT":
            continue

        name = entity.dxf.name
        try:
            insert_pos = entity.dxf.insert
            scale = (
                getattr(entity.dxf, "xscale", 1.0),
                getattr(entity.dxf, "yscale", 1.0),
                getattr(entity.dxf, "zscale", 1.0),
            )
            rotation = getattr(entity.dxf, "rotation", 0.0)
        except Exception:
            insert_pos, scale, rotation = None, None, None

        try:
            children = list(entity.virtual_entities())
        except Exception as error:
            print(f"  INSERT '{name}': virtual_entities() FAILED: {error}")
            continue

        cxs, cys = [], []
        for child in children:
            ctype = child.dxftype()
            try:
                if ctype == "LINE":
                    start = child.dxf.start
                    end = child.dxf.end
                    p1 = reader._scale_point(float(start.x), float(start.y))
                    p2 = reader._scale_point(float(end.x), float(end.y))
                    cxs += [p1[0], p2[0]]
                    cys += [p1[1], p2[1]]
                elif ctype in ("LWPOLYLINE", "POLYLINE"):
                    for p in reader.extract_polyline(child):
                        cxs.append(p[0])
                        cys.append(p[1])
            except Exception:
                continue

        child_types = {}
        for child in children:
            t = child.dxftype()
            child_types[t] = child_types.get(t, 0) + 1

        if cxs and cys:
            print(
                f"  INSERT '{name}'  insert_point={insert_pos}  "
                f"scale={scale}  rotation={rotation}"
            )
            print(
                f"      exploded extents (meters): x=[{min(cxs):.2f}, {max(cxs):.2f}]  "
                f"y=[{min(cys):.2f}, {max(cys):.2f}]  "
                f"children_by_type={child_types}"
            )
        else:
            print(
                f"  INSERT '{name}'  insert_point={insert_pos}  "
                f"-> no LINE/POLYLINE geometry in its {len(children)} children "
                f"(types: {child_types})"
            )


# =============================================================
# MAIN
# =============================================================

def main():
    print(f"Loading: {DWG_PATH}")
    reader = DWGReader(DWG_PATH)
    reader.load()

    print(
        f"\nDetected $INSUNITS = {reader.detected_insunits}  "
        f"-> unit_scale to meters = {reader.unit_scale}"
    )
    print("(If this scale looks wrong for this file, pass "
          "assume_unitless_as='m'/'in'/'ft' to DWGReader(...) and rerun.)")

    print(f"\nLayers ({len(reader.layers)}):")
    for layer in reader.layers:
        print(f"  - {layer}")

    print(f"\nTotal entities (top-level, raw): {len(reader.raw_entities)}")
    print(f"Total entities (flattened, blocks exploded): {len(reader.flattened_entities)}")
    print(f"Total drawing bbox area: {reader.compute_total_bbox_area():.3f} m^2")

    print_insert_extents(reader)

    print("\n--- ALL CANDIDATE ROOMS (before area filtering) ---")
    print(f"Current MIN_ROOM_AREA = {reader.MIN_ROOM_AREA} m^2")
    reader.print_all_candidate_rooms()

    print("\n--- FINAL DETECTED ROOMS (after all filtering) ---")
    reader.print_layer_area_report()
    final_rooms = reader.detect_rooms()
    print(f"\nFinal room count: {len(final_rooms)}")
    for room in final_rooms:
        print(
            f"  id={room['id']:3d}  name={room.get('name', ''):20s}  "
            f"area={room['area']:8.3f} m^2  layer={room['layer']}"
        )

    print("\n--- DOORS ---")
    doors = reader.detect_doors()
    print(f"Doors found via INSERT blocks: {len(doors)}")
    for door in doors:
        print(f"  {door}")

    print("\n--- ALL INSERT (block) ENTITIES, top-level ---")
    print("(use this to find the real door block name if detect_doors() found 0)")
    insert_names = {}
    for entity in reader.raw_entities:
        if entity.dxftype() == "INSERT":
            name = entity.dxf.name
            insert_names[name] = insert_names.get(name, 0) + 1
    for name, count in sorted(insert_names.items(), key=lambda x: -x[1]):
        print(f"  {name}: {count}")

    print("\n--- ALL TEXT / MTEXT LABELS ---")
    labels = reader.extract_text_labels()
    print(f"Found {len(labels)} text labels")
    for label in labels:
        print(f"  '{label['text']}' at {label['position']}")


if __name__ == "__main__":
    main()