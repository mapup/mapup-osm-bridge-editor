
import geopandas as gpd
import pandas as pd
from enum import Enum
from typing import List,Dict,Tuple
import logging
import pyproj
import fiona
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CRS(Enum):
    """Enum for Coordinate Reference Systems."""
    EPSG_3857 = "EPSG:3857"

class BufferDistance(Enum):
    """Enum for buffer distances."""
    BRIDGE_POINT = 15
    ROAD = 5

class FilePath(Enum):
    """Enum for file paths."""
    OSM_ROAD_POINTS = "osm_road_points.gpkg"
    STATE_ROAD = "ky_roads_with_unique_id.gpkg"

class SpatialPredicate(Enum):
    """Enum for spatial join predicates."""
    INTERSECTS = "intersects"
    OVERLAPS = "overlaps"
    CONTAINS = "contains"
    WITHIN = "within"

class OutputControl(Enum):
    """Enum for output control flags."""
    SAVE_INTERMEDIATE_GEOPACKAGES = False

class GeoprocessingError(Exception):
    """Custom exception for geoprocessing errors."""
    pass

class FileReadError(GeoprocessingError):
    """Exception raised when there's an error reading a file."""
    pass

class CRSTransformError(GeoprocessingError):
    """Exception raised when there's an error transforming CRS."""
    pass

class BufferCreationError(GeoprocessingError):
    """Exception raised when there's an error creating a buffer."""
    pass

class SpatialJoinError(GeoprocessingError):
    """Exception raised when there's an error performing a spatial join."""
    pass

class GroupingError(GeoprocessingError):
    """Exception raised when there's an error during the grouping operation."""
    pass

class DataLoadError(Exception):
    """Exception raised when there's an error loading data."""
    pass

class OutputPreparationError(Exception):
    """Exception raised when there's an error preparing the output."""
    pass

def validate_file_path(file_path: str) -> str:
    """
    Validate a file path for security and existence.

    Args:
        file_path (str): The file path to validate.

    Returns:
        str: The validated absolute file path.

    Raises:
        ValueError: If the file path is invalid or doesn't meet the existence requirement.
    """
    try:
        path = Path(file_path).resolve()
        if not path.exists():
            raise ValueError(f"File does not exist: {path}")
        return str(path)
    except Exception as e:
        logger.error(f"Error validating file path {file_path}: {str(e)}")
        raise ValueError(f"Invalid file path: {file_path}") from e
    
def read_geopackage(file_path: str) -> gpd.GeoDataFrame:
    """
    Read a GeoPackage file and return a GeoDataFrame.

    Args:
        file_path (str): Path to the GeoPackage file.

    Returns:
        gpd.GeoDataFrame: The read GeoDataFrame.

    Raises:
        FileReadError: If there's an error reading the file.
    """
    try:
        file_path=validate_file_path(file_path)
        return gpd.read_file(file_path, engine="pyogrio", use_arrow=True)
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {str(e)}")
        raise FileReadError(f"Failed to read GeoPackage: {file_path}") from e

def transform_crs(gdf: gpd.GeoDataFrame, target_crs: CRS) -> gpd.GeoDataFrame:
    """
    Transform the CRS of a GeoDataFrame if it doesn't match the target CRS.

    Args:
        gdf (gpd.GeoDataFrame): Input GeoDataFrame.
        target_crs (CRS): Target CRS.

    Returns:
        gpd.GeoDataFrame: GeoDataFrame with transformed CRS.

    Raises:
        CRSTransformError: If there's an error during CRS transformation.
    """
    try:
        if not gdf.crs.is_exact_same(pyproj.CRS.from_user_input(target_crs.value)):
            return gdf.to_crs(epsg=target_crs.value.split(":")[1])
        return gdf
    except Exception as e:
        logger.error(f"Error transforming CRS to {target_crs.value}: {str(e)}")
        raise CRSTransformError("Failed to transform CRS") from e


def create_buffer(gdf: gpd.GeoDataFrame, buffer_distance: BufferDistance) -> gpd.GeoDataFrame:
    """
    Create a buffer around geometries in a GeoDataFrame.

    Args:
        gdf (gpd.GeoDataFrame): Input GeoDataFrame.
        buffer_distance (BufferDistance): Buffer distance enum.

    Returns:
        gpd.GeoDataFrame: GeoDataFrame with buffered geometries.

    Raises:
        BufferCreationError: If there's an error creating the buffer.
        ValueError: If the CRS units are not supported.
    """
    try:
        crs = gdf.crs
        if crs.is_projected:
            # For projected CRS, units are typically meters
            distance = buffer_distance.value
        elif crs.is_geographic:
            # For geographic CRS, convert degrees to meters (approximate)
            distance = buffer_distance.value / 111000  # 1 degree ≈ 111 km
        else:
            raise ValueError("Unsupported CRS type")
        
        buffered = gdf.copy()
        buffered['geometry'] = gdf.buffer(distance)
        return buffered
    except Exception as e:
        logger.error(f"Error creating buffer: {str(e)}")
        raise BufferCreationError("Failed to create buffer") from e

def perform_spatial_join(left_gdf: gpd.GeoDataFrame, right_gdf: gpd.GeoDataFrame, 
                         predicates: List[SpatialPredicate]) -> gpd.GeoDataFrame:
    """
    Perform spatial joins with multiple predicates and combine results.

    Args:
        left_gdf (gpd.GeoDataFrame): Left GeoDataFrame for join.
        right_gdf (gpd.GeoDataFrame): Right GeoDataFrame for join.
        predicates (List[SpatialPredicate]): List of spatial predicates to use.

    Returns:
        gpd.GeoDataFrame: Combined result of spatial joins.

    Raises:
        SpatialJoinError: If there's an error during spatial join.
    """
    try:
        results: Dict[SpatialPredicate, gpd.GeoDataFrame] = {}
        for pred in predicates:
            try:
                result = gpd.sjoin(left_gdf, right_gdf, how='inner', predicate=pred.value)
                results[pred] = result
            except Exception as e:
                logger.warning(f"Error in spatial join with predicate {pred.value}: {str(e)}")
                continue

        if not results:
            raise SpatialJoinError("All spatial joins failed")

        combined = pd.concat(results.values())
        return combined.drop_duplicates()
    except Exception as e:
        logger.error(f"Error performing spatial join: {str(e)}")
        raise SpatialJoinError("Failed to perform spatial join") from e

def group_and_aggregate(df: pd.DataFrame) -> gpd.GeoDataFrame:
    """
    Group by geometry and aggregate specified columns.

    Args:
        df (pd.DataFrame): Input DataFrame. 

    Returns:
        gpd.GeoDataFrame: Grouped and aggregated GeoDataFrame.

    Raises:
        GroupingError: If there's an error during grouping and aggregation.
    """
    try:
        
        #Spatial join sometimes gives same rows within a buffer, so drop duplicates
        drop_duplicates_cols=['geometry', 'created_unique_id_1_left', 'bridge_id_left','created_unique_id_1_right','RD_NAME_right']
        grouped = df[drop_duplicates_cols].drop_duplicates().groupby(['geometry', 'created_unique_id_1_left', 'bridge_id_left']).agg({
            'created_unique_id_1_right': lambda x: ', '.join(x.astype(str)),
            'RD_NAME_right': lambda x: ', '.join(x.astype(str)),
        }).reset_index()

        return gpd.GeoDataFrame(grouped, geometry='geometry', crs=df.crs)
    except KeyError as e:
        logger.error(f"Grouping error: missing column {str(e)}")
        raise GroupingError("Grouping failed due to missing column") from e
    except Exception as e:
        logger.error(f"Unexpected error during grouping: {str(e)}")
        raise GroupingError("Unexpected error during grouping") from e

def save_geopackage(gdf: gpd.GeoDataFrame, file_path: str) -> None:
    """
    Save a GeoDataFrame to a GeoPackage file if SAVE_INTERMEDIATE_GEOPACKAGES is True.

    Args:
        gdf (gpd.GeoDataFrame): GeoDataFrame to save.
        file_path (str): Path to save the GeoPackage.

    Raises:
        GeoprocessingError: If there's an error saving the GeoPackage.
    """
    file_path=validate_file_path(file_path)

    if OutputControl.SAVE_INTERMEDIATE_GEOPACKAGES.value:
        try:
            with fiona.Env():
                gdf.to_file(file_path, driver="GPKG")
            logger.info(f"Saved GeoPackage: {file_path}")
        except Exception as e:
            logger.error(f"Error saving GeoPackage {file_path}: {str(e)}")
            raise GeoprocessingError(f"Failed to save GeoPackage: {file_path}") from e

def save_csv(df: pd.DataFrame, file_path: str) -> None:
    """
    Save a DataFrame to a CSV file.

    Args:
        df (pd.DataFrame): DataFrame to save.
        file_path (str): Path to save the CSV.

    Raises:
        GeoprocessingError: If there's an error saving the CSV.
    """
    try:
        file_path=validate_file_path(file_path)
        df.to_csv(file_path, index=False)
        logger.info(f"Saved CSV: {file_path}")
    except Exception as e:
        logger.error(f"Error saving CSV {file_path}: {str(e)}")
        raise GeoprocessingError(f"Failed to save CSV: {file_path}") from e

def load_and_transform_data() -> Tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """
    Load and transform the input data.
    
    Returns:
        Tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]: Transformed OSM road points and state road data.
    
    Raises:
        DataLoadError: If there's an error loading or transforming the data.
    """
    try:
        # Read GeoPackage files
        osm_road_points = read_geopackage(FilePath.OSM_ROAD_POINTS.value)
        state_road = read_geopackage(FilePath.STATE_ROAD.value)

        #Change 'NAME' to column name that contains road names from state_road dataset, if its RD_NAME then no need to change
        # state_road.rename(columns={'NAME':'RD_NAME'}, inplace=True)

        logger.info(f"OSM Road Points CRS: {osm_road_points.crs}")
        logger.info(f"State Road CRS: {state_road.crs}")

        # Transform CRS
        state_road = transform_crs(state_road, CRS.EPSG_3857)
        osm_road_points = transform_crs(osm_road_points, CRS.EPSG_3857)

        return osm_road_points, state_road
    except (FileReadError, CRSTransformError) as e:
        logger.error(f"Error loading and transforming data: {str(e)}")
        raise DataLoadError("Failed to load and transform data") from e

def prepare_final_output(grouped_gpd: gpd.GeoDataFrame, osm_road_points: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    Prepare the final output by grouping, aggregating, and merging data.
    
    Args:
        grouped_gpd (gpd.GeoDataFrame): Grouped and aggregated data.
        osm_road_points (gpd.GeoDataFrame): Original OSM road points data.
    
    Returns:
        pd.DataFrame: Final processed data.
    
    Raises:
        OutputPreparationError: If there's an error preparing the final output.
    """
    try:
        # Prepare final DataFrame for CSV
        final_df = grouped_gpd.drop(columns='geometry').rename(columns={
            "created_unique_id_1_left": "created_unique_id",
            'bridge_id_left': 'bridge_id',
            'created_unique_id_1_right': 'neighbouring_ids',
            'RD_NAME_right': 'neighbouring_roads'
        })
        
        #Add osm ids in final_df
        final_df=final_df.merge(osm_road_points[["osm_id","created_unique_id","bridge_id"]], on=['created_unique_id','bridge_id'], how='left')
        
        return final_df
    except (GroupingError, ValueError) as e:
        logger.error(f"Error preparing final output: {str(e)}")
        raise OutputPreparationError("Failed to prepare final output") from e


def main() -> None:
    try:
        # Load and transform data
        osm_road_points, state_road = load_and_transform_data()

        # Create buffers
        osm_road_points_buffer = create_buffer(osm_road_points, BufferDistance.BRIDGE_POINT)
        
        # Perform intersection
        roads_within_buffer = gpd.overlay(state_road, osm_road_points_buffer, how='intersection')

        # Filter roads
        filtered_roads = roads_within_buffer[roads_within_buffer['created_unique_id_1'] == roads_within_buffer['created_unique_id_2']]
        
        # Create buffer
        filtered_roads_buffer = create_buffer(filtered_roads, BufferDistance.ROAD)

        # Save intermediate results
        save_geopackage(roads_within_buffer, "roads_within_buffer.gpkg")
        save_geopackage(filtered_roads, "filtered_roads_within_buffer.gpkg")
        save_geopackage(filtered_roads_buffer, "filtered_roads_buffer_5m.gpkg")

        # Perform spatial joins
        joined = perform_spatial_join(filtered_roads_buffer, roads_within_buffer, 
                                      [SpatialPredicate.INTERSECTS, SpatialPredicate.OVERLAPS, 
                                       SpatialPredicate.CONTAINS, SpatialPredicate.WITHIN])

        # Save joined result
        save_geopackage(joined, "joined_roads.gpkg")

        # Group and aggregate
        grouped_gpd = group_and_aggregate(joined)

        # Prepare final results
        final_df = prepare_final_output(grouped_gpd, osm_road_points)

        # Save final results as CSV (always generated)
        save_csv(final_df, "grouped_neighbouring_roads.csv")

        logger.info("Geospatial analysis completed successfully.")


    except FileReadError as e:
        logger.error(f"File read error: {str(e)}")
    except CRSTransformError as e:
        logger.error(f"CRS transformation error: {str(e)}")
    except BufferCreationError as e:
        logger.error(f"Buffer creation error: {str(e)}")
    except SpatialJoinError as e:
        logger.error(f"Spatial join error: {str(e)}")
    except GroupingError as e:
        logger.error(f"Grouping error: {str(e)}")
    except DataLoadError as e:
        logger.error(f"Data Loading error: {str(e)}")
    except OutputPreparationError as e:
        logger.error(f"Output preparation error: {str(e)}")
    except GeoprocessingError as e:
        logger.error(f"Geoprocessing error: {str(e)}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")

if __name__ == "__main__":
    main()