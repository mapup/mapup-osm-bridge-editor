import osmium
import networkx as nx

class WayHandler(osmium.SimpleHandler):
    def __init__(self):
        super(WayHandler, self).__init__()
        self.ways = {}
        self.nodes = set()

    def way(self, w):
        self.ways[w.id] = [n.ref for n in w.nodes]
        self.nodes.update(w.nodes)

def build_graph(ways):
    G = nx.Graph()
    for way_id, nodes in ways.items():
        for i in range(len(nodes) - 1):
            G.add_edge(nodes[i], nodes[i+1], way_id=way_id)
    return G

def find_shortest_path(graph, start_way, end_way, ways):
    start_node = ways[start_way][0]
    end_node = ways[end_way][0]

    path = nx.shortest_path(graph, start_node, end_node)

    way_path = []
    current_way = None
    for i in range(len(path) - 1):
        edge_data = graph.get_edge_data(path[i], path[i+1])
        if edge_data['way_id'] != current_way:
            current_way = edge_data['way_id']
            way_path.append(current_way)

    return way_path

def main(osm_file, start_way_id, end_way_id):
    handler = WayHandler()
    handler.apply_file(osm_file)
    
    graph = build_graph(handler.ways)

    shortest_path = find_shortest_path(graph, start_way_id, end_way_id, handler.ways)
    
    print(f"Shortest path from {start_way_id} to {end_way_id}:")
    # print(f"{start_way_id}, {', '.join(map(str, shortest_path))}, {end_way_id}")
    #remove first wayId
    shortest_path.pop(0)
    print(shortest_path)

if __name__ == "__main__":
    osm_file = "./kentucky-2-way-bridge.osm"  # Path to the OSM file
    start_way_id = 17561921  # Replace with your given_Way_ID_1
    end_way_id = 97759371    # Replace with your given_way_Id_2
    main(osm_file, start_way_id, end_way_id)