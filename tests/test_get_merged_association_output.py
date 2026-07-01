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

    def test_permission_error_raises(self):
        with patch("geopandas.read_file", side_effect=PermissionError):
            with self.assertRaises(PermissionError):
                mod.read_geopackage_to_dataframe("locked.gpkg")

    def test_generic_exception_raises(self):
        # gpd.io.file.DriverError may not exist in all geopandas versions;
        # a non-file/permission error will either be caught by the generic handler or propagate
        with patch("geopandas.read_file", side_effect=OSError("unexpected")):
            with self.assertRaises((OSError, AttributeError)):
                mod.read_geopackage_to_dataframe("bad.gpkg")


class TestCalculateOsmSimilarityExceptions(unittest.TestCase):
    def test_type_error_propagates(self):
        with patch("fuzzywuzzy.fuzz.token_sort_ratio", side_effect=TypeError("bad type")):
            with self.assertRaises(TypeError):
                mod.calculate_osm_similarity("a", "b")

    def test_value_error_propagates(self):
        with patch("fuzzywuzzy.fuzz.token_sort_ratio", side_effect=ValueError("bad val")):
            with self.assertRaises(ValueError):
                mod.calculate_osm_similarity("a", "b")

    def test_generic_exception_propagates(self):
        with patch("fuzzywuzzy.fuzz.token_sort_ratio", side_effect=RuntimeError("crash")):
            with self.assertRaises(RuntimeError):
                mod.calculate_osm_similarity("a", "b")


class TestExtractCoordinatesExceptions(unittest.TestCase):
    def test_generic_exception_propagates(self):
        class BadGeom:
            @property
            def x(self):
                raise RuntimeError("corrupt geometry")
            @property
            def y(self):
                raise RuntimeError("corrupt geometry")

        with patch("pandas.isnull", return_value=False):
            with self.assertRaises((RuntimeError, AttributeError)):
                mod.extract_coordinates(BadGeom())


class TestCalculateSimilarityForNeighbouringRoadsExceptions(unittest.TestCase):
    def _make_df(self):
        return pd.DataFrame({
            "neighbouring_roads": ["A,B"],
            "col1": ["x"],
            "col2": ["y"],
        })

    def test_value_error_raises(self):
        df = self._make_df()
        with patch("pandas.concat", side_effect=ValueError("concat error")):
            with self.assertRaises(ValueError):
                mod.calculate_similarity_for_neighbouring_roads(
                    df, "neighbouring_roads", ["col1", "col2"], "sim"
                )

    def test_generic_exception_raises(self):
        df = self._make_df()
        with patch("pandas.concat", side_effect=RuntimeError("crash")):
            with self.assertRaises(RuntimeError):
                mod.calculate_similarity_for_neighbouring_roads(
                    df, "neighbouring_roads", ["col1", "col2"], "sim"
                )


class TestMain(unittest.TestCase):
    def _milepoint_gdf(self):
        import geopandas as gpd
        from shapely.geometry import Point
        return gpd.GeoDataFrame({
            "osm_id": ["123"],
            "bridge_id": ["B001"],
            "name": ["Main St"],
            "geometry": [Point(-85.0, 37.5)],
        }, crs="EPSG:4326")

    def _hydro_df(self):
        return pd.DataFrame({
            "final_osm_id": ["123"],
            "8 - Structure Number": ["B001"],
            "osm_similarity": [80],
            "osm_similarity_col": ["name"],
            "Unique_Bridge_OSM_Combinations": [1],
            "6A - Features Intersected": ["River"],
            "7 - Facility Carried By Structure": ["Main Street"],
            "bridge_length": [30.0],
            "osm_name": ["Main St"],
            "final_stream_id": ["S001"],
            "stream_name": ["Big Creek"],
        })

    def _neighbours_df(self):
        return pd.DataFrame({
            "osm_id": ["123"],
            "bridge_id": ["B001"],
            "neighbouring_roads": ["Main St,Oak Ave"],
        })

    def _stats_df(self):
        return pd.DataFrame({
            "Description": [
                "Not editing: Unsnapped",
                "Not editing: Different OSM NBI association in both approaches",
                "Not editing: MapRoulette bridges [(Multiple OSM ways within 30m bridge buffer) and (OSM road match % < 70)]",
                "Editing: Automated bridge edits",
            ],
            "bridges": [10, 0, 0, 0],
        })

    def test_main_happy_path(self):
        csv_responses = [self._hydro_df(), self._neighbours_df(), self._stats_df()]
        call_idx = [0]

        def mock_read_csv(path, **kwargs):
            r = csv_responses[call_idx[0]]
            call_idx[0] += 1
            return r

        def sim_side_effect(df, *args, **kwargs):
            df = df.copy()
            df["neighbouring_roads_similarity"] = 75
            return df

        def update_side_effect(stats, desc, val, lst):
            lst = list(lst) + [val]
            return stats, lst

        with patch.object(mod, "read_geopackage_to_dataframe", return_value=self._milepoint_gdf()), \
             patch("pandas.read_csv", side_effect=mock_read_csv), \
             patch.object(mod, "calculate_similarity_for_neighbouring_roads", side_effect=sim_side_effect), \
             patch.object(mod, "update_stats", side_effect=update_side_effect), \
             patch("pandas.DataFrame.to_csv"):
            mod.main()

    def test_main_raises_on_read_failure(self):
        with patch.object(mod, "read_geopackage_to_dataframe", side_effect=FileNotFoundError("no file")):
            with self.assertRaises(Exception):
                mod.main()

    def test_main_raises_on_csv_read_failure(self):
        with patch.object(mod, "read_geopackage_to_dataframe", return_value=self._milepoint_gdf()), \
             patch("pandas.read_csv", side_effect=FileNotFoundError("missing csv")):
            with self.assertRaises(Exception):
                mod.main()


if __name__ == "__main__":
    unittest.main()
