import json

from pathlib import Path

from .dwg_reader import DWGReader

from .room_detector import RoomDetector

from luxscale_client import LuxScaleClient


class CADPipeline:

    def __init__(

        self,

        dwg_path,

        api_url,

        output_dir="output"
    ):

        self.dwg_path = Path(

            dwg_path
        )

        self.api_url = api_url

        self.output_dir = Path(

            output_dir
        )

        self.output_dir.mkdir(

            parents=True,

            exist_ok=True
        )

    # ========================================================
    # RUN CAD ANALYSIS
    # ========================================================

    def analyze_cad(self):

        reader = DWGReader(

            self.dwg_path
        )

        reader.load()

        cad_report = reader.analyze()

        output_file = (

            self.output_dir

            /

            "cad_analysis.json"
        )

        with open(

            output_file,

            "w",

            encoding="utf-8"
        ) as file:

            json.dump(

                cad_report,

                file,

                indent=2,

                ensure_ascii=False
            )

        print(

            f"CAD analysis saved to: "
            f"{output_file}"
        )

        return cad_report

    # ========================================================
    # DETECT ROOMS
    # ========================================================

    def detect_rooms(

        self,

        cad_report
    ):

        detector = RoomDetector()

        rooms = detector.detect_rooms(

            cad_report
        )

        rooms_file = (

            self.output_dir

            /

            "detected_rooms.json"
        )

        with open(

            rooms_file,

            "w",

            encoding="utf-8"
        ) as file:

            json.dump(

                rooms,

                file,

                indent=2,

                ensure_ascii=False
            )

        print(

            f"Detected rooms: "
            f"{len(rooms)}"
        )

        print(

            f"Rooms saved to: "
            f"{rooms_file}"
        )

        return rooms

    # ========================================================
    # SEND ROOM TO LUXSCALE
    # ========================================================

    def calculate_room(

        self,

        room,

        place="Office",

        height=3.2,

        standard_ref_no="5.2.1",

        project_name="CAD Project"
    ):

        client = LuxScaleClient(

            self.api_url
        )

        payload = {

            "sides":
                room["sides"],

            "height":
                height,

            "place":
                place,

            "project_info": {

                "project_name":
                    project_name,

                "standard_ref_no":
                    standard_ref_no
            },

            "fast":
                False
        }

        print(

            "Sending room to LuxScaleAI..."
        )

        print(

            payload
        )

        result = client.calculate_raw(

            payload
        )

        return result