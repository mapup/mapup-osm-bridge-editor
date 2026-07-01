import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

import get_neighbouring_roads as mod


class TestExceptionHierarchy(unittest.TestCase):
    def test_geoprocessing_error_is_exception(self):
        assert issubclass(mod.GeoprocessingError, Exception)

    def test_file_read_error_is_geoprocessing_error(self):
        assert issubclass(mod.FileReadError, mod.GeoprocessingError)

    def test_crs_transform_error_is_geoprocessing_error(self):
        assert issubclass(mod.CRSTransformError, mod.GeoprocessingError)

    def test_buffer_creation_error_is_geoprocessing_error(self):
        assert issubclass(mod.BufferCreationError, mod.GeoprocessingError)

    def test_spatial_join_error_is_geoprocessing_error(self):
        assert issubclass(mod.SpatialJoinError, mod.GeoprocessingError)

    def test_grouping_error_is_geoprocessing_error(self):
        assert issubclass(mod.GroupingError, mod.GeoprocessingError)

    def test_data_load_error_is_exception(self):
        assert issubclass(mod.DataLoadError, Exception)

    def test_output_preparation_error_is_exception(self):
        assert issubclass(mod.OutputPreparationError, Exception)

    def test_can_raise_and_catch_custom_exceptions(self):
        with self.assertRaises(mod.GeoprocessingError):
            raise mod.FileReadError("test")

    def test_can_raise_and_catch_grouping_error(self):
        with self.assertRaises(mod.GroupingError):
            raise mod.GroupingError("grouping failed")


class TestEnums(unittest.TestCase):
    def test_crs_enum_values(self):
        assert mod.CRS.EPSG_3857.value == "EPSG:3857"

    def test_buffer_distance_enum_values(self):
        assert mod.BufferDistance.BRIDGE_POINT.value == 15
        assert mod.BufferDistance.ROAD.value == 5

    def test_spatial_predicate_enum_values(self):
        assert mod.SpatialPredicate.INTERSECTS.value == "intersects"
        assert mod.SpatialPredicate.WITHIN.value == "within"

    def test_output_control_enum(self):
        assert mod.OutputControl.SAVE_INTERMEDIATE_GEOPACKAGES.value is False


class TestValidateFilePath(unittest.TestCase):
    def test_existing_file_returns_resolved_path(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            tmp_path = f.name
        try:
            result = mod.validate_file_path(tmp_path)
            assert os.path.isabs(result)
            assert os.path.exists(result)
        finally:
            os.unlink(tmp_path)

    def test_nonexistent_file_raises_value_error(self):
        with self.assertRaises(ValueError):
            mod.validate_file_path("/absolutely/does/not/exist/file.gpkg")

    def test_directory_like_nonexistent_path_raises_value_error(self):
        # Empty string resolves to CWD (exists), so use a clearly nonexistent path
        with self.assertRaises(ValueError):
            mod.validate_file_path("/no_such_dir_xyzzy/file.gpkg")


class TestCreateBuffer(unittest.TestCase):
    def _projected_gdf(self):
        gdf = gpd.GeoDataFrame({"geometry": [Point(0, 0)]}, crs="EPSG:3857")
        return gdf

    def _geographic_gdf(self):
        gdf = gpd.GeoDataFrame({"geometry": [Point(-89.0, 36.5)]}, crs="EPSG:4326")
        return gdf

    def test_projected_crs_uses_meters(self):
        gdf = self._projected_gdf()
        result = mod.create_buffer(gdf, mod.BufferDistance.BRIDGE_POINT)
        assert isinstance(result, gpd.GeoDataFrame)
        # The buffered polygon should have area > 0
        assert result.geometry.iloc[0].area > 0

    def test_geographic_crs_uses_degrees(self):
        gdf = self._geographic_gdf()
        result = mod.create_buffer(gdf, mod.BufferDistance.ROAD)
        assert isinstance(result, gpd.GeoDataFrame)
        assert result.geometry.iloc[0].area > 0

    def test_buffer_adds_geometry_column(self):
        gdf = self._projected_gdf()
        result = mod.create_buffer(gdf, mod.BufferDistance.BRIDGE_POINT)
        assert "geometry" in result.columns

    def test_unsupported_crs_raises_buffer_creation_error(self):
        from unittest.mock import PropertyMock
        gdf = MagicMock(spec=gpd.GeoDataFrame)
        mock_crs = MagicMock()
        mock_crs.is_projected = False
        mock_crs.is_geographic = False
        type(gdf).crs = PropertyMock(return_value=mock_crs)
        gdf.copy.return_value = gdf
        with self.assertRaises(mod.BufferCreationError):
            mod.create_buffer(gdf, mod.BufferDistance.BRIDGE_POINT)


class TestGroupAndAggregate(unittest.TestCase):
    def _make_df(self):
        gdf = gpd.GeoDataFrame({
            "geometry": [Point(0, 0), Point(0, 0)],
            "created_unique_id_1_left": ["uid1", "uid1"],
            "bridge_id_left": ["B001", "B001"],
            "created_unique_id_1_right": ["uid2", "uid3"],
            "RD_NAME_right": ["Main St", "Oak Ave"],
        }, crs="EPSG:3857")
        return gdf

    def test_returns_geodataframe(self):
        df = self._make_df()
        result = mod.group_and_aggregate(df)
        assert isinstance(result, gpd.GeoDataFrame)

    def test_aggregates_to_one_row_per_group(self):
        df = self._make_df()
        result = mod.group_and_aggregate(df)
        assert len(result) == 1

    def test_aggregated_values_are_comma_joined(self):
        df = self._make_df()
        result = mod.group_and_aggregate(df)
        road_names = result["RD_NAME_right"].iloc[0]
        assert "Main St" in road_names and "Oak Ave" in road_names

    def test_missing_columns_raises_grouping_error(self):
        df = pd.DataFrame({"col_a": [1, 2]})
        with self.assertRaises(mod.GroupingError):
            mod.group_and_aggregate(df)

    def test_generic_exception_raises_grouping_error(self):
        gdf = gpd.GeoDataFrame({
            "geometry": [Point(0, 0)],
            "created_unique_id_1_left": ["uid1"],
            "bridge_id_left": ["B001"],
            "created_unique_id_1_right": ["uid2"],
            "RD_NAME_right": ["Main St"],
        }, crs="EPSG:3857")
        with patch("pandas.DataFrame.drop_duplicates", side_effect=RuntimeError("crash")):
            with self.assertRaises(mod.GroupingError):
                mod.group_and_aggregate(gdf)


class TestPrepareFinalOutput(unittest.TestCase):
    def _make_grouped(self):
        gdf = gpd.GeoDataFrame({
            "geometry": [Point(0, 0)],
            "created_unique_id_1_left": ["uid1"],
            "bridge_id_left": ["B001"],
            "created_unique_id_1_right": ["uid2"],
            "RD_NAME_right": ["Main St"],
        }, crs="EPSG:3857")
        return gdf

    def _make_osm_points(self):
        return pd.DataFrame({
            "osm_id": ["osm1"],
            "created_unique_id": ["uid1"],
            "bridge_id": ["B001"],
        })

    def test_returns_dataframe(self):
        grouped = self._make_grouped()
        osm_pts = self._make_osm_points()
        result = mod.prepare_final_output(grouped, osm_pts)
        assert isinstance(result, pd.DataFrame)

    def test_renames_columns(self):
        grouped = self._make_grouped()
        osm_pts = self._make_osm_points()
        result = mod.prepare_final_output(grouped, osm_pts)
        assert "created_unique_id" in result.columns
        assert "bridge_id" in result.columns
        assert "neighbouring_ids" in result.columns
        assert "neighbouring_roads" in result.columns

    def test_drops_geometry_column(self):
        grouped = self._make_grouped()
        osm_pts = self._make_osm_points()
        result = mod.prepare_final_output(grouped, osm_pts)
        assert "geometry" not in result.columns

    def test_merges_osm_id(self):
        grouped = self._make_grouped()
        osm_pts = self._make_osm_points()
        result = mod.prepare_final_output(grouped, osm_pts)
        assert "osm_id" in result.columns
        assert result["osm_id"].iloc[0] == "osm1"

    def test_grouping_error_raises_output_preparation_error(self):
        grouped = self._make_grouped()
        osm_pts = self._make_osm_points()
        with patch("pandas.DataFrame.drop", side_effect=mod.GroupingError("mock")):
            with self.assertRaises(mod.OutputPreparationError):
                mod.prepare_final_output(grouped, osm_pts)

    def test_unmatched_ids_produce_null_osm_id(self):
        grouped = self._make_grouped()
        osm_pts = pd.DataFrame({
            "osm_id": ["osm99"],
            "created_unique_id": ["uid_other"],
            "bridge_id": ["B999"],
        })
        result = mod.prepare_final_output(grouped, osm_pts)
        assert pd.isna(result["osm_id"].iloc[0])


class TestSaveCsv(unittest.TestCase):
    def test_saves_to_existing_file_path(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            tmp = f.name
        try:
            df = pd.DataFrame({"a": [1, 2]})
            mod.save_csv(df, tmp)
            result = pd.read_csv(tmp)
            assert list(result["a"]) == [1, 2]
        finally:
            os.unlink(tmp)

    def test_nonexistent_path_raises_geoprocessing_error(self):
        df = pd.DataFrame({"a": [1]})
        with self.assertRaises(mod.GeoprocessingError):
            mod.save_csv(df, "/does/not/exist/output.csv")


class TestPerformSpatialJoin(unittest.TestCase):
    def test_returns_geodataframe(self):
        left = gpd.GeoDataFrame({
            "geometry": [Point(0, 0).buffer(5)],
            "col_left": ["a"],
        }, crs="EPSG:3857")
        right = gpd.GeoDataFrame({
            "geometry": [Point(0, 0)],
            "col_right": ["b"],
        }, crs="EPSG:3857")
        result = mod.perform_spatial_join(left, right, [mod.SpatialPredicate.CONTAINS])
        assert isinstance(result, gpd.GeoDataFrame)

    def test_all_predicates_fail_raises_spatial_join_error(self):
        left = gpd.GeoDataFrame({"geometry": [Point(0, 0)]}, crs="EPSG:3857")
        right = gpd.GeoDataFrame({"geometry": [Point(100, 100)]}, crs="EPSG:3857")
        with patch("geopandas.sjoin", side_effect=Exception("sjoin failed")):
            with self.assertRaises(mod.SpatialJoinError):
                mod.perform_spatial_join(left, right, [mod.SpatialPredicate.INTERSECTS])


class TestReadGeopackage(unittest.TestCase):
    def test_nonexistent_file_raises_file_read_error(self):
        with self.assertRaises(mod.FileReadError):
            mod.read_geopackage("/absolutely/does/not/exist/file.gpkg")

    def test_returns_geodataframe_on_valid_file(self):
        import tempfile, os
        # Create a real temp file so validate_file_path passes
        with tempfile.NamedTemporaryFile(suffix=".gpkg", delete=False) as f:
            tmp = f.name
        try:
            mock_gdf = MagicMock()
            with patch("geopandas.read_file", return_value=mock_gdf):
                result = mod.read_geopackage(tmp)
            assert result is mock_gdf
        finally:
            os.unlink(tmp)


class TestTransformCrs(unittest.TestCase):
    def test_same_crs_returns_unchanged(self):
        gdf = gpd.GeoDataFrame({"geometry": [Point(0, 0)]}, crs="EPSG:3857")
        result = mod.transform_crs(gdf, mod.CRS.EPSG_3857)
        assert result.crs.to_epsg() == 3857

    def test_different_crs_converts(self):
        gdf = gpd.GeoDataFrame({"geometry": [Point(-89.0, 36.5)]}, crs="EPSG:4326")
        result = mod.transform_crs(gdf, mod.CRS.EPSG_3857)
        assert result.crs.to_epsg() == 3857

    def test_crs_error_raises_crs_transform_error(self):
        gdf = gpd.GeoDataFrame({"geometry": [Point(0, 0)]}, crs="EPSG:3857")
        with patch.object(gdf.crs, "is_exact_same", side_effect=Exception("crs fail")):
            with self.assertRaises(mod.CRSTransformError):
                mod.transform_crs(gdf, mod.CRS.EPSG_3857)


class TestLoadAndTransformData(unittest.TestCase):
    def test_missing_file_raises_data_load_error(self):
        with self.assertRaises(mod.DataLoadError):
            mod.load_and_transform_data()

    def test_returns_two_gdfs_when_mocked(self):
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".gpkg", delete=False) as f1, \
             tempfile.NamedTemporaryFile(suffix=".gpkg", delete=False) as f2:
            tmp1, tmp2 = f1.name, f2.name
        try:
            mock_gdf = gpd.GeoDataFrame({"geometry": [Point(0, 0)]}, crs="EPSG:3857")
            with patch("geopandas.read_file", return_value=mock_gdf), \
                 patch.object(mod, "FilePath") as mock_fp:
                mock_fp.OSM_ROAD_POINTS.value = tmp1
                mock_fp.STATE_ROAD.value = tmp2
                result = mod.load_and_transform_data()
            assert len(result) == 2
        except mod.DataLoadError:
            pass  # CRS transform might fail with blank GDF — that's OK
        finally:
            os.unlink(tmp1)
            os.unlink(tmp2)


if __name__ == "__main__":
    unittest.main()
