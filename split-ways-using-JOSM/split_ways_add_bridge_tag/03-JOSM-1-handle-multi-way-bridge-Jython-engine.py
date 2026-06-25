from org.openstreetmap.josm.gui import MainApplication
from org.openstreetmap.josm.data.coor import LatLon
from org.openstreetmap.josm.data.osm import Node, Way, OsmPrimitiveType
from org.openstreetmap.josm.actions import SplitWayAction
from org.openstreetmap.josm.command import AddCommand, ChangeCommand
from org.openstreetmap.josm.tools import Geometry
from org.openstreetmap.josm.data.projection import ProjectionRegistry
from org.openstreetmap.josm.data import UndoRedoHandler
from org.openstreetmap.josm.command import ChangePropertyCommand
import java.util.ArrayList

# Constants
BRIDGE_TAG = "bridge"
BRIDGE_VALUE = "yes"
BRIDGE_ID_TAG = "bridge:id"

coordinatesList = [
    {
        "points": [
            {"latitude": 36.6490109994807, "longitude": -89.06306871832646, "wayId": 16208279},
            {"latitude": 36.649008842327014, "longitude": -89.06324527869246, "wayId": 16208919},
        ],
        "additionalBridgeWayIds": [],
        "bridgeId": "098C00033N"
    }
]

def tag_way_as_bridge(way, bridge_id):
    add_tag_command = ChangePropertyCommand(way, BRIDGE_TAG, BRIDGE_VALUE)
    UndoRedoHandler.getInstance().add(add_tag_command)
    add_bridge_id_command = ChangePropertyCommand(way, BRIDGE_ID_TAG, bridge_id)
    UndoRedoHandler.getInstance().add(add_bridge_id_command)
    print("Way %d tagged successfully." % way.getId())

def get_data_set():
    return MainApplication.getLayerManager().getEditDataSet()

def _tag_bridge_way_after_split(data_set, is_first_point, closest_node, pre_existing_node, bridge_id):
    selected_ways = data_set.getSelectedWays()
    for selected_way in selected_ways:
        selected_way_nodes = selected_way.getNodes()
        is_bridge_way = False

        if is_first_point:
            is_bridge_way = (selected_way_nodes[0] == closest_node and selected_way_nodes[-1] == pre_existing_node) or \
                            (selected_way_nodes[-1] == closest_node and selected_way_nodes[0] == pre_existing_node)
        else:
            is_bridge_way = (selected_way_nodes[0] == pre_existing_node and selected_way_nodes[-1] == closest_node) or \
                            (selected_way_nodes[-1] == pre_existing_node and selected_way_nodes[0] == closest_node)

        if is_bridge_way:
            tag_way_as_bridge(selected_way, bridge_id)
            break

def add_node_to_way(way, lat_lon, is_first_point, pre_existing_node, bridge_id):
    data_set = get_data_set()
    projection = ProjectionRegistry.getProjection()
    way_nodes = way.getNodes()
    closest_index = -1
    closest_distance = float('inf')
    closest_lat_lon = lat_lon

    for i in range(len(way_nodes) - 1):
        segment_start = projection.latlon2eastNorth(way_nodes[i].getCoor())
        segment_end = projection.latlon2eastNorth(way_nodes[i + 1].getCoor())
        point = Geometry.closestPointToSegment(
            segment_start,
            segment_end,
            projection.latlon2eastNorth(lat_lon)
        )
        point_lat_lon = projection.eastNorth2latlon(point)
        distance = lat_lon.greatCircleDistance(point_lat_lon)
        if distance < closest_distance:
            closest_distance = distance
            closest_index = i
            closest_lat_lon = point_lat_lon

    if closest_index == -1:
        print("Failed to find a suitable segment to insert the node.")
        return None

    closest_node = Node(closest_lat_lon)
    new_way_nodes = java.util.ArrayList(way_nodes)
    new_way_nodes.add(closest_index + 1, closest_node)

    new_way = Way(way)
    new_way.setNodes(new_way_nodes)

    UndoRedoHandler.getInstance().add(AddCommand(data_set, closest_node))
    UndoRedoHandler.getInstance().add(ChangeCommand(way, new_way))

    data_set.setSelected(closest_node)
    SplitWayAction.runOn(data_set)

    print("Node added at latitude: %f, longitude: %f and Node ID: %d" % (lat_lon.lat(), lat_lon.lon(), closest_node.getId()))

    _tag_bridge_way_after_split(data_set, is_first_point, closest_node, pre_existing_node, bridge_id)

    return closest_node

def tag_additional_bridge_ways(additional_bridge_way_ids, bridge_id):
    data_set = get_data_set()
    for way_id in additional_bridge_way_ids:
        way = data_set.getPrimitiveById(way_id, OsmPrimitiveType.WAY)
        if way:
            tag_way_as_bridge(way, bridge_id)
        else:
            print("Additional bridge way %d not found." % way_id)

def _process_no_additional_ways(current_way, next_way, current_point, next_point, bridge_id):
    current_way_nodes = current_way.getNodes()
    next_way_nodes = next_way.getNodes()

    common_node = None
    if current_way_nodes[0] == next_way_nodes[0] or current_way_nodes[0] == next_way_nodes[-1]:
        common_node = current_way_nodes[0]
    elif current_way_nodes[-1] == next_way_nodes[0] or current_way_nodes[-1] == next_way_nodes[-1]:
        common_node = current_way_nodes[-1]

    if current_point["latitude"] == -1 and current_point["longitude"] == -1:
        tag_way_as_bridge(current_way, bridge_id)
    else:
        add_node_to_way(current_way, LatLon(current_point["latitude"], current_point["longitude"]), True, common_node, bridge_id)

    if next_point["latitude"] == -1 and next_point["longitude"] == -1:
        tag_way_as_bridge(next_way, bridge_id)
    else:
        add_node_to_way(next_way, LatLon(next_point["latitude"], next_point["longitude"]), False, common_node, bridge_id)

def _process_with_additional_ways(current_way, next_way, current_point, next_point, bridge_id, additional_bridge_way_ids, data_set):
    current_way_nodes = current_way.getNodes()
    additional_bridge_way = data_set.getPrimitiveById(additional_bridge_way_ids[0], OsmPrimitiveType.WAY)
    additional_bridge_way_nodes = additional_bridge_way.getNodes()

    common_node = None
    if current_way_nodes[0] == additional_bridge_way_nodes[0] or current_way_nodes[0] == additional_bridge_way_nodes[-1]:
        common_node = current_way_nodes[0]
    elif current_way_nodes[-1] == additional_bridge_way_nodes[0] or current_way_nodes[-1] == additional_bridge_way_nodes[-1]:
        common_node = current_way_nodes[-1]

    if current_point["latitude"] == -1 and current_point["longitude"] == -1:
        add_tag_command = ChangePropertyCommand(current_way, BRIDGE_TAG, BRIDGE_VALUE)
        UndoRedoHandler.getInstance().add(add_tag_command)
    else:
        add_node_to_way(current_way, LatLon(current_point["latitude"], current_point["longitude"]), True, common_node, bridge_id)

    next_way_nodes = next_way.getNodes()
    additional_bridge_way = data_set.getPrimitiveById(additional_bridge_way_ids[-1], OsmPrimitiveType.WAY)
    additional_bridge_way_nodes = additional_bridge_way.getNodes()

    common_node = None
    if next_way_nodes[0] == additional_bridge_way_nodes[0] or next_way_nodes[0] == additional_bridge_way_nodes[-1]:
        common_node = next_way_nodes[0]
    elif next_way_nodes[-1] == additional_bridge_way_nodes[0] or next_way_nodes[-1] == additional_bridge_way_nodes[-1]:
        common_node = next_way_nodes[-1]

    if current_point["latitude"] == -1 and current_point["longitude"] == -1:
        add_tag_command = ChangePropertyCommand(next_way, BRIDGE_TAG, BRIDGE_VALUE)
        UndoRedoHandler.getInstance().add(add_tag_command)
    else:
        add_node_to_way(next_way, LatLon(next_point["latitude"], next_point["longitude"]), False, common_node, bridge_id)

def process_coordinate_set(coordinate_set):
    data_set = get_data_set()
    if not data_set:
        print("No active data set found.")
        return

    points = coordinate_set["points"]
    additional_bridge_way_ids = coordinate_set["additionalBridgeWayIds"]
    bridge_id = coordinate_set["bridgeId"]

    current_point = points[0]
    next_point = points[1]

    current_way = data_set.getPrimitiveById(current_point["wayId"], OsmPrimitiveType.WAY)
    next_way = data_set.getPrimitiveById(next_point["wayId"], OsmPrimitiveType.WAY)

    if not current_way or not next_way:
        print("Way not found for point %d or %d" % (0, 1))

    if len(additional_bridge_way_ids) == 0:
        _process_no_additional_ways(current_way, next_way, current_point, next_point, bridge_id)
    else:
        _process_with_additional_ways(current_way, next_way, current_point, next_point, bridge_id, additional_bridge_way_ids, data_set)

    tag_additional_bridge_ways(additional_bridge_way_ids, bridge_id)

    MainApplication.getMap().mapView.repaint()

# Main execution
try:
    for coordinate_set in coordinatesList:
        process_coordinate_set(coordinate_set)
except Exception as error:
    print("An error occurred: %s" % str(error))
