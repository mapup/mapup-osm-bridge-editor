import unittest
from unittest.mock import patch
import pandas as pd
import geopandas as gpd
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


class TestRun(unittest.TestCase):
    def _make_bridge_gdf(self):
        import geopandas as gpd
        gdf = gpd.GeoDataFrame({
            mod.STRUCTURE_NUMBER: ["  B001  "],
            "geometry": [Point(0, 0)],
        }, crs="EPSG:4326")
        return gdf

    def _make_osm_gdf(self):
        import geopandas as gpd
        gdf = gpd.GeoDataFrame({
            "osm_id": ["123"],
            "geometry": [LineString([(0, 0), (1, 0)])],
        }, crs="EPSG:4326")
        return gdf

    def _make_assoc_df(self):
        return pd.DataFrame({
            mod.STRUCTURE_NUMBER: ["B001"],
            "final_osm_id": [123],
            "osm_name": ["Main St"],
            "final_stream_id": ["S1"],
            "stream_name": ["River"],
            mod.FEATURES_INTERSECTED: ["River"],
            mod.FACILITY_CARRIED: ["US 60"],
            "bridge_length": [32.81],
            "Unique_Bridge_OSM_Combinations": [1],
        })

    def test_run_produces_csv_with_projected_points(self):
        import geopandas as gpd
        bridge_gdf = self._make_bridge_gdf()
        osm_gdf = self._make_osm_gdf()
        assoc_df = self._make_assoc_df()

        bridge_gdf_crs = bridge_gdf.to_crs(epsg=4326)
        osm_gdf_crs = osm_gdf.to_crs(epsg=4326)

        call_count = [0]

        def mock_read_file(path, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return bridge_gdf.copy()
            return osm_gdf.copy()

        with patch("geopandas.read_file", side_effect=mock_read_file), \
             patch("pandas.read_csv", return_value=assoc_df), \
             patch("pandas.DataFrame.to_csv") as mock_save:
            mod.run("bridges.gpkg", "osm.gpkg", "assoc.csv", "out.csv")
        mock_save.assert_called_once()

    def test_run_handles_nan_osm_id_gracefully(self):
        import geopandas as gpd
        bridge_gdf = self._make_bridge_gdf()
        osm_gdf = self._make_osm_gdf()
        # final_osm_id is NaN → falls into ValueError branch
        assoc_df = pd.DataFrame({
            mod.STRUCTURE_NUMBER: ["B001"],
            "final_osm_id": [float("nan")],
            "osm_name": [""],
            "final_stream_id": [""],
            "stream_name": [""],
            mod.FEATURES_INTERSECTED: [""],
            mod.FACILITY_CARRIED: [""],
            "bridge_length": [10.0],
            "Unique_Bridge_OSM_Combinations": [1],
        })

        call_count = [0]

        def mock_read_file(path, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return bridge_gdf.copy()
            return osm_gdf.copy()

        with patch("geopandas.read_file", side_effect=mock_read_file), \
             patch("pandas.read_csv", return_value=assoc_df), \
             patch("pandas.DataFrame.to_csv") as mock_save:
            mod.run("bridges.gpkg", "osm.gpkg", "assoc.csv", "out.csv")
        # NaN osm_id → except branch → projected_long/lat = ""
        mock_save.assert_called_once()

    def test_run_handles_missing_osm_way(self):
        import geopandas as gpd
        bridge_gdf = self._make_bridge_gdf()
        # OSM GDF has no matching osm_id
        osm_gdf = gpd.GeoDataFrame({
            "osm_id": ["999"],
            "geometry": [LineString([(5, 5), (6, 5)])],
        }, crs="EPSG:4326")
        assoc_df = self._make_assoc_df()

        call_count = [0]

        def mock_read_file(path, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return bridge_gdf.copy()
            return osm_gdf.copy()

        with patch("geopandas.read_file", side_effect=mock_read_file), \
             patch("pandas.read_csv", return_value=assoc_df), \
             patch("pandas.DataFrame.to_csv"):
            # IndexError branch when osm_way not found → projected_long/lat = ""
            mod.run("bridges.gpkg", "osm.gpkg", "assoc.csv", "out.csv")


if __name__ == "__main__":
    unittest.main()
