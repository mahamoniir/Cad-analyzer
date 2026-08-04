from __future__ import annotations

from pathlib import Path
from typing import Optional
import math
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
import os
import ezdxf
from ezdxf import edgeminer


# Typical Windows install locations for ODA File Converter.
# Checked only when running locally on Windows (deploy uses Linux paths).
_WINDOWS_ODA_CANDIDATES = [
    r"C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe",
    r"C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe",
    r"C:\Program Files\ODA\ODAFileConverter 26.12.0\ODAFileConverter.exe",
    r"C:\Program Files (x86)\ODA\ODAFileConverter\ODAFileConverter.exe",
]


class DWGReader:

    # Layers whose closed shapes should NEVER be treated as rooms.
    # Matched as a case-insensitive substring against the layer name.
    # Tune this list using print_layer_area_report() against your real files.
    EXCLUDED_LAYER_KEYWORDS = [
        "mobiliario", "furniture", "muebles", "furn",
        "dim", "dimension", "text", "annotation", "anno",
        "hatch", "title", "grid", "detail", "symbol",
        "elec", "electrical", "plumb", "fixture",
    ]

    # Block-name keywords used to identify door inserts.
    DOOR_BLOCK_KEYWORDS = ["door", "puerta", "dver", "m_door"]

    # Minimum polygon area (in drawing units, expected to be meters after
    # $INSUNITS scaling) to be considered a room at all, when there is NO
    # text label to vouch for it. Tune this against your smallest real
    # unlabeled room.
    MIN_ROOM_AREA = 1.5

    # Labeled spaces (closets, linen, etc.) can legitimately be tiny —
    # trust the label over the area cutoff used for unlabeled noise.
    MIN_LABELED_ROOM_AREA = 0.3

    def __init__(
        self,
        file_path: str,
        oda_path: Optional[str] = None
    ):
        self.original_file_path = Path(file_path)
        self.oda_path = oda_path
        self.file_path = self.original_file_path
        self.doc = None
        self.modelspace = None
        self.entities = []
        self.layers = []
        self.converted_dxf_path = None

        # Populated by detect_rooms(): text labels that were found in the
        # drawing but never matched to any closed geometry candidate.
        # Useful for surfacing "label found, no boundary detected" in the
        # GUI instead of the room silently vanishing.
        self.unmatched_labels = []

    # =========================================================
    # LOAD
    # =========================================================

    def load(self):
        if not self.original_file_path.exists():
            raise FileNotFoundError(
                f"CAD file not found:\n{self.original_file_path}"
            )

        extension = self.original_file_path.suffix.lower()

        # -----------------------------------------------------
        # DWG -> DXF THROUGH ODA
        # -----------------------------------------------------
        if extension == ".dwg":
            self.converted_dxf_path = self.convert_dwg_to_dxf()
            self.file_path = Path(self.converted_dxf_path)
        elif extension == ".dxf":
            self.file_path = self.original_file_path
        else:
            raise ValueError(
                "Unsupported CAD file format. Only DWG and DXF are supported."
            )

        # -----------------------------------------------------
        # READ DXF WITH EZDXF
        # -----------------------------------------------------
        try:
            self.doc = ezdxf.readfile(str(self.file_path))
        except Exception as error:
            raise RuntimeError(f"Could not read converted DXF:\n{error}")

        self.modelspace = self.doc.modelspace()
        self.entities = list(self.modelspace)
        self.layers = [layer.dxf.name for layer in self.doc.layers]

        return self

    # =========================================================
    # FIND ODA
    # =========================================================

    def find_oda_converter(self):
        # Explicit path passed to DWGReader(oda_path=...)
        if self.oda_path and Path(self.oda_path).exists():
            return str(self.oda_path)

        # Local Windows: use installed ODA under Program Files.
        # Deployed Linux containers never hit this branch.
        if sys.platform == "win32":
            for candidate in _WINDOWS_ODA_CANDIDATES:
                if Path(candidate).exists():
                    return candidate
            # Also pick up versioned folders like "ODAFileConverter 27.1.0"
            for base in (
                Path(r"C:\Program Files\ODA"),
                Path(r"C:\Program Files (x86)\ODA"),
            ):
                if not base.is_dir():
                    continue
                for exe in base.glob("ODAFileConverter*/ODAFileConverter.exe"):
                    return str(exe)

        # Env vars set in the Dockerfile (Linux deploy)
        for env_key in ("LUXSCALE_ODA_PATH", "ODA_REAL_BIN"):
            env_path = os.environ.get(env_key)
            if env_path and Path(env_path).exists():
                return env_path

        # Resolve via PATH — finds /usr/local/bin/ODAFileConverter
        # (the xvfb wrapper) since it precedes /usr/bin in PATH.
        which_result = shutil.which("ODAFileConverter")
        if which_result:
            return which_result

        return None

    # =========================================================
    # CONVERT DWG -> DXF
    # =========================================================

    def convert_dwg_to_dxf(self):
        oda_exe = self.find_oda_converter()

        if not oda_exe:
            raise RuntimeError(
                "ODA File Converter was not found.\n\n"
                "Please install ODA File Converter or "
                "set the correct path in dwg_reader.py."
            )

        temp_root = Path(tempfile.mkdtemp(prefix="luxscale_oda_"))
        input_dir = temp_root / "input"
        output_dir = temp_root / "output"
        input_dir.mkdir()
        output_dir.mkdir()

        source_copy = input_dir / self.original_file_path.name
        shutil.copy2(self.original_file_path, source_copy)

        command = [
            oda_exe,
            str(input_dir),
            str(output_dir),
            "ACAD2018",
            "DXF",
            "0",
            "1"
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=180
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("ODA File Converter timed out.")

        if result.returncode != 0:
            raise RuntimeError(
                "ODA File Converter failed.\n\n"
                f"STDOUT:\n{result.stdout}\n\n"
                f"STDERR:\n{result.stderr}"
            )

        dxf_files = list(output_dir.glob("*.dxf"))

        if not dxf_files:
            raise RuntimeError(
                "ODA completed but no DXF file was created.\n\n"
                f"Output:\n{result.stdout}\n"
                f"Errors:\n{result.stderr}"
            )

        return str(dxf_files[0])

    # =========================================================
    # SUMMARY
    # =========================================================

    def get_summary(self):
        rooms = self.detect_rooms()
        doors = self.detect_doors()

        return {
            "file": str(self.original_file_path),
            "converted_file": str(self.file_path),
            "layers": len(self.layers),
            "entities": len(self.entities),
            "rooms": len(rooms),
            "doors": len(doors),
            "unmatched_labels": len(self.unmatched_labels),
        }

    # =========================================================
    # LAYER FILTERING
    # =========================================================

    def is_room_layer(self, layer_name):
        """Return False if this layer should never produce a room
        (furniture, dimensions, text, hatching, etc.)."""
        name = (layer_name or "").lower()
        return not any(
            keyword in name
            for keyword in self.EXCLUDED_LAYER_KEYWORDS
        )

    # =========================================================
    # GEOMETRY HELPERS
    # =========================================================

    @staticmethod
    def distance(p1, p2):
        return math.sqrt(
            (p2[0] - p1[0]) ** 2
            + (p2[1] - p1[1]) ** 2
        )

    @staticmethod
    def same_point(p1, p2, tolerance=0.05):
        return DWGReader.distance(p1, p2) <= tolerance

    # =========================================================
    # POLYLINE POINTS
    # =========================================================

    def extract_polyline(self, entity):
        points = []

        try:
            if entity.dxftype() == "LWPOLYLINE":
                for point in entity.get_points():
                    points.append((float(point[0]), float(point[1])))

            elif entity.dxftype() == "POLYLINE":
                for vertex in entity.vertices:
                    location = vertex.dxf.location
                    points.append((float(location.x), float(location.y)))

        except Exception:
            return []

        return points

    # =========================================================
    # LOOP CANDIDATES (raw geometry, not yet tied to a room)
    # =========================================================

    def collect_polyline_candidates(self):
        """Every closed LWPOLYLINE/POLYLINE on a room-eligible layer,
        as a raw geometry candidate. No area filtering here — even a
        tiny closed shape might turn out to be a labeled closet."""
        candidates = []

        for index, entity in enumerate(self.entities):
            entity_type = entity.dxftype()

            if entity_type not in ["LWPOLYLINE", "POLYLINE"]:
                continue
            if not self.is_room_layer(entity.dxf.layer):
                continue

            points = self.extract_polyline(entity)
            if len(points) < 3:
                continue

            is_closed = False
            try:
                is_closed = bool(entity.closed)
            except Exception:
                pass
            if not is_closed and self.same_point(points[0], points[-1]):
                is_closed = True
            if not is_closed:
                continue

            if self.same_point(points[0], points[-1]):
                points = points[:-1]

            area = self.polygon_area(points)
            if area <= 0:
                continue

            candidates.append({
                "source": "polyline",
                "index": index,
                "entity": entity,
                "points": points,
                "area": area,
                "centroid": self.polygon_centroid(points),
                "layer": entity.dxf.layer,
            })

        return candidates

    def collect_line_loop_candidates(self):
        """Every closed loop minable out of raw LINE geometry, as a raw
        geometry candidate. No area filtering here for the same reason
        as collect_polyline_candidates."""
        lines = []
        for index, entity in enumerate(self.entities):
            if entity.dxftype() != "LINE":
                continue
            if not self.is_room_layer(entity.dxf.layer):
                continue
            try:
                start = entity.dxf.start
                end = entity.dxf.end
                p1 = (float(start.x), float(start.y))
                p2 = (float(end.x), float(end.y))
                if self.distance(p1, p2) < 0.001:
                    continue
                lines.append({"index": index, "start": p1, "end": p2, "entity": entity})
            except Exception:
                continue

        if len(lines) < 3:
            return []

        gap_tol = self.estimate_gap_tolerance(lines)
        edges = [
            edgeminer.make_edge(line["start"], line["end"], payload=line)
            for line in lines
        ]
        deposit = edgeminer.Deposit(edges, gap_tol=gap_tol)

        candidates = []
        seen_signatures = set()

        for edge in deposit.edges:
            for clockwise in (True, False):
                for start_edge in (edge, edge.reversed()):
                    loop = edgeminer.find_loop_by_edge(deposit, start_edge, clockwise=clockwise)
                    if len(loop) < 3:
                        continue

                    points = self.loop_edges_to_points(loop, gap_tol)
                    if len(points) < 3:
                        continue

                    area = self.polygon_area(points)
                    if area <= 0:
                        continue

                    signature = self.loop_signature(points, gap_tol)
                    if signature in seen_signatures:
                        continue
                    seen_signatures.add(signature)

                    segment_payloads = [s.payload for s in loop if s.payload is not None]
                    layer_counts = Counter(
                        p["entity"].dxf.layer
                        for p in segment_payloads
                        if p.get("entity") is not None
                    )
                    dominant_layer = layer_counts.most_common(1)[0][0] if layer_counts else "UNKNOWN"
                    index_hint = min((p["index"] for p in segment_payloads), default=0)

                    candidates.append({
                        "source": "line_loop",
                        "index": index_hint,
                        "entity": None,
                        "points": points,
                        "area": area,
                        "centroid": self.polygon_centroid(points),
                        "layer": dominant_layer,
                    })

        return self.filter_container_loops(candidates)

    def collect_all_candidates(self):
        """Merge polyline and line-loop candidates, deduping near-identical
        geometry (prefer the polyline source — it's an authored entity,
        not something mined out of raw lines)."""
        polyline_candidates = self.collect_polyline_candidates()
        line_candidates = self.collect_line_loop_candidates()

        seen = {}
        for candidate in polyline_candidates + line_candidates:
            signature = self.loop_signature(candidate["points"], 0.05)
            existing = seen.get(signature)
            if existing is None or (
                existing["source"] != "polyline" and candidate["source"] == "polyline"
            ):
                seen[signature] = candidate

        candidates = list(seen.values())
        for candidate_id, candidate in enumerate(candidates):
            candidate["id"] = candidate_id

        return candidates

    # =========================================================
    # LINE-BASED ROOM HELPERS
    # =========================================================

    @staticmethod
    def polygon_centroid(points):
        if len(points) < 3:
            return points[0]

        signed_area = 0.0
        centroid_x = 0.0
        centroid_y = 0.0

        for i in range(len(points)):
            x1, y1 = points[i]
            x2, y2 = points[(i + 1) % len(points)]
            cross = (x1 * y2) - (x2 * y1)
            signed_area += cross
            centroid_x += (x1 + x2) * cross
            centroid_y += (y1 + y2) * cross

        if abs(signed_area) < 1e-12:
            return (
                sum(point[0] for point in points) / len(points),
                sum(point[1] for point in points) / len(points),
            )

        factor = 1.0 / (3.0 * signed_area)
        return (
            centroid_x * factor,
            centroid_y * factor,
        )

    @staticmethod
    def point_in_polygon(point, polygon):
        x, y = point
        inside = False

        for i in range(len(polygon)):
            x1, y1 = polygon[i]
            x2, y2 = polygon[(i + 1) % len(polygon)]

            intersects = (
                (y1 > y) != (y2 > y)
                and x < (x2 - x1) * (y - y1) / ((y2 - y1) + 1e-12) + x1
            )
            if intersects:
                inside = not inside

        return inside

    @staticmethod
    def estimate_gap_tolerance(segments):
        xs = []
        ys = []

        for segment in segments:
            xs.extend((segment["start"][0], segment["end"][0]))
            ys.extend((segment["start"][1], segment["end"][1]))

        if not xs or not ys:
            return 0.05

        diagonal = math.sqrt(
            (max(xs) - min(xs)) ** 2
            + (max(ys) - min(ys)) ** 2
        )

        return min(max(diagonal * 1e-4, 0.05), 2.0)

    def loop_edges_to_points(self, loop_edges, gap_tol):
        points = []

        for edge in loop_edges:
            point = (float(edge.start.x), float(edge.start.y))
            if not points or not self.same_point(points[-1], point, tolerance=gap_tol):
                points.append(point)

        if len(points) > 2 and self.same_point(points[0], points[-1], tolerance=gap_tol):
            points.pop()

        return points

    @staticmethod
    def loop_signature(points, gap_tol):
        quant = max(gap_tol, 0.001)
        normalized = sorted(
            (round(point[0] / quant), round(point[1] / quant))
            for point in points
        )
        return len(points), tuple(normalized)

    def filter_container_loops(self, loops):
        if len(loops) < 2:
            return loops

        filtered = []

        for i, candidate in enumerate(loops):
            is_merged_outer_loop = False
            for j, other in enumerate(loops):
                if i == j:
                    continue
                if candidate["area"] <= other["area"] * 1.05:
                    continue
                if self.point_in_polygon(other["centroid"], candidate["points"]):
                    is_merged_outer_loop = True
                    break

            if not is_merged_outer_loop:
                filtered.append(candidate)

        return filtered if filtered else loops

    # =========================================================
    # DOORS
    # =========================================================

    def detect_doors(self):
        """Detect doors inserted as block references (INSERT entities)
        whose block name matches a known door keyword, and pull the
        block's actual line/arc geometry (leaf + swing arc) so the
        frontend can draw the real door symbol instead of just a dot
        at its insertion point.

        If this returns doors with an empty "geometry" list, the door
        block in this drawing contains entity types not yet handled by
        entity_to_draw_data() (e.g. SPLINE/ELLIPSE) — the frontend can
        fall back to drawing a simple rectangle using "width" and
        "rotation" in that case."""
        doors = []

        for entity in self.entities:
            if entity.dxftype() != "INSERT":
                continue

            try:
                name = (entity.dxf.name or "").lower()
                if not any(keyword in name for keyword in self.DOOR_BLOCK_KEYWORDS):
                    continue

                insert = entity.dxf.insert

                # Explode the block into its real geometry (door leaf
                # line + swing arc, usually) instead of just recording
                # the insertion point.
                geometry = []
                try:
                    for sub_entity in entity.virtual_entities():
                        sub_data = self.entity_to_draw_data(sub_entity)
                        if sub_data:
                            geometry.append(sub_data)
                except Exception:
                    geometry = []

                # Fallback width estimate from the exploded geometry's
                # bounding box, in case the frontend wants to draw a
                # simple placeholder rectangle for door blocks whose
                # geometry didn't come through cleanly.
                width = None
                xs, ys = [], []
                for item in geometry:
                    if item["type"] == "LINE":
                        xs.extend([item["start"][0], item["end"][0]])
                        ys.extend([item["start"][1], item["end"][1]])
                    elif item["type"] == "POLYLINE":
                        xs.extend(p[0] for p in item["points"])
                        ys.extend(p[1] for p in item["points"])
                    elif item["type"] in ("ARC", "CIRCLE"):
                        xs.append(item["center"][0])
                        ys.append(item["center"][1])
                if xs and ys:
                    width = round(max(max(xs) - min(xs), max(ys) - min(ys)), 4)

                doors.append({
                    "block_name": entity.dxf.name,
                    "layer": entity.dxf.layer,
                    "position": [float(insert.x), float(insert.y)],
                    "rotation": float(getattr(entity.dxf, "rotation", 0.0)),
                    "width": width,
                    "geometry": geometry,
                })
            except Exception:
                continue

        return doors

    # =========================================================
    # TEXT LABELS (for room naming)
    # =========================================================

    def extract_text_labels(self):
        """Pull TEXT/MTEXT entities from the drawing so room names can be
        matched from real architect-placed labels instead of being
        synthesized as 'Room {area}'."""
        labels = []

        for entity in self.entities:
            entity_type = entity.dxftype()

            if entity_type not in ("TEXT", "MTEXT"):
                continue

            try:
                if entity_type == "TEXT":
                    content = entity.dxf.text
                else:
                    content = entity.plain_text()

                content = (content or "").strip()
                if not content:
                    continue

                pos = entity.dxf.insert
                labels.append({
                    "text": content,
                    "position": (float(pos.x), float(pos.y)),
                })
            except Exception:
                continue

        return labels

    def find_label_for_room(self, points, text_labels):
        if not text_labels:
            return None

        for label in text_labels:
            if self.point_in_polygon(label["position"], points):
                return label["text"]

        return None

    # =========================================================
    # LABEL-DRIVEN ROOM ASSIGNMENT
    # =========================================================

    def assign_labels_to_candidates(self, candidates, text_labels):
        """For every text label, claim the SMALLEST candidate polygon
        that contains it and hasn't already been claimed. Smallest =
        most specific: if a label sits inside both a big open-plan
        outline and a smaller room-shaped sub-loop, the sub-loop is
        almost always the real room boundary.

        Returns (labeled_rooms, used_ids, unmatched_labels). A label
        ends up in unmatched_labels when no closed candidate contains
        its position at all (usually a gap in the wall geometry near
        that label), OR when every candidate containing it is already
        claimed by another label — e.g. an open-plan KITCHEN/DINING/
        LIVING area with no interior wall separating them all sits
        inside one shared outer boundary. We deliberately do NOT fall
        back to reusing an already-claimed candidate here: doing so
        would create multiple room objects with identical geometry
        (and therefore identical centroids), which renders as stacked,
        overlapping labels in the UI."""
        used_ids = set()
        labeled_rooms = []
        unmatched_labels = []

        for label in text_labels:
            containing = [
                c for c in candidates
                if c["area"] >= self.MIN_LABELED_ROOM_AREA
                and self.point_in_polygon(label["position"], c["points"])
            ]
            if not containing:
                unmatched_labels.append(label)
                continue

            containing.sort(key=lambda c: c["area"])
            chosen = next((c for c in containing if c["id"] not in used_ids), None)
            if chosen is None:
                # Every containing candidate is already claimed by
                # another label. Don't fabricate a duplicate room that
                # reuses the same boundary/centroid — surface it as
                # unmatched instead.
                unmatched_labels.append(label)
                continue

            used_ids.add(chosen["id"])

            room = self.create_room(chosen["index"], chosen["points"], chosen.get("entity"))
            room["name"] = label["text"]
            room["layer"] = chosen.get("layer", room["layer"])
            labeled_rooms.append(room)

        return labeled_rooms, used_ids, unmatched_labels

    # =========================================================
    # DETECT ROOMS
    # =========================================================

    def detect_rooms(self):
        text_labels = self.extract_text_labels()
        candidates = self.collect_all_candidates()

        labeled_rooms, used_ids, unmatched_labels = self.assign_labels_to_candidates(
            candidates, text_labels
        )
        self.unmatched_labels = unmatched_labels

        # Leftover geometry has no matching text label — still worth
        # surfacing, just filtered more conservatively since there's
        # no label to vouch for a tiny/odd shape.
        leftover_rooms = []
        for candidate in candidates:
            if candidate["id"] in used_ids:
                continue
            if candidate["area"] < self.MIN_ROOM_AREA:
                continue
            room = self.create_room(candidate["index"], candidate["points"], candidate.get("entity"))
            room["layer"] = candidate.get("layer", room["layer"])
            leftover_rooms.append(room)

        leftover_rooms = self.remove_duplicate_rooms(leftover_rooms)
        leftover_rooms = self.filter_container_rooms(
            leftover_rooms, all_rooms=labeled_rooms + leftover_rooms
        )

        all_rooms = labeled_rooms + leftover_rooms
        for position, room in enumerate(all_rooms):
            room["id"] = position + 1

        return all_rooms

    # =========================================================
    # FILTER OUTER-ENVELOPE / CONTAINER ROOMS (unlabeled only)
    # =========================================================

    def filter_container_rooms(self, rooms, all_rooms=None):
        """Drop any unlabeled 'room' that is really an outer envelope
        wrapping several smaller rooms rather than a real room.
        `all_rooms` supplies the full set of rooms (labeled + leftover)
        used for containment checks, so a leftover container that wraps
        *labeled* rooms still gets caught even though those rooms live
        in a separate list. Labeled rooms are never candidates for
        removal here — the text label is treated as ground truth.

        Two signals must BOTH be true before something is dropped:
          1. It contains the centroids of at least 2 smaller rooms, AND
          2. Its area is a large fraction of the ENTIRE drawing's
             bounding-box footprint (not just larger than nearby rooms).
        Requiring both avoids nuking legitimately nested rooms, like an
        en-suite bathroom sitting inside a master bedroom — that bedroom
        is small relative to the whole building, so signal 2 protects
        it, even though signal 1 alone would have flagged it."""
        if all_rooms is None:
            all_rooms = rooms

        if len(rooms) < 1 or len(all_rooms) < 2:
            return rooms

        total_bbox_area = self.compute_total_bbox_area()
        # If we can't compute a sane footprint, fall back to the old
        # (more conservative) behavior of just requiring multiple
        # contained rooms.
        envelope_area_threshold = (
            total_bbox_area * 0.30 if total_bbox_area > 0 else None
        )

        containers = set()

        for candidate in rooms:
            contained_count = 0

            for other in all_rooms:
                if other is candidate:
                    continue
                if other["area"] >= candidate["area"] * 0.8:
                    continue
                if self.point_in_polygon(other["centroid"], candidate["points"]):
                    contained_count += 1

            if contained_count < 2:
                continue

            if envelope_area_threshold is not None:
                if candidate["area"] >= envelope_area_threshold:
                    containers.add(id(candidate))
            else:
                # No bbox available — keep old conservative rule.
                containers.add(id(candidate))

        filtered = [room for room in rooms if id(room) not in containers]

        return filtered if filtered else rooms

    def compute_total_bbox_area(self):
        """Bounding-box area of the entire drawing's wall/room-relevant
        geometry, used as a reference footprint to detect outer-envelope
        false-positive rooms."""
        xs = []
        ys = []

        for entity in self.entities:
            entity_type = entity.dxftype()

            if entity_type == "LINE":
                try:
                    start = entity.dxf.start
                    end = entity.dxf.end
                    xs.extend([float(start.x), float(end.x)])
                    ys.extend([float(start.y), float(end.y)])
                except Exception:
                    continue

            elif entity_type in ("LWPOLYLINE", "POLYLINE"):
                for point in self.extract_polyline(entity):
                    xs.append(point[0])
                    ys.append(point[1])

        if not xs or not ys:
            return 0.0

        return (max(xs) - min(xs)) * (max(ys) - min(ys))

    # =========================================================
    # REMOVE DUPLICATES
    # =========================================================

    def remove_duplicate_rooms(self, rooms):
        unique = []
        keys = set()

        for room in rooms:
            key = (
                round(room["area"], 2),
                round(room["centroid"][0], 2),
                round(room["centroid"][1], 2),
            )

            if key in keys:
                continue

            keys.add(key)
            unique.append(room)

        return unique

    # =========================================================
    # CREATE ROOM
    # =========================================================

    def create_room(self, index, points, entity, text_labels=None):
        area = self.polygon_area(points)

        sides = []
        perimeter = 0.0

        for i in range(len(points)):
            p1 = points[i]
            p2 = points[(i + 1) % len(points)]
            length = self.distance(p1, p2)
            sides.append(round(length, 3))
            perimeter += length

        min_x = min(p[0] for p in points)
        max_x = max(p[0] for p in points)
        min_y = min(p[1] for p in points)
        max_y = max(p[1] for p in points)

        centroid = (
            sum(p[0] for p in points) / len(points),
            sum(p[1] for p in points) / len(points),
        )

        layer = "UNKNOWN"
        if entity is not None:
            try:
                layer = entity.dxf.layer
            except Exception:
                pass

        name = self.find_label_for_room(points, text_labels)
        if not name:
            name = f"Room {index + 1}"

        return {
            "id": index + 1,
            "name": name,
            "layer": layer,
            "area": round(area, 3),
            "width": round(max_x - min_x, 3),
            "length": round(max_y - min_y, 3),
            "perimeter": round(perimeter, 3),
            "sides": sides,
            "points": [
                [round(p[0], 4), round(p[1], 4)]
                for p in points
            ],
            "centroid": [
                round(centroid[0], 4),
                round(centroid[1], 4),
            ],
        }

    # =========================================================
    # AREA
    # =========================================================

    @staticmethod
    def polygon_area(points):
        area = 0.0

        for i in range(len(points)):
            x1, y1 = points[i]
            x2, y2 = points[(i + 1) % len(points)]
            area += (x1 * y2 - x2 * y1)

        return abs(area / 2.0)

    # =========================================================
    # DRAW DATA
    # =========================================================

    def get_draw_data(self):
        entities = []

        for entity in self.entities:
            data = self.entity_to_draw_data(entity)
            if data:
                entities.append(data)

        rooms = self.detect_rooms()

        return {
            "layers": self.layers,
            "rooms": rooms,
            "doors": self.detect_doors(),
            "entities": entities,
            # Text labels that were found in the drawing but never
            # matched to any closed geometry candidate. Populated as a
            # side effect of detect_rooms() above. Surface these in the
            # GUI (e.g. "3 room labels found, no boundary detected") so
            # a missing room reads as a wall-gap problem, not a mystery.
            "unmatched_labels": [
                {"text": label["text"], "position": list(label["position"])}
                for label in self.unmatched_labels
            ],
        }

    # =========================================================
    # ENTITY DRAW DATA
    # =========================================================

    def entity_to_draw_data(self, entity):
        entity_type = entity.dxftype()

        if entity_type == "LINE":
            try:
                start = entity.dxf.start
                end = entity.dxf.end
                return {
                    "type": "LINE",
                    "start": [float(start.x), float(start.y)],
                    "end": [float(end.x), float(end.y)],
                    "layer": entity.dxf.layer,
                }
            except Exception:
                return None

        if entity_type in ["LWPOLYLINE", "POLYLINE"]:
            points = self.extract_polyline(entity)
            if len(points) >= 2:
                return {
                    "type": "POLYLINE",
                    "points": [
                        [float(p[0]), float(p[1])]
                        for p in points
                    ],
                    "layer": entity.dxf.layer,
                }
            return None

        if entity_type == "ARC":
            try:
                center = entity.dxf.center
                return {
                    "type": "ARC",
                    "center": [float(center.x), float(center.y)],
                    "radius": float(entity.dxf.radius),
                    "start_angle": float(entity.dxf.start_angle),
                    "end_angle": float(entity.dxf.end_angle),
                    "layer": entity.dxf.layer,
                }
            except Exception:
                return None

        if entity_type == "CIRCLE":
            try:
                center = entity.dxf.center
                return {
                    "type": "CIRCLE",
                    "center": [float(center.x), float(center.y)],
                    "radius": float(entity.dxf.radius),
                    "layer": entity.dxf.layer,
                }
            except Exception:
                return None

        if entity_type == "INSERT":
            # Furniture, fixtures, doors, and most stair symbols are
            # block references, not raw geometry. Explode the block
            # (and any nested blocks inside it — virtual_entities()
            # recurses) into its real LINE/ARC/CIRCLE/POLYLINE
            # sub-entities so it actually renders instead of vanishing.
            try:
                sub_entities = []
                for sub_entity in entity.virtual_entities():
                    sub_data = self.entity_to_draw_data(sub_entity)
                    if sub_data:
                        sub_entities.append(sub_data)

                if not sub_entities:
                    return None

                return {
                    "type": "BLOCK",
                    "block_name": entity.dxf.name,
                    "layer": entity.dxf.layer,
                    "entities": sub_entities,
                }
            except Exception:
                return None

        return None

    # =========================================================
    # DIAGNOSTICS
    # =========================================================

    def print_layer_area_report(self):
        """Run this once against a real drawing to see which layers are
        producing rooms and their area ranges — use it to tune
        EXCLUDED_LAYER_KEYWORDS and MIN_ROOM_AREA."""
        from collections import defaultdict

        report = defaultdict(list)
        for room in self.detect_rooms():
            report[room["layer"]].append(room["area"])

        for layer, areas in sorted(report.items()):
            print(
                f"{layer:20s} count={len(areas):3d}  "
                f"min={min(areas):.3f}  max={max(areas):.3f}"
            )

        if self.unmatched_labels:
            print("\nUnmatched text labels (no closed boundary found):")
            for label in self.unmatched_labels:
                print(f"  '{label['text']}' at {label['position']}")