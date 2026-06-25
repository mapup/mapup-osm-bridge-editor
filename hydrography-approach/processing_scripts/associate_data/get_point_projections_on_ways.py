import geopandas as gpd
import pandas as pd

STRUCTURE_NUMBER = "8 - Structure Number"
FEATURES_INTERSECTED = "6A - Features Intersected"
FACILITY_CARRIED = "7 - Facility Carried By Structure"


def project_point_on_line(point, line):
    # Calculate the projected point on the line
    projected_point = line.interpolate(line.project(point))
    return projected_point


def run(final_bridges, filtered_highways, bridge_association_lengths, bridge_with_proj_points):
    # Load geopackage files
    bridge_points_gdf = gpd.read_file(
        final_bridges
    )
    osm_ways_gdf = gpd.read_file(
        filtered_highways, layer="lines"
    )

    # Load CSV file
    associations_df = pd.read_csv(
        bridge_association_lengths
    )

    # Ensure CRS is consistent
    bridge_points_gdf = bridge_points_gdf.to_crs(epsg=4326)
    osm_ways_gdf = osm_ways_gdf.to_crs(epsg=4326)

    # Trim whitespace from 8 - Structure Number in associations_df and bridge_points_gdf
    associations_df[STRUCTURE_NUMBER] = associations_df[
        STRUCTURE_NUMBER
    ].str.strip()
    bridge_points_gdf[STRUCTURE_NUMBER] = bridge_points_gdf[
        STRUCTURE_NUMBER
    ].str.strip()

    projected_data = []

    for _, row in associations_df.iterrows():
        structure_number = row[STRUCTURE_NUMBER]

        try:
            final_osm_id = str(
                int(row["final_osm_id"])
            )  # Convert to integer and then to string

            # Find the corresponding bridge point
            bridge_point = bridge_points_gdf.loc[
                bridge_points_gdf[STRUCTURE_NUMBER] == structure_number
            ].geometry.values[0]

            # Find the corresponding OSM way
            osm_way = osm_ways_gdf.loc[
                osm_ways_gdf["osm_id"] == final_osm_id
            ].geometry.values[0]

            # Project the bridge point onto the OSM way
            projected_point = project_point_on_line(bridge_point, osm_way)

            # Append the result to the list
            projected_data.append(
                {
                    STRUCTURE_NUMBER: structure_number,
                    "final_osm_id": row["final_osm_id"],
                    "osm_name": row["osm_name"],
                    "final_stream_id": row["final_stream_id"],
                    "stream_name": row["stream_name"],
                    FEATURES_INTERSECTED: row[FEATURES_INTERSECTED],
                    FACILITY_CARRIED: row[
                        FACILITY_CARRIED
                    ],
                    "bridge_length": round(row["bridge_length"]/3.281,2),
                    "projected_long": projected_point.x,
                    "projected_lat": projected_point.y,
                    "Unique_Bridge_OSM_Combinations": row["Unique_Bridge_OSM_Combinations"]
                }
            )
        except (ValueError, KeyError, IndexError):
            # Handle cases where final_osm_id is NaN or OSM way is not found
            projected_data.append(
                {
                    STRUCTURE_NUMBER: structure_number,
                    "final_osm_id": row["final_osm_id"],
                    "osm_name": row["osm_name"],
                    "final_stream_id": row["final_stream_id"],
                    "stream_name": row["stream_name"],
                    FEATURES_INTERSECTED: row[FEATURES_INTERSECTED],
                    FACILITY_CARRIED: row[
                        FACILITY_CARRIED
                    ],
                    "bridge_length": round(row["bridge_length"]/3.281,2),
                    "projected_long": "",
                    "projected_lat": "",
                    "Unique_Bridge_OSM_Combinations": row["Unique_Bridge_OSM_Combinations"]
                }
            )

    # Create output DataFrame
    output_df = pd.DataFrame(projected_data)

    # Save to CSV
    output_df.to_csv(
        bridge_with_proj_points,
        index=False,
    )