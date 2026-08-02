from PySide6.QtWidgets import (

    QMainWindow,

    QWidget,

    QVBoxLayout,

    QHBoxLayout,

    QPushButton,

    QLabel,

    QFileDialog,

    QComboBox,

    QDoubleSpinBox,

    QLineEdit,

    QTableWidget,

    QTableWidgetItem,

    QTextEdit,

    QSplitter,

    QMessageBox
)

from PySide6.QtCore import Qt

from cad_analyzer.dwg_reader import DWGReader

from gui.cad_viewer import CADViewer
from gui.result_window import LightingResultWindow

from luxscale_client import LuxScaleClient


class MainWindow(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle(

            "LuxScale CAD Analyzer"
        )

        self.resize(

            1600,

            950
        )

        self.reader = None

        self.rooms = []

        self.current_room = None

        self.places = {}

        self.category_keywords = {}

        self.client = (

            LuxScaleClient(

                "http://127.0.0.1:5000"
            )
        )

        self.build_ui()

        self.load_places()

    # =====================================================
    # UI
    # =====================================================

    def build_ui(self):

        central = QWidget()

        self.setCentralWidget(

            central
        )

        root = QVBoxLayout(

            central
        )

        title = QLabel(

            "LuxScale CAD Analyzer"
        )

        title.setStyleSheet(

            "font-size: 28px; font-weight: bold;"
        )

        root.addWidget(

            title
        )

        # -------------------------------------------------
        # FILE BAR
        # -------------------------------------------------

        file_layout = QHBoxLayout()

        self.file_label = QLabel(

            "No CAD file selected"
        )

        select_button = QPushButton(

            "Select CAD File"
        )

        select_button.clicked.connect(

            self.select_file
        )

        analyze_button = QPushButton(

            "Analyze CAD"
        )

        analyze_button.clicked.connect(

            self.analyze_cad
        )

        file_layout.addWidget(

            self.file_label
        )

        file_layout.addWidget(

            select_button
        )

        file_layout.addWidget(

            analyze_button
        )

        root.addLayout(

            file_layout
        )

        # -------------------------------------------------
        # SUMMARY
        # -------------------------------------------------

        self.summary_label = QLabel(

            "No CAD analyzed"
        )

        root.addWidget(

            self.summary_label
        )

        # -------------------------------------------------
        # MAIN SPLITTER
        # -------------------------------------------------

        splitter = QSplitter(

            Qt.Orientation.Horizontal
        )

        root.addWidget(

            splitter,

            1
        )

        # =================================================
        # LEFT SIDE
        # =================================================

        left = QWidget()

        left_layout = QVBoxLayout(

            left
        )

        left_layout.addWidget(

            QLabel(

                "CAD Drawing"
            )
        )

        self.viewer = CADViewer()

        self.viewer.roomClicked.connect(

            self.on_room_clicked_on_canvas
        )

        self.viewer.doorClicked.connect(

            self.on_door_clicked
        )

        self.viewer.wallClicked.connect(

            self.on_wall_clicked
        )

        self.viewer.selectionCleared.connect(

            self.on_canvas_selection_cleared
        )

        left_layout.addWidget(

            self.viewer,

            2
        )

        self.object_details_label = QLabel(

            "Click a room, door, or wall in the drawing — "

            "or a row below — to see its details."
        )

        self.object_details_label.setWordWrap(

            True
        )

        self.object_details_label.setStyleSheet(

            "color: #cccccc; padding: 4px 0;"
        )

        left_layout.addWidget(

            self.object_details_label
        )

        left_layout.addWidget(

            QLabel(

                "Detected Rooms"
            )
        )

        self.room_table = QTableWidget()

        self.room_table.setColumnCount(

            8
        )

        self.room_table.setHorizontalHeaderLabels(

            [

                "ID",

                "Name",

                "Layer",

                "Area (m²)",

                "Width (m)",

                "Length (m)",

                "Sides",

                "Perimeter"
            ]
        )

        self.room_table.cellClicked.connect(

            self.room_selected
        )

        left_layout.addWidget(

            self.room_table,

            1
        )

        splitter.addWidget(

            left
        )

        # =================================================
        # RIGHT SIDE
        # =================================================

        right = QWidget()

        right_layout = QVBoxLayout(

            right
        )

        right_layout.addWidget(

            QLabel(

                "Selected Room"
            )
        )

        self.selected_room_label = QLabel(

            "No room selected"
        )

        right_layout.addWidget(

            self.selected_room_label
        )

        self.side_labels = []

        for i in range(

            4
        ):

            label = QLabel(

                f"Side {i + 1}: -"
            )

            self.side_labels.append(

                label
            )

            right_layout.addWidget(

                label
            )

        self.area_label = QLabel(

            "Area: -"
        )

        right_layout.addWidget(

            self.area_label
        )

        # -------------------------------------------------
        # HEIGHT
        # -------------------------------------------------

        right_layout.addWidget(

            QLabel(

                "Ceiling Height (m)"
            )
        )

        self.height_input = QDoubleSpinBox()

        self.height_input.setRange(

            0.1,

            100
        )

        self.height_input.setValue(

            3.2
        )

        self.height_input.setDecimals(

            2
        )

        right_layout.addWidget(

            self.height_input
        )

        # -------------------------------------------------
        # PLACE
        # -------------------------------------------------

        right_layout.addWidget(

            QLabel(

                "Room Type"
            )
        )

        self.place_combo = QComboBox()

        self.place_combo.currentTextChanged.connect(

            self.place_changed
        )

        right_layout.addWidget(

            self.place_combo
        )

        self.required_lux_label = QLabel(

            "Required Lux: -"
        )

        right_layout.addWidget(

            self.required_lux_label
        )

        self.uniformity_label = QLabel(

            "Uniformity: -"
        )

        right_layout.addWidget(

            self.uniformity_label
        )

        self.category_label = QLabel(

            "Standard Category: -"
        )

        self.category_label.setWordWrap(

            True
        )

        right_layout.addWidget(

            self.category_label
        )

        # -------------------------------------------------
        # STANDARD REF
        # -------------------------------------------------

        right_layout.addWidget(

            QLabel(

                "Standard Reference"
            )
        )

        self.standard_ref_input = QLineEdit()

        right_layout.addWidget(

            self.standard_ref_input
        )

        # -------------------------------------------------
        # PROJECT NAME
        # -------------------------------------------------

        right_layout.addWidget(

            QLabel(

                "Project Name"
            )
        )

        self.project_name_input = QLineEdit(

            "CAD Lighting Analysis"
        )

        right_layout.addWidget(

            self.project_name_input
        )

        # -------------------------------------------------
        # CALCULATE
        # -------------------------------------------------

        self.calculate_button = QPushButton(

            "Calculate Lighting"
        )

        self.calculate_button.setEnabled(

            False
        )

        self.calculate_button.clicked.connect(

            self.calculate_lighting
        )

        right_layout.addWidget(

            self.calculate_button
        )

        right_layout.addWidget(

            QLabel(

                "Calculation Result"
            )
        )

        self.result_text = QTextEdit()

        self.result_text.setReadOnly(

            True
        )

        right_layout.addWidget(

            self.result_text,

            1
        )

        splitter.addWidget(

            right
        )

        splitter.setSizes(

            [

                900,

                600
            ]
        )

    # =====================================================
    # LOAD API DATA
    # =====================================================

    def load_places(self):

        try:

            data = (

                self.client.get_places()
            )

            self.place_combo.clear()

            self.places = {}

            for place in data.get(

                "calculator_places",

                []
            ):

                name = (

                    place.get(

                        "key"
                    )
                )

                if not name:

                    continue

                self.places[name] = place

                self.place_combo.addItem(

                    name
                )

            self.category_keywords = (

                data.get(

                    "category_keywords",

                    {}
                )
            )

            self.place_changed(

                # self.place_combo.currentIndex()
                self.place_combo.currentText()
            )

        except Exception as error:

            QMessageBox.warning(

                self,

                "API Error",

                (

                    "Could not load places from LuxScale API:\n"

                    f"{error}"
                )
            )

    # =====================================================
    # SELECT FILE
    # =====================================================

    def select_file(self):

        file_path, _ = QFileDialog.getOpenFileName(

            self,

            "Select CAD File",

            "",

            "CAD Files (*.dxf *.dwg);;All Files (*)"
        )

        if file_path:

            self.file_label.setText(

                file_path
            )

    # =====================================================
    # ANALYZE CAD
    # =====================================================

    def analyze_cad(self):

        file_path = (

            self.file_label.text()
        )

        if not file_path or file_path == "No CAD file selected":

            QMessageBox.warning(

                self,

                "No File",

                "Please select a CAD file first."
            )

            return

        try:

            self.current_room = None
            self.calculate_button.setEnabled(
                False
            )
            self.selected_room_label.setText(
                "No room selected"
            )
            self.result_text.clear()

            self.reader = DWGReader(

                file_path
            )

            self.reader.load()

            self.rooms = (

                self.reader.detect_rooms()
            )

            draw_data = (

                self.reader.get_draw_data()
            )

            self.viewer.set_cad_data(

                draw_data["entities"],

                self.rooms
            )

            self.populate_rooms()

            summary = (

                self.reader.get_summary()
            )

            self.summary_label.setText(

                (

                    f"Layers: {summary['layers']}    "

                    f"Entities: {summary['entities']}    "

                    f"Rooms: {len(self.rooms)}"
                )
            )

            if not self.rooms:

                QMessageBox.warning(

                    self,

                    "No Rooms Detected",

                    (

                        "The CAD file was loaded successfully, "

                        "but no closed room boundaries were detected.\n\n"

                        "The drawing will still be displayed graphically."
                    )
                )

        except Exception as error:

            QMessageBox.critical(

                self,

                "CAD Error",

                str(error)
            )

    # =====================================================
    # POPULATE ROOM TABLE
    # =====================================================

    def populate_rooms(self):

        self.room_table.setRowCount(

            0
        )

        for row, room in enumerate(

            self.rooms
        ):

            self.room_table.insertRow(

                row
            )

            self.room_table.setItem(

                row,

                0,

                QTableWidgetItem(

                    str(

                        room["id"]
                    )
                )
            )

            self.room_table.setItem(

                row,

                1,

                QTableWidgetItem(

                    room.get(

                        "name",

                        ""
                    )
                )
            )

            self.room_table.setItem(

                row,

                2,

                QTableWidgetItem(

                    room["layer"]
                )
            )

            self.room_table.setItem(

                row,

                3,

                QTableWidgetItem(

                    str(

                        room["area"]
                    )
                )
            )

            self.room_table.setItem(

                row,

                4,

                QTableWidgetItem(

                    str(

                        room["width"]
                    )
                )
            )

            self.room_table.setItem(

                row,

                5,

                QTableWidgetItem(

                    str(

                        room["length"]
                    )
                )
            )

            self.room_table.setItem(

                row,

                6,

                QTableWidgetItem(

                    ", ".join(

                        str(

                            side
                        )

                        for side in room["sides"]
                    )
                )
            )

            self.room_table.setItem(

                row,

                7,

                QTableWidgetItem(

                    str(

                        room["perimeter"]
                    )
                )
            )

    # =====================================================
    # ROOM SELECTED
    # =====================================================

    def room_selected(

        self,

        row,

        column
    ):

        if row < 0 or row >= len(

            self.rooms
        ):

            return

        room = self.rooms[row]

        self._apply_room_selection(

            room
        )

        self.viewer.set_selected_room(

            room["id"]
        )

    def _apply_room_selection(

        self,

        room
    ):

        """Shared by table clicks and canvas clicks: updates the right-side
        panel (name, sides, area, enables Calculate) and the object
        details line for a given room dict."""

        self.current_room = room

        room_display_name = room.get(

            "name"
        ) or f"Room {room['id']}"

        self.selected_room_label.setText(

            (

                f"{room_display_name} | "

                f"{room['area']} m²"
            )
        )

        sides = (

            room["sides"]
        )

        for i, label in enumerate(

            self.side_labels
        ):

            if i < len(sides):

                label.setText(

                    (

                        f"Side {i + 1}: "

                        f"{sides[i]} m"
                    )
                )

            else:

                label.setText(

                    f"Side {i + 1}: -"
                )

        self.area_label.setText(

            f"Area: {room['area']} m²"
        )

        self.calculate_button.setEnabled(

            True
        )

        self.object_details_label.setText(

            (

                f"Room — {room_display_name} | "

                f"layer: {room.get('layer', 'UNKNOWN')} | "

                f"area: {room['area']} m² | "

                f"perimeter: {room.get('perimeter', '-')} m"
            )
        )

    # =====================================================
    # CANVAS SELECTION (room / door / wall clicked in the drawing)
    # =====================================================

    def on_room_clicked_on_canvas(

        self,

        room
    ):

        self._apply_room_selection(

            room
        )

        # Sync the table selection to match, without re-triggering
        # cellClicked (selectRow doesn't emit it).
        for row, existing_room in enumerate(

            self.rooms
        ):

            if existing_room.get("id") == room.get("id"):

                self.room_table.selectRow(

                    row
                )

                break

    def on_door_clicked(

        self,

        door
    ):

        self.object_details_label.setText(

            (

                f"Door — block: {door.get('block_name', 'UNKNOWN')} | "

                f"layer: {door.get('layer', 'UNKNOWN')} | "

                f"position: ({door['position'][0]:.3f}, "

                f"{door['position'][1]:.3f}) | "

                f"rotation: {door.get('rotation', 0.0):.1f}°"
            )
        )

    def on_wall_clicked(

        self,

        entity
    ):

        length = self.get_entity_length(

            entity
        )

        self.object_details_label.setText(

            (

                f"Wall — layer: {entity.get('layer', 'UNKNOWN')} | "

                f"type: {entity.get('type', '-')} | "

                f"length: {length:.3f} m"
            )
        )

    def on_canvas_selection_cleared(self):

        self.object_details_label.setText(

            "Click a room, door, or wall in the drawing — "

            "or a row below — to see its details."
        )

    @staticmethod
    def get_entity_length(

        entity
    ):

        if entity.get("type") == "LINE":

            start = entity["start"]

            end = entity["end"]

            return (

                (

                    (end[0] - start[0]) ** 2

                    +

                    (end[1] - start[1]) ** 2
                )

                **

                0.5
            )

        if entity.get("type") == "POLYLINE":

            points = entity.get(

                "points",

                []
            )

            total = 0.0

            for i in range(

                len(points) - 1
            ):

                p1 = points[i]

                p2 = points[i + 1]

                total += (

                    (

                        (p2[0] - p1[0]) ** 2

                        +

                        (p2[1] - p1[1]) ** 2
                    )

                    **

                    0.5
                )

            return total

        return 0.0

    # =====================================================
    # PLACE CHANGED
    # =====================================================

    def place_changed(

        self,

        text
    ):

        place = (

            self.places.get(

                text,

                {}
            )
        )

        self.required_lux_label.setText(

            (

                f"Required Lux: "

                f"{place.get('lux', '-')}"
            )
        )

        self.uniformity_label.setText(

            (

                f"Uniformity: "

                f"{place.get('uniformity', '-')}"
            )
        )

        category = (

            self.find_category(

                text
            )
        )

        self.category_label.setText(

            (

                f"Standard Category: "

                f"{category}"
            )
        )

        # Keep user-entered reference, but help when field is empty.
        if not self.standard_ref_input.text().strip():
            default_ref = self.get_place_default_standard_ref(
                text
            )
            if default_ref:
                self.standard_ref_input.setText(
                    default_ref
                )

    # =====================================================
    # FIND STANDARD CATEGORY
    # =====================================================

    def find_category(

        self,

        place_name
    ):

        search_text = (

            place_name.lower()
        )

        for category, keywords in (

            self.category_keywords.items()
        ):

            if search_text in category.lower():

                return category

            for keyword in keywords:

                if keyword.lower() in search_text:

                    return category

        return "No category matched"

    def get_place_default_standard_ref(
        self,
        place_name
    ):

        place = self.places.get(
            place_name,
            {}
        )

        for key in (
            "standard_ref_no",
            "standard_ref",
            "default_standard_ref_no",
            "reference",
            "ref_no"
        ):
            value = place.get(key)
            if value:
                return str(value).strip()

        return ""

    @staticmethod
    def get_valid_room_sides(
        room
    ):

        valid_sides = []

        for raw_side in room.get(
            "sides",
            []
        ):
            try:
                side = float(raw_side)
            except (
                TypeError,
                ValueError
            ):
                continue

            if side > 0.001:
                valid_sides.append(
                    round(side, 4)
                )

        return valid_sides

    # =====================================================
    # CALCULATE
    # =====================================================

    def calculate_lighting(self):

        if not self.current_room:

            QMessageBox.warning(

                self,

                "No Room Selected",

                "Select a detected room first."
            )

            return

        room = (

            self.current_room
        )

        place = (

            self.place_combo.currentText().strip()
        )

        if not place:
            QMessageBox.warning(
                self,
                "Room Type Missing",
                "Select a room type before calculating lighting."
            )
            return

        sides = self.get_valid_room_sides(
            room
        )
        if len(sides) < 3:
            QMessageBox.warning(
                self,
                "Invalid Room Geometry",
                "Selected room boundary is invalid. Please select another room."
            )
            return

        standard_ref = (

            self.standard_ref_input.text().strip()
        )
        if not standard_ref:
            standard_ref = self.get_place_default_standard_ref(
                place
            )
        height = self.height_input.value()
        project_name = self.project_name_input.text().strip()

        try:

            result = (

                self.client.calculate(

                    sides=sides,

                    height=height,

                    place=place,

                    standard_ref_no=standard_ref if standard_ref else None,

                    project_name=project_name,

                    fast=False
                )
            )

            self.result_text.setPlainText(
                (
                    f"Status: {result.get('status', '-')}\n"
                    f"Options: {len(result.get('results', []) or [])}\n"
                    f"Length x Width: {result.get('length', '-')} x "
                    f"{result.get('width', '-')} m\n\n"
                    "Detailed view opened in a new window."
                )
            )

            detail_window = LightingResultWindow(
                room=room,
                result=result,
                request_context={
                    "place": place,
                    "height": height,
                    "standard_ref_no": standard_ref,
                    "project_name": project_name,
                },
                parent=self
            )
            detail_window.exec()

        except Exception as error:

            QMessageBox.critical(

                self,

                "Calculation Error",

                str(error)
            )