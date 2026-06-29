import sys
import os
import unittest
import importlib.util

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_script_path = os.path.join(
    REPO_ROOT,
    "split-ways-using-JOSM",
    "split_ways_add_bridge_tag",
    "02-shortest-route-between-two-ways.py",
)
spec = importlib.util.spec_from_file_location("shortest_route", _script_path)
shortest_route = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shortest_route)


class TestBuildGraph(unittest.TestCase):
    def test_simple_two_way_graph(self):
        ways = {
            1: [100, 101, 102],
            2: [102, 103],
        }
        G = shortest_route.build_graph(ways)
        assert G.has_edge(100, 101)
        assert G.has_edge(101, 102)
        assert G.has_edge(102, 103)
        assert G[100][101]["way_id"] == 1
        assert G[102][103]["way_id"] == 2

    def test_single_node_way_produces_no_edges(self):
        ways = {1: [100]}
        G = shortest_route.build_graph(ways)
        assert G.number_of_edges() == 0

    def test_empty_ways(self):
        G = shortest_route.build_graph({})
        assert G.number_of_nodes() == 0


class TestFindShortestPath(unittest.TestCase):
    def _build(self, ways):
        return shortest_route.build_graph(ways)

    def test_direct_path_same_way(self):
        ways = {1: [100, 101, 102]}
        G = self._build(ways)
        path = shortest_route.find_shortest_path(G, 1, 1, ways)
        assert path == [1]

    def test_path_across_two_ways(self):
        ways = {1: [100, 101], 2: [101, 102]}
        G = self._build(ways)
        path = shortest_route.find_shortest_path(G, 1, 2, ways)
        assert 1 in path
        assert 2 in path

    def test_disconnected_raises(self):
        ways = {1: [100, 101], 2: [200, 201]}
        G = self._build(ways)
        import networkx as nx
        with self.assertRaises(nx.NetworkXNoPath):
            shortest_route.find_shortest_path(G, 1, 2, ways)


if __name__ == "__main__":
    unittest.main()
