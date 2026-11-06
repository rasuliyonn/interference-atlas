import unittest

from atlas.graph import (
    build_interference_graph,
    channel_count,
    dsatur_coloring,
    greedy_coloring,
    max_clique,
    plan_channels,
    validate_coloring,
)
from atlas.model import Environment, Transmitter
from atlas.plan import demo_plan


def graph_from(edges, nodes):
    graph = {node: set() for node in nodes}
    for left, right in edges:
        graph[left].add(right)
        graph[right].add(left)
    return graph


class GraphBuildingTests(unittest.TestCase):
    def test_close_sites_share_an_edge_and_far_sites_do_not(self):
        env = Environment(model="free-space")
        near = [Transmitter("A", 0, 0, 30), Transmitter("B", 500, 0, 30)]
        far = [Transmitter("A", 0, 0, 30), Transmitter("B", 90_000, 0, 30)]
        self.assertIn("B", build_interference_graph(env, near)["A"])
        self.assertNotIn("B", build_interference_graph(env, far)["A"])

    def test_forced_edges_are_symmetric_and_validated(self):
        env = Environment()
        sites = [Transmitter("A", 0, 0), Transmitter("B", 90_000, 0)]
        graph = build_interference_graph(env, sites, forced_edges=[("A", "B")])
        self.assertIn("B", graph["A"])
        self.assertIn("A", graph["B"])
        with self.assertRaises(KeyError):
            build_interference_graph(env, sites, forced_edges=[("A", "Z")])

    def test_demo_graph_is_connected_but_not_complete(self):
        plan = demo_plan()
        graph = build_interference_graph(plan.environment, plan.transmitters)
        node_count = len(graph)
        edges = sum(len(v) for v in graph.values()) // 2
        self.assertGreater(edges, node_count - 1)
        self.assertLess(edges, node_count * (node_count - 1) // 2)
        self.assertTrue(all(graph[name] for name in graph))


class ColouringTests(unittest.TestCase):
    def test_triangle_needs_three_channels(self):
        graph = graph_from([("A", "B"), ("B", "C"), ("C", "A")], "ABC")
        colours = dsatur_coloring(graph)
        validate_coloring(graph, colours)
        self.assertEqual(channel_count(colours), 3)
        self.assertEqual(len(max_clique(graph)), 3)

    def test_odd_cycle_needs_three_channels(self):
        nodes = list("ABCDE")
        edges = [("A", "B"), ("B", "C"), ("C", "D"), ("D", "E"), ("E", "A")]
        graph = graph_from(edges, nodes)
        self.assertEqual(channel_count(dsatur_coloring(graph)), 3)
        self.assertEqual(len(max_clique(graph)), 2)

    def test_bipartite_graph_needs_two_channels(self):
        graph = graph_from([("A", "C"), ("A", "D"), ("B", "C"), ("B", "D")], "ABCD")
        self.assertEqual(channel_count(dsatur_coloring(graph)), 2)

    def test_complete_graph_needs_one_channel_per_node(self):
        nodes = list("ABCDE")
        edges = [(a, b) for i, a in enumerate(nodes) for b in nodes[i + 1 :]]
        graph = graph_from(edges, nodes)
        colours = dsatur_coloring(graph)
        self.assertEqual(channel_count(colours), 5)
        validate_coloring(graph, colours)

    def test_colouring_never_beats_the_clique_bound(self):
        plan = demo_plan()
        result = plan_channels(plan.environment, plan.transmitters)
        validate_coloring(result["graph"], result["channels"])
        self.assertGreaterEqual(result["channel_count"], result["lower_bound"])
        self.assertGreaterEqual(result["greedy_count"], result["lower_bound"])
        self.assertLessEqual(result["lower_bound"], len(result["graph"]))
        for left, right in result["graph"].items():
            for neighbour in right:
                self.assertNotEqual(result["channels"][left], result["channels"][neighbour])

    def test_invalid_assignment_is_caught(self):
        graph = graph_from([("A", "B")], "AB")
        with self.assertRaises(ValueError):
            validate_coloring(graph, {"A": 0, "B": 0})
        with self.assertRaises(ValueError):
            validate_coloring(graph, {"A": 0})

    def test_greedy_and_dsatur_both_produce_valid_colourings(self):
        plan = demo_plan()
        graph = build_interference_graph(plan.environment, plan.transmitters)
        validate_coloring(graph, greedy_coloring(graph))
        validate_coloring(graph, dsatur_coloring(graph))


if __name__ == "__main__":
    unittest.main()
