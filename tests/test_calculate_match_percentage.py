import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np

import calculate_match_percentage as mod


class TestCalculateSimilarityVectorized(unittest.TestCase):
    def _make_df(self):
        return pd.DataFrame({
            "col_a": ["Main Street", "Oak Avenue", None],
            "col_b": ["Main St", "Oak Ave", "Elm Road"],
            "fixed": ["Main Street", "Oak Avenue", "Elm Road"],
        })

    def test_basic_similarity(self):
        df = self._make_df()
        scores, cols = mod.calculate_similarity_vectorized(df, ["col_a", "col_b"], "fixed")
        assert scores[0] == 100  # exact match via col_a
        assert scores[1] > 80   # close match

    def test_nan_values_handled(self):
        df = pd.DataFrame({
            "col_a": [None, None],
            "fixed": ["Test Road", "Other"],
        })
        scores, cols = mod.calculate_similarity_vectorized(df, ["col_a"], "fixed")
        assert all(scores == 0)
        assert all(cols == "")

    def test_missing_fixed_column_raises(self):
        df = pd.DataFrame({"col_a": ["x"]})
        with self.assertRaises(ValueError):
            mod.calculate_similarity_vectorized(df, ["col_a"], "nonexistent")

    def test_col_not_in_df_skipped(self):
        df = pd.DataFrame({
            "col_a": ["Road A"],
            "fixed": ["Road A"],
        })
        scores, cols = mod.calculate_similarity_vectorized(df, ["col_a", "missing_col"], "fixed")
        assert scores[0] == 100

    def test_returns_two_series(self):
        df = pd.DataFrame({"col_a": ["x"], "fixed": ["x"]})
        result = mod.calculate_similarity_vectorized(df, ["col_a"], "fixed")
        assert len(result) == 2

    def test_all_zero_scores_give_empty_col_name(self):
        df = pd.DataFrame({"col_a": [None], "fixed": ["Road"]})
        scores, cols = mod.calculate_similarity_vectorized(df, ["col_a"], "fixed")
        assert cols[0] == ""


class TestReadExplodedOsmDataCsv(unittest.TestCase):
    def test_reads_requested_columns(self):
        mock_df = pd.DataFrame({"osm_id": [1, 2], "name": ["A", "B"]})
        with patch("pandas.read_csv", return_value=mock_df[["osm_id"]]):
            result_df, available_cols = mod.read_exploded_osm_data_csv("fake.csv", ["osm_id"])
        assert "osm_id" in result_df.columns
        assert "osm_id" in available_cols

    def test_empty_data_error_raises(self):
        with patch("pandas.read_csv", side_effect=pd.errors.EmptyDataError):
            with self.assertRaises(pd.errors.EmptyDataError):
                mod.read_exploded_osm_data_csv("fake.csv", ["col"])

    def test_value_error_on_missing_column_raises(self):
        with patch("pandas.read_csv", side_effect=ValueError("col not found")):
            with self.assertRaises(ValueError):
                mod.read_exploded_osm_data_csv("fake.csv", ["missing_col"])


if __name__ == "__main__":
    unittest.main()
