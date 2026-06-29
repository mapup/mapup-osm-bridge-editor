import unittest
from unittest.mock import MagicMock, patch
import pandas as pd

import get_merged_association_output as mod


class TestCalculateOsmSimilarity(unittest.TestCase):
    def test_identical_strings(self):
        score = mod.calculate_osm_similarity("Main Street", "Main Street")
        assert score == 100

    def test_different_strings(self):
        score = mod.calculate_osm_similarity("Main Street", "Oak Avenue")
        assert score < 100

    def test_empty_strings(self):
        score = mod.calculate_osm_similarity("", "")
        assert score == 100

    def test_token_order_independent(self):
        s1 = mod.calculate_osm_similarity("Street Main", "Main Street")
        assert s1 == 100

    def test_returns_int_like(self):
        result = mod.calculate_osm_similarity("A", "B")
        assert isinstance(result, (int, float))


class TestExtractCoordinates(unittest.TestCase):
    def test_none_returns_none_none(self):
        x, y = mod.extract_coordinates(None)
        assert x is None and y is None

    def test_nan_returns_none_none(self):
        x, y = mod.extract_coordinates(float("nan"))
        assert x is None and y is None

    def test_valid_geometry(self):
        geom = MagicMock()
        geom.__bool__ = lambda self: True
        geom.x = 10.0
        geom.y = 20.0
        with patch("pandas.isnull", return_value=False):
            x, y = mod.extract_coordinates(geom)
        assert x == 10.0 and y == 20.0

    def test_geometry_without_xy_raises(self):
        class BadGeom:
            pass  # no x/y attribute

        with patch("pandas.isnull", return_value=False):
            with self.assertRaises(AttributeError):
                mod.extract_coordinates(BadGeom())


class TestUpdateStats(unittest.TestCase):
    def _make_stats(self):
        return pd.DataFrame({
            "Description": ["Step A", "Step B"],
            "bridges": [0, 0],
        })

    def test_updates_value(self):
        stats = self._make_stats()
        updated, lst = mod.update_stats(stats, "Step A", 42, [])
        assert updated.loc[updated["Description"] == "Step A", "bridges"].values[0] == 42
        assert 42 in lst

    def test_unknown_description_raises_key_error(self):
        stats = self._make_stats()
        with self.assertRaises(KeyError):
            mod.update_stats(stats, "Unknown step", 5, [])


class TestCalculateSimilarityForNeighbouringRoads(unittest.TestCase):
    def test_basic_similarity_computed(self):
        df = pd.DataFrame({
            "neighbouring_roads": ["Main St,Oak Ave"],
            "col1": ["Main Street"],
            "col2": ["Oak Avenue"],
        })
        result = mod.calculate_similarity_for_neighbouring_roads(
            df, "neighbouring_roads", ["col1", "col2"], "neighbour_similarity"
        )
        assert "neighbour_similarity" in result.columns
        assert result["neighbour_similarity"].iloc[0] > 0

    def test_missing_neighbouring_roads_col_raises(self):
        df = pd.DataFrame({"col1": ["x"], "col2": ["y"]})
        with self.assertRaises(KeyError):
            mod.calculate_similarity_for_neighbouring_roads(
                df, "nonexistent", ["col1", "col2"], "sim"
            )

    def test_missing_fixed_col_raises(self):
        df = pd.DataFrame({"neighbouring_roads": ["A,B"]})
        with self.assertRaises(KeyError):
            mod.calculate_similarity_for_neighbouring_roads(
                df, "neighbouring_roads", ["missing_col", "also_missing"], "sim"
            )


class TestReadGeopackageToDataframe(unittest.TestCase):
    def test_file_not_found_raises(self):
        with patch("geopandas.read_file", side_effect=FileNotFoundError):
            with self.assertRaises(FileNotFoundError):
                mod.read_geopackage_to_dataframe("missing.gpkg")

    def test_returns_geodataframe(self):
        mock_gdf = MagicMock()
        with patch("geopandas.read_file", return_value=mock_gdf):
            result = mod.read_geopackage_to_dataframe("file.gpkg")
        assert result is mock_gdf


if __name__ == "__main__":
    unittest.main()
