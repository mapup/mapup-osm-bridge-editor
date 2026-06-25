import csv
import json
import logging
from multiprocessing import Pool, cpu_count

import pyproj
from shapely.geometry import LineString, Point
from shapely.ops import nearest_points, transform
import argparse

def parse_arguments():
    parser = argparse.ArgumentParser(description="Process bridge data.")
    parser.add_argument("geojson_file", type=str, help="Path to the GeoJSON file.")
    parser.add_argument("csv_file", type=str, help="Path to the CSV file.")
    return parser.parse_args()

def setup_logging():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler("debug.log"), logging.StreamHandler()],
    )

def load_geojson(file_path):
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
        return data
    except Exception as e:
        logging.error(f"Error loading GeoJSON file: {e}")
        return None

def load_csv(file_path):
    bridge_data = []
    try:
        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row_number, row in enumerate(reader, start=1):
                try:
                    osm_id = row["final_osm_id"]
                    bridge_id = row["STRUCTURE_NUMBER_008"]
                    bridge_length = float(row["bridge_length"])
                    bridge_coordinate = (float(row["final_lat"]), float(row["final_long"]))
                    bridge_data.append(
                        {
                            "index": row_number,
                            "osm_id": osm_id,
                            "bridge_id": bridge_id,
                            "bridge_length": bridge_length,
                            "bridge_coordinate": bridge_coordinate,
                        }
                    )
                except Exception as e:
                    logging.error(f"Error processing row {row_number} in CSV file: {e}")
    except Exception as e:
        logging.error(f"Error loading CSV file: {e}")
    return bridge_data

def find_nearest_point_on_line(line, point):
    try:
        nearest_geoms = nearest_points(line, point)
        return nearest_geoms[0]
    except Exception as e:
        logging.error(f"Error finding nearest point on line: {e}")
        return None

def find_way_id_for_point(point, all_lines_with_ids):
    try:
        for line, way_id in all_lines_with_ids:
            if line.distance(point) < 1e-6:
                return way_id
    except Exception as e:
        logging.error(f"Error finding way ID for point: {e}")
    return None

def calculate_points_on_way(line, nearest_point, half_distance, all_lines_with_ids):
    try:
        forward_visited = []
        backward_visited = []
        nearest_distance = line.project(nearest_point)
        forward_distance = nearest_distance + half_distance
        backward_distance = nearest_distance - half_distance
        forward_point = (
            line.interpolate(forward_distance) if forward_distance <= line.length else None
        )
        backward_point = (
            line.interpolate(backward_distance) if backward_distance >= 0 else None
        )

        forward_way_id = None
        backward_way_id = None

        if forward_point is None:
            forward_point, forward_way_id, forward_visited = extend_along_connected_way(
                line, forward_distance - line.length, all_lines_with_ids
            )
        else:
            forward_way_id = find_way_id_for_point(forward_point, all_lines_with_ids)

        if backward_point is None:
            backward_point, backward_way_id, backward_visited = extend_along_connected_way(
                line, -backward_distance, all_lines_with_ids, reverse=True
            )
        else:
            backward_way_id = find_way_id_for_point(backward_point, all_lines_with_ids)

        return forward_point, forward_way_id, forward_visited, backward_point, backward_way_id, backward_visited
    except Exception as e:
        logging.error(f"Error calculating points on way: {e}")
        return None, None, [], None, None, []

def _find_connected_lines(current_line, all_lines_with_ids, connection_point, visited):
    current_line_way_id = None
    possible_next_lines = []
    for line, way_id in all_lines_with_ids:
        if line.equals(current_line):
            current_line_way_id = way_id
            continue
        if way_id in visited:
            continue
        if connection_point.equals(Point(line.coords[0])):
            possible_next_lines.append((line, way_id))
        elif connection_point.equals(Point(line.coords[-1])):
            inverted_line = LineString(line.coords[::-1])
            possible_next_lines.append((inverted_line, way_id))
    return current_line_way_id, possible_next_lines

def extend_along_connected_way(
    current_line, remaining_distance, all_lines_with_ids, reverse=False, visited=None
):
    if visited is None:
        visited = []

    try:
        start_or_end = 0 if reverse else -1
        connection_point = Point(current_line.coords[start_or_end])
        current_line_way_id, possible_next_lines = _find_connected_lines(
            current_line, all_lines_with_ids, connection_point, visited
        )

        if len(possible_next_lines) > 1:
            logging.warning(f"Split detected at point {current_line_way_id}. Stopping.")
            return None, current_line_way_id, visited

        if len(possible_next_lines) == 1:
            next_line, way_id = possible_next_lines[0]
            if remaining_distance <= next_line.length:
                next_point = next_line.interpolate(remaining_distance)
                return next_point, way_id, visited
            else:
                visited.append(way_id)
                return_point, return_wayid, return_visited = extend_along_connected_way(
                    next_line, 
                    remaining_distance - next_line.length, 
                    all_lines_with_ids, 
                    reverse, 
                    visited
                )
                return return_point, return_wayid, return_visited

        logging.warning(f"No connected line found at point {current_line_way_id}. Stopping.")
        return None, current_line_way_id, visited
    except Exception as e:
        logging.error(f"Error extending along connected way: {e}")
        return None, None, visited

def _transform_result_points(forward_point_utm, backward_point_utm, inverse_project):
    forward_point = Point(-1, -1)
    backward_point = Point(-1, -1)
    if forward_point_utm is not None:
        forward_point = transform(inverse_project, forward_point_utm)
    if backward_point_utm is not None:
        backward_point = transform(inverse_project, backward_point_utm)
    return forward_point, backward_point

def _build_result_dict(osm_id, bridge_id, bridge_length, input_coordinate, nearest_point_utm,
                       forward_point, backward_point, forward_way_id, forward_visited,
                       backward_way_id, backward_visited, actual_forward_distance, actual_backward_distance):
    return {
        "original_osm_id": osm_id,
        "bridge_id": bridge_id,
        "bridge_length": bridge_length,
        "bridge_coordinate": input_coordinate,
        "input_coordinate": input_coordinate,
        "nearest_point": (nearest_point_utm.x, nearest_point_utm.y),
        "forward_point": (forward_point.x, forward_point.y),
        "backward_point": (backward_point.x, backward_point.y),
        "forward_way_id": forward_way_id if forward_way_id is not None else -1,
        "forward_visited": forward_visited if forward_visited is not None else "None",
        "backward_way_id": backward_way_id if backward_way_id is not None else -1,
        "backward_visited": backward_visited if backward_visited is not None else "None",
        "actual_forward_distance": actual_forward_distance,
        "actual_backward_distance": actual_backward_distance,
    }

def process_single_bridge(bridge, lines_utm_with_ids, project, inverse_project):
    try:
        logging.info(f"Processing bridge {bridge['index']}/6599")
        osm_id = bridge["osm_id"]
        bridge_length = bridge["bridge_length"]
        input_coordinate = bridge["bridge_coordinate"]
        bridge_id = bridge["bridge_id"]
        half_distance = bridge_length / 2
        point = Point(input_coordinate)
        point_utm = transform(project, point)

        for line_utm, way_id in lines_utm_with_ids:
            if way_id != osm_id:
                continue
            nearest_point_utm = find_nearest_point_on_line(line_utm, point_utm)
            if line_utm.distance(point_utm) < 1:
                (
                    forward_point_utm,
                    forward_way_id,
                    forward_visited,
                    backward_point_utm,
                    backward_way_id,
                    backward_visited,
                ) = calculate_points_on_way(
                    line_utm, nearest_point_utm, half_distance, lines_utm_with_ids
                )

                forward_point, backward_point = _transform_result_points(
                    forward_point_utm, backward_point_utm, inverse_project
                )

                actual_forward_distance = point_utm.distance(forward_point_utm)
                actual_backward_distance = point_utm.distance(backward_point_utm)
                result = _build_result_dict(
                    osm_id, bridge_id, bridge_length, input_coordinate, nearest_point_utm,
                    forward_point, backward_point, forward_way_id, forward_visited,
                    backward_way_id, backward_visited, actual_forward_distance, actual_backward_distance
                )

                # Write the result immediately to the CSV file
                with open("bridge-osm-association-with-split-coords.csv", "a", encoding="utf-8-sig") as rf:
                    writer = csv.writer(rf)
                    writer.writerow(
                        [
                            result["original_osm_id"],
                            result["bridge_id"],
                            result["bridge_coordinate"],
                            result["bridge_length"],
                            result["forward_point"][1],
                            result["forward_point"][0],
                            result["forward_way_id"],
                            result["forward_visited"],
                            result["backward_point"][1],
                            result["backward_point"][0],
                            result["backward_way_id"],
                            result["backward_visited"],
                        ]
                    )

                return result
    except Exception as e:
        logging.error(f"Error processing bridge {bridge['osm_id']}: {e}")
    return None

def process_bridge_data_parallel(bridge_data, lines_with_ids, project, inverse_project):
    try:
        lines_utm_with_ids = [
            (transform(project, line), way_id) for way_id, line in lines_with_ids.items()
        ]
        pool = Pool(cpu_count())
        results = pool.starmap(
            process_single_bridge,
            [
                (bridge, lines_utm_with_ids, project, inverse_project)
                for bridge in bridge_data
            ],
        )
        pool.close()
        pool.join()
        return [result for result in results if result is not None]
    except Exception as e:
        logging.error(f"Error processing bridge data in parallel: {e}")
        return []

def main():
    setup_logging()
    logging.info("Starting processing...")

    args = parse_arguments()

    try:
        # Load the GeoJSON file
        geojson_file_path = args.geojson_file
        geojson_data = load_geojson(geojson_file_path)
        if not geojson_data:
            logging.error("Failed to load GeoJSON data. Exiting.")
            return
        logging.info("Reading OSM data completed.")

        # Load the CSV file containing bridge data
        csv_file_path = args.csv_file
        bridge_data = load_csv(csv_file_path)
        if not bridge_data:
            logging.error("Failed to load bridge data. Exiting.")
            return
        logging.info("Reading bridge data completed.")

        lines_with_ids = {
            feature["properties"]["osm_id"]: LineString(
                feature["geometry"]["coordinates"]
            )
            for feature in geojson_data["features"]
        }
        logging.info("Consolidated lines with IDs.")

        # Define projection transformations
        wgs84 = pyproj.CRS("EPSG:4326")
        utm_zone = pyproj.CRS("EPSG:32616")  # UTM zone for your input coordinates
        project = pyproj.Transformer.from_crs(wgs84, utm_zone, always_xy=True).transform
        inverse_project = pyproj.Transformer.from_crs(
            utm_zone, wgs84, always_xy=True
        ).transform

        # Initialize the results CSV file with headers
        with open(
            "bridge-osm-association-with-split-coords.csv", "w", encoding="utf-8-sig"
        ) as rf:
            writer = csv.writer(rf)
            writer.writerow(
                [
                    "osm_id",
                    "bridge_id",
                    "bridge_coordinate",
                    "bridge_length",
                    "first_split_point_lat",
                    "first_split_point_lon",
                    "osm_id_for_first_split_point",
                    "osm_id_ways_in_between_forwards",
                    "second_split_point_lat",
                    "second_split_point_lon",
                    "osm_id_for_second_split_point",
                    "osm_id_ways_in_between_backwards",
                ]
            )

        # Process each bridge entry in parallel
        process_bridge_data_parallel(
            bridge_data, lines_with_ids, project, inverse_project
        )

        logging.info("Processing completed successfully.")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()
