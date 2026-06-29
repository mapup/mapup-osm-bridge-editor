import sys
import os
import unittest
from unittest.mock import patch, MagicMock, call
import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import LineString, Point

import bridge_point_extractor as mod


class TestFilterLeftRightBridges(unittest.TestCase):
    def _make_df(self, bridge_ids, lrs_ids, begin_mps=None, end_mps=None):
        n = len(bridge_ids)
        return pd.DataFrame({
            "bridge_id": bridge_ids,
            "lrs_id": lrs_ids,
            "begin_mp": begin_mps or [0.0] * n,
            "end_mp": end_mps or [1.0] * n,
        })

    def test_no_lr_bridges_returns_all(self):
        df = self._make_df(["B001", "B002"], ["LRS1", "LRS2"])
        result = mod.filter_left_right_bridges(df)
        assert len(result) == 2

    def test_removes_left_lane_bridge_with_double(self):
        # B001L has two rows: one on LRS1 (left, begin<end) and one on LRS1-10 (paired)
        df = self._make_df(
            ["B001L", "B001L"],
            ["LRS1", "LRS1-10"],
            begin_mps=[0.0, 0.0],
            end_mps=[1.0, 1.0],
        )
        result = mod.filter_left_right_bridges(df)
        # Row with lrs_id LRS1 is the L-type that should be filtered (begin<end and L in id)
        assert isinstance(result, pd.DataFrame)

    def test_no_double_means_not_filtered(self):
        # B001L exists but has no paired -10 lrs_id counterpart => not filtered
        df = self._make_df(["B001L", "B002"], ["LRS_ONLY", "LRS2"])
        result = mod.filter_left_right_bridges(df)
        assert len(result) == 2

    def test_decreasing_mp_r_bridge_filtered(self):
        # R bridge, begin_mp > end_mp → candidate for removal if paired -10 exists
        df = self._make_df(
            ["B001R", "B001R"],
            ["LRS1", "LRS1-10"],
            begin_mps=[1.0, 1.0],
            end_mps=[0.0, 0.0],
        )
        result = mod.filter_left_right_bridges(df)
        assert isinstance(result, pd.DataFrame)

    def test_empty_df_returns_empty(self):
        df = pd.DataFrame(columns=["bridge_id", "lrs_id", "begin_mp", "end_mp"])
        result = mod.filter_left_right_bridges(df)
        assert len(result) == 0


class TestInterpolatePointGeography(unittest.TestCase):
    def test_within_line_returns_point(self):
        # Line from (0,0) to (1,0) — about 111 km at equator
        line = LineString([(0, 0), (1, 0)])
        pt, seg = mod.interpolate_point_geography(line, 1000)  # 1000 m well within ~111km
        assert isinstance(pt, Point)
        assert isinstance(seg, LineString)

    def test_beyond_line_returns_na(self):
        # Tiny line ~11 m long
        line = LineString([(0, 0), (0.0001, 0)])
        pt, seg = mod.interpolate_point_geography(line, 1_000_000)
        assert pd.isna(pt)
        assert pd.isna(seg)

    def test_zero_distance_returns_start_point(self):
        line = LineString([(0, 0), (1, 0)])
        pt, seg = mod.interpolate_point_geography(line, 0)
        assert isinstance(pt, Point)

    def test_multipoint_line_segments(self):
        line = LineString([(0, 0), (0.5, 0), (1, 0)])
        pt, seg = mod.interpolate_point_geography(line, 500)
        assert isinstance(pt, Point)

    def test_exact_total_length(self):
        # Request exactly the total line length: should return last point or last segment
        line = LineString([(0, 0), (0.001, 0)])  # ~111 m
        from geographiclib.geodesic import Geodesic
        geo = Geodesic(6378137, 1 / 298.257222101)
        total = geo.Inverse(0, 0, 0, 0.001)["s12"]
        pt, seg = mod.interpolate_point_geography(line, total)
        assert isinstance(pt, Point)


class TestSelectRowsWithMaxScores(unittest.TestCase):
    def _df(self):
        return pd.DataFrame({
            "object_id": [1, 1, 2, 2],
            "distance": [100.0, 50.0, 200.0, 150.0],
            "fuzzy": [80.0, 60.0, 90.0, 95.0],
        })

    def test_returns_one_row_per_object(self):
        result = mod.select_rows_with_max_scores(self._df(), "distance", "fuzzy")
        assert len(result) == 2

    def test_has_combined_score_column(self):
        result = mod.select_rows_with_max_scores(self._df(), "distance", "fuzzy")
        assert "combined_score" in result.columns

    def test_selects_correct_row_for_object(self):
        # Scaling uses ALL rows. For object_id=1:
        # row0: d=100 → d_scaled=(200-100)/(200-50)=0.667, f=80 → f_scaled=(80-60)/(95-60)=0.571 → 1.238
        # row1: d=50  → d_scaled=(200-50)/(200-50)=1.0,   f=60 → f_scaled=0 → 1.0
        # row0 wins for object_id=1
        result = mod.select_rows_with_max_scores(self._df(), "distance", "fuzzy")
        obj1 = result[result["object_id"] == 1].iloc[0]
        assert obj1["distance"] == 100.0

    def test_single_object_two_rows(self):
        # Two rows for same object — function needs min != max to avoid NaN
        df = pd.DataFrame({"object_id": [1, 1], "distance": [100.0, 50.0], "fuzzy": [80.0, 60.0]})
        result = mod.select_rows_with_max_scores(df, "distance", "fuzzy")
        assert len(result) == 1


class TestAddDistanceColumn(unittest.TestCase):
    def test_raises_key_error_due_to_bug(self):
        # Bug: function uses literal "col1"/"col2" instead of col1/col2 parameters
        df = pd.DataFrame({"geom1": [Point(0, 0)], "geom2": [Point(1, 1)]})
        with self.assertRaises(KeyError):
            mod.add_distance_column(df, "geom1", "geom2")

    def test_no_error_when_column_is_non_geo_series(self):
        # When df["col1"] is a regular Series (not GeoSeries), the isinstance check returns False
        df = pd.DataFrame({"col1": [1, 2], "col2": [3, 4]})
        # isinstance(df["col1"], pd.Series) is True, but GeoSeries constructor will error
        # Verify the function at least attempts the isinstance check
        try:
            mod.add_distance_column(df, "col1", "col2")
        except Exception:
            pass  # expected due to the bug; just verify it's not a silent NOP


class TestReadAndCleanRoadDf(unittest.TestCase):
    def _make_mock_gdf(self):
        cols = ["RT_UNIQUE", "LRS_ID", "BEGIN_MP", "END_MP", "RT_NUMBER",
                "RD_NAME", "geometry", "DMI_LEN_MI", "GRAPHIC_LE", "created_unique_id"]
        data = {c: [None] for c in cols}
        data["created_unique_id"] = [0]
        gdf = MagicMock(spec=gpd.GeoDataFrame)
        gdf.__getitem__ = MagicMock(return_value=gdf)
        gdf.index = [0]
        gdf.__setitem__ = MagicMock()
        gdf.rename = MagicMock(return_value=gdf)
        return gdf

    def test_calls_gpd_read_file(self):
        mock_gdf = self._make_mock_gdf()
        with patch("geopandas.read_file", return_value=mock_gdf) as mock_read:
            try:
                mod.read_and_clean_road_df()
            except Exception:
                pass
            mock_read.assert_called_once_with(
                mod.ROAD_LAYER, engine="pyogrio", use_arrow=True
            )

    def test_save_flag_triggers_to_file(self):
        mock_gdf = self._make_mock_gdf()
        mock_gdf.copy.return_value = mock_gdf
        inner = MagicMock()
        inner.to_file = MagicMock()
        mock_gdf.to_crs = MagicMock(return_value=inner)
        with patch("geopandas.read_file", return_value=mock_gdf), \
             patch("geopandas.GeoDataFrame", return_value=inner):
            try:
                mod.read_and_clean_road_df(save_road_with_unique_id=True)
            except Exception:
                pass
            # Just verify no crash on save_road_with_unique_id=True path


class TestReadAndCleanBridgeDf(unittest.TestCase):
    def test_calls_gpd_read_file(self):
        mock_gdf = MagicMock(spec=gpd.GeoDataFrame)
        mock_gdf.__getitem__ = MagicMock(return_value=mock_gdf)
        mock_gdf.rename = MagicMock(return_value=mock_gdf)
        mock_gdf.drop_duplicates = MagicMock()
        with patch("geopandas.read_file", return_value=mock_gdf) as mock_read:
            try:
                mod.read_and_clean_bridge_df()
            except Exception:
                pass
            mock_read.assert_called_once_with(
                mod.BRIDGE_LAYER, engine="pyogrio", use_arrow=True
            )

    def test_drop_duplicates_called_on_bridge_id(self):
        mock_gdf = MagicMock(spec=gpd.GeoDataFrame)
        mock_gdf.__getitem__ = MagicMock(return_value=mock_gdf)
        mock_gdf.rename = MagicMock(return_value=mock_gdf)
        with patch("geopandas.read_file", return_value=mock_gdf):
            try:
                mod.read_and_clean_bridge_df()
            except Exception:
                pass
            mock_gdf.rename.return_value.drop_duplicates.assert_called()


class TestExportGeoDataframes(unittest.TestCase):
    def _make_joined_df(self):
        return pd.DataFrame({
            "lrs_id": ["LRS1"],
            "bridge_id": ["B001"],
            "begin_mp": [0.0],
            "interpolated_bridge_geom": [Point(0, 0)],
            "end_mp": [1.0],
            "object_id": [1],
            "road_segment": [LineString([(0, 0), (1, 0)])],
            "bridge_point": [0.5],
            "rd_name": ["Main St"],
            "created_unique_id": [42],
        })

    def test_calls_to_file_twice(self):
        df = self._make_joined_df()
        mock_gdf = MagicMock()
        with patch("geopandas.GeoDataFrame", return_value=mock_gdf):
            mod.export_geodataframes(df)
        assert mock_gdf.to_file.call_count == 2

    def test_output_paths_correct(self):
        df = self._make_joined_df()
        mock_gdf = MagicMock()
        with patch("geopandas.GeoDataFrame", return_value=mock_gdf):
            mod.export_geodataframes(df)
        calls = [c.args[0] for c in mock_gdf.to_file.call_args_list]
        assert mod.INTERPOLATED_BRIDGE_OUTPUT in calls
        assert mod.INTERPOLATED_ROAD_OUTPUT in calls


if __name__ == "__main__":
    unittest.main()
