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


class TestCalculateSimilarityVectorizedExceptions(unittest.TestCase):
    def test_value_error_in_fuzz_propagates(self):
        df = pd.DataFrame({"col_a": ["x", "y"], "fixed": ["x", "y"]})
        with patch("fuzzywuzzy.fuzz.token_sort_ratio", side_effect=ValueError("bad")):
            with self.assertRaises(ValueError):
                mod.calculate_similarity_vectorized(df, ["col_a"], "fixed")

    def test_type_error_in_fuzz_propagates(self):
        df = pd.DataFrame({"col_a": ["x", "y"], "fixed": ["x", "y"]})
        with patch("fuzzywuzzy.fuzz.token_sort_ratio", side_effect=TypeError("bad type")):
            with self.assertRaises(TypeError):
                mod.calculate_similarity_vectorized(df, ["col_a"], "fixed")

    def test_generic_exception_in_outer_propagates(self):
        df = pd.DataFrame({"col_a": ["x"], "fixed": ["x"]})
        with patch("fuzzywuzzy.fuzz.token_sort_ratio", side_effect=RuntimeError("crash")):
            with self.assertRaises(RuntimeError):
                mod.calculate_similarity_vectorized(df, ["col_a"], "fixed")


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

    def test_generic_exception_in_read_csv_raises(self):
        with patch("pandas.read_csv", side_effect=RuntimeError("io crash")):
            with self.assertRaises(RuntimeError):
                mod.read_exploded_osm_data_csv("fake.csv", ["col"])

    def test_concat_value_error_raises(self):
        with patch("pandas.read_csv", return_value=pd.DataFrame({"col": [1]})), \
             patch("pandas.concat", side_effect=ValueError("no objects")):
            with self.assertRaises(ValueError):
                mod.read_exploded_osm_data_csv("fake.csv", ["col"])

    def test_concat_generic_exception_raises(self):
        with patch("pandas.read_csv", return_value=pd.DataFrame({"col": [1]})), \
             patch("pandas.concat", side_effect=RuntimeError("concat crash")):
            with self.assertRaises(RuntimeError):
                mod.read_exploded_osm_data_csv("fake.csv", ["col"])

    def test_multiple_columns_concatenated(self):
        def side_effect(path, usecols):
            col = usecols[0]
            return pd.DataFrame({col: [1, 2]})

        with patch("pandas.read_csv", side_effect=side_effect):
            df, cols = mod.read_exploded_osm_data_csv("fake.csv", ["osm_id", "name"])
        assert "osm_id" in df.columns
        assert "name" in df.columns
        assert cols == ["osm_id", "name"]


class TestRun(unittest.TestCase):
    def _bridge_df(self):
        return pd.DataFrame({
            "final_osm_id": ["123"],
            "7 - Facility Carried By Structure": ["Main Street"],
            "6A - Features Intersected": ["River"],
            "stream_name": ["Creek"],
        })

    def _osm_df(self):
        return pd.DataFrame({"osm_id": ["123"], "name": ["Main St"]})

    def test_run_produces_output_csv(self):
        bridge_df = self._bridge_df()
        osm_df = self._osm_df()

        def mock_read_csv(path, *args, **kwargs):
            usecols = kwargs.get("usecols")
            if usecols:
                col = usecols[0]
                if col == "osm_id":
                    return pd.DataFrame({"osm_id": ["123"]})
                elif col == "name":
                    return pd.DataFrame({"name": ["Main St"]})
                return pd.DataFrame({col: [None]})
            return bridge_df

        with patch("pandas.read_csv", side_effect=mock_read_csv), \
             patch("pandas.DataFrame.to_csv") as mock_save:
            mod.run("bridge.csv", "out.csv", "osm.csv")
        mock_save.assert_called_once()

    def test_run_exception_propagates(self):
        with patch("pandas.read_csv", side_effect=Exception("disk error")):
            with self.assertRaises(Exception):
                mod.run("bridge.csv", "out.csv", "osm.csv")


if __name__ == "__main__":
    unittest.main()
