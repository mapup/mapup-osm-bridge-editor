import pandas as pd
import numpy as np
from typing import List, Tuple, Optional
from fuzzywuzzy import fuzz
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Function to calculate similarity
def calculate_similarity_vectorized(df: pd.DataFrame, cols: List[str], fixed_column: str) -> Tuple[pd.Series, pd.Series]:
    """
    Calculate the maximum similarity score between columns and a fixed column using vectorized operations.
    Handles NaN values, empty inputs, and exceptions.

    Parameters:
        df (pandas.DataFrame): The DataFrame containing the data.
        cols (list): A list of column names to compare.
        fixed_column (str): The column name to compare against.

    Returns:
        tuple: A tuple containing two Series: max similarity scores and corresponding column names.
    """
    def vectorized_fuzz(s1: pd.Series, s2: pd.Series) -> pd.Series:
        try:
            mask = s1.notna() & s2.notna()
            result = pd.Series(0, index=s1.index)
            if mask.any():
                result[mask] = np.vectorize(fuzz.token_sort_ratio, otypes=[np.int64])(
                    s1[mask].astype(str), s2[mask].astype(str)
                )
            return result
        except ValueError as e:
            logger.error(f"ValueError in vectorized_fuzz: {str(e)}", exc_info=True)
            raise 
        except TypeError as e:
            logger.error(f"TypeError in vectorized_fuzz: {str(e)}", exc_info=True)
            raise 
        except Exception as e:
            logger.error(f"Unexpected error in vectorized_fuzz: {str(e)}", exc_info=True)
            raise 

    try:
        if fixed_column not in df.columns:
            raise ValueError(f"Fixed column '{fixed_column}' not found in DataFrame")

        similarity_scores = pd.DataFrame(
            {col: vectorized_fuzz(df[col], df[fixed_column]) for col in cols if col in df.columns}
        )
        
        max_scores = similarity_scores.max(axis=1)
        max_cols = similarity_scores.idxmax(axis=1)
        
        # Handle cases where all scores are 0 (i.e., all values were NaN)
        mask_all_zero = (max_scores == 0)
        max_cols = max_cols.where(~mask_all_zero, '')
        
        return max_scores, max_cols
    except KeyError as e:
        logger.error(f"KeyError in calculate_similarity_vectorized: {str(e)}", exc_info=True)
        raise 
    except ValueError as e:
        logger.error(f"ValueError in calculate_similarity_vectorized: {str(e)}", exc_info=True)
        raise 
    except Exception as e:
        logger.error(f"Unexpected error in calculate_similarity_vectorized: {str(e)}", exc_info=True)
        raise 


def read_exploded_osm_data_csv(exploded_osm_data_csv: str, osm_cols_for_road_names: List[str]) -> Tuple[pd.DataFrame, List[str]]:
    """
    Reads the 'exploded_osm_data' CSV file and returns a DataFrame with the required columns.

    Parameters:
        exploded_osm_data_csv (str): The path to the CSV file.
        osm_cols_for_road_names (list): The list of column names to read from the CSV file.

    Returns:
        pandas.DataFrame: The DataFrame containing the required columns.
    """
    series_list=[]
    available_osm_road_names=[]
    for col in osm_cols_for_road_names:
        try:
            series=pd.read_csv(exploded_osm_data_csv,usecols=[col])
            series_list.append(series)
            available_osm_road_names.append(col)
        except pd.errors.EmptyDataError as e:
            logger.error(f"Empty data error when reading CSV: {e}", exc_info=True)
            raise
        except ValueError as e:
            logger.warning(f"Column {col} not found in CSV: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error when reading CSV: {e}", exc_info=True)
            raise
    
    
    try:
        exploded_osm_data_df=pd.concat(series_list,axis=1)
        return exploded_osm_data_df, available_osm_road_names
    except ValueError as e:
        logger.error(f"ValueError when concatenating series: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error when concatenating series: {e}", exc_info=True)
        raise
    

def run(bridge_with_proj_points, bridge_match_percentage,exploded_osm_data_csv):
    """
    Run the main function to calculate similarity scores for bridges.

    Args:
        bridge_with_proj_points (str): The path to the CSV file containing bridge data with projected points.
        bridge_match_percentage (str): The path to save the CSV file with similarity scores.
        exploded_osm_data_csv (str): The path to the CSV file containing exploded OSM data.

    Returns:
        None

    Description:
        This function reads the bridge data with projected points from the specified CSV file. It then reads the exploded OSM data from the specified CSV file and selects the required columns. The function reads the required columns one at a time because the CSV file is too large to read all at once. It merges the bridge data with the exploded OSM data based on the 'final_osm_id' and 'osm_id' columns. It calculates the similarity scores for OSM and NHD data using the specified fixed columns. Finally, it saves the DataFrame with similarity scores to the specified CSV file.

    """
    try:
        df = pd.read_csv(bridge_with_proj_points)

        # Read the 'exploded_osm_data' CSV file and select the required columns
        osm_cols_for_road_names=["osm_id",  "name",  "ref",    "name_1",    "name_2",    "name_3",    "name_5",    "name_4",
                            "name1",    "tiger:name_base_1",    "tiger:name_base_2",    "tiger:name_base_3",
                            "tiger:name_base",    "alt_name",    "name:en",    "official_name",    "bridge:name"]

        # Read only required columns one at a time because the CSV file is too large to read all at once
        exploded_osm_data_df,available_osm_road_names = read_exploded_osm_data_csv(exploded_osm_data_csv, osm_cols_for_road_names)

        df['final_osm_id'] = df['final_osm_id'].astype('object')
        exploded_osm_data_df['osm_id'] = exploded_osm_data_df['osm_id'].astype('object')

        #Merge the data on 'final_osm_id' and 'osm_id'
        df = pd.merge(df, exploded_osm_data_df, left_on='final_osm_id', right_on='osm_id', how='left', validate="many_to_many")

        available_osm_road_names.remove('osm_id')

        #get osm_similarity
        fixed_column_1="7 - Facility Carried By Structure"
        fixed_column_2="6A - Features Intersected"

        # Calculate OSM similarity
        df["osm_similarity"], df["osm_similarity_col"] = calculate_similarity_vectorized(
            df, available_osm_road_names, fixed_column_1
        )
        osm_similarity_2, osm_similarity_col_2 = calculate_similarity_vectorized(
            df, available_osm_road_names, fixed_column_2
        )
        mask = osm_similarity_2 > df["osm_similarity"]
        df.loc[mask, "osm_similarity"] = osm_similarity_2[mask]
        df.loc[mask, "osm_similarity_col"] = osm_similarity_col_2[mask]


        #get nhd_similarity
        nhd_cols_for_stream_name=["stream_name"]
        fixed_column="6A - Features Intersected"
        df["nhd_similarity"], df["nhd_similarity_col"] = calculate_similarity_vectorized(
            df, nhd_cols_for_stream_name, fixed_column
        )

        # Save the DataFrame with similarity scores
        df.to_csv(bridge_match_percentage, index=False)
    
    except Exception as e:
        logger.error(f"Error in run function: {str(e)}", exc_info=True)
        raise
