import unittest
from unittest.mock import patch, MagicMock
import pandas as pd

import create_bridge_stats as mod


def _make_stats():
    return pd.DataFrame({
        "Description": ["Total bridges", "Filtered bridges", "Final bridges"],
        "bridges": [0, 0, 0],
    })


class TestUpdateStats(unittest.TestCase):
    def test_updates_existing_description(self):
        stats = _make_stats()
        updated, lst = mod.update_stats(stats, "Total bridges", 100, [])
        assert updated.loc[updated["Description"] == "Total bridges", "bridges"].values[0] == 100
        assert lst == [100]

    def test_appends_to_stats_list(self):
        stats = _make_stats()
        _, lst = mod.update_stats(stats, "Filtered bridges", 50, [100])
        assert lst == [100, 50]

    def test_missing_description_raises_key_error(self):
        stats = _make_stats()
        with self.assertRaises(KeyError):
            mod.update_stats(stats, "Nonexistent description", 10, [])


class TestCalculateAndUpdateStats(unittest.TestCase):
    def test_subtracts_sum_and_length(self):
        stats = _make_stats()
        length_fn = lambda: 30
        updated, lst = mod.calculate_and_update_stats(
            stats, "Filtered bridges", 100, [100], length_fn
        )
        # value = 100 - sum([100][1:]) - 30 = 100 - 0 - 30 = 70
        assert updated.loc[updated["Description"] == "Filtered bridges", "bridges"].values[0] == 70
        assert 70 in lst

    def test_propagates_exception_from_update_stats(self):
        stats = _make_stats()
        with self.assertRaises(KeyError):
            mod.calculate_and_update_stats(stats, "Bad description", 100, [], lambda: 0)


class TestGetCsvLength(unittest.TestCase):
    def test_returns_row_count(self):
        df = pd.DataFrame({"a": [1, 2, 3]})
        with patch("pandas.read_csv", return_value=df):
            assert mod.get_csv_length("fake.csv") == 3

    def test_file_not_found_raises(self):
        with patch("pandas.read_csv", side_effect=FileNotFoundError):
            with self.assertRaises(FileNotFoundError):
                mod.get_csv_length("missing.csv")

    def test_invalid_csv_raises_value_error(self):
        with patch("pandas.read_csv", side_effect=ValueError("bad csv")):
            with self.assertRaises(ValueError):
                mod.get_csv_length("bad.csv")


class TestGetGpkgLength(unittest.TestCase):
    def test_returns_row_count(self):
        mock_gdf = MagicMock()
        mock_gdf.__len__ = lambda self: 5
        with patch("geopandas.read_file", return_value=mock_gdf):
            assert mod.get_gpkg_length("fake.gpkg") == 5

    def test_file_not_found_raises(self):
        with patch("geopandas.read_file", side_effect=FileNotFoundError):
            with self.assertRaises(FileNotFoundError):
                mod.get_gpkg_length("missing.gpkg")

    def test_value_error_raises(self):
        with patch("geopandas.read_file", side_effect=ValueError("not a gpkg")):
            with self.assertRaises(ValueError):
                mod.get_gpkg_length("bad.gpkg")

    def test_generic_exception_raises(self):
        with patch("geopandas.read_file", side_effect=RuntimeError("unexpected")):
            with self.assertRaises(RuntimeError):
                mod.get_gpkg_length("bad.gpkg")


class TestGetCsvLengthException(unittest.TestCase):
    def test_generic_exception_raises(self):
        with patch("pandas.read_csv", side_effect=RuntimeError("io error")):
            with self.assertRaises(RuntimeError):
                mod.get_csv_length("bad.csv")


class TestCreateBridgeStatistics(unittest.TestCase):
    def _descriptions(self, state="Kentucky"):
        return [
            f"Total bridges in the {state} NBI database.",
            "Not editing: overlapping bridges - bridges with duplicate coordinates",
            "Not editing: Non-posted culverts",
            "Not editing: Bridges already exist in OSM",
            "Not editing: Bridges near/on freeways",
            "Not editing: Bridges on opposite directions (parallel bridges) at the same location",
            "Not editing: Bridges near tunnel=culvert in OSM",
            "Not editing: Nearby bridges",
            "Not editing: Unsnapped",
            "Not editing: Different OSM NBI association in both approaches",
            "Not editing: MapRoulette bridges [(Multiple OSM ways within 30m bridge buffer) and (OSM road match % < 70)]",
            "Editing: Automated bridge edits",
        ]

    def test_creates_stats_csv(self):
        mock_gdf = MagicMock()
        mock_gdf.__len__ = lambda self: 10
        mock_df = pd.DataFrame({"a": [1] * 10})

        with patch("geopandas.read_file", return_value=mock_gdf), \
             patch("pandas.read_csv", return_value=mock_df), \
             patch("pandas.DataFrame.to_csv") as mock_save, \
             patch("builtins.print"):
            mod.create_bridge_statistics(
                bridge_edit_stats="stats.csv",
                state="Kentucky",
                input_csv="bridges.csv",
                yes_filter_bridges="yes.gpkg",
                manmade_filter_bridges="manmade.gpkg",
                parallel_filter_bridges="parallel.gpkg",
                final_bridges="final.gpkg",
                final_bridges_csv="final.csv",
                total_bridges=100,
                overlapping_or_duplicate_coordinates=5,
                non_posted_culverts=3,
            )
        mock_save.assert_called_once()

    def test_raises_on_file_not_found(self):
        with patch("geopandas.read_file", side_effect=FileNotFoundError("missing")):
            with self.assertRaises(Exception):
                mod.create_bridge_statistics(
                    bridge_edit_stats="stats.csv",
                    state="KY",
                    input_csv="bridges.csv",
                    yes_filter_bridges="yes.gpkg",
                    manmade_filter_bridges="manmade.gpkg",
                    parallel_filter_bridges="parallel.gpkg",
                    final_bridges="final.gpkg",
                    final_bridges_csv="final.csv",
                    total_bridges=100,
                    overlapping_or_duplicate_coordinates=5,
                    non_posted_culverts=3,
                )


if __name__ == "__main__":
    unittest.main()
