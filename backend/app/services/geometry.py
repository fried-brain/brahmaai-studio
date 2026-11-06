from collections.abc import Sequence

Point = tuple[float, float]


def cross(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def on_segment(a: Point, b: Point, p: Point, epsilon: float = 1e-7) -> bool:
    return (
        min(a[0], b[0]) - epsilon <= p[0] <= max(a[0], b[0]) + epsilon
        and min(a[1], b[1]) - epsilon <= p[1] <= max(a[1], b[1]) + epsilon
        and abs(cross(a, b, p)) <= epsilon
    )


def segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    ab_c, ab_d = cross(a, b, c), cross(a, b, d)
    cd_a, cd_b = cross(c, d, a), cross(c, d, b)
    eps = 1e-7
    if ((ab_c > eps and ab_d < -eps) or (ab_c < -eps and ab_d > eps)) and (
        (cd_a > eps and cd_b < -eps) or (cd_a < -eps and cd_b > eps)
    ):
        return True
    return (
        (abs(ab_c) <= eps and on_segment(a, b, c))
        or (abs(ab_d) <= eps and on_segment(a, b, d))
        or (abs(cd_a) <= eps and on_segment(c, d, a))
        or (abs(cd_b) <= eps and on_segment(c, d, b))
    )


def validate_polygon(vertices: Sequence[Point]) -> None:
    if len(vertices) < 3:
        raise ValueError("A plot polygon requires at least 3 vertices")
    if len(vertices) > 500:
        raise ValueError("A plot polygon cannot exceed 500 vertices")
    if len(set(vertices)) != len(vertices):
        raise ValueError("A plot polygon cannot contain duplicate vertices")
    count = len(vertices)
    for index, point in enumerate(vertices):
        following = vertices[(index + 1) % count]
        if point == following:
            raise ValueError("A plot polygon cannot contain zero-length edges")
    for i in range(count):
        a, b = vertices[i], vertices[(i + 1) % count]
        for j in range(i + 1, count):
            # Adjacent edges share a vertex by design; first and last are adjacent too.
            if j == i or j == i + 1 or (i == 0 and j == count - 1):
                continue
            c, d = vertices[j], vertices[(j + 1) % count]
            if segments_intersect(a, b, c, d):
                raise ValueError("A plot polygon cannot self-intersect or touch itself")
    if abs(signed_double_area(vertices)) <= 1e-6:
        raise ValueError("A plot polygon must enclose a non-zero area")


def signed_double_area(vertices: Sequence[Point]) -> float:
    return sum(
        vertices[i][0] * vertices[(i + 1) % len(vertices)][1]
        - vertices[(i + 1) % len(vertices)][0] * vertices[i][1]
        for i in range(len(vertices))
    )


def polygon_area_mm2(vertices: Sequence[Point]) -> float:
    return abs(signed_double_area(vertices)) / 2


def polygon_perimeter_mm(vertices: Sequence[Point]) -> float:
    return sum(
        ((vertices[(i + 1) % len(vertices)][0] - vertices[i][0]) ** 2
         + (vertices[(i + 1) % len(vertices)][1] - vertices[i][1]) ** 2) ** 0.5
        for i in range(len(vertices))
    )


def point_location(point: Point, polygon: Sequence[Point], epsilon: float = 1e-7) -> str:
    """Return inside, boundary, or outside using an even-odd ray cast."""
    x, y = point
    inside = False
    for index, start in enumerate(polygon):
        end = polygon[(index + 1) % len(polygon)]
        if on_segment(start, end, point, epsilon):
            return "boundary"
        if (start[1] > y) != (end[1] > y):
            crossing_x = (end[0] - start[0]) * (y - start[1]) / (end[1] - start[1]) + start[0]
            if x < crossing_x:
                inside = not inside
    return "inside" if inside else "outside"


def polygon_within_polygon(inner: Sequence[Point], outer: Sequence[Point]) -> bool:
    """True when all inner edges remain inside/on the outer polygon."""
    for index, start in enumerate(inner):
        end = inner[(index + 1) % len(inner)]
        midpoint = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        if point_location(start, outer) == "outside" or point_location(midpoint, outer) == "outside":
            return False
        for edge_index, boundary_start in enumerate(outer):
            boundary_end = outer[(edge_index + 1) % len(outer)]
            if segments_intersect(start, end, boundary_start, boundary_end):
                # Coincident boundary edges are valid; crossing/touching at an
                # isolated point is not, unless it is a shared endpoint.
                collinear = abs(cross(start, end, boundary_start)) <= 1e-7 and abs(cross(start, end, boundary_end)) <= 1e-7
                shared_endpoint = (
                    on_segment(boundary_start, boundary_end, start)
                    or on_segment(boundary_start, boundary_end, end)
                    or on_segment(start, end, boundary_start)
                    or on_segment(start, end, boundary_end)
                )
                if not collinear and not shared_endpoint:
                    return False
    return True


def polygons_overlap(first: Sequence[Point], second: Sequence[Point]) -> bool:
    """Detect positive-area overlap while permitting rooms to share walls."""
    if len(first) == len(second) and set(first) == set(second):
        return True
    for i, a in enumerate(first):
        b = first[(i + 1) % len(first)]
        for j, c in enumerate(second):
            d = second[(j + 1) % len(second)]
            ab_c, ab_d = cross(a, b, c), cross(a, b, d)
            cd_a, cd_b = cross(c, d, a), cross(c, d, b)
            if ((ab_c > 1e-7 and ab_d < -1e-7) or (ab_c < -1e-7 and ab_d > 1e-7)) and (
                (cd_a > 1e-7 and cd_b < -1e-7) or (cd_a < -1e-7 and cd_b > 1e-7)
            ):
                return True
    return any(point_location(point, second) == "inside" for point in first) or any(
        point_location(point, first) == "inside" for point in second
    )
