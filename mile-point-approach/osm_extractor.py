from typing import Tuple, Optional
from shapely.geometry import Point, LineString, base
from shapely.ops import nearest_points
import geopandas as gpd
import pandas as pd

# Constants for file paths
BRIDGE_LINK_LAYER = "interpolated_road.gpkg"
OSM_SHAPE_FILE_LAYER = "gis_osm_roads_free_1.shp"
BRIDGE_LOCATIONS_LAYER = "interpolated_bridge.gpkg"
OUTPUT_OSM_LINKS_GPKG = "osm_road_raw.gpkg"
OUTPUT_OSM_POINTS_GPKG = "osm_road_points.gpkg"


def load_data(file_path, crs: int = 3857) -> gpd.GeoDataFrame:
    """
    Load data from a file and convert to specified CRS.

    Args:
        file_path (Path): Path to the input file.
        crs (int): Coordinate Reference System to convert to. Default is 3857.

    Returns:
        gpd.GeoDataFrame: Loaded and converted GeoDataFrame.
    """
    if not file_path:
        raise ValueError("The file path cannot be empty.")
    df = gpd.read_file(file_path, engine="pyogrio", use_arrow=True)
    try:
        return df.to_crs(crs)
    except Exception as e:
        raise ValueError(f"Failed to convert CRS: {str(e)}")


def prepare_bridge_data(bridge_df: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Prepare bridge data by calculating road length and creating a buffer.

    Args:
        bridge_df (gpd.GeoDataFrame): Input bridge GeoDataFrame.

    Returns:
        gpd.GeoDataFrame: Prepared bridge GeoDataFrame.
    """
    bridge_df["road_length"] = bridge_df.geometry.length
    bridge_df.set_geometry(
        bridge_df["geometry"].buffer(5, cap_style="flat", single_sided=False),
        inplace=True,
    )
    return bridge_df


def load_and_prepare_data() -> (
    Tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame]
):
    """
    Loads and prepares the bridge, OSM, and bridge location data from the specified file paths.

    Returns:
        tuple: A tuple containing the prepared bridge, OSM, and bridge location GeoDataFrames.
    """
    bridge_df = load_data(BRIDGE_LINK_LAYER)
    osm_df = load_data(OSM_SHAPE_FILE_LAYER)
    bridge_location_df = load_data(BRIDGE_LOCATIONS_LAYER)

    bridge_df = prepare_bridge_data(bridge_df)

    return bridge_df, osm_df, bridge_location_df


def project_point_to_line(
    point: Point, line: LineString, max_distance: float = 1000.0
) -> Point:
    """
    Project a point perpendicularly onto a line.

    Args:
        point (Point): The point to project.
        line (LineString): The line to project onto.
        max_distance (float, optional): The maximum distance from the projected point to the original point. Defaults to float('inf').

    Returns:
        Point: The projected point on the line. If the distance is greater than the maximum distance, returns the original point.

    Raises:
        TypeError: If input types are incorrect.
        ValueError: If geometric operations fail.
    """
    if not isinstance(point, base.BaseGeometry) or not isinstance(
        line, base.BaseGeometry
    ):
        raise TypeError(f"Expected a Shapely geometry object, got {type(point)} and type {type(line)} instead.")

    try:
        projected_point = nearest_points(point, line)[1]
        distance = point.distance(projected_point)

        return projected_point if distance <= max_distance else point
    except Exception as e:
        raise ValueError(f"Error in geometric operations: {str(e)}")

def process_and_merge_osm_data(
    osm_df: gpd.GeoDataFrame,
    bridge_df: gpd.GeoDataFrame,
    bridge_location_df: gpd.GeoDataFrame,
    max_snap_distance: float = 10,
) -> Tuple[gpd.GeoDataFrame, gpd.GeoSeries]:
    """
    Processes and merges the OSM data with bridge data and bridge location data.

    Args:
        osm_df (GeoDataFrame): GeoDataFrame containing OSM road data.
        bridge_df (GeoDataFrame): GeoDataFrame containing bridge data.
        bridge_location_df (GeoDataFrame): GeoDataFrame containing bridge location data.

    Returns:
        tuple: A tuple containing the final merged GeoDataFrame and the point geometries.
    """
    osm_df = gpd.overlay(osm_df, bridge_df, how="intersection")
    osm_df = osm_df[osm_df["bridge_id"].notnull()]
    osm_df["osm_length"] = osm_df.geometry.length
    final_df = osm_df.merge(
        bridge_location_df, on="bridge_id", suffixes=("_osm", "_bridge")
    )
    final_df = gpd.GeoDataFrame(final_df, geometry="geometry_osm")
    final_df["distance"] = final_df.geometry.distance(final_df["geometry_bridge"])

    final_df["min_distance"] = final_df.groupby("geometry_bridge")[
        "distance"
    ].transform("min")
    final_df = final_df[final_df["min_distance"] == final_df["distance"]]

    point_geom = final_df.apply(
        lambda row: project_point_to_line(
            row["geometry_bridge"], row["geometry_osm"], max_snap_distance
        ),
        axis=1,
    )

    final_point_geom = point_geom.where(point_geom != final_df.geometry_bridge, pd.NA)
    final_point_geom = final_point_geom[final_point_geom.notnull()]

    return final_df, final_point_geom


def iterative_intersection_process(
    bridge_df: gpd.GeoDataFrame,
    osm_df: gpd.GeoDataFrame,
    bridge_location_df: gpd.GeoDataFrame,
    max_iterations: int = 4,
    buffer_size: float = 15,
    max_buffer: float = 30,
    buffer_increment: float = 5,
) -> Tuple[gpd.GeoDataFrame, gpd.GeoSeries]:
    """
    Iteratively processes and merges the OSM data with bridge data and bridge location data using increasing buffer sizes.

    Args:
        bridge_df (GeoDataFrame): GeoDataFrame containing bridge data.
        osm_df (GeoDataFrame): GeoDataFrame containing OSM road data.
        bridge_location_df (GeoDataFrame): GeoDataFrame containing bridge location data.
        max_iterations (int, optional): Maximum number of iterations. Defaults to 4.

    Returns:
        tuple: A tuple containing the final merged GeoDataFrame and a GeoSeries of point geometries.

    Raises:
        ValueError: If input DataFrames are empty or None.
    """
    if bridge_df.empty or osm_df.empty or bridge_location_df.empty:
        raise ValueError("Input DataFrames cannot be empty")

    final_df_list = []
    point_geom_list = []

    iteration_count = 0

    while (
        not bridge_df.empty
        and buffer_size <= max_buffer
        and iteration_count < max_iterations
    ):
        # Create a buffer around bridge geometries
        bridge_buffer = bridge_df.copy()
        bridge_buffer.set_geometry(
            bridge_buffer["geometry"].buffer(
                buffer_size, cap_style="flat", single_sided=False
            ),
            inplace=True,
        )

        # Process and merge OSM data with buffered bridge data
        processed_df, temp_point_geom = process_and_merge_osm_data(
            osm_df, bridge_buffer, bridge_location_df
        )

        if not processed_df.empty:
            final_df_list.append(processed_df)
            point_geom_list.extend(temp_point_geom)

            # Remove processed bridges from the original DataFrame
            processed_ids = processed_df["bridge_id"].unique()
            bridge_df = bridge_df[~bridge_df["bridge_id"].isin(processed_ids)]

        buffer_size += buffer_increment
        iteration_count += 1

    # Combine all processed data
    final_df = pd.concat(final_df_list, ignore_index=True)
    point_geom = gpd.GeoSeries(point_geom_list)

    return final_df, point_geom


def save_results(final_df: gpd.GeoDataFrame, point_geom: gpd.GeoSeries) -> None:
    """
    Saves the final merged results to GeoPackage files.

    Args:
        final_df (GeoDataFrame): The final merged GeoDataFrame to save.
        point_geom (GeoSeries): The point geometries to save.
    """
    final_df.drop(columns=["geometry_bridge"], inplace=True)
    osm_points = final_df.set_geometry(point_geom)
    osm_points.drop_duplicates(subset=["bridge_id"], inplace=True)

    try:
        osm_points.to_file(OUTPUT_OSM_POINTS_GPKG)
    except (IOError, OSError) as e:
        print(f"Error saving OSM points: {str(e)}")
    except Exception as e:
        print(f"Unexpected error saving OSM points: {str(e)}")

    try:
        final_df.to_file(OUTPUT_OSM_LINKS_GPKG)
    except (IOError, OSError) as e:
        print(f"Error saving OSM roads: {str(e)}")
    except Exception as e:
        print(f"Unexpected error saving OSM roads: {str(e)}")

def main():
    """
    Main function to execute the processing pipeline.
    """
    bridge_df, osm_df, bridge_location_df = load_and_prepare_data()
    final_df, point_geom = process_and_merge_osm_data(
        bridge_df=bridge_df, osm_df=osm_df, bridge_location_df=bridge_location_df
    )
    save_results(final_df, point_geom)


if __name__ == "__main__":
    main()
