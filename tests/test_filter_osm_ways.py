import subprocess
import unittest
from unittest.mock import patch, call, MagicMock

import filter_osm_ways as mod


class TestFilterOsmPbf(unittest.TestCase):
    def test_calls_subprocess_with_correct_args(self):
        with patch("subprocess.run") as mock_run:
            mod.filter_osm_pbf("input.osm.pbf", "output.osm.pbf", ["w/highway=motorway"])
        mock_run.assert_called_once_with(
            ["osmium", "tags-filter", "input.osm.pbf", "w/highway=motorway", "-o", "output.osm.pbf"],
            check=True,
        )

    def test_multiple_filters_passed_as_list(self):
        filters = ["w/highway=motorway", "w/highway=trunk"]
        with patch("subprocess.run") as mock_run:
            mod.filter_osm_pbf("in.pbf", "out.pbf", filters)
        cmd = mock_run.call_args[0][0]
        assert "w/highway=motorway" in cmd
        assert "w/highway=trunk" in cmd

    def test_check_true_propagates_subprocess_error(self):
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "osmium")):
            with self.assertRaises(subprocess.CalledProcessError):
                mod.filter_osm_pbf("in.pbf", "out.pbf", [])

    def test_empty_filters_produces_minimal_command(self):
        with patch("subprocess.run") as mock_run:
            mod.filter_osm_pbf("in.pbf", "out.pbf", [])
        cmd = mock_run.call_args[0][0]
        assert cmd == ["osmium", "tags-filter", "in.pbf", "-o", "out.pbf"]


class TestConvertToGeopackage(unittest.TestCase):
    def test_calls_ogr2ogr_with_correct_args(self):
        with patch("subprocess.run") as mock_run:
            mod.convert_to_geopackage("filtered.osm.pbf", "output.gpkg")
        mock_run.assert_called_once_with(
            ["ogr2ogr", "-f", "GPKG", "output.gpkg", "filtered.osm.pbf"],
            check=True,
        )

    def test_check_true_propagates_ogr2ogr_error(self):
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "ogr2ogr")):
            with self.assertRaises(subprocess.CalledProcessError):
                mod.convert_to_geopackage("in.pbf", "out.gpkg")


class TestFilterWays(unittest.TestCase):
    def test_calls_both_subprocesses(self):
        with patch("subprocess.run") as mock_run:
            mod.filter_ways("in.pbf", "filtered.pbf", "out.gpkg")
        assert mock_run.call_count == 2

    def test_first_call_is_osmium(self):
        with patch("subprocess.run") as mock_run:
            mod.filter_ways("in.pbf", "filtered.pbf", "out.gpkg")
        first_cmd = mock_run.call_args_list[0][0][0]
        assert first_cmd[0] == "osmium"

    def test_second_call_is_ogr2ogr(self):
        with patch("subprocess.run") as mock_run:
            mod.filter_ways("in.pbf", "filtered.pbf", "out.gpkg")
        second_cmd = mock_run.call_args_list[1][0][0]
        assert second_cmd[0] == "ogr2ogr"

    def test_16_highway_types_in_filters(self):
        captured_filters = []

        def capture(cmd, **kwargs):
            if cmd[0] == "osmium":
                # filters are everything between the input file and -o
                in_idx = cmd.index("in.pbf")
                o_idx = cmd.index("-o")
                captured_filters.extend(cmd[in_idx + 1:o_idx])

        with patch("subprocess.run", side_effect=capture):
            mod.filter_ways("in.pbf", "filtered.pbf", "out.gpkg")
        assert len(captured_filters) == 16

    def test_includes_motorway_and_residential(self):
        captured_filters = []

        def capture(cmd, **kwargs):
            if cmd[0] == "osmium":
                in_idx = cmd.index("in.pbf")
                o_idx = cmd.index("-o")
                captured_filters.extend(cmd[in_idx + 1:o_idx])

        with patch("subprocess.run", side_effect=capture):
            mod.filter_ways("in.pbf", "filtered.pbf", "out.gpkg")
        assert "w/highway=motorway" in captured_filters
        assert "w/highway=residential" in captured_filters

    def test_output_gpkg_is_correct_file(self):
        with patch("subprocess.run") as mock_run:
            mod.filter_ways("in.pbf", "filtered.pbf", "my_output.gpkg")
        second_cmd = mock_run.call_args_list[1][0][0]
        assert "my_output.gpkg" in second_cmd

    def test_prints_success_message(self):
        with patch("subprocess.run"), patch("builtins.print") as mock_print:
            mod.filter_ways("in.pbf", "filtered.pbf", "out.gpkg")
        mock_print.assert_called_once()
        assert "out.gpkg" in mock_print.call_args[0][0]


if __name__ == "__main__":
    unittest.main()
