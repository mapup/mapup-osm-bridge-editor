import sys
import os
import unittest
import importlib.util
from unittest.mock import patch, MagicMock

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


class TestWayHandler(unittest.TestCase):
    def test_init_has_empty_ways_and_nodes(self):
        handler = shortest_route.WayHandler()
        assert handler.ways == {}
        assert handler.nodes == set()

    def test_way_method_stores_node_refs(self):
        handler = shortest_route.WayHandler()
        mock_way = MagicMock()
        mock_way.id = 42
        node1 = MagicMock()
        node1.ref = 100
        node2 = MagicMock()
        node2.ref = 101
        mock_way.nodes = [node1, node2]
        handler.way(mock_way)
        assert 42 in handler.ways
        assert handler.ways[42] == [100, 101]


class TestMain(unittest.TestCase):
    def test_main_calls_handler_and_prints(self):
        ways = {1: [100, 101], 2: [101, 102]}

        def fake_apply_file(self_handler, path):
            self_handler.ways = ways

        with patch.object(shortest_route.WayHandler, 'apply_file', fake_apply_file), \
             patch('builtins.print'):
            # start_way=1, end_way=2 → path goes 100→101→102, way_path=[1, 2]
            # pop(0) removes 1, leaving [2]
            shortest_route.main("any.osm", 1, 2)


class TestFindShortestPath(unittest.TestCase):
    def _build(self, ways):
        return shortest_route.build_graph(ways)

    def test_direct_path_same_way_returns_empty(self):
        # start_node == end_node → nx.shortest_path returns [node] → no edges → []
        ways = {1: [100, 101, 102]}
        G = self._build(ways)
        path = shortest_route.find_shortest_path(G, 1, 1, ways)
        assert path == []

    def test_path_across_two_ways(self):
        # Ways share no common node; connected via way 3
        # start_node=200 (way 2), end_node=100 (way 1)
        # path: 200→101 (way 3) → 101→100 (way 1) → way_path=[3, 1]
        ways = {1: [100, 101], 2: [200, 201], 3: [101, 200]}
        G = self._build(ways)
        path = shortest_route.find_shortest_path(G, 2, 1, ways)
        assert len(path) >= 1
        assert 1 in path

    def test_disconnected_raises(self):
        ways = {1: [100, 101], 2: [200, 201]}
        G = self._build(ways)
        import networkx as nx
        with self.assertRaises(nx.NetworkXNoPath):
            shortest_route.find_shortest_path(G, 1, 2, ways)


if __name__ == "__main__":
    unittest.main()
