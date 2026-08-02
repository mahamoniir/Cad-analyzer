from PySide6.QtCore import QThread, Signal


class CADAnalysisWorker(QThread):

    finished = Signal(object)

    error = Signal(str)

    progress = Signal(str)

    def __init__(
        self,
        pipeline
    ):

        super().__init__()

        self.pipeline = pipeline

    def run(self):

        try:

            self.progress.emit(
                "Loading DWG file..."
            )

            cad_report = (

                self.pipeline.analyze_cad()
            )

            self.progress.emit(

                "Detecting rooms..."
            )

            rooms = (

                self.pipeline.detect_rooms(

                    cad_report
                )
            )

            self.finished.emit({

                "cad_report":
                    cad_report,

                "rooms":
                    rooms
            })

        except Exception as e:

            self.error.emit(
                str(e)
            )


class LightingCalculationWorker(QThread):

    finished = Signal(object)

    error = Signal(str)

    progress = Signal(str)

    def __init__(

        self,

        pipeline,

        room,

        place,

        height,

        standard_ref_no,

        project_name
    ):

        super().__init__()

        self.pipeline = pipeline

        self.room = room

        self.place = place

        self.height = height

        self.standard_ref_no = (

            standard_ref_no
        )

        self.project_name = (

            project_name
        )

    def run(self):

        try:

            self.progress.emit(

                "Calculating lighting..."
            )

            result = (

                self.pipeline.calculate_room(

                    room=self.room,

                    place=self.place,

                    height=self.height,

                    standard_ref_no=(

                        self.standard_ref_no
                    ),

                    project_name=(

                        self.project_name
                    )
                )
            )

            self.finished.emit(
                result
            )

        except Exception as e:

            self.error.emit(
                str(e)
            )