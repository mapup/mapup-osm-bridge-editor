import geopandas as gpd
import pandas as pd
from fuzzywuzzy import fuzz
from geographiclib.geodesic import Geodesic
from shapely.geometry import LineString, Point

# Constants
BRIDGE_LAYER = "kentucky_bridges.gpkg"
ROAD_LAYER = "kentucky_roads.gpkg"
INTERPOLATED_BRIDGE_OUTPUT = "interpolated_bridge.gpkg"
INTERPOLATED_ROAD_OUTPUT = "interpolated_road.gpkg"
ROAD_WITH_UNIQUE_ID_OUTPUT = "ky_roads_with_unique_id.gpkg"
CRS_EPSG_4326 = "EPSG:4326"
CRS_EPSG_3857 = "EPSG:3857"
CRS_EPSG_6473 = "EPSG:6473"



def read_and_clean_road_df(save_road_with_unique_id=False):
    """
    Reads and cleans the road data from the specified GeoPackage file.

    Returns:
        GeoDataFrame: Cleaned road data with selected columns renamed.
    """
    road_df = gpd.read_file(ROAD_LAYER, engine="pyogrio", use_arrow=True)
    road_df["created_unique_id"]=road_df.index

    #Save road data with "created_unique_id" if save_road_with_unique_id is True
    if save_road_with_unique_id:
        (gpd.GeoDataFrame(road_df.copy()).to_crs(epsg=CRS_EPSG_3857.split(':')[-1])).to_file(ROAD_WITH_UNIQUE_ID_OUTPUT, driver="GPKG")
    
    road_association = {
        "RT_UNIQUE": "rt_unique",
        "LRS_ID": "lrs_id",
        "BEGIN_MP": "begin_mp",
        "END_MP": "end_mp",
        "RT_NUMBER": "rt_number",
        "RD_NAME": "rd_name",
        "geometry": "geometry",
        "DMI_LEN_MI": "dmi_len_mi",
        "GRAPHIC_LE": "graphic_le",
        "created_unique_id": "created_unique_id"
    }
    road_df = road_df[list(road_association.keys())].rename(columns=road_association)
    return road_df

def read_and_clean_bridge_df():
    """
    Reads and cleans the bridge data from the specified GeoPackage file.

    Returns:
        GeoDataFrame: Cleaned bridge data with selected columns renamed and duplicates removed.
    """
    bridge_df = gpd.read_file(BRIDGE_LAYER, engine="pyogrio", use_arrow=True)
    bridge_association = {
        "RT_UNIQUE": "rt_unique",
        "MIDPOINT_M": "bridge_point",
        "RT_NUMBER": "rt_number",
        "BRIDGE_ID": "bridge_id",
        "FEATINT": "feature_under_bridge",
        "FACILITY_7": "feature_over_bridge",
        "LOCATION": "bridge_location_desc",
        "geometry": "geometry",
        "OBJECTID": "object_id"
    }
    bridge_df = bridge_df[list(bridge_association.keys())].rename(
        columns=bridge_association
    )
    bridge_df.drop_duplicates(subset=["bridge_id"], inplace=True)
    return bridge_df

def filter_left_right_bridges(joined_df):
    """
    Filters out bridges containing 'L' or 'R' in their ID that have both left and right lanes.

    Args:
        joined_df (GeoDataFrame): DataFrame containing joined road and bridge data.

    Returns:
        GeoDataFrame: Filtered DataFrame without left-right bridges.
    """
    bridges_containing_lr = joined_df[
        joined_df["bridge_id"].str.contains("L")
        | joined_df["bridge_id"].str.contains("R")
    ]

    merged_bridges = bridges_containing_lr.merge(
        bridges_containing_lr, on="bridge_id", how="inner"
    )
    merged_bridges["has_left_lane"] = (
        merged_bridges["lrs_id_y"].str.replace(r"-10$", "", regex=True)
        == merged_bridges["lrs_id_x"]
    ) & merged_bridges["lrs_id_y"].str.contains("-10")

    merged_bridges["has_potential_double"] = merged_bridges.groupby("bridge_id")[
        "has_left_lane"
    ].transform(lambda x: any(x))
    merged_bridges = merged_bridges[merged_bridges["has_potential_double"] == True]

    left_right_mask = (
        (joined_df["begin_mp"] < joined_df["end_mp"])
        & (joined_df["bridge_id"].str.contains("L"))
        & joined_df["lrs_id"].isin(merged_bridges["lrs_id_x"])
    ) | (
        (joined_df["begin_mp"] > joined_df["end_mp"])
        & (joined_df["bridge_id"].str.contains("R"))
        & joined_df["lrs_id"].isin(merged_bridges["lrs_id_x"])
    )
    return joined_df[~left_right_mask]

def add_distance_column(df, col1, col2):
    """
    Adds a distance column to the DataFrame by calculating the distance between two geometry columns.

    Args:
        df (DataFrame): DataFrame containing geometry columns.
        col1 (str): Column name for the first geometry.
        col2 (str): Column name for the second geometry.

    Note:
        This function assumes the geometries are in CRS EPSG:3857.
    """
    if isinstance(df["col1"], pd.Series):
        df["col1"] = gpd.GeoSeries(df["col1"], crs=CRS_EPSG_3857)
        df["distance"] = df.apply(lambda row: row["col1"].distance(row["col2"]), axis=1)

def merge_road_and_bridge_dfs(road_df, bridge_df):
    """
    Merges the road and bridge DataFrames based on common columns and filters the result.

    Args:
        road_df (GeoDataFrame): Cleaned road data.
        bridge_df (GeoDataFrame): Cleaned bridge data.

    Returns:
        GeoDataFrame: Merged and filtered DataFrame.
    """
    joined_df = road_df.merge(
        bridge_df,
        how="inner",
        on=["rt_number", "rt_unique"],
        suffixes=("_road", "_bridge"),
    )

    bridge_point_mask = (joined_df["bridge_id"].notnull()) & (
        (joined_df["bridge_point"]).between(
            joined_df["begin_mp"], joined_df["end_mp"], inclusive="left"
        )
        | (joined_df["bridge_point"]).between(
            joined_df["end_mp"], joined_df["begin_mp"], inclusive="left"
        )
    )
    joined_df = joined_df[bridge_point_mask]

    joined_df["bridge_line_segment_point"] = (
        joined_df["bridge_point"] - joined_df["begin_mp"]
    ).where(
        joined_df["bridge_point"] > joined_df["begin_mp"],
        joined_df["begin_mp"] - joined_df["bridge_point"],
    )

    joined_df["bridge_line_segment_point"] = (
        joined_df["graphic_le"] / joined_df["dmi_len_mi"]
    ) * joined_df["bridge_line_segment_point"]

    joined_df = filter_left_right_bridges(joined_df)

    joined_df["distance_from_bridge"] = (
        gpd.GeoSeries(joined_df["geometry_road"], crs=CRS_EPSG_4326).to_crs(
            CRS_EPSG_6473
        )
    ).distance(
        gpd.GeoSeries(joined_df["geometry_bridge"], crs=CRS_EPSG_4326).to_crs(
            CRS_EPSG_6473
        ),
        align=False,
    )

    joined_df["road_name_score"] = joined_df.apply(
        lambda row: fuzz.partial_ratio(row["rd_name"], row["feature_over_bridge"]),
        axis=1,
    )

    joined_df = joined_df[(joined_df["distance_from_bridge"] < 1000)]
    return joined_df

def interpolate_point_geography(line, distance_miles):
    """
    Interpolates a point on a line at a specified distance.

    Args:
        line (LineString): Line geometry to interpolate along.
        distance_miles (float): Distance in miles from the start of the line to interpolate.

    Returns:
        tuple: Interpolated point and corresponding line segment, or (pd.NA, pd.NA) if distance exceeds the line length.
    """
    coord_list = [tuple(reversed(line.coords[i])) for i in range(len(line.coords))]
    geodesic = Geodesic(6378137, 1 / 298.257222101)
    total_length = sum(
        geodesic.Inverse(
            coord_list[i][0],
            coord_list[i][1],
            coord_list[i + 1][0],
            coord_list[i + 1][1],
        )["s12"]
        for i in range(len(coord_list) - 1)
    )
    if distance_miles > total_length:
        return pd.NA, pd.NA

    current_distance = 0
    for i in range(len(coord_list) - 1):
        segment_line = geodesic.InverseLine(
            coord_list[i][0],
            coord_list[i][1],
            coord_list[i + 1][0],
            coord_list[i + 1][1],
        )
        segment_length = segment_line.s13
        if current_distance + segment_length >= distance_miles:
            remaining_distance = distance_miles - current_distance
            interpolated_point = segment_line.Position(remaining_distance)
            return (
                Point(interpolated_point["lon2"], interpolated_point["lat2"]),
                LineString([line.coords[i], line.coords[i + 1]]),
            )
        current_distance += segment_length
    return pd.NA, pd.NA

def select_rows_with_max_scores(df, distance_col, fuzzy_col):
    """
    Selects rows with the highest combined score of distance and fuzzy matching.

    Args:
        df (DataFrame): DataFrame containing distance and fuzzy matching columns.
        distance_col (str): Column name for distance values.
        fuzzy_col (str): Column name for fuzzy matching scores.

    Returns:
        DataFrame: Filtered DataFrame with rows having the highest combined score for each object_id.
    """
    df["distance_scaled"] = (df[distance_col].max() - df[distance_col]) / (
        df[distance_col].max() - df[distance_col].min()
    )

    # Min-max scaling for fuzzy_score (to maximize)
    df["fuzzy_score_scaled"] = (df[fuzzy_col] - df[fuzzy_col].min()) / (
        df[fuzzy_col].max() - df[fuzzy_col].min()
    )

    # Combine the scaled scores (you can adjust the weights if needed)
    df["combined_score"] = df["distance_scaled"] + df["fuzzy_score_scaled"]

    # Group by object_id and get the index of the max combined_score
    idx = df.groupby("object_id")["combined_score"].idxmax()

    # Select rows based on the index
    result_df = df.loc[idx].reset_index(drop=True)
    return result_df

def process_joined_df(joined_df):
    """
    Processes the joined DataFrame to interpolate bridge points and calculate distances.

    Args:
        joined_df (GeoDataFrame): DataFrame containing joined road and bridge data.

    Returns:
        GeoDataFrame: Processed DataFrame with interpolated bridge points and distances.
    """
    result = joined_df[["geometry_road", "bridge_line_segment_point"]].apply(
        lambda row: interpolate_point_geography(
            row["geometry_road"], row["bridge_line_segment_point"] * 1609.344
        ),
        axis=1,
        result_type="expand",
    )

    joined_df["interpolated_bridge_geom"], joined_df["road_segment"] = (
        result[0],
        result[1],
    )

    joined_df = joined_df[joined_df["interpolated_bridge_geom"].notnull()]

    joined_df["distance_from_interpolated_bridge"] = (
        gpd.GeoSeries(joined_df["interpolated_bridge_geom"], crs=CRS_EPSG_4326).to_crs(
            CRS_EPSG_6473
        )
    ).distance(
        gpd.GeoSeries(joined_df["geometry_bridge"], crs=CRS_EPSG_4326).to_crs(
            CRS_EPSG_6473
        ),
        align=False,
    )

    final_df = select_rows_with_max_scores(
        joined_df, "distance_from_interpolated_bridge", "road_name_score"
    )

    return final_df

def export_geodataframes(joined_df):
    """
    Exports the processed DataFrame to GeoPackage files for interpolated bridge points and road segments.

    Args:
        joined_df (GeoDataFrame): Processed DataFrame to export.
    """
    point_filtered = joined_df[
        [
            "lrs_id",
            "bridge_id",
            "begin_mp",
            "interpolated_bridge_geom",
            "end_mp",
            "object_id",
        ]
    ]
    point_filtered.rename(
        columns={"interpolated_bridge_geom": "geometry"}, inplace=True
    )
    point_filtered.set_geometry(point_filtered["geometry"])
    gpd.GeoDataFrame(point_filtered).to_file(INTERPOLATED_BRIDGE_OUTPUT, driver="GPKG")

    road_filtered = joined_df[
        [
            "lrs_id",
            "bridge_id",
            "begin_mp",
            "road_segment",
            "end_mp",
            "bridge_point",
            "object_id",
            "rd_name",
            "created_unique_id"
        ]
    ]
    road_filtered.rename(columns={"road_segment": "geometry"},inplace=True)
    road_filtered.rename(columns={"rd_name":"state_rd_name"},inplace=True)

    road_filtered.set_geometry(road_filtered["geometry"])
    gpd.GeoDataFrame(road_filtered).to_file(INTERPOLATED_ROAD_OUTPUT, driver="GPKG")

def main():
    """
    Main function to execute the processing pipeline.
    """
    road_df = read_and_clean_road_df(save_road_with_unique_id=True)
    bridge_df = read_and_clean_bridge_df()
    joined_df = merge_road_and_bridge_dfs(road_df, bridge_df)
    joined_df = process_joined_df(joined_df)
    export_geodataframes(joined_df)

if __name__ == "__main__":
    main()
