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


if __name__ == "__main__":
    unittest.main()
