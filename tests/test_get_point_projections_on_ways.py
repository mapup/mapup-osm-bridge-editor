import unittest
from shapely.geometry import LineString, Point

import get_point_projections_on_ways as mod


class TestProjectPointOnLine(unittest.TestCase):
    def test_point_projects_onto_line(self):
        line = LineString([(0, 0), (10, 0)])
        point = Point(5, 3)
        projected = mod.project_point_on_line(point, line)
        assert abs(projected.x - 5.0) < 1e-9
        assert abs(projected.y - 0.0) < 1e-9

    def test_point_on_line_returns_same_point(self):
        line = LineString([(0, 0), (10, 0)])
        point = Point(3, 0)
        projected = mod.project_point_on_line(point, line)
        assert abs(projected.x - 3.0) < 1e-9
        assert abs(projected.y - 0.0) < 1e-9

    def test_projection_at_endpoint(self):
        line = LineString([(0, 0), (10, 0)])
        point = Point(15, 0)
        projected = mod.project_point_on_line(point, line)
        assert abs(projected.x - 10.0) < 1e-9

    def test_diagonal_line(self):
        line = LineString([(0, 0), (10, 10)])
        point = Point(10, 0)
        projected = mod.project_point_on_line(point, line)
        assert abs(projected.x - 5.0) < 1e-6
        assert abs(projected.y - 5.0) < 1e-6


if __name__ == "__main__":
    unittest.main()
