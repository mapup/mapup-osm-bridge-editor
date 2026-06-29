import unittest
from unittest.mock import patch, MagicMock
import pandas as pd

import process_filter_nbi_bridges as mod


class TestExcludeDuplicateBridges(unittest.TestCase):
    def _make_df(self):
        return pd.DataFrame({
            "16 - Latitude (decimal)": [36.5, 36.5, 37.0],
            "17 - Longitude (decimal)": [-89.0, -89.0, -90.0],
            "8 - Structure Number": ["B001", "B002", "B003"],
            "43B - Main Span Design": ["Beam", "Culvert", "Culvert"],
            "41 - Structure Operational Status Code": ["A", "A", "P"],
        })

    def test_removes_duplicate_coordinates(self):
        df = self._make_df()
        with patch("pandas.DataFrame.to_csv"):
            result, stats = mod.exclude_duplicate_bridges(df, "/tmp/out.csv")
        # Row 0 and 1 have same lat/lon — one is dropped
        assert len(result) < 3

    def test_removes_non_posted_culverts(self):
        df = pd.DataFrame({
            "16 - Latitude (decimal)": [36.5, 37.0, 38.0],
            "17 - Longitude (decimal)": [-89.0, -90.0, -91.0],
            "8 - Structure Number": ["B001", "B002", "B003"],
            "43B - Main Span Design": ["Culvert", "Culvert", "Beam"],
            "41 - Structure Operational Status Code": ["A", "P", "A"],
        })
        with patch("pandas.DataFrame.to_csv"):
            result, stats = mod.exclude_duplicate_bridges(df, "/tmp/out.csv")
        structure_numbers = result["8 - Structure Number"].tolist()
        assert "B001" not in structure_numbers  # culvert, not posted
        assert "B002" in structure_numbers      # culvert, posted
        assert "B003" in structure_numbers      # beam

    def test_removes_structure_numbers_with_asterisk(self):
        df = pd.DataFrame({
            "16 - Latitude (decimal)": [36.5, 37.0],
            "17 - Longitude (decimal)": [-89.0, -90.0],
            "8 - Structure Number": ["B*001", "B002"],
            "43B - Main Span Design": ["Beam", "Beam"],
            "41 - Structure Operational Status Code": ["A", "A"],
        })
        with patch("pandas.DataFrame.to_csv"):
            result, stats = mod.exclude_duplicate_bridges(df, "/tmp/out.csv")
        assert "B*001" not in result["8 - Structure Number"].tolist()

    def test_returns_stats_list(self):
        df = self._make_df()
        with patch("pandas.DataFrame.to_csv"):
            _, stats = mod.exclude_duplicate_bridges(df, "/tmp/out.csv")
        assert len(stats) == 3
        assert stats[0] == 3  # total bridges


class TestConvertToGpkg(unittest.TestCase):
    def test_creates_geodataframe_and_saves(self):
        df = pd.DataFrame({
            "17 - Longitude (decimal)": [-89.0, -90.0],
            "16 - Latitude (decimal)": [36.5, 37.0],
            "name": ["A", "B"],
        })
        mock_gdf = MagicMock()
        with patch("geopandas.GeoDataFrame", return_value=mock_gdf):
            mod.convert_to_gpkg(df, "/tmp/test.gpkg")
        mock_gdf.to_file.assert_called_once()


if __name__ == "__main__":
    unittest.main()
