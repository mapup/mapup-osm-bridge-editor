import * as console from "josm/scriptingconsole";

const LatLon = Java.type("org.openstreetmap.josm.data.coor.LatLon");
const Node = Java.type("org.openstreetmap.josm.data.osm.Node");
const Way = Java.type("org.openstreetmap.josm.data.osm.Way");
const MainApplication = Java.type("org.openstreetmap.josm.gui.MainApplication");
const SplitWayAction = Java.type("org.openstreetmap.josm.actions.SplitWayAction");
const AddCommand = Java.type("org.openstreetmap.josm.command.AddCommand");
const ChangeCommand = Java.type("org.openstreetmap.josm.command.ChangeCommand");
const Geometry = Java.type("org.openstreetmap.josm.tools.Geometry");
const ProjectionRegistry = Java.type("org.openstreetmap.josm.data.projection.ProjectionRegistry");
const UndoRedoHandler = Java.type("org.openstreetmap.josm.data.UndoRedoHandler");
const OsmPrimitiveType = Java.type("org.openstreetmap.josm.data.osm.OsmPrimitiveType");
const ChangePropertyCommand = Java.type("org.openstreetmap.josm.command.ChangePropertyCommand");

console.clear();

// Constants
const BRIDGE_TAG = "bridge";
const BRIDGE_VALUE = "yes";

// Improved coordinate list structure
const coordinatesList = [
  {
    points: [
      { latitude: 37.94437953176317, longitude: -84.66657196098026, wayId: 16223905 },
      { latitude: 37.94451578934621, longitude: -84.666586, wayId: 16223905 }
    ],
    bridge_id: "057C00032N"
  },
];

function getDataSet() {
  return MainApplication.getLayerManager().getEditDataSet();
}
const BBox = Java.type("org.openstreetmap.josm.data.osm.BBox");

function findClosestWay(lat, lon) {
  const dataSet = getDataSet();
  if (!dataSet) {
    console.println("No active data set found.");
    return null;
  }

  const givenPoint = new LatLon(lat, lon);
  const searchDistanceMeters = 5; // 50 meters search radius

  // Calculate the bounding box
  const bbox = calculateBBox(givenPoint, searchDistanceMeters);

  // Use JOSM's built-in search functionality with BBox
  const nearbyWays = dataSet.searchWays(bbox);

  let closestWay = null;
  let minDistance = Infinity;

  const projection = ProjectionRegistry.getProjection();
  const pointEN = projection.latlon2eastNorth(givenPoint);

  for (const way of nearbyWays) {
    const wayNodes = way.getNodes();
    for (let i = 0; i < wayNodes.size() - 1; i++) {
      const node1EN = projection.latlon2eastNorth(wayNodes.get(i).getCoor());
      const node2EN = projection.latlon2eastNorth(wayNodes.get(i + 1).getCoor());

      const closestPointEN = Geometry.closestPointToSegment(node1EN, node2EN, pointEN);
      const segmentDistance = pointEN.distance(closestPointEN);

      if (segmentDistance < minDistance) {
        minDistance = segmentDistance;
        closestWay = way;
      }
    }
  }

  if (closestWay) {
  } else {
    console.println(`No way found within 5 meters of lat: ${lat}, lon: ${lon}`);
  }

  return closestWay;
}

// The calculateBBox function remains the same as in the previous answer

function calculateBBox(center, distanceMeters) {
  const earthRadiusMeters = 6371000; // Earth's radius in meters
  const latRadian = center.lat() * Math.PI / 180;

  // Calculate the latitude difference
  const latDiff = distanceMeters / earthRadiusMeters;
  // Calculate the longitude difference
  const lonDiff = distanceMeters / (earthRadiusMeters * Math.cos(latRadian));
  // Convert differences to degrees
  const latDiffDegrees = latDiff * 180 / Math.PI;
  const lonDiffDegrees = lonDiff * 180 / Math.PI;

  // Calculate the corner points
  const minLat = center.lat() - latDiffDegrees;
  const maxLat = center.lat() + latDiffDegrees;
  const minLon = center.lon() - lonDiffDegrees;
  const maxLon = center.lon() + lonDiffDegrees;
  // Create and return the BBox
  return new BBox(new LatLon(minLat, minLon), new LatLon(maxLat, maxLon));
}

function addNodeToWay(way, latLon, isFirstPoint, preExistingNodeId) {
  const dataSet = getDataSet();
  const projection = ProjectionRegistry.getProjection();
  const wayNodes = way.getNodes();
  let closestIndex = -1;
  let closestDistance = Infinity;
  let closestLatLon = latLon;

  for (let i = 0; i < wayNodes.size() - 1; i++) {
    const segmentStart = projection.latlon2eastNorth(wayNodes.get(i).getCoor());
    const segmentEnd = projection.latlon2eastNorth(wayNodes.get(i + 1).getCoor());
    const point = Geometry.closestPointToSegment(
      segmentStart,
      segmentEnd,
      projection.latlon2eastNorth(latLon)
    );
    const pointLatLon = projection.eastNorth2latlon(point);
    const distance = latLon.greatCircleDistance(pointLatLon);
    if (distance < closestDistance) {
      closestDistance = distance;
      closestIndex = i;
      closestLatLon = pointLatLon;
    }
  }

  if (closestIndex === -1) {
    console.println("Failed to find a suitable segment to insert the node.");
    return null;
  }

  const closestNode = new Node(closestLatLon);
  const newWayNodes = new java.util.ArrayList(wayNodes);
  newWayNodes.add(closestIndex + 1, closestNode);

  const newWay = new Way(way);
  newWay.setNodes(newWayNodes);

  UndoRedoHandler.getInstance().add(new AddCommand(dataSet, closestNode));
  UndoRedoHandler.getInstance().add(new ChangeCommand(way, newWay));

  console.println(`Node added at latitude: ${latLon.lat()}, longitude: ${latLon.lon()} and Node ID: ${closestNode.getId()}`);

  return closestNode;
}

function isNodeAtEndpoints(wayNodes, startNode, endNode) {
  return (wayNodes[0] === startNode && wayNodes[wayNodes.length - 1] === endNode) ||
    (wayNodes[0] === endNode && wayNodes[wayNodes.length - 1] === startNode);
}

function tagBridgeWay(startNode, endNode, bridgeId) {

  const dataSet = getDataSet();
  if (!dataSet) {
    console.println("No active data set found.");
    return;
  }
  if (startNode) {
    console.println("Start node found");
    dataSet.setSelected(startNode);
    SplitWayAction.runOn(dataSet);
  }
  if (endNode) {
    console.println("End node found");
    dataSet.setSelected(endNode);
    SplitWayAction.runOn(dataSet);
  }
  const selectedWays = dataSet.getSelectedWays();
  for (const way of selectedWays) {
    const wayNodes = way.getNodes();
    let matched = false;
    if (startNode && endNode) {
      matched = isNodeAtEndpoints(wayNodes, startNode, endNode);
    } else if (endNode) {
      matched = wayNodes[wayNodes.length - 1] === endNode;
    } else if (startNode) {
      matched = wayNodes[0] === startNode;
    }
    if (matched) {
      const addTagCommand = new ChangePropertyCommand(way, BRIDGE_TAG, BRIDGE_VALUE);
      UndoRedoHandler.getInstance().add(addTagCommand);
      const addBridgeIdCommand = new ChangePropertyCommand(way, "bridge:id", bridgeId);
      UndoRedoHandler.getInstance().add(addBridgeIdCommand);
      console.println(`Bridge way ${way.getId()} tagged successfully.`);
      return;
    }
  }
  console.println("Could not identify a unique way among the selected ones connecting the specified nodes as a bridge.");
}

function handlePoint(point, i, points, way, wayId, addNodeToWayFn, LatLonType) {
  const closestWayId = way.getId();
  if (closestWayId !== wayId && closestWayId >= 0 && way.hasTag("bridge:id")) {
    return { skip: true };
  }
  if (point.latitude == -1 && point.longitude == -1) {
    return { skip: true };
  }
  const node = addNodeToWayFn(way, new LatLonType(point.latitude, point.longitude));
  return { skip: false, node, isFirst: i === 0, isLast: i === points.length - 1 };
}

function processCoordinateSet(coordinateSet) {
  const dataSet = getDataSet();
  if (!dataSet) {
    console.println("No active data set found.");
    return;
  }

  const { points, bridge_id } = coordinateSet;
  const wayId = points[0].wayId;
  let startNode, endNode = null;

  for (let i = 0; i < points.length; i++) {
    const point = points[i];
    const way = findClosestWay(point.latitude, point.longitude);

    if (!way) {
      console.println(`Way not found for point ${i}`);
      return;
    }
    const result = handlePoint(point, i, points, way, wayId, addNodeToWay, LatLon);
    if (result.skip) continue;
    if (result.isFirst) endNode = result.node;
    if (result.isLast) startNode = result.node;
  }

  if (startNode || endNode) {
    tagBridgeWay(startNode, endNode, bridge_id);
  } else {
    const way = dataSet.getPrimitiveById(wayId, OsmPrimitiveType.WAY);
    const addTagCommand = new ChangePropertyCommand(way, BRIDGE_TAG, BRIDGE_VALUE);
    UndoRedoHandler.getInstance().add(addTagCommand);
    const addBridgeIdCommand = new ChangePropertyCommand(way, "bridge:id", bridge_id);
    UndoRedoHandler.getInstance().add(addBridgeIdCommand);
  }

  MainApplication.getMap().mapView.repaint();
}

// Main execution
try {
  for (const coordinateSet of coordinatesList) {
    processCoordinateSet(coordinateSet);
  }
} catch (error) {
  console.println(`An error occurred: ${error.message}`);
}