import math


def distance(
    p1,
    p2
):

    dx = p2[0] - p1[0]

    dy = p2[1] - p1[1]

    return math.sqrt(

        dx * dx

        +

        dy * dy
    )


def polygon_area(
    points
):

    if len(points) < 3:

        return 0.0

    area = 0.0

    for i in range(
        len(points)
    ):

        x1, y1 = points[i]

        x2, y2 = points[
            (i + 1)
            %
            len(points)
        ]

        area += (

            x1 * y2

            -

            x2 * y1
        )

    return abs(
        area
    ) / 2.0


def polygon_perimeter(
    points
):

    if len(points) < 2:

        return 0.0

    perimeter = 0.0

    for i in range(
        len(points)
    ):

        p1 = points[i]

        p2 = points[

            (i + 1)
            %
            len(points)
        ]

        perimeter += distance(
            p1,
            p2
        )

    return perimeter


def bounding_box(
    points
):

    if not points:

        return None

    xs = [

        point[0]

        for point in points
    ]

    ys = [

        point[1]

        for point in points
    ]

    return {

        "min_x":
            min(xs),

        "max_x":
            max(xs),

        "min_y":
            min(ys),

        "max_y":
            max(ys),

        "width":
            max(xs)
            -
            min(xs),

        "height":
            max(ys)
            -
            min(ys)
    }


def polygon_side_lengths(
    points
):

    sides = []

    for i in range(
        len(points)
    ):

        p1 = points[i]

        p2 = points[

            (i + 1)
            %
            len(points)
        ]

        sides.append(

            distance(
                p1,
                p2
            )
        )

    return sides


def remove_duplicate_last_point(
    points
):

    if len(points) > 1:

        if points[0] == points[-1]:

            return points[:-1]

    return points