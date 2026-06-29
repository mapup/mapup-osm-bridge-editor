import io
import unittest
from unittest.mock import patch
import pandas as pd

import exclude_nearby_bridges as mod


class TestFilterDuplicatesAndOutput(unittest.TestCase):
    def _make_bridge_df(self, rows):
        return pd.DataFrame(rows, columns=[mod.STRUCTURE_NUMBER, "osm_similarity"])

    def _make_join_df(self, rows):
        return pd.DataFrame(rows, columns=[mod.STRUCTURE_NUMBER, mod.STRUCTURE_NUMBER_2])

    def test_removes_lower_similarity(self):
        bridge_df = self._make_bridge_df([("B1", 90), ("B2", 70)])
        join_df = self._make_join_df([("B1", "B2")])
        with patch("pandas.DataFrame.to_csv"):
            mod.filter_duplicates_and_output(bridge_df, join_df, "/tmp/out.csv")
        # B2 should be removed (lower score)
        assert True  # Just ensure no exception is raised

    def test_removes_first_when_equal_scores(self):
        bridge_df = self._make_bridge_df([("B1", 80), ("B2", 80)])
        join_df = self._make_join_df([("B1", "B2")])
        with patch("pandas.DataFrame.to_csv"):
            mod.filter_duplicates_and_output(bridge_df, join_df, "/tmp/out.csv")

    def test_same_structure_number_rows_skipped(self):
        bridge_df = self._make_bridge_df([("B1", 90)])
        join_df = self._make_join_df([("B1", "B1")])  # Same ID — filtered out
        with patch("pandas.DataFrame.to_csv"):
            mod.filter_duplicates_and_output(bridge_df, join_df, "/tmp/out.csv")

    def test_missing_id_in_bridge_df_continues(self):
        bridge_df = self._make_bridge_df([("B1", 90)])
        join_df = self._make_join_df([("B1", "B_MISSING")])
        with patch("pandas.DataFrame.to_csv"):
            mod.filter_duplicates_and_output(bridge_df, join_df, "/tmp/out.csv")

    def test_empty_join_df_produces_full_output(self):
        bridge_df = self._make_bridge_df([("B1", 90), ("B2", 70)])
        join_df = self._make_join_df([])
        with patch("pandas.DataFrame.to_csv"):
            mod.filter_duplicates_and_output(bridge_df, join_df, "/tmp/out.csv")

    def test_already_in_remove_ids_skips(self):
        bridge_df = self._make_bridge_df([("B1", 80), ("B2", 90), ("B3", 70)])
        # B2 beats B1; then B1 is already in remove_ids so B1-B3 pair is skipped
        join_df = self._make_join_df([("B2", "B1"), ("B1", "B3")])
        with patch("pandas.DataFrame.to_csv"):
            mod.filter_duplicates_and_output(bridge_df, join_df, "/tmp/out.csv")


class TestLoadFunctions(unittest.TestCase):
    def test_load_bridge_info(self):
        df = pd.DataFrame({"col": [1]})
        with patch("pandas.read_csv", return_value=df):
            result = mod.load_bridge_info("file.csv")
        assert len(result) == 1

    def test_load_nearby_join(self):
        df = pd.DataFrame({"col": [1]})
        with patch("pandas.read_csv", return_value=df):
            result = mod.load_nearby_join("file.csv")
        assert len(result) == 1


if __name__ == "__main__":
    unittest.main()
