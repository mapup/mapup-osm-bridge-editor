import math

import pandas as pd

STRUCTURE_NUMBER = "8 - Structure Number"
STRUCTURE_LENGTH = "49 - Structure Length (ft.)"


def haversine(lon1, lat1, lon2, lat2):
    """
    Function to calculate Haversine distance among two points
    """
    # Radius of the Earth in kilometers
    R = 6371.0

    # Convert latitude and longitude from degrees to radians
    lon1 = math.radians(lon1)
    lat1 = math.radians(lat1)
    lon2 = math.radians(lon2)
    lat2 = math.radians(lat2)

    # Compute differences between the coordinates
    dlon = lon2 - lon1
    dlat = lat2 - lat1

    # Haversine formula
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # Distance in kilometers
    distance = R * c

    return distance


def extract_coordinates(wkt):
    """
    Function to extract latitude and longitude from WKT (Well-Known Text) format
    """
    if pd.isna(wkt):
        return None, None
    # Remove 'POINT (' and ')'
    coords = wkt.replace("POINT (", "").replace(")", "")
    # Split the coordinates
    lon, lat = coords.split()
    return float(lat), float(lon)


def _resolve_location_single_osm(group, true_stream, min_dist):
    """
    Resolve long/lat when combo-count == 1 (single unique OSM id).
    """
    if len(true_stream) == 1:
        long, lat = true_stream[["Long_intersection", "Lat_intersection"]].iloc[0]
    elif len(true_stream) > 1:
        min_dist_match = true_stream[true_stream["Is_Min_Dist"]]
        if not min_dist_match.empty:
            long, lat = min_dist_match[
                ["Long_intersection", "Lat_intersection"]
            ].iloc[0]
        else:
            long, lat = true_stream[["Long_intersection", "Lat_intersection"]].iloc[0]
    else:
        # If there are no rows with stream_check as TRUE, use MIN-DIST
        if not min_dist.empty:
            long, lat = min_dist[["Long_intersection", "Lat_intersection"]].iloc[0]
        else:
            long, lat = group[["Long_intersection", "Lat_intersection"]].iloc[0]
    return long, lat


def _resolve_osm_for_multiple(true_stream, min_dist):
    """
    Resolve (osm_id, osm_name, stream_id, stream_name, long, lat) when combo-count > 1.
    """
    cols = [
        "osm_id",
        "name",
        "permanent_identifier_x",
        "gnis_name",
        "Long_intersection",
        "Lat_intersection",
    ]
    if len(true_stream) == 1:
        # If there is exactly one OSM id with stream_check as TRUE
        osm_id, osm_name, stream_id, stream_name, long, lat = true_stream[cols].iloc[0]
    elif not min_dist.empty:
        # If there are multiple OSM ids with stream_check as TRUE, use 'MIN-DIST'
        osm_id, osm_name, stream_id, stream_name, long, lat = min_dist[cols].iloc[0]
    else:
        osm_id, osm_name, stream_id, stream_name, long, lat = [
            pd.NA, pd.NA, pd.NA, pd.NA, pd.NA, pd.NA,
        ]
    return osm_id, osm_name, stream_id, stream_name, long, lat


def determine_final_osm_id(group):
    """
    Function to determine the final_osm_id, final_long, and final_lat for each group
    """
    true_stream = group[group["Is_Stream_Identical"]]
    min_dist = group[group["Is_Min_Dist"]]
    if group["combo-count"].iloc[0] == 1:
        # If there is only one unique OSM id
        osm_id = group["osm_id"].iloc[0]
        osm_name = group["name"].iloc[0]
        if len(min_dist) == 0:
            stream_id = pd.NA
            stream_name = pd.NA
        else:
            stream_id = min_dist["permanent_identifier_x"].iloc[0]
            stream_name = min_dist["gnis_name"].iloc[0]
        long, lat = _resolve_location_single_osm(group, true_stream, min_dist)
    else:
        osm_id, osm_name, stream_id, stream_name, long, lat = _resolve_osm_for_multiple(
            true_stream, min_dist
        )
    return pd.Series(
        [osm_id, osm_name, stream_id, stream_name, long, lat],
        index=[
            "final_osm_id",
            "osm_name",
            "final_stream_id",
            "stream_name",
            "final_long",
            "final_lat",
        ],
    )


def merge_join_data_with_intersections(all_join_csv, intersections_csv):
    """
    Function to tag all data join result with intersections information.
    """
    # Load the final join data
    final_join_data = pd.read_csv(all_join_csv)

    # Load the intersection data
    intersection_data = pd.read_csv(intersections_csv, low_memory=False)
    intersection_data = intersection_data[
        ["WKT", "osm_id", "permanent_identifier", "gnis_name"]
    ]

    # Perform the left merge
    df = pd.merge(
        final_join_data,
        intersection_data,
        how="left",
        left_on=["osm_id", "permanent_identifier_x"],
        right_on=["osm_id", "permanent_identifier"],
        validate="many_to_many",
    )

    return df


def create_intermediate_association(df, intermediate_association):
    """
    Function to create intermediate association among bridges and ways.
    """
    # Apply the function to the WKT column to create new columns
    df[["Lat_intersection", "Long_intersection"]] = df["WKT"].apply(
        lambda x: pd.Series(extract_coordinates(x))
    )

    # Calculate Haversine distance
    df["Haversine_dist"] = df.apply(
        lambda row: haversine(
            row["17 - Longitude (decimal)"],
            row["16 - Latitude (decimal)"],
            row["Long_intersection"],
            row["Lat_intersection"],
        ),
        axis=1,
    )

    # Calculate minimum Haversine distance for each bridge
    df["Min_Haversine_dist"] = df.groupby(STRUCTURE_NUMBER)[
        "Haversine_dist"
    ].transform("min")

    # Flag rows with minimum distance
    df["Is_Min_Dist"] = df["Min_Haversine_dist"] == df["Haversine_dist"]

    # Check if stream identifiers match
    df["Is_Stream_Identical"] = (
        df["permanent_identifier_x"] == df["permanent_identifier_y"]
    )

    # Count unique OSM-Bridge combinations
    df["Unique_Bridge_OSM_Combinations"] = df.groupby(STRUCTURE_NUMBER)[
        "osm_id"
    ].transform("nunique")

    # Save intermediate results
    df.to_csv(intermediate_association)
    print(f"\n{intermediate_association} file has been created successfully!")

    return df


def create_final_associations(df, association_with_intersections):
    """
    Function to create final association among bridges and ways.
    """
    # Group by 'BRIDGE_ID' and calculate the number of unique 'osm_id's for each group
    unique_osm_count = (
        df.groupby(STRUCTURE_NUMBER)["osm_id"].nunique().reset_index()
    )

    # Rename the column to 'combo-count'
    unique_osm_count.rename(columns={"osm_id": "combo-count"}, inplace=True)

    # Merge the unique counts back to the original dataframe
    df = df.merge(unique_osm_count, on=STRUCTURE_NUMBER, how="left", validate="many_to_many")

    # Apply the function to each group and create a new DataFrame with final_osm_id, final_long, and final_lat for each BRIDGE_ID
    final_values_df = (
        df.groupby(STRUCTURE_NUMBER).apply(determine_final_osm_id).reset_index()
    )

    # Merge the final values back to the original dataframe
    df = df.merge(final_values_df, on=STRUCTURE_NUMBER, how="left", validate="many_to_many")

    # Save the updated dataframe to a new CSV file
    df.to_csv(
        association_with_intersections,
        index=False,
    )
    print(f"\n{association_with_intersections} file has been created successfully!")

    return df


def add_bridge_details(df, nbi_bridge_data, bridge_association_lengths):
    """
    Function to add bridge information to associated data.
    """
    bridge_data_df = pd.read_csv(
        nbi_bridge_data,
        low_memory=False,
    )

    # Merge the data on '8 - Structure Number'
    merged_df = pd.merge(
        df,
        bridge_data_df[
            [
                STRUCTURE_NUMBER,
                STRUCTURE_LENGTH,
                "6A - Features Intersected",
                "7 - Facility Carried By Structure",
            ]
        ],
        on=STRUCTURE_NUMBER,
        how="left",
        validate="many_to_many",
    )

    # Select the required columns and ensure the uniqueness
    result_df = merged_df[
        [
            STRUCTURE_NUMBER,
            "final_osm_id",
            "osm_name",
            "final_stream_id",
            "stream_name",
            "final_long",
            "final_lat",
            "6A - Features Intersected",
            "7 - Facility Carried By Structure",
            STRUCTURE_LENGTH,
            "Unique_Bridge_OSM_Combinations"
        ]
    ].drop_duplicates()

    # Rename '49 - Structure Length (ft.)' to 'bridge_length'
    result_df.rename(
        columns={STRUCTURE_LENGTH: "bridge_length"}, inplace=True
    )

    # Save the resulting DataFrame to a new CSV file
    result_df.to_csv(
        bridge_association_lengths,
        index=False,
    )
    print(
        f"\n{bridge_association_lengths} file has been created successfully!"
    )


def process_final_id(
    all_join_csv,
    intersections_csv,
    intermediate_association,
    association_with_intersections,
    nbi_bridge_data,
    bridge_association_lengths
):
    df = merge_join_data_with_intersections(all_join_csv, intersections_csv)
    intermediate_df = create_intermediate_association(df, intermediate_association)
    final_df = create_final_associations(
        intermediate_df, association_with_intersections
    )
    add_bridge_details(final_df, nbi_bridge_data, bridge_association_lengths)
