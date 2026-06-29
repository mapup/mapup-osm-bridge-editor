import math
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np

import determine_final_osm_id as mod


class TestHaversine(unittest.TestCase):
    def test_same_point_returns_zero(self):
        assert mod.haversine(0, 0, 0, 0) == 0.0

    def test_known_distance(self):
        # NYC to LA roughly 3940 km
        dist = mod.haversine(-74.006, 40.7128, -118.2437, 34.0522)
        assert 3900 < dist < 4000

    def test_symmetry(self):
        d1 = mod.haversine(0, 0, 10, 10)
        d2 = mod.haversine(10, 10, 0, 0)
        assert abs(d1 - d2) < 1e-9

    def test_equatorial_distance(self):
        dist = mod.haversine(0, 0, 1, 0)
        expected = 2 * math.pi * 6371.0 / 360
        assert abs(dist - expected) < 1


class TestExtractCoordinates(unittest.TestCase):
    def test_valid_wkt(self):
        lat, lon = mod.extract_coordinates("POINT (-89.063 36.649)")
        assert abs(lat - 36.649) < 1e-6
        assert abs(lon - (-89.063)) < 1e-6

    def test_nan_input(self):
        lat, lon = mod.extract_coordinates(float("nan"))
        assert lat is None and lon is None

    def test_none_like_nan(self):
        lat, lon = mod.extract_coordinates(pd.NA)
        assert lat is None and lon is None


class TestResolveLocationSingleOsm(unittest.TestCase):
    def _make_df(self, rows):
        return pd.DataFrame(rows, columns=["Long_intersection", "Lat_intersection", "Is_Min_Dist"])

    def test_single_true_stream_row(self):
        true_stream = self._make_df([(10.0, 20.0, True)])
        min_dist = self._make_df([])
        group = self._make_df([(10.0, 20.0, True)])
        long, lat = mod._resolve_location_single_osm(group, true_stream, min_dist)
        assert long == 10.0 and lat == 20.0

    def test_multiple_true_stream_with_min_dist(self):
        true_stream = pd.DataFrame({
            "Long_intersection": [1.0, 2.0],
            "Lat_intersection": [3.0, 4.0],
            "Is_Min_Dist": [True, False],
        })
        min_dist = true_stream[true_stream["Is_Min_Dist"]]
        group = true_stream.copy()
        long, lat = mod._resolve_location_single_osm(group, true_stream, min_dist)
        assert long == 1.0 and lat == 3.0

    def test_multiple_true_stream_without_min_dist_match(self):
        true_stream = pd.DataFrame({
            "Long_intersection": [1.0, 2.0],
            "Lat_intersection": [3.0, 4.0],
            "Is_Min_Dist": [False, False],
        })
        min_dist = pd.DataFrame(columns=["Long_intersection", "Lat_intersection", "Is_Min_Dist"])
        group = true_stream.copy()
        long, lat = mod._resolve_location_single_osm(group, true_stream, min_dist)
        assert long == 1.0 and lat == 3.0

    def test_empty_true_stream_uses_min_dist(self):
        true_stream = pd.DataFrame(columns=["Long_intersection", "Lat_intersection", "Is_Min_Dist"])
        min_dist = pd.DataFrame({"Long_intersection": [5.0], "Lat_intersection": [6.0], "Is_Min_Dist": [True]})
        group = min_dist.copy()
        long, lat = mod._resolve_location_single_osm(group, true_stream, min_dist)
        assert long == 5.0 and lat == 6.0

    def test_empty_true_stream_empty_min_dist_uses_group(self):
        true_stream = pd.DataFrame(columns=["Long_intersection", "Lat_intersection", "Is_Min_Dist"])
        min_dist = pd.DataFrame(columns=["Long_intersection", "Lat_intersection", "Is_Min_Dist"])
        group = pd.DataFrame({"Long_intersection": [7.0], "Lat_intersection": [8.0], "Is_Min_Dist": [False]})
        long, lat = mod._resolve_location_single_osm(group, true_stream, min_dist)
        assert long == 7.0 and lat == 8.0


class TestResolveOsmForMultiple(unittest.TestCase):
    COLS = ["osm_id", "name", "permanent_identifier_x", "gnis_name", "Long_intersection", "Lat_intersection"]

    def _make_df(self, data):
        return pd.DataFrame([data], columns=self.COLS)

    def test_single_true_stream(self):
        true_stream = self._make_df(["id1", "Road A", "stream1", "Creek", 1.0, 2.0])
        min_dist = pd.DataFrame(columns=self.COLS)
        osm_id, osm_name, stream_id, stream_name, long, lat = mod._resolve_osm_for_multiple(true_stream, min_dist)
        assert osm_id == "id1"
        assert long == 1.0

    def test_multiple_true_stream_uses_min_dist(self):
        true_stream = pd.DataFrame(
            [["id1", "A", "s1", "c1", 1.0, 2.0], ["id2", "B", "s2", "c2", 3.0, 4.0]],
            columns=self.COLS
        )
        min_dist = self._make_df(["id2", "B", "s2", "c2", 3.0, 4.0])
        osm_id, _, _, _, long, _ = mod._resolve_osm_for_multiple(true_stream, min_dist)
        assert osm_id == "id2"
        assert long == 3.0

    def test_empty_both_returns_na(self):
        true_stream = pd.DataFrame(columns=self.COLS)
        min_dist = pd.DataFrame(columns=self.COLS)
        osm_id, osm_name, stream_id, stream_name, long, lat = mod._resolve_osm_for_multiple(true_stream, min_dist)
        assert pd.isna(osm_id)


class TestDetermineFinalOsmId(unittest.TestCase):
    def _base_group(self, combo_count, osm_id, is_stream, is_min):
        return pd.DataFrame({
            "combo-count": [combo_count],
            "osm_id": [osm_id],
            "name": ["Road"],
            "permanent_identifier_x": ["stream1"],
            "gnis_name": ["Creek"],
            "Long_intersection": [10.0],
            "Lat_intersection": [20.0],
            "Is_Stream_Identical": [is_stream],
            "Is_Min_Dist": [is_min],
        })

    def test_single_combo_with_min_dist(self):
        group = self._base_group(1, "osm1", True, True)
        result = mod.determine_final_osm_id(group)
        assert result["final_osm_id"] == "osm1"

    def test_single_combo_no_min_dist(self):
        group = self._base_group(1, "osm1", False, False)
        result = mod.determine_final_osm_id(group)
        assert result["final_osm_id"] == "osm1"
        assert pd.isna(result["final_stream_id"])

    def test_multiple_combo(self):
        row = {"combo-count": 2, "osm_id": "osm2", "name": "Road B",
               "permanent_identifier_x": "s2", "gnis_name": "River",
               "Long_intersection": 5.0, "Lat_intersection": 6.0,
               "Is_Stream_Identical": True, "Is_Min_Dist": True}
        group = pd.DataFrame([row])
        result = mod.determine_final_osm_id(group)
        assert result["final_osm_id"] == "osm2"


class TestCreateIntermediateAssociation(unittest.TestCase):
    def test_creates_expected_columns(self):
        df = pd.DataFrame({
            "WKT": ["POINT (-89.063 36.649)"],
            "17 - Longitude (decimal)": [-89.063],
            "16 - Latitude (decimal)": [36.649],
            "permanent_identifier_x": ["s1"],
            "permanent_identifier_y": ["s1"],
            "osm_id": ["123"],
            mod.STRUCTURE_NUMBER: ["BRG001"],
        })
        with patch.object(df.__class__, "to_csv"):
            result = mod.create_intermediate_association(df, "/tmp/test.csv")
        assert "Haversine_dist" in result.columns
        assert "Is_Min_Dist" in result.columns
        assert "Is_Stream_Identical" in result.columns


class TestCreateFinalAssociations(unittest.TestCase):
    def test_produces_final_osm_id_column(self):
        df = pd.DataFrame({
            mod.STRUCTURE_NUMBER: ["B1", "B1"],
            "osm_id": ["osm1", "osm1"],
            "name": ["Road", "Road"],
            "permanent_identifier_x": ["s1", "s1"],
            "gnis_name": ["Creek", "Creek"],
            "Long_intersection": [1.0, 1.0],
            "Lat_intersection": [2.0, 2.0],
            "Is_Stream_Identical": [True, True],
            "Is_Min_Dist": [True, False],
        })
        with patch("pandas.DataFrame.to_csv"):
            result = mod.create_final_associations(df, "/tmp/out.csv")
        assert "final_osm_id" in result.columns


class TestMergeJoinDataWithIntersections(unittest.TestCase):
    def test_merges_on_osm_id(self):
        join_df = pd.DataFrame({
            "osm_id": ["1"], "permanent_identifier_x": ["p1"],
            "col_a": ["val_a"]
        })
        intersect_df = pd.DataFrame({
            "WKT": ["POINT (0 0)"], "osm_id": ["1"],
            "permanent_identifier": ["p1"], "gnis_name": ["Creek"]
        })
        with patch("pandas.read_csv", side_effect=[join_df, intersect_df]):
            result = mod.merge_join_data_with_intersections("a.csv", "b.csv")
        assert "WKT" in result.columns


class TestAddBridgeDetails(unittest.TestCase):
    def test_returns_none_and_saves(self):
        df = pd.DataFrame({
            mod.STRUCTURE_NUMBER: ["B1"],
            "final_osm_id": ["osm1"],
            "osm_name": ["Road"],
            "final_stream_id": ["s1"],
            "stream_name": ["Creek"],
            "final_long": [1.0],
            "final_lat": [2.0],
            "6A - Features Intersected": ["Feature"],
            "7 - Facility Carried By Structure": ["Road"],
            "Unique_Bridge_OSM_Combinations": [1],
        })
        bridge_data = pd.DataFrame({
            mod.STRUCTURE_NUMBER: ["B1"],
            mod.STRUCTURE_LENGTH: [100.0],
            "6A - Features Intersected": ["Feature"],
            "7 - Facility Carried By Structure": ["Road"],
        })
        with patch("pandas.read_csv", return_value=bridge_data), \
             patch("pandas.DataFrame.to_csv"):
            mod.add_bridge_details(df, "nbi.csv", "out.csv")


if __name__ == "__main__":
    unittest.main()
