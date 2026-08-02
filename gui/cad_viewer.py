import math

from PySide6.QtWidgets import QGraphicsView
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QImage, QPixmap
from PySide6.QtCore import Qt, QRectF, Signal


class CADViewer(QGraphicsView):

    # Emitted when a room / door / wall is clicked in the drawing.
    # roomClicked carries the full room dict (same shape as DWGReader
    # rooms). doorClicked carries the full door dict. wallClicked
    # carries the raw entity dict from get_draw_data()["entities"].
    roomClicked = Signal(dict)
    doorClicked = Signal(dict)
    wallClicked = Signal(dict)

    # Emitted when a click lands on empty space, so callers can clear
    # whatever "selected object" panel they're showing.
    selectionCleared = Signal()

    # Room fill: light blue, translucent
    ROOM_FILL = QColor(70, 130, 220, 60)
    ROOM_FILL_SELECTED = QColor(235, 27, 38, 90)   # SC red accent on select
    ROOM_BORDER = QColor(90, 160, 255, 220)
    ROOM_BORDER_SELECTED = QColor(235, 27, 38, 255)

    ENTITY_LINE = QColor(90, 90, 90, 160)          # dim background geometry
    WALL_LINE_SELECTED = QColor(255, 195, 40, 255)  # amber highlight for a clicked wall

    DOOR_COLOR = QColor(80, 220, 120, 220)          # green door arcs
    DOOR_COLOR_SELECTED = QColor(235, 27, 38, 255)  # SC red accent on select

    LABEL_COLOR = QColor(230, 230, 230, 255)

    # Screen-space pixel tolerance used when hit-testing clicks against
    # doors and walls. Rooms don't need one — point-in-polygon is exact.
    DOOR_HIT_PADDING = 6
    WALL_HIT_TOLERANCE = 6

    def __init__(self, parent=None):
        super().__init__(parent)

        self.entities = []
        self.rooms = []
        self.doors = []

        self.selected_room = None
        self.selected_door_index = None
        self.selected_wall_index = None

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

        self._label_font = QFont("Poppins", 8)

        # Recomputed at the end of every paintEvent so mouse handlers can
        # convert a click position back into drawing-world coordinates
        # using the exact transform that was just rendered.
        self._transform_state = None

    def set_cad_data(self, entities, rooms, doors=None):
        self.entities = entities
        self.rooms = rooms
        self.doors = doors or []
        self.selected_room = None
        self.selected_door_index = None
        self.selected_wall_index = None
        self.viewport().update()

    # =====================================================
    # SELECTION STATE
    # =====================================================

    def set_selected_room(self, room_id):
        self.selected_room = room_id
        self.selected_door_index = None
        self.selected_wall_index = None
        self.viewport().update()

    def set_selected_door(self, door_index):
        self.selected_door_index = door_index
        self.selected_room = None
        self.selected_wall_index = None
        self.viewport().update()

    def set_selected_wall(self, wall_index):
        self.selected_wall_index = wall_index
        self.selected_room = None
        self.selected_door_index = None
        self.viewport().update()

    def clear_selection(self):
        self.selected_room = None
        self.selected_door_index = None
        self.selected_wall_index = None
        self.viewport().update()

    # =====================================================
    # PAINT
    # =====================================================

    def paintEvent(self, event):
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self.entities and not self.rooms:
            painter.setPen(QPen(self.LABEL_COLOR))
            painter.drawText(30, 40, "No CAD geometry loaded")
            self._transform_state = None
            return

        all_points = self._collect_points()
        if not all_points:
            self._transform_state = None
            return

        min_x, max_x, min_y, max_y = self._bounds(all_points)
        width = max(max_x - min_x, 1)
        height = max(max_y - min_y, 1)

        margin = 50
        viewport_width = self.viewport().width()
        viewport_height = self.viewport().height()

        scale = min(
            (viewport_width - margin * 2) / width,
            (viewport_height - margin * 2) / height,
        )

        # Stored so mousePressEvent can invert it later, and so hit
        # tests can re-derive the same screen-space positions the
        # drawing was just painted with.
        self._transform_state = {
            "min_x": min_x,
            "max_y": max_y,
            "scale": scale,
            "margin": margin,
        }

        transform = self._transform

        self._draw_background_entities(painter, transform)
        self._draw_rooms(painter, transform)
        self._draw_doors(painter, transform, scale)

    # =====================================================
    # COORDINATE TRANSFORM (world <-> screen)
    # =====================================================

    def _transform(self, point):
        """World-space CAD point -> screen-space pixel, using the
        transform computed during the most recent paintEvent."""
        state = self._transform_state
        if state is None:
            return point
        x = (point[0] - state["min_x"]) * state["scale"] + state["margin"]
        y = (state["max_y"] - point[1]) * state["scale"] + state["margin"]
        return x, y

    def _untransform(self, screen_point):
        """Screen-space pixel -> world-space CAD point, the inverse of
        _transform(). Returns None if nothing has been painted yet."""
        state = self._transform_state
        if state is None:
            return None
        x = (screen_point[0] - state["margin"]) / state["scale"] + state["min_x"]
        y = state["max_y"] - (screen_point[1] - state["margin"]) / state["scale"]
        return x, y

    # =====================================================
    # HELPERS
    # =====================================================

    def _collect_points(self):
        all_points = []

        for entity in self.entities:
            if not entity:
                continue
            if entity["type"] == "LINE":
                all_points.append(entity["start"])
                all_points.append(entity["end"])
            elif entity["type"] == "POLYLINE":
                all_points.extend(entity["points"])

        for room in self.rooms:
            all_points.extend(room["points"])

        for door in self.doors:
            all_points.append(door["position"])

        return all_points

    @staticmethod
    def _bounds(points):
        min_x = min(p[0] for p in points)
        max_x = max(p[0] for p in points)
        min_y = min(p[1] for p in points)
        max_y = max(p[1] for p in points)
        return min_x, max_x, min_y, max_y

    @staticmethod
    def _point_in_polygon(point, polygon):
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
    def _point_to_segment_distance(point, seg_start, seg_end):
        px, py = point
        x1, y1 = seg_start
        x2, y2 = seg_end

        dx = x2 - x1
        dy = y2 - y1
        length_sq = dx * dx + dy * dy

        if length_sq < 1e-9:
            return math.hypot(px - x1, py - y1)

        t = ((px - x1) * dx + (py - y1) * dy) / length_sq
        t = max(0.0, min(1.0, t))

        closest_x = x1 + t * dx
        closest_y = y1 + t * dy

        return math.hypot(px - closest_x, py - closest_y)

    # =====================================================
    # DRAW BACKGROUND (raw CAD lines, dimmed — walls, pergola slats, etc.)
    # =====================================================

    def _draw_background_entities(self, painter, transform):
        default_pen = QPen(self.ENTITY_LINE, 1)
        selected_pen = QPen(self.WALL_LINE_SELECTED, 3)

        for index, entity in enumerate(self.entities):
            if not entity:
                continue

            is_selected = index == self.selected_wall_index
            painter.setPen(selected_pen if is_selected else default_pen)

            if entity["type"] == "LINE":
                p1 = transform(entity["start"])
                p2 = transform(entity["end"])
                painter.drawLine(int(p1[0]), int(p1[1]), int(p2[0]), int(p2[1]))

            elif entity["type"] == "POLYLINE":
                points = [transform(p) for p in entity["points"]]
                for i in range(len(points) - 1):
                    painter.drawLine(
                        int(points[i][0]), int(points[i][1]),
                        int(points[i + 1][0]), int(points[i + 1][1]),
                    )

    # =====================================================
    # DRAW ROOMS (filled polygons + labels)
    # =====================================================

    def _draw_rooms(self, painter, transform):
        from PySide6.QtGui import QPolygonF
        from PySide6.QtCore import QPointF

        painter.setFont(self._label_font)

        # --- pass 1: fill + border for every room polygon ---
        for room in self.rooms:
            is_selected = (
                self.selected_room is not None
                and room.get("id") == self.selected_room
            )

            points = [transform(p) for p in room["points"]]
            polygon = QPolygonF([QPointF(x, y) for x, y in points])

            fill = self.ROOM_FILL_SELECTED if is_selected else self.ROOM_FILL
            border = self.ROOM_BORDER_SELECTED if is_selected else self.ROOM_BORDER

            painter.setBrush(QBrush(fill))
            painter.setPen(QPen(border, 2 if is_selected else 1.5))
            painter.drawPolygon(polygon)

        # --- pass 2: labels, largest rooms first, skipping overlaps ---
        placed_rects = []
        rooms_by_size = sorted(
            self.rooms, key=lambda r: r.get("area", 0), reverse=True
        )

        metrics = painter.fontMetrics()
        padding_x, padding_y = 10, 6

        for room in rooms_by_size:
            if room.get("area", 0) < 1.0:
                continue

            name = room.get("name") or f"Room {room.get('id', '?')}"
            area = room.get("area", 0)
            line1 = str(name)
            line2 = f"{area} m²"

            text_w = max(metrics.horizontalAdvance(line1), metrics.horizontalAdvance(line2))
            label_w = text_w + padding_x * 2
            label_h = metrics.height() * 2 + padding_y * 2

            center = transform(room["centroid"])

            # Room's own screen-space bounding box — labels are clamped
            # inside this so they never drift into a neighboring room.
            room_points = [transform(p) for p in room["points"]]
            room_min_x = min(p[0] for p in room_points)
            room_max_x = max(p[0] for p in room_points)
            room_min_y = min(p[1] for p in room_points)
            room_max_y = max(p[1] for p in room_points)

            def make_rect(cx, cy):
                rect = QRectF(cx - label_w / 2, cy - label_h / 2, label_w, label_h)
                # Clamp inside the room's own bounds where possible.
                if label_w < (room_max_x - room_min_x):
                    if rect.left() < room_min_x:
                        rect.moveLeft(room_min_x)
                    if rect.right() > room_max_x:
                        rect.moveRight(room_max_x)
                if label_h < (room_max_y - room_min_y):
                    if rect.top() < room_min_y:
                        rect.moveTop(room_min_y)
                    if rect.bottom() > room_max_y:
                        rect.moveBottom(room_max_y)
                return rect

            rect = make_rect(center[0], center[1])

            if any(rect.intersects(placed) for placed in placed_rects):
                # Try offsets in a small spiral of directions before
                # giving up on this label entirely.
                offsets = [
                    (0, -label_h), (0, label_h),
                    (label_w, 0), (-label_w, 0),
                    (label_w, -label_h), (-label_w, -label_h),
                    (label_w, label_h), (-label_w, label_h),
                    (0, -label_h * 1.8), (0, label_h * 1.8),
                ]
                found = False
                for dx, dy in offsets:
                    candidate = make_rect(center[0] + dx, center[1] + dy)
                    if not any(candidate.intersects(placed) for placed in placed_rects):
                        rect = candidate
                        found = True
                        break
                if not found:
                    # No free spot found — skip rather than draw
                    # unreadable overlapping text.
                    continue

            placed_rects.append(rect)

            painter.setBrush(QBrush(QColor(10, 10, 10, 165)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 4, 4)

            painter.setPen(QPen(self.LABEL_COLOR))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                f"{line1}\n{line2}",
            )

    # =====================================================
    # DRAW DOORS (small circle markers)
    # =====================================================

    def _draw_doors(self, painter, transform, scale):
        base_radius = max(4, min(8, scale * 0.15))

        for index, door in enumerate(self.doors):
            is_selected = index == self.selected_door_index
            color = self.DOOR_COLOR_SELECTED if is_selected else self.DOOR_COLOR
            radius = base_radius * 1.6 if is_selected else base_radius

            painter.setBrush(QBrush(color))
            painter.setPen(QPen(color, 1))

            x, y = transform(door["position"])
            painter.drawEllipse(
                QRectF(x - radius, y - radius, radius * 2, radius * 2)
            )

    # =====================================================
    # MOUSE INTERACTION — click to select room / door / wall
    # =====================================================

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self._transform_state is None:
            super().mousePressEvent(event)
            return

        pos = event.position() if hasattr(event, "position") else event.pos()
        click_screen = (pos.x(), pos.y())

        # Priority: doors first (smallest, most specific target), then
        # rooms (large fills), then walls (thin lines, easy to miss so
        # they're the fallback rather than the first thing tested).
        door_index = self._hit_test_door(click_screen)
        if door_index is not None:
            self.set_selected_door(door_index)
            self.doorClicked.emit(self.doors[door_index])
            super().mousePressEvent(event)
            return

        room = self._hit_test_room(click_screen)
        if room is not None:
            self.set_selected_room(room.get("id"))
            self.roomClicked.emit(room)
            super().mousePressEvent(event)
            return

        wall_index = self._hit_test_wall(click_screen)
        if wall_index is not None:
            self.set_selected_wall(wall_index)
            self.wallClicked.emit(self.entities[wall_index])
            super().mousePressEvent(event)
            return

        self.clear_selection()
        self.selectionCleared.emit()
        super().mousePressEvent(event)

    def _hit_test_door(self, click_screen):
        state = self._transform_state
        base_radius = max(4, min(8, state["scale"] * 0.15))
        threshold = base_radius + self.DOOR_HIT_PADDING

        for index, door in enumerate(self.doors):
            door_screen = self._transform(door["position"])
            distance = math.hypot(
                click_screen[0] - door_screen[0],
                click_screen[1] - door_screen[1],
            )
            if distance <= threshold:
                return index

        return None

    def _hit_test_room(self, click_screen):
        world_point = self._untransform(click_screen)
        if world_point is None:
            return None

        containing = [
            room for room in self.rooms
            if self._point_in_polygon(world_point, room["points"])
        ]
        if not containing:
            return None

        # Smallest containing room wins, so e.g. a bathroom nested
        # inside a bedroom's fill is still selectable on its own.
        return min(containing, key=lambda r: r.get("area", float("inf")))

    def _hit_test_wall(self, click_screen):
        best_index = None
        best_distance = self.WALL_HIT_TOLERANCE

        for index, entity in enumerate(self.entities):
            if not entity:
                continue

            if entity["type"] == "LINE":
                segments = [(entity["start"], entity["end"])]
            elif entity["type"] == "POLYLINE":
                pts = entity["points"]
                segments = [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
            else:
                continue

            for seg_start, seg_end in segments:
                p1 = self._transform(seg_start)
                p2 = self._transform(seg_end)
                distance = self._point_to_segment_distance(click_screen, p1, p2)
                if distance < best_distance:
                    best_distance = distance
                    best_index = index

        return best_index

    # =====================================================
    # EXPORT
    # =====================================================

    def export_to_image(self, file_path, width=None, height=None):
        """Render the current CAD drawing (background entities, rooms,
        doors) to a PNG/JPG file at the given path. If width/height are
        not given, uses the current viewport size. Returns True on
        success, False if there was nothing to render."""

        if not self.entities and not self.rooms:
            return False

        render_width = width or max(self.viewport().width(), 800)
        render_height = height or max(self.viewport().height(), 600)

        image = QImage(render_width, render_height, QImage.Format.Format_ARGB32)
        image.fill(QColor(10, 10, 10, 255))  # SC dark background

        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        all_points = self._collect_points()
        if not all_points:
            painter.end()
            return False

        min_x, max_x, min_y, max_y = self._bounds(all_points)
        w = max(max_x - min_x, 1)
        h = max(max_y - min_y, 1)

        margin = 50
        scale = min(
            (render_width - margin * 2) / w,
            (render_height - margin * 2) / h,
        )

        def transform(point):
            x = (point[0] - min_x) * scale + margin
            y = (max_y - point[1]) * scale + margin
            return x, y

        self._draw_background_entities(painter, transform)
        self._draw_rooms(painter, transform)
        self._draw_doors(painter, transform, scale)

        painter.end()

        return image.save(str(file_path))