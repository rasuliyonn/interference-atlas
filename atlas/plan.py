"""Spectrum plans: JSON loading, validation and the built-in demo scenario."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .model import Environment, Transmitter

MAX_TRANSMITTERS = 512


@dataclass(frozen=True)
class Plan:
    environment: Environment
    transmitters: Tuple[Transmitter, ...]
    width_m: float
    height_m: float
    forced_edges: Tuple[Tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.transmitters:
            raise ValueError("plan needs at least one transmitter")
        if len(self.transmitters) > MAX_TRANSMITTERS:
            raise ValueError("plan exceeds %d transmitters" % MAX_TRANSMITTERS)
        names = [t.name for t in self.transmitters]
        if len(set(names)) != len(names):
            raise ValueError("transmitter names must be unique")
        for tower in self.transmitters:
            if not (0.0 <= tower.x <= self.width_m and 0.0 <= tower.y <= self.height_m):
                raise ValueError(
                    "%s is outside the %.0fx%.0f m planning area"
                    % (tower.name, self.width_m, self.height_m)
                )


def plan_from_dict(payload: Dict[str, Any]) -> Plan:
    if "transmitters" not in payload:
        raise ValueError("plan JSON needs a 'transmitters' array")
    environment = Environment(**payload.get("environment", {}))
    towers = tuple(Transmitter(**item) for item in payload["transmitters"])
    forced = tuple(tuple(pair) for pair in payload.get("forced_edges", ()))
    return Plan(
        environment=environment,
        transmitters=towers,
        width_m=float(payload.get("width_m", 10000.0)),
        height_m=float(payload.get("height_m", 10000.0)),
        forced_edges=forced,
    )


def load_plan(path: str) -> Plan:
    with open(path, "r", encoding="utf-8") as handle:
        return plan_from_dict(json.load(handle))


def demo_plan(columns: int = 5, rows: int = 4, spacing_m: float = 2500.0) -> Plan:
    """A 5x4 small-cell grid: dense enough that channels must be reused."""
    towers: List[Transmitter] = []
    margin = spacing_m * 0.6
    for row in range(rows):
        for column in range(columns):
            name = "T%02d" % (row * columns + column + 1)
            power = 30.0 + (1.5 if (row + column) % 3 == 0 else 0.0)
            towers.append(
                Transmitter(
                    name=name,
                    x=margin + column * spacing_m,
                    y=margin + row * spacing_m,
                    power_dbm=power,
                    gain_dbi=10.0,
                )
            )
    return Plan(
        environment=Environment(
            frequency_mhz=900.0,
            channel_width_mhz=0.2,
            noise_figure_db=7.0,
            model="log-distance",
            exponent=3.2,
            adjacency_isolation_db=30.0,
        ),
        transmitters=tuple(towers),
        width_m=margin * 2 + (columns - 1) * spacing_m,
        height_m=margin * 2 + (rows - 1) * spacing_m,
    )


def demo_with_forced_edge() -> Plan:
    base = demo_plan()
    return Plan(
        environment=base.environment,
        transmitters=base.transmitters,
        width_m=base.width_m,
        height_m=base.height_m,
        forced_edges=(("T01", "T12"),),
    )
