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
const BRIDGE_ID_TAG = "bridge:id";

// Improved coordinate list structure
const coordinatesList = [
  {
    points: [
      { latitude: 36.6490109994807, longitude: -89.06306871832646, wayId: 16208279 },
      { latitude: 36.649008842327014, longitude: -89.06324527869246, wayId: 16208919 },
    ],
    additionalBridgeWayIds: [],
    bridgeId : "057C00032N"
  }
];

function getDataSet() {
  return MainApplication.getLayerManager().getEditDataSet();
}

function tagWays(way, bridgeId){
  const addTagCommand = new ChangePropertyCommand(way, BRIDGE_TAG, BRIDGE_VALUE);
  UndoRedoHandler.getInstance().add(addTagCommand);
  const addBridgeIdTagCommand = new ChangePropertyCommand(way, BRIDGE_ID_TAG, bridgeId);
  UndoRedoHandler.getInstance().add(addBridgeIdTagCommand);
  console.println(`Bridge way ${way.getId()} tagged successfully.`);
}

function addNodeToWay(way, latLon, isFirstPoint, preExistingNode, bridgeId) {
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

  dataSet.setSelected(closestNode);
  SplitWayAction.runOn(dataSet);

  console.println(`Node added at latitude: ${latLon.lat()}, longitude: ${latLon.lon()} and Node ID: ${closestNode.getId()}`);

  // Tag the appropriate way as a bridge
  const selectedWays = dataSet.getSelectedWays();
  for (const selectedWay of selectedWays) {
    const selectedWayNodes = selectedWay.getNodes();
    let isBridgeWay = false;

    if (isFirstPoint) {
      isBridgeWay = (selectedWayNodes.get(0) === closestNode && selectedWayNodes.get(selectedWayNodes.size() - 1) === preExistingNode) ||
        (selectedWayNodes.get(selectedWayNodes.size() - 1) === closestNode && selectedWayNodes.get(0) === preExistingNode);
    } else {
      isBridgeWay = (selectedWayNodes.get(0) === preExistingNode && selectedWayNodes.get(selectedWayNodes.size() - 1) === closestNode) ||
        (selectedWayNodes.get(selectedWayNodes.size() - 1) === preExistingNode && selectedWayNodes.get(0) === closestNode);
    }

    if (isBridgeWay) {
      tagWays(selectedWay, bridgeId);
      break;
    }
  }

  return closestNode;
}

function tagAdditionalBridgeWays(additionalBridgeWayIds) {
  const dataSet = getDataSet();
  for (const wayId of additionalBridgeWayIds) {
    const way = dataSet.getPrimitiveById(wayId, OsmPrimitiveType.WAY);
    if (way) {
      const addTagCommand = new ChangePropertyCommand(way, BRIDGE_TAG, BRIDGE_VALUE);
      UndoRedoHandler.getInstance().add(addTagCommand);
      console.println(`Additional bridge way ${wayId} tagged successfully.`);
    } else {
      console.println(`Additional bridge way ${wayId} not found.`);
    }
  }
}

function findCommonNode(wayA, wayB) {
  const nodesA = wayA.getNodes();
  const nodesB = wayB.getNodes();
  const firstA = nodesA.get(0).getId();
  const lastA = nodesA.get(nodesA.size() - 1).getId();
  if (firstA === nodesB.get(0).getId() || firstA === nodesB.get(nodesB.size() - 1).getId()) {
    return nodesA.get(0);
  }
  if (lastA === nodesB.get(0).getId() || lastA === nodesB.get(nodesB.size() - 1).getId()) {
    return nodesA.get(nodesA.size() - 1);
  }
  return null;
}

function tagOrAddNode(way, point, isFirst, commonNode, bridgeId) {
  if (point.latitude === -1 && point.longitude === -1) {
    tagWays(way, bridgeId);
  } else {
    addNodeToWay(way, new LatLon(point.latitude, point.longitude), isFirst, commonNode, bridgeId);
  }
}

function processNoAdditionalWays(currentWay, nextWay, currentPoint, nextPoint, bridgeId) {
  const commonNode = findCommonNode(currentWay, nextWay);
  tagOrAddNode(currentWay, currentPoint, true, commonNode, bridgeId);
  tagOrAddNode(nextWay, nextPoint, false, commonNode, bridgeId);
}

function processWithAdditionalWays(dataSet, currentWay, nextWay, currentPoint, nextPoint, bridgeId, additionalBridgeWayIds) {
  const firstAdditionalWay = dataSet.getPrimitiveById(additionalBridgeWayIds[0], OsmPrimitiveType.WAY);
  const commonNodeCurrent = findCommonNode(currentWay, firstAdditionalWay);
  tagOrAddNode(currentWay, currentPoint, true, commonNodeCurrent, bridgeId);

  const lastAdditionalWay = dataSet.getPrimitiveById(additionalBridgeWayIds[additionalBridgeWayIds.length - 1], OsmPrimitiveType.WAY);
  const commonNodeNext = findCommonNode(nextWay, lastAdditionalWay);
  tagOrAddNode(nextWay, nextPoint, false, commonNodeNext, bridgeId);
}

function processCoordinateSet(coordinateSet) {
  const dataSet = getDataSet();
  if (!dataSet) {
    console.println("No active data set found.");
    return;
  }

  const { points, additionalBridgeWayIds } = coordinateSet;
  const currentPoint = points[0];
  const nextPoint = points[1];
  const bridgeId = coordinateSet.bridgeId;
  const currentWay = dataSet.getPrimitiveById(currentPoint.wayId, OsmPrimitiveType.WAY);
  const nextWay = dataSet.getPrimitiveById(nextPoint.wayId, OsmPrimitiveType.WAY);

  if (!currentWay || !nextWay) {
    console.println(`Way not found for point 0 or 1`);
    return;
  }

  if (additionalBridgeWayIds.length === 0) {
    processNoAdditionalWays(currentWay, nextWay, currentPoint, nextPoint, bridgeId);
  } else {
    processWithAdditionalWays(dataSet, currentWay, nextWay, currentPoint, nextPoint, bridgeId, additionalBridgeWayIds);
  }

  tagAdditionalBridgeWays(additionalBridgeWayIds);

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