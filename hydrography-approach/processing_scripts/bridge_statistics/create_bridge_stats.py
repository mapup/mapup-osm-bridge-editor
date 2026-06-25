import pandas as pd
import geopandas as gpd
import os
from typing import List,Tuple
import logging

DONE_WITHIN_CODE = "Done within code"

# Set up logging
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_gpkg_length(gpkg_file: str) -> int:
    """
    Reads a GeoPackage file and returns its length.

    Args:
        gpkg_file (str): Path to GeoPackage file to read.

    Returns:
        int: Length of GeoPackage file.

    Raises:
        FileNotFoundError: If the specified file does not exist.
        ValueError: If the file is not a valid GeoPackage file.
    """
    try:
        gdf = gpd.read_file(gpkg_file)
        return len(gdf)
    except FileNotFoundError as e:
        logger.error(f"File {gpkg_file} does not exist: {str(e)}", exc_info=True)
        raise FileNotFoundError(f"File {gpkg_file} does not exist.")
    except ValueError as e:
        logger.error(f"{gpkg_file} is not a valid GeoPackage file: {str(e)}", exc_info=True)
        raise ValueError(f"{gpkg_file} is not a valid GeoPackage file.")
    except Exception as e:
        logger.error(f"Unexpected error while reading GeoPackage file {gpkg_file}: {str(e)}", exc_info=True)
        raise
    

def get_csv_length(csv_file: str) -> int:
    """
    Reads a CSV file and returns its length.

    Args:
        csv_file (str): Path to CSV file to read.

    Returns:
        int: Length of CSV file.

    Raises:
        FileNotFoundError: If the specified file does not exist.
        ValueError: If the file is not a valid CSV file.
    """
    try:
        df_csv = pd.read_csv(csv_file)
        return len(df_csv)
    except FileNotFoundError as e:
        logger.error(f"File {csv_file} does not exist: {str(e)}", exc_info=True)
        raise FileNotFoundError(f"File {csv_file} does not exist.")
    except ValueError as e:
        logger.error(f"{csv_file} is not a valid CSV file: {str(e)}", exc_info=True)
        raise ValueError(f"{csv_file} is not a valid CSV file.")
    except Exception as e:
        logger.error(f"Unexpected error while reading CSV file {csv_file}: {str(e)}", exc_info=True)
        raise
    

def update_stats(stats: pd.DataFrame, description: str, count: int, stats_list: List[int]) -> Tuple[pd.DataFrame, List[int]]:
    """
    Updates the statistics based on the given description and count.

    Args:
        stats (pd.DataFrame): The DataFrame containing the statistics.
        description (str): The description of the statistic to be updated.
        count (int): The count to be appended to the stats list and assigned to the specified description.
        stats_list (List[int]): The list containing the statistics.

    Returns:
        Tuple[pd.DataFrame, List[int]]: The updated statistics DataFrame and the updated statistics list.

    Raises:
        KeyError: If the specified description does not exist in the DataFrame.
    """
    try:
        if not (stats["Description"] == description).any():
            logger.error(f"Description '{description}' does not exist in the DataFrame.", exc_info=True)
            raise KeyError(f"Description '{description}' does not exist in the DataFrame.")
        
        stats_list.append(count)
        stats.loc[stats["Description"] == description, "bridges"] = count
        return stats, stats_list
    except Exception as e:
        logger.error(f"Unexpected error in update_stats: {str(e)}", exc_info=True)
        raise

def calculate_and_update_stats(stats: pd.DataFrame, description: str, base_value: int, stats_list: List[int], length_function, *args) -> Tuple[pd.DataFrame, List[int]]:
    """
    Calculates the statistics based on the base value and the provided length function, then updates the statistics.

    Args:
        stats (pd.DataFrame): The DataFrame containing the statistics.
        description (str): The description of the statistic to be updated.
        base_value (int): The base value used for calculation.
        stats_list (List[int]): The list containing the statistics.
        length_function (callable): The function to get the length for calculation.
        *args: Additional arguments for the length function.

    Returns:
        Tuple[pd.DataFrame, List[int]]: The updated statistics DataFrame and the updated statistics list.
    """
    try:
        value = base_value - sum(stats_list[1:]) - length_function(*args)
        return update_stats(stats, description, value, stats_list)
    except Exception as e:
        logger.error(f"Error calculating and updating stats for {description}: {str(e)}", exc_info=True)
        raise

def create_bridge_statistics(
    bridge_edit_stats: str, state: str, input_csv: str, yes_filter_bridges: str, manmade_filter_bridges: str, parallel_filter_bridges: str, final_bridges: str, final_bridges_csv: str,
    total_bridges: int, overlapping_or_duplicate_coordinates: int, non_posted_culverts: int
) -> None:
    """
    Function to create statistics of the bridges in the NBI data.

    Args:
        bridge_edit_stats (str): The path to the output CSV file.
        state (str): The state for which the statistics are generated.
        input_csv (str): The path to the input CSV file.
        yes_filter_bridges (str): The path to the GeoPackage file.
        parallel_filter_bridges (str): The path to the GeoPackage file.
        final_bridges (str): The path to the GeoPackage file.
        final_bridges_csv (str): The path to the CSV file.
        total_bridges (int): The total number of bridges in the NBI database.
        overlapping_or_duplicate_coordinates (int): The number of bridges with duplicate coordinates.
        non_posted_culverts (int): The number of non-posted culverts.

    Returns:
        None

    Raises:
        FileNotFoundError: If any of the specified files do not exist.
        ValueError: If any of the specified files are not valid CSV files or GeoPackages.

    Function to create statistics of the bridges in the NBI data
    """
    try:
        data = {
                "Description": [
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
                    "Editing: Automated bridge edits"
                ],
                "Data-links": [
                    # "NBI-{{state}}-bridge-data.csv"
                    os.path.split(input_csv)[1],

                    DONE_WITHIN_CODE,
                    DONE_WITHIN_CODE,

                    #"NBI-Filtered-Yes-Manmade-Bridges.gpkg"
                    os.path.split(yes_filter_bridges)[1],

                    "(already filtered as existing bridges)",

                    #"Parallel-Filter-Bridges.gpkg"
                    os.path.split(parallel_filter_bridges)[1],

                    #"{{state}}-Final-NBI-Bridges.gpkg"
                    os.path.split(final_bridges)[1],

                    #"Final-bridges-with-percentage-match.csv"
                    os.path.split(final_bridges_csv)[1],

                    DONE_WITHIN_CODE,
                    DONE_WITHIN_CODE,
                    "merged-approaches-association-output.csv",
                    "merged-approaches-association-output.csv"
                ]
            }
        stats = pd.DataFrame(data)
        stats["bridges"]=0

        stats_list=[]

        #Total bridges in the {state} NBI database.
        stats,stats_list=update_stats(stats,f"Total bridges in the {state} NBI database.", total_bridges,stats_list)
        
        #Not editing: overlapping bridges - bridges with duplicate coordinates
        stats,stats_list=update_stats(stats,"Not editing: overlapping bridges - bridges with duplicate coordinates", overlapping_or_duplicate_coordinates,stats_list)

        #Not editing: Non-posted culverts
        stats,stats_list=update_stats(stats,"Not editing: Non-posted culverts", non_posted_culverts,stats_list)

        #Not editing: Bridges already exist in OSM
        stats, stats_list = calculate_and_update_stats(stats, "Not editing: Bridges already exist in OSM", stats_list[0], stats_list, get_gpkg_length, yes_filter_bridges)

        #Not editing: Bridges near/on freeways
        stats, stats_list = calculate_and_update_stats(stats, "Not editing: Bridges near/on freeways", stats_list[0], stats_list, get_gpkg_length, manmade_filter_bridges)

        #Not editing: Bridges on opposite directions (parallel bridges) at the same location
        stats, stats_list = calculate_and_update_stats(stats, "Not editing: Bridges on opposite directions (parallel bridges) at the same location", stats_list[0], stats_list, get_gpkg_length, parallel_filter_bridges)

        #Not editing: Bridges near tunnel=culvert in OSM
        stats, stats_list = calculate_and_update_stats(stats, "Not editing: Bridges near tunnel=culvert in OSM", stats_list[0], stats_list, get_gpkg_length, final_bridges)

        #Not editing: Nearby bridges
        stats, stats_list = calculate_and_update_stats(stats, "Not editing: Nearby bridges", stats_list[0], stats_list, get_csv_length, final_bridges_csv)

        print(stats)

        #Save stats
        stats.to_csv(bridge_edit_stats, index=False)
    
    except Exception as e:
        logger.error(f"Unexpected error occurred: {str(e)}", exc_info=True)
        raise

