"""Interference graph construction, channel assignment and colouring bounds."""
from __future__ import annotations

import math
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .model import Environment, Transmitter

Adjacency = Dict[str, Set[str]]


def build_interference_graph(
    environment: Environment,
    transmitters: Sequence[Transmitter],
    isolation_margin_db: float = 18.0,
    forced_edges: Iterable[Tuple[str, str]] = (),
) -> Adjacency:
    """Connect transmitters whose co-channel leakage rises above the noise floor.

    An edge means "these two must not share a channel". The test is symmetric:
    a pair is linked if either receiver would see the other above the margin.
    """
    names = [t.name for t in transmitters]
    graph: Adjacency = {name: set() for name in names}
    for index, first in enumerate(transmitters):
        for second in transmitters[index + 1 :]:
            if environment.potential_interference_db(first, second) >= isolation_margin_db:
                graph[first.name].add(second.name)
                graph[second.name].add(first.name)
    for left, right in forced_edges:
        if left not in graph or right not in graph:
            raise KeyError("forced edge references unknown transmitter: %s-%s" % (left, right))
        graph[left].add(right)
        graph[right].add(left)
    return graph


def degrees(graph: Adjacency) -> Dict[str, int]:
    return {name: len(neighbours) for name, neighbours in graph.items()}


def greedy_coloring(graph: Adjacency, order: Optional[Sequence[str]] = None) -> Dict[str, int]:
    if order is None:
        order = sorted(graph, key=lambda name: (-len(graph[name]), name))
    colors: Dict[str, int] = {}
    for name in order:
        used = {colors[n] for n in graph[name] if n in colors}
        channel = 0
        while channel in used:
            channel += 1
        colors[name] = channel
    return colors


def dsatur_coloring(graph: Adjacency) -> Dict[str, int]:
    """Degree-of-saturation colouring: pick the most constrained vertex first."""
    names = sorted(graph)
    colors: Dict[str, int] = {}
    saturation: Dict[str, Set[int]] = {name: set() for name in names}
    while len(colors) < len(names):
        candidates = [name for name in names if name not in colors]
        name = max(candidates, key=lambda n: (len(saturation[n]), len(graph[n]), -names.index(n)))
        used = saturation[name]
        channel = 0
        while channel in used:
            channel += 1
        colors[name] = channel
        for neighbour in graph[name]:
            if neighbour not in colors:
                saturation[neighbour].add(channel)
    return colors


def max_clique(graph: Adjacency) -> List[str]:
    """Bron-Kerbosch with pivoting; a clique lower-bounds the channel count."""
    best: List[str] = []

    def expand(current: Set[str], candidates: Set[str], excluded: Set[str]) -> None:
        nonlocal best
        if not candidates and not excluded:
            if len(current) > len(best):
                best = sorted(current)
            return
        pivot = max(candidates | excluded, key=lambda v: len(graph[v] & candidates), default=None)
        blocked = graph[pivot] if pivot is not None else set()
        for vertex in sorted(candidates - blocked):
            expand(current | {vertex}, candidates & graph[vertex], excluded & graph[vertex])
            candidates.discard(vertex)
            excluded.add(vertex)

    expand(set(), set(graph), set())
    return best


def validate_coloring(graph: Adjacency, colors: Dict[str, int]) -> None:
    missing = set(graph) - set(colors)
    if missing:
        raise ValueError("no channel assigned to: %s" % ", ".join(sorted(missing)))
    for name, neighbours in graph.items():
        for neighbour in neighbours:
            if colors[name] == colors[neighbour]:
                raise ValueError("%s and %s share channel %d" % (name, neighbour, colors[name]))


def channel_count(colors: Dict[str, int]) -> int:
    return len(set(colors.values())) if colors else 0


def plan_channels(
    environment: Environment,
    transmitters: Sequence[Transmitter],
    isolation_margin_db: float = 18.0,
    forced_edges: Iterable[Tuple[str, str]] = (),
) -> Dict[str, object]:
    """Build the interference graph and assign channels, reporting both bounds."""
    graph = build_interference_graph(environment, transmitters, isolation_margin_db, forced_edges)
    by_dsatur = dsatur_coloring(graph)
    by_greedy = greedy_coloring(graph)
    validate_coloring(graph, by_dsatur)
    clique = max_clique(graph)
    lower_bound = max(1, len(clique)) if graph else 0
    upper_bound = channel_count(by_dsatur)

    positions = {t.name: t for t in transmitters}
    reuse = []
    names = sorted(graph)
    for index, first in enumerate(names):
        for second in names[index + 1 :]:
            if by_dsatur[first] != by_dsatur[second]:
                continue
            distance = math.hypot(
                positions[first].x - positions[second].x,
                positions[first].y - positions[second].y,
            )
            reuse.append((first, second, round(distance)))
    return {
        "graph": graph,
        "channels": by_dsatur,
        "greedy_channels": by_greedy,
        "greedy_count": channel_count(by_greedy),
        "channel_count": upper_bound,
        "lower_bound": lower_bound,
        "clique": clique,
        "optimal": upper_bound == lower_bound,
        "edges": sum(len(v) for v in graph.values()) // 2,
        "reuse_pairs": sorted(reuse, key=lambda item: item[2]),
    }


def graph_density(graph: Adjacency) -> float:
    nodes = len(graph)
    if nodes < 2:
        return 0.0
    return sum(len(v) for v in graph.values()) / (nodes * (nodes - 1))
