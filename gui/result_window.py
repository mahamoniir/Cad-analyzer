import math

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import (
    QColor,
    QBrush,
    QPainter,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class RoomPreviewWidget(QWidget):

    def __init__(
        self,
        room,
        parent=None
    ):

        super().__init__(parent)
        self.room = room
        self.setMinimumSize(360, 260)

    def paintEvent(self, event):

        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QBrush(QColor("#f8f8f8")))

        points = self.room.get("points", [])
        if len(points) < 3:
            painter.setPen(QPen(Qt.GlobalColor.darkGray, 1))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "No room geometry available",
            )
            return

        xs = [point[0] for point in points]
        ys = [point[1] for point in points]

        min_x = min(xs)
        max_x = max(xs)
        min_y = min(ys)
        max_y = max(ys)

        width = max(max_x - min_x, 1e-6)
        height = max(max_y - min_y, 1e-6)

        margin = 28.0
        draw_width = max(self.width() - (2 * margin), 40)
        draw_height = max(self.height() - (2 * margin), 40)
        scale = min(draw_width / width, draw_height / height)

        def transform(point):
            x = ((point[0] - min_x) * scale) + margin
            y = ((max_y - point[1]) * scale) + margin
            return QPointF(x, y)

        polygon = QPolygonF([transform(point) for point in points])

        painter.setBrush(QBrush(QColor(208, 230, 255, 95)))
        painter.setPen(QPen(QColor("#1f6fb2"), 2))
        painter.drawPolygon(polygon)

        room_id = self.room.get("id", "-")
        area = self.room.get("area", "-")
        painter.setPen(QPen(QColor("#0d3558"), 1))
        painter.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
            f"Room {room_id} | Area: {area} m^2",
        )


class LightingResultWindow(QDialog):

    OPTION_COLUMNS = [
        "Status",
        "Selection",
        "Luminaire",
        "Power (W)",
        "Fixtures",
        "Layout",
        "Avg Lux",
        "U0",
        "Total Power (W)",
        "Spacing (m)",
    ]

    def __init__(
        self,
        room,
        result,
        request_context,
        parent=None
    ):

        super().__init__(parent)

        self.room = room
        self.result = result or {}
        self.request_context = request_context or {}
        self.normalized_options = []

        self.setWindowTitle("Lighting Calculation Details")
        self.resize(1360, 850)

        self.build_ui()
        self.populate()

    @staticmethod
    def _as_bool(value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            return lowered in ("1", "true", "yes", "y")
        return bool(value)

    @staticmethod
    def _as_float(value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    @staticmethod
    def _fmt(value, decimals=3):
        if value is None:
            return "-"
        if isinstance(value, str):
            return value
        return f"{value:.{decimals}f}"

    @staticmethod
    def _coalesce(data, keys, default=None):
        for key in keys:
            if key in data and data[key] is not None:
                value = data[key]
                if isinstance(value, str) and not value.strip():
                    continue
                return value
        return default

    def build_ui(self):

        root = QVBoxLayout(self)

        title = QLabel("Calculation Results")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        root.addWidget(title)

        self.meta_text = QTextEdit()
        self.meta_text.setReadOnly(True)
        self.meta_text.setMaximumHeight(170)
        root.addWidget(self.meta_text)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, 1)

        left = QWidget()
        left_layout = QVBoxLayout(left)

        left_layout.addWidget(QLabel("Selected Room Drawing"))
        self.room_preview = RoomPreviewWidget(self.room)
        left_layout.addWidget(self.room_preview, 2)

        left_layout.addWidget(QLabel("Room / Request Details"))
        self.room_details_text = QTextEdit()
        self.room_details_text.setReadOnly(True)
        left_layout.addWidget(self.room_details_text, 3)

        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)

        right_layout.addWidget(QLabel("Sorted Fixture Options"))
        self.options_table = QTableWidget()
        self.options_table.setColumnCount(len(self.OPTION_COLUMNS))
        self.options_table.setHorizontalHeaderLabels(self.OPTION_COLUMNS)
        self.options_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.options_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.options_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.options_table.verticalHeader().setVisible(False)
        header = self.options_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.options_table.itemSelectionChanged.connect(
            self.option_selection_changed
        )
        right_layout.addWidget(self.options_table, 3)

        right_layout.addWidget(QLabel("Selected Option Details"))
        self.option_details_text = QTextEdit()
        self.option_details_text.setReadOnly(True)
        right_layout.addWidget(self.option_details_text, 2)

        splitter.addWidget(right)
        splitter.setSizes([520, 840])

    def normalize_option(
        self,
        row,
        index
    ):

        fixtures = self._as_float(self._coalesce(row, ["Fixtures"]))
        power = self._as_float(self._coalesce(row, ["Power (W)"]))
        total_power = self._as_float(
            self._coalesce(row, ["Total Power (W/H)", "Total Power (W)"])
        )
        avg_lux = self._as_float(
            self._coalesce(
                row,
                ["E_avg_grid_lx", "e_avg_grid_lx", "Average Lux"],
            )
        )
        u0 = self._as_float(
            self._coalesce(
                row,
                ["U0_calculated", "u0_calculated", "Uniformity"],
            )
        )
        lux_gap = self._as_float(self._coalesce(row, ["Lux gap"]))
        u0_gap = self._as_float(self._coalesce(row, ["U0 gap"]))
        spacing_x = self._as_float(self._coalesce(row, ["Spacing X (m)"]))
        spacing_y = self._as_float(self._coalesce(row, ["Spacing Y (m)"]))

        layout_text = self._coalesce(row, ["Layout grid"], "")
        if not layout_text:
            nx = self._coalesce(row, ["layout_nx"])
            ny = self._coalesce(row, ["layout_ny"])
            if nx and ny:
                layout_text = f"{nx} x {ny}"

        return {
            "index": index,
            "is_compliant": self._as_bool(row.get("is_compliant")),
            "selection": self._coalesce(row, ["Selection"], "-"),
            "luminaire": self._coalesce(row, ["Luminaire"], "-"),
            "power_w": power,
            "fixtures": fixtures,
            "layout": layout_text or "-",
            "avg_lux": avg_lux,
            "u0": u0,
            "total_power_w": total_power,
            "spacing_x": spacing_x,
            "spacing_y": spacing_y,
            "lux_gap": lux_gap,
            "u0_gap": u0_gap,
            "lux_basis": self._coalesce(
                row,
                ["Lux compliance basis", "lux_compliance_basis"],
                "-",
            ),
            "beam_angle_deg": self._as_float(
                self._coalesce(
                    row,
                    ["Beam angle (deg)", "Beam Angle (deg)", "beam_angle_deg"],
                )
            ),
            "efficacy": self._as_float(self._coalesce(row, ["Efficacy (lm/W)"])),
            "ies_file": self._coalesce(row, ["IES file"], "-"),
            "maintenance_factor": self._as_float(
                self._coalesce(row, ["Maintenance factor"])
            ),
            "uniformity_scale": self._coalesce(
                row,
                ["Uniformity (IES scale)"],
                "-",
            ),
            "raw": row,
        }

    @staticmethod
    def option_sort_key(option):
        large = 10**9
        return (
            0 if option["is_compliant"] else 1,
            option["fixtures"] if option["fixtures"] is not None else large,
            option["total_power_w"] if option["total_power_w"] is not None else large,
            option["u0_gap"] if option["u0_gap"] is not None else large,
            option["lux_gap"] if option["lux_gap"] is not None else large,
            option["index"],
        )

    def populate(self):

        self.populate_meta()
        self.populate_room_details()
        self.populate_options()

    def populate_meta(self):

        lines = []
        lines.append("Response")
        lines.append(f"- Status: {self.result.get('status', '-')}")
        lines.append(f"- Options returned: {len(self.result.get('results', []) or [])}")
        lines.append(f"- Equivalent length (m): {self.result.get('length', '-')}")
        lines.append(f"- Equivalent width (m): {self.result.get('width', '-')}")

        meta = self.result.get("calculation_meta", {}) or {}
        poly = meta.get("polygon") if isinstance(meta, dict) else None
        if isinstance(poly, dict) and poly:
            lines.append("")
            lines.append("Polygon geometry")
            lines.append(f"- Vertices: {poly.get('vertex_count', len(poly.get('vertices') or []))}")
            lines.append(f"- Area (m²): {poly.get('area_m2', '-')}")
            lines.append(f"- Perimeter (m): {poly.get('perimeter_m', '-')}")
            lines.append(f"- Convex: {poly.get('is_convex', '-')}")
        elif meta:
            lines.append("")
            lines.append("Calculation Meta")
            for key in sorted(meta.keys()):
                lines.append(f"- {key}: {meta[key]}")

        standard_row = self.result.get("standard_row")
        if isinstance(standard_row, dict) and standard_row:
            lines.append("")
            lines.append("Standard Reference")
            for key in (
                "ref_no",
                "category",
                "task_or_activity",
                "Em_r_lx",
                "Uo",
                "UGR_L",
                "Ra",
            ):
                if key in standard_row:
                    lines.append(f"- {key}: {standard_row.get(key)}")

        self.meta_text.setPlainText("\n".join(lines))

    def populate_room_details(self):

        room = self.room or {}
        sides = room.get("sides", [])
        sides_text = ", ".join(str(side) for side in sides) if sides else "-"
        points = room.get("points") or []

        context = self.request_context
        lines = [
            f"Room ID: {room.get('id', '-')}",
            f"Layer: {room.get('layer', '-')}",
            f"Area (m^2): {room.get('area', '-')}",
            f"Perimeter (m): {room.get('perimeter', '-')}",
            f"Width (m): {room.get('width', '-')}",
            f"Length (m): {room.get('length', '-')}",
            f"Vertices: {len(points)}",
            f"Sides (m): {sides_text}",
            "",
            "Request Inputs",
            f"Category: {context.get('place', '-')}",
            f"Task / activity: {context.get('task_or_activity', '-') or '-'}",
            f"Ceiling height (m): {context.get('height', '-')}",
            f"Standard ref: {context.get('standard_ref_no', '-') or '-'}",
            f"Project name: {context.get('project_name', '-')}",
            f"API: /cad_calc (polygon)",
        ]
        self.room_details_text.setPlainText("\n".join(lines))

    def populate_options(self):

        results = self.result.get("results", []) or []
        self.normalized_options = [
            self.normalize_option(row, index)
            for index, row in enumerate(results)
        ]
        self.normalized_options.sort(key=self.option_sort_key)

        self.options_table.setRowCount(len(self.normalized_options))
        for row_index, option in enumerate(self.normalized_options):
            status = "Compliant" if option["is_compliant"] else "Not compliant"
            spacing = (
                f"{self._fmt(option['spacing_x'], 2)} x {self._fmt(option['spacing_y'], 2)}"
                if option["spacing_x"] is not None and option["spacing_y"] is not None
                else "-"
            )
            values = [
                status,
                str(option["selection"]),
                str(option["luminaire"]),
                self._fmt(option["power_w"], 1),
                self._fmt(option["fixtures"], 0),
                str(option["layout"]),
                self._fmt(option["avg_lux"], 2),
                self._fmt(option["u0"], 3),
                self._fmt(option["total_power_w"], 1),
                spacing,
            ]

            for col_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                if option["is_compliant"]:
                    item.setBackground(QBrush(QColor(224, 245, 229)))
                self.options_table.setItem(row_index, col_index, item)

        if self.normalized_options:
            self.options_table.selectRow(0)
            self.set_option_details(self.normalized_options[0])
        else:
            self.option_details_text.setPlainText("No options returned.")

    def option_selection_changed(self):

        selected = self.options_table.selectionModel().selectedRows()
        if not selected:
            return

        row = selected[0].row()
        if row < 0 or row >= len(self.normalized_options):
            return

        self.set_option_details(self.normalized_options[row])

    def set_option_details(
        self,
        option
    ):

        status = "Compliant" if option["is_compliant"] else "Not compliant"
        lines = [
            "Option Summary",
            f"- Status: {status}",
            f"- Selection mode: {option['selection']}",
            f"- Luminaire: {option['luminaire']}",
            f"- Fixtures: {self._fmt(option['fixtures'], 0)}",
            f"- Power per fixture (W): {self._fmt(option['power_w'], 1)}",
            f"- Total power (W): {self._fmt(option['total_power_w'], 1)}",
            "",
            "Performance",
            f"- Avg lux (compliance basis): {self._fmt(option['avg_lux'], 2)}",
            f"- Lux basis: {option['lux_basis']}",
            f"- U0 calculated: {self._fmt(option['u0'], 3)}",
            f"- Lux gap: {self._fmt(option['lux_gap'], 3)}",
            f"- U0 gap: {self._fmt(option['u0_gap'], 3)}",
            "",
            "Layout and Photometry",
            f"- Layout grid: {option['layout']}",
            f"- Spacing X (m): {self._fmt(option['spacing_x'], 2)}",
            f"- Spacing Y (m): {self._fmt(option['spacing_y'], 2)}",
            f"- Efficacy (lm/W): {self._fmt(option['efficacy'], 2)}",
            f"- Beam angle (deg): {self._fmt(option['beam_angle_deg'], 2)}",
            f"- IES file: {option['ies_file']}",
            f"- Uniformity scale: {option['uniformity_scale']}",
            f"- Maintenance factor: {self._fmt(option['maintenance_factor'], 3)}",
        ]

        extra_lines = []
        known_keys = {
            "selection",
            "luminaire",
            "power (w)",
            "fixtures",
            "layout grid",
            "layout_nx",
            "layout_ny",
            "average lux",
            "e_avg_grid_lx",
            "e_avg_grid_direct_calibrated_lx",
            "e_avg_grid_includes_ir_boost",
            "e_min_grid_lx",
            "e_max_grid_lx",
            "u0_calculated",
            "u1_calculated",
            "uniformity",
            "uniformity (ies scale)",
            "lux gap",
            "u0 gap",
            "lux compliance basis",
            "lux_compliance_basis",
            "is_compliant",
            "spacing x (m)",
            "spacing y (m)",
            "total power (w/h)",
            "total power (w)",
            "beam angle (deg)",
            "beam angle (�)",
            "beam angle nominal (�)",
            "beam angle (deg)",
            "beam_angle_deg",
            "beam_angle_nominal_deg",
            "efficacy (lm/w)",
            "ies file",
            "ies lumens (lm)",
            "room reflectance preset",
            "maintenance factor",
            "fixture density warning",
            "standard margin (lux %)",
            "standard margin (u0 %)",
            "inter-reflection fraction (est.)",
            "beam source",
        }

        raw = option["raw"]
        for key in sorted(raw.keys(), key=lambda text: text.lower()):
            if key.lower() in known_keys:
                continue
            extra_lines.append(f"- {key}: {raw[key]}")

        if extra_lines:
            lines.extend(["", "Other Fields"])
            lines.extend(extra_lines)

        self.option_details_text.setPlainText("\n".join(lines))
