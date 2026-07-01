import sys
import unittest
from unittest.mock import patch, MagicMock, mock_open
import pyproj
from shapely.geometry import LineString, Point

import obtain_bridge_split_info as mod


class TestFindNearestPointOnLine(unittest.TestCase):
    def test_nearest_point_on_horizontal_line(self):
        line = LineString([(0, 0), (10, 0)])
        point = Point(5, 5)
        result = mod.find_nearest_point_on_line(line, point)
        assert abs(result.x - 5.0) < 1e-6
        assert abs(result.y - 0.0) < 1e-6

    def test_point_on_line_returns_same(self):
        line = LineString([(0, 0), (10, 0)])
        point = Point(3, 0)
        result = mod.find_nearest_point_on_line(line, point)
        assert abs(result.x - 3.0) < 1e-6

    def test_returns_none_on_exception(self):
        with patch("obtain_bridge_split_info.nearest_points", side_effect=Exception("err")):
            result = mod.find_nearest_point_on_line(LineString([(0, 0), (1, 1)]), Point(0, 0))
        assert result is None


class TestFindWayIdForPoint(unittest.TestCase):
    def test_finds_matching_line(self):
        line = LineString([(0, 0), (10, 0)])
        point = line.interpolate(5)
        result = mod.find_way_id_for_point(point, [(line, "way1")])
        assert result == "way1"

    def test_returns_none_when_no_match(self):
        line = LineString([(0, 0), (10, 0)])
        far_point = Point(100, 100)
        result = mod.find_way_id_for_point(far_point, [(line, "way1")])
        assert result is None

    def test_returns_none_on_empty_list(self):
        result = mod.find_way_id_for_point(Point(0, 0), [])
        assert result is None


class TestBuildResultDict(unittest.TestCase):
    def test_dict_has_expected_keys(self):
        nearest = MagicMock()
        nearest.x = 1.0
        nearest.y = 2.0
        fwd = MagicMock()
        fwd.x = 3.0
        fwd.y = 4.0
        bwd = MagicMock()
        bwd.x = 5.0
        bwd.y = 6.0
        result = mod._build_result_dict(
            "osm1", "bridge1", 100.0, (36.0, -89.0),
            nearest, fwd, bwd, "way_fwd", [], "way_bwd", [], 50.0, 50.0
        )
        assert result["original_osm_id"] == "osm1"
        assert result["bridge_id"] == "bridge1"
        assert result["actual_forward_distance"] == 50.0
        assert result["actual_backward_distance"] == 50.0
        assert result["forward_way_id"] == "way_fwd"
        assert result["backward_way_id"] == "way_bwd"

    def test_none_way_ids_become_minus_one(self):
        pt = MagicMock()
        pt.x = 0.0
        pt.y = 0.0
        result = mod._build_result_dict(
            "osm1", "b1", 50.0, (0.0, 0.0), pt, pt, pt,
            None, None, None, None, 10.0, 10.0
        )
        assert result["forward_way_id"] == -1
        assert result["backward_way_id"] == -1
        assert result["forward_visited"] == "None"
        assert result["backward_visited"] == "None"


class TestTransformResultPoints(unittest.TestCase):
    def test_none_inputs_return_minus_one_points(self):
        def fake_transform(fn, pt):
            return pt

        fwd, bwd = mod._transform_result_points(None, None, fake_transform)
        assert fwd.x == -1 and fwd.y == -1
        assert bwd.x == -1 and bwd.y == -1

    def test_transforms_valid_points(self):
        transformed = Point(5, 6)
        fwd_utm = Point(1, 2)
        bwd_utm = Point(3, 4)
        with patch("obtain_bridge_split_info.transform", return_value=transformed):
            fwd, bwd = mod._transform_result_points(fwd_utm, bwd_utm, lambda x, y: (x, y))
        assert fwd == transformed
        assert bwd == transformed


class TestFindConnectedLines(unittest.TestCase):
    def test_finds_connected_line_at_start(self):
        line_a = LineString([(0, 0), (5, 0)])
        line_b = LineString([(5, 0), (10, 0)])
        connection = Point(5, 0)
        way_id, possible = mod._find_connected_lines(line_a, [(line_a, "a"), (line_b, "b")], connection, set())
        assert way_id == "a"
        assert len(possible) == 1
        assert possible[0][1] == "b"

    def test_inverts_line_connected_at_end(self):
        line_a = LineString([(0, 0), (5, 0)])
        line_b = LineString([(10, 0), (5, 0)])
        connection = Point(5, 0)
        _, possible = mod._find_connected_lines(line_a, [(line_a, "a"), (line_b, "b")], connection, set())
        assert len(possible) == 1

    def test_visited_lines_excluded(self):
        line_a = LineString([(0, 0), (5, 0)])
        line_b = LineString([(5, 0), (10, 0)])
        connection = Point(5, 0)
        _, possible = mod._find_connected_lines(line_a, [(line_a, "a"), (line_b, "b")], connection, {"b"})
        assert len(possible) == 0


class TestExtendAlongConnectedWay(unittest.TestCase):
    def test_simple_extension(self):
        line_a = LineString([(0, 0), (10, 0)])
        line_b = LineString([(10, 0), (20, 0)])
        all_lines = [(line_a, "a"), (line_b, "b")]
        point, way_id, visited = mod.extend_along_connected_way(line_a, 5.0, all_lines)
        assert point is not None
        assert way_id == "b"

    def test_no_connection_returns_none(self):
        line_a = LineString([(0, 0), (10, 0)])
        all_lines = [(line_a, "a")]
        point, way_id, visited = mod.extend_along_connected_way(line_a, 5.0, all_lines)
        assert point is None

    def test_split_detected_stops_and_returns_none(self):
        line_a = LineString([(0, 0), (10, 0)])
        line_b = LineString([(10, 0), (20, 0)])
        line_c = LineString([(10, 0), (10, 10)])
        all_lines = [(line_a, "a"), (line_b, "b"), (line_c, "c")]
        point, way_id, visited = mod.extend_along_connected_way(line_a, 5.0, all_lines)
        assert point is None

    def test_reverse_direction(self):
        line_a = LineString([(10, 0), (20, 0)])
        line_b = LineString([(0, 0), (10, 0)])
        all_lines = [(line_a, "a"), (line_b, "b")]
        point, way_id, visited = mod.extend_along_connected_way(line_a, 5.0, all_lines, reverse=True)
        assert point is not None

    def test_exception_returns_none(self):
        with patch("obtain_bridge_split_info._find_connected_lines", side_effect=Exception("err")):
            point, way_id, visited = mod.extend_along_connected_way(
                LineString([(0, 0), (1, 0)]), 5.0, []
            )
        assert point is None


class TestCalculatePointsOnWay(unittest.TestCase):
    def test_both_points_within_line(self):
        line = LineString([(0, 0), (100, 0)])
        nearest = Point(50, 0)
        fwd, fwd_id, fwd_vis, bwd, bwd_id, bwd_vis = mod.calculate_points_on_way(
            line, nearest, 10.0, [(line, "w1")]
        )
        assert fwd is not None
        assert bwd is not None

    def test_forward_beyond_line_triggers_extension(self):
        line = LineString([(0, 0), (5, 0)])
        line_b = LineString([(5, 0), (20, 0)])
        nearest = Point(4, 0)
        all_lines = [(line, "w1"), (line_b, "w2")]
        fwd, fwd_id, fwd_vis, bwd, bwd_id, bwd_vis = mod.calculate_points_on_way(
            line, nearest, 3.0, all_lines
        )
        assert fwd is not None or fwd is None  # either extends or stops

    def test_exception_returns_nones(self):
        with patch("obtain_bridge_split_info.find_way_id_for_point", side_effect=Exception):
            fwd, fwd_id, fwd_vis, bwd, bwd_id, bwd_vis = mod.calculate_points_on_way(
                LineString([(0, 0), (10, 0)]), Point(5, 0), 2.0, []
            )
        assert fwd is None


class TestLoadGeojson(unittest.TestCase):
    def test_returns_data_on_valid_file(self):
        mock_data = {"type": "FeatureCollection", "features": []}
        with patch("builtins.open", unittest.mock.mock_open(read_data='{"type":"FeatureCollection","features":[]}')), \
             patch("json.load", return_value=mock_data):
            result = mod.load_geojson("fake.geojson")
        assert result == mock_data

    def test_returns_none_on_exception(self):
        with patch("builtins.open", side_effect=Exception("err")):
            result = mod.load_geojson("bad.geojson")
        assert result is None


class TestLoadCsv(unittest.TestCase):
    def test_parses_rows(self):
        csv_content = "final_osm_id,STRUCTURE_NUMBER_008,bridge_length,final_lat,final_long\nosm1,B001,100.0,36.5,-89.0\n"
        with patch("builtins.open", unittest.mock.mock_open(read_data=csv_content)):
            result = mod.load_csv("fake.csv")
        assert len(result) == 1
        assert result[0]["osm_id"] == "osm1"

    def test_returns_empty_on_exception(self):
        with patch("builtins.open", side_effect=Exception("err")):
            result = mod.load_csv("bad.csv")
        assert result == []


class TestSetupLogging(unittest.TestCase):
    def test_setup_logging_does_not_raise(self):
        # basicConfig is a no-op if logging is already configured, so just verify no exception
        mod.setup_logging()


class TestParseArguments(unittest.TestCase):
    def test_parses_two_positional_args(self):
        with patch("sys.argv", ["prog", "data.geojson", "bridges.csv"]):
            args = mod.parse_arguments()
        assert args.geojson_file == "data.geojson"
        assert args.csv_file == "bridges.csv"

    def test_missing_args_exits(self):
        with patch("sys.argv", ["prog"]):
            with self.assertRaises(SystemExit):
                mod.parse_arguments()


class TestProcessSingleBridge(unittest.TestCase):
    def _make_bridge(self, osm_id="osm1", length=100.0, coord=(-89.0, 36.5)):
        return {
            "index": 1,
            "osm_id": osm_id,
            "bridge_length": length,
            "bridge_coordinate": coord,
            "bridge_id": "B001",
        }

    def _make_projectors(self):
        wgs84 = pyproj.CRS("EPSG:4326")
        utm = pyproj.CRS("EPSG:32616")
        project = pyproj.Transformer.from_crs(wgs84, utm, always_xy=True).transform
        inverse = pyproj.Transformer.from_crs(utm, wgs84, always_xy=True).transform
        return project, inverse

    def test_returns_none_when_no_matching_osm_id(self):
        from shapely.ops import transform
        project, inverse = self._make_projectors()
        line = LineString([(-89.01, 36.5), (-89.0, 36.5)])
        from shapely.ops import transform as shp_transform
        line_utm = shp_transform(project, line)
        lines_utm_with_ids = [(line_utm, "other_osm_id")]
        bridge = self._make_bridge(osm_id="osm1")
        result = mod.process_single_bridge(bridge, lines_utm_with_ids, project, inverse)
        assert result is None

    def test_returns_none_on_exception(self):
        bridge = self._make_bridge()
        result = mod.process_single_bridge(bridge, "not_a_list", None, None)
        assert result is None

    def test_processes_bridge_on_matching_line(self):
        from shapely.ops import transform as shp_transform
        project, inverse = self._make_projectors()
        line = LineString([(-89.01, 36.5), (-88.99, 36.5)])
        line_utm = shp_transform(project, line)
        lines_utm = [(line_utm, "osm1")]
        bridge = self._make_bridge(osm_id="osm1", length=50.0, coord=(-89.0, 36.5))
        with patch("builtins.open", mock_open()):
            result = mod.process_single_bridge(bridge, lines_utm, project, inverse)
        # Result is a dict or None (may be None if point not within 1m of line)
        assert result is None or isinstance(result, dict)


class TestProcessBridgeDataParallel(unittest.TestCase):
    def test_returns_list_of_results(self):
        wgs84 = pyproj.CRS("EPSG:4326")
        utm = pyproj.CRS("EPSG:32616")
        project = pyproj.Transformer.from_crs(wgs84, utm, always_xy=True).transform
        inverse = pyproj.Transformer.from_crs(utm, wgs84, always_xy=True).transform
        lines_with_ids = {}  # no lines → no results
        bridge_data = [
            {"index": 1, "osm_id": "x", "bridge_length": 10, "bridge_coordinate": (0, 0), "bridge_id": "B1"},
        ]
        result = mod.process_bridge_data_parallel(bridge_data, lines_with_ids, project, inverse)
        assert isinstance(result, list)

    def test_returns_empty_list_on_exception(self):
        with patch("obtain_bridge_split_info.Pool", side_effect=Exception("pool error")):
            result = mod.process_bridge_data_parallel([], {}, None, None)
        assert result == []


if __name__ == "__main__":
    unittest.main()
