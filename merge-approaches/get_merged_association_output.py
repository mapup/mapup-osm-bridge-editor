import geopandas as gpd
import pandas as pd
from fuzzywuzzy import fuzz
from typing import Union, Tuple, List
import logging

# Set up logging
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Function to calculate similarity
def calculate_osm_similarity(name: str, target: str) -> float:
    """
    Calculate the similarity between two strings using the token_sort_ratio function from the fuzz library.

    Parameters:
        name (str): The first string to compare.
        target (str): The second string to compare.

    Returns:
        int: The similarity score between the two strings, ranging from 0 to 100.
    """
    try:
        return fuzz.token_sort_ratio(name, target)
    except TypeError as e:
        logger.error(f"TypeError in calculate_osm_similarity: {str(e)}", exc_info=True)
        raise
    except ValueError as e:
        logger.error(f"ValueError in calculate_osm_similarity: {str(e)}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error in calculate_osm_similarity: {str(e)}", exc_info=True)
        raise


def read_geopackage_to_dataframe(filepath: str) -> gpd.GeoDataFrame:
    """
    Read a GeoPackage file into a GeoDataFrame.

    Args:
        filepath (str): Path to the GeoPackage file.

    Returns:
        gpd.GeoDataFrame: The read GeoDataFrame.
    """
    try:
        return gpd.read_file(filepath)
    except FileNotFoundError as e:
        logger.error(f"FileNotFoundError: GeoPackage file not found at {filepath}: {str(e)}", exc_info=True)
        raise
    except PermissionError as e:
        logger.error(f"PermissionError: Unable to access GeoPackage file at {filepath}: {str(e)}", exc_info=True)
        raise
    except gpd.io.file.DriverError as e:
        logger.error(f"DriverError: Unable to read GeoPackage file at {filepath}: {str(e)}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error while reading GeoPackage file at {filepath}: {str(e)}", exc_info=True)
        raise


def extract_coordinates(geom: object) -> Union[Tuple[float, float] , Tuple[None, None]]:
    """
    Extract the coordinates from a geometry object.

    Args:
        geom (object): The geometry object from which to extract the coordinates.

    Returns:
        tuple[float, float] | tuple[None, None]: A tuple containing the x and y coordinates of the geometry object,
        or None if the geometry object is None or NaN.
    """
    # Function to extract coordinates from geometry object
    try:
        if geom is None or pd.isnull(geom):
            return None, None
        else:
            return geom.x, geom.y
    except AttributeError as e:
        logger.error(f"AttributeError in extract_coordinates: Geometry object lacks 'x' or 'y' attribute: {str(e)}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error in extract_coordinates: {str(e)}", exc_info=True)
        raise

def calculate_similarity_for_neighbouring_roads(
    merge_df: pd.DataFrame,
    neighbouring_roads_col: str,
    fixed_cols: List[str],
    column_name_to_store_similarity: str
) -> pd.DataFrame:
    """
    Calculate the similarity between the fixed columns and the neighbouring roads for each row in the merge_df DataFrame.
    
    Parameters:
        merge_df (pandas.DataFrame): The DataFrame containing the merged data.
        neighbouring_roads_col (str): The name of the column in merge_df that contains the neighbouring roads.
        fixed_cols (List[str]): The list of fixed columns to compare with the neighbouring roads.
        neighbouring_roads_similarity_col_name (str): The name of the column to store the similarity score.
    
    Returns:
        pandas.DataFrame: The merge_df DataFrame with the added similarity columns and the dropped similarity columns.
    """
    try:
        if neighbouring_roads_col not in merge_df.columns:
            raise KeyError(f"Column '{neighbouring_roads_col}' not found in DataFrame")
        
        for col in fixed_cols:
            if col not in merge_df.columns:
                raise KeyError(f"Fixed column '{col}' not found in DataFrame")
            
        neighbouring_roads_expanded_df=merge_df[neighbouring_roads_col].str.split(',', expand=True)
        neighbouring_roads_expanded_df=pd.concat([neighbouring_roads_expanded_df, merge_df[fixed_cols]], axis=1)
        
        merge_df[fixed_cols[0]+'_similarity']=neighbouring_roads_expanded_df.apply(lambda x: max([ calculate_osm_similarity(x[col], x[fixed_cols[0]]) for col in neighbouring_roads_expanded_df.columns if col not in fixed_cols]), axis=1)
        merge_df[fixed_cols[1]+'_similarity']=neighbouring_roads_expanded_df.apply(lambda x: max([ calculate_osm_similarity(x[col], x[fixed_cols[1]]) for col in neighbouring_roads_expanded_df.columns if col not in fixed_cols]), axis=1)
        merge_df[column_name_to_store_similarity]=merge_df[[fixed_cols[0]+'_similarity',fixed_cols[1]+'_similarity']].max(axis=1)
        merge_df.drop([fixed_cols[0]+'_similarity',fixed_cols[1]+'_similarity'], axis=1, inplace=True)
        
        return merge_df
    except KeyError as e:
        logger.error(f"KeyError in calculate_similarity_for_neighbouring_roads: {str(e)}", exc_info=True)
        raise
    except ValueError as e:
        logger.error(f"ValueError in calculate_similarity_for_neighbouring_roads: {str(e)}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error in calculate_similarity_for_neighbouring_roads: {str(e)}", exc_info=True)
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



def main():
    try:
        neighbouring_roads_output = "grouped_neighbouring_roads.csv"
        mile_point_output = "osm_road_points.gpkg"
        hydrography_output = "hydrography-method/output-data/csv-files/Final-bridges-with-percentage-match.csv"
        bridge_edit_stats = "hydrography-method/output-data/csv-files/Kentucky-bridge-edit-stats.csv"
        similarity_threshold = 70
        prepare_bridge_stats = True
        
        # Read GeoPackage and CSV into DataFrames
        milepoint_df = read_geopackage_to_dataframe(mile_point_output)
        milepoint_df = milepoint_df.to_crs("EPSG:4326")
        hydrography_df = pd.read_csv(hydrography_output,dtype={"final_osm_id":object})
        neighbouring_roads_df = pd.read_csv(neighbouring_roads_output,dtype={"osm_id":object})

        # Remove the trailing '.0' from the specified column
        hydrography_df['final_osm_id'] = hydrography_df['final_osm_id'].apply(lambda x: str(x).replace('.0', '') if isinstance(x, str) and x.endswith('.0') else x)
        

        # Merge DataFrames and select desired columns
        milepoint_df.rename(columns={"osm_id": "osm_id_mile"}, inplace=True)
        milepoint_cols = ["bridge_id", "osm_id_mile", "name", "geometry"]

        merge_df = pd.merge(
            hydrography_df,
            milepoint_df[milepoint_cols],
            left_on="8 - Structure Number",
            right_on="bridge_id",
            how="left",
            validate="many_to_many",
        )
        merge_df.rename(columns={"osm_similarity": "osm_similarity_hydro"}, inplace=True)
        merge_df.rename(columns={"final_osm_id": "osm_id_hydro"}, inplace=True)
        # merge_df.rename(columns={"osm_id": "osm_id_mile"}, inplace=True)

        # Merge on neighbouring roads
        merge_df = merge_df.merge(
            neighbouring_roads_df,
            left_on=["osm_id_mile","bridge_id"],
            right_on=["osm_id","bridge_id"],
            how="left",
        )

        if prepare_bridge_stats:
            #For final stats, unsnapped are blanks in point geometry
            #merge_df.to_csv("unsnapped.csv",index=False)
            try:
                stats=pd.read_csv(bridge_edit_stats)
                curr_index=stats.loc[stats["Description"] == "Not editing: Unsnapped"].index.values[0]
                stats_list=stats['bridges'].tolist()[:curr_index]
            except FileNotFoundError as e:
                logger.error(f"FileNotFoundError: {str(e)}", exc_info=True)
                raise
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}", exc_info=True)
                raise

            #Not editing: Unsnapped
            unsnapped=(merge_df.geometry.isnull()).sum()
            stats,stats_list=update_stats(stats,"Not editing: Unsnapped", unsnapped,stats_list)


        # Calculate similarity for neighbouring roads
        neighbouring_roads_col='neighbouring_roads'
        fixed_cols=['7 - Facility Carried By Structure','6A - Features Intersected']
        column_name_to_store_similarity="neighbouring_roads_similarity"
        merge_df=calculate_similarity_for_neighbouring_roads(merge_df, neighbouring_roads_col, fixed_cols,column_name_to_store_similarity)

        #Get max similarity between osm road names and neighbouring roads names
        merge_df['combined_max_similarity']=merge_df[['neighbouring_roads_similarity','osm_similarity_hydro']].max(axis=1)
        merge_df['combined_max_similarity_col']=merge_df['osm_similarity_col']
        merge_df.loc[merge_df['osm_similarity_hydro'] < merge_df['neighbouring_roads_similarity'],['combined_max_similarity_col']]="neighbouring_roads"

        # Extract coordinates from geometry
        merge_df["projected_long_mile"], merge_df["projected_lat_mile"] = zip(
            *merge_df["geometry"].apply(extract_coordinates)
        )

        #Save data where hydro osm id and milepoint osm id are same
        merge_df=merge_df[merge_df['osm_id_mile']==merge_df['osm_id_hydro']]

        #removing null geometry
        merge_df=merge_df[~merge_df['geometry'].isnull()]

        if prepare_bridge_stats:
            #Not editing: Different OSM NBI association in both approaches
            different_osm_ids_in_both_approaches=stats_list[0]-sum(stats_list[1:])-len(merge_df)
            stats,stats_list=update_stats(stats,"Not editing: Different OSM NBI association in both approaches", different_osm_ids_in_both_approaches,stats_list)

        #Automated and Maproulette edits 
        merge_df['osm_edits']="Automated"
        mask=(merge_df["Unique_Bridge_OSM_Combinations"] > 1 ) & ( merge_df["combined_max_similarity"]<similarity_threshold)
        merge_df.loc[mask,"osm_edits"]="Maproulette"

        if prepare_bridge_stats:
            #Not editing: MapRoulette bridges [(Multiple OSM ways within 30m bridge buffer) and (OSM road match % < 70)
            maproulette_edits=len(merge_df[mask])
            stats,stats_list=update_stats(stats,"Not editing: MapRoulette bridges [(Multiple OSM ways within 30m bridge buffer) and (OSM road match % < 70)]", maproulette_edits,stats_list)


        # Select desired columns for output
        keep_cols = ['8 - Structure Number', 'osm_id_hydro', 'osm_name', 'final_stream_id', 'stream_name', '6A - Features Intersected', '7 - Facility Carried By Structure', 'bridge_length', 'Unique_Bridge_OSM_Combinations', 'combined_max_similarity', 'projected_long_mile', 'projected_lat_mile', 'osm_edits']
        merge_df=merge_df[keep_cols]
        merge_df.rename(columns={"osm_id_hydro": "osm_id"}, inplace=True)

        if prepare_bridge_stats:
            #Editing: Automated bridge edits
            stats,stats_list=update_stats(stats,"Editing: Automated bridge edits", stats_list[0]-sum(stats_list[1:]),stats_list)

            #save stats
            stats.to_csv(bridge_edit_stats, index=False)
            print(stats)

        merge_df.to_csv("merged-approaches-association-output.csv", index=False)
            
    except Exception as e:
        logger.error(f"Unexpected error occurred: {str(e)}", exc_info=True)
        raise 

if __name__ == "__main__":
    main()
