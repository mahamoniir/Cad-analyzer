from .geometry import (

    polygon_area,

    polygon_perimeter,

    bounding_box,

    polygon_side_lengths,

    remove_duplicate_last_point
)


class RoomDetector:

    def __init__(

        self,

        min_area=5.0,

        max_area=10000.0
    ):

        self.min_area = min_area

        self.max_area = max_area

    # ========================================================
    # DETECT ROOMS
    # ========================================================

    def detect_rooms(

        self,

        cad_report
    ):

        rooms = []

        entities = (

            cad_report[

                "modelspace"
            ][

                "entities"
            ]
        )

        room_id = 1

        for entity in entities:

            entity_type = (

                entity.get(
                    "type"
                )
            )

            if entity_type not in [

                "LWPOLYLINE",

                "POLYLINE"
            ]:

                continue

            if not entity.get(
                "closed",
                False
            ):

                continue

            raw_points = (

                entity.get(
                    "points",
                    []
                )
            )

            points = []

            for point in raw_points:

                if isinstance(
                    point,
                    dict
                ):

                    points.append(

                        [

                            point["x"],

                            point["y"]
                        ]
                    )

                else:

                    points.append(

                        [

                            point[0],

                            point[1]
                        ]
                    )

            points = (

                remove_duplicate_last_point(

                    points
                )
            )

            if len(points) < 3:

                continue

            area = polygon_area(
                points
            )

            if area < self.min_area:

                continue

            if area > self.max_area:

                continue

            bbox = bounding_box(
                points
            )

            sides = polygon_side_lengths(
                points
            )

            room = {

                "id":
                    f"room_{room_id:03d}",

                "source_entity_handle":
                    entity.get(
                        "handle"
                    ),

                "source_layer":
                    entity.get(
                        "layer"
                    ),

                "boundary":
                    points,

                "area":
                    round(
                        area,
                        4
                    ),

                "perimeter":
                    round(

                        polygon_perimeter(
                            points
                        ),

                        4
                    ),

                "sides":
                    [

                        round(
                            side,
                            4
                        )

                        for side in sides
                    ],

                "bounding_box":
                    bbox,

                "width":
                    bbox["width"],

                "length":
                    bbox["height"],

                "height":
                    None,

                "place":
                    None,

                "standard_ref_no":
                    None
            }

            rooms.append(
                room
            )

            room_id += 1

        return rooms