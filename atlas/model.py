"""Link budgets, interference and SINR evaluation for co-channel spectrum planning.

All powers are dBm, all losses dB, distances metres, frequencies MHz.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

MIN_DISTANCE_M = 1.0


@dataclass(frozen=True)
class Transmitter:
    name: str
    x: float
    y: float
    power_dbm: float = 30.0
    gain_dbi: float = 0.0

    def position(self) -> Tuple[float, float]:
        return (self.x, self.y)


@dataclass(frozen=True)
class ServingLink:
    serving: str
    channel: int
    signal_dbm: float
    interference_dbm: float
    noise_dbm: float
    sinr_db: float
    interferers: Tuple[Tuple[str, float], ...]

    @property
    def quality(self) -> str:
        if self.sinr_db >= 20.0:
            return "great"
        if self.sinr_db >= 10.0:
            return "good"
        if self.sinr_db >= 0.0:
            return "fair"
        return "outage"


def distance_m(a: Transmitter, b: Transmitter) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def bearing_deg(a: Transmitter, b: Transmitter) -> float:
    """Compass bearing from a to b, 0 = north, clockwise."""
    angle = math.degrees(math.atan2(b.x - a.x, b.y - a.y))
    return (angle + 360.0) % 360.0


def free_space_loss_db(distance: float, frequency_mhz: float) -> float:
    d = max(distance, MIN_DISTANCE_M)
    return 32.44 + 20.0 * math.log10(d / 1000.0) + 20.0 * math.log10(frequency_mhz)


def log_distance_loss_db(
    distance: float,
    frequency_mhz: float,
    reference_distance_m: float = 25.0,
    exponent: float = 2.8,
) -> float:
    d = max(distance, MIN_DISTANCE_M)
    reference = free_space_loss_db(reference_distance_m, frequency_mhz)
    return reference + 10.0 * exponent * math.log10(max(d, reference_distance_m) / reference_distance_m)


def noise_floor_dbm(bandwidth_hz: float, noise_figure_db: float = 7.0) -> float:
    """Thermal noise in a bandwidth: -174 dBm/Hz + 10log10(B) + NF."""
    return -174.0 + 10.0 * math.log10(bandwidth_hz) + noise_figure_db


@dataclass(frozen=True)
class Environment:
    frequency_mhz: float = 900.0
    channel_width_mhz: float = 0.2
    noise_figure_db: float = 7.0
    model: str = "log-distance"
    exponent: float = 2.8
    adjacency_isolation_db: float = 30.0
    out_of_band_isolation_db: float = 70.0

    @property
    def noise_dbm(self) -> float:
        return noise_floor_dbm(self.channel_width_mhz * 1e6, self.noise_figure_db)

    def path_loss_db(self, distance: float) -> float:
        if self.model == "free-space":
            return free_space_loss_db(distance, self.frequency_mhz)
        if self.model == "log-distance":
            return log_distance_loss_db(distance, self.frequency_mhz, exponent=self.exponent)
        raise ValueError("unknown propagation model: %r" % (self.model,))

    def rx_power_dbm(self, transmitter: Transmitter, x: float, y: float) -> float:
        d = math.hypot(transmitter.x - x, transmitter.y - y)
        return transmitter.power_dbm + transmitter.gain_dbi - self.path_loss_db(d)

    def potential_interference_db(self, a: Transmitter, b: Transmitter) -> float:
        """Worst-case co-channel interference above the noise floor, both directions."""
        a_at_b = self.rx_power_dbm(a, b.x, b.y)
        b_at_a = self.rx_power_dbm(b, a.x, a.y)
        return max(a_at_b, b_at_a) - self.noise_dbm


def evaluate_link(
    environment: Environment,
    channel_of: Dict[str, int],
    x: float,
    y: float,
    transmitters: Sequence[Transmitter],
) -> ServingLink:
    """Strongest-server SINR with adjacent-channel isolation applied."""
    if not transmitters:
        raise ValueError("at least one transmitter is required")
    powers = {t.name: environment.rx_power_dbm(t, x, y) for t in transmitters}
    serving = max(powers, key=lambda name: powers[name])
    serving_channel = channel_of[serving]

    interferers: List[Tuple[str, float]] = []
    interference_linear = 0.0
    for name, power in powers.items():
        if name == serving:
            continue
        separation = abs(channel_of[name] - serving_channel)
        if separation == 0:
            isolation = 0.0
        elif separation == 1:
            isolation = environment.adjacency_isolation_db
        else:
            isolation = environment.out_of_band_isolation_db
        effective = power - isolation
        interference_linear += 10.0 ** (effective / 10.0)
        interferers.append((name, effective))

    noise_linear = 10.0 ** (environment.noise_dbm / 10.0)
    total_interference = interference_linear + noise_linear
    sinr_db = powers[serving] - 10.0 * math.log10(total_interference)
    interference_dbm = (
        10.0 * math.log10(interference_linear) if interference_linear > 0.0 else -300.0
    )
    interferers.sort(key=lambda item: item[1], reverse=True)
    return ServingLink(
        serving=serving,
        channel=serving_channel,
        signal_dbm=powers[serving],
        interference_dbm=interference_dbm,
        noise_dbm=environment.noise_dbm,
        sinr_db=sinr_db,
        interferers=tuple(interferers),
    )


@dataclass(frozen=True)
class CoverageCell:
    x: float
    y: float
    link: ServingLink


def coverage_grid(
    environment: Environment,
    channel_of: Dict[str, int],
    transmitters: Sequence[Transmitter],
    width: float,
    height: float,
    columns: int = 32,
    rows: int = 16,
) -> List[CoverageCell]:
    if columns < 1 or rows < 1:
        raise ValueError("grid must have at least one row and column")
    cells: List[CoverageCell] = []
    for row in range(rows):
        for column in range(columns):
            x = (column + 0.5) * width / columns
            y = (row + 0.5) * height / rows
            link = evaluate_link(environment, channel_of, x, y, transmitters)
            cells.append(CoverageCell(x=x, y=y, link=link))
    return cells


def summarize_coverage(cells: Iterable[CoverageCell]) -> Dict[str, float]:
    counts = {"great": 0, "good": 0, "fair": 0, "outage": 0}
    sinr_values: List[float] = []
    for cell in cells:
        counts[cell.link.quality] += 1
        sinr_values.append(cell.link.sinr_db)
    total = max(1, len(sinr_values))
    summary: Dict[str, float] = {key: 100.0 * value / total for key, value in counts.items()}
    ordered = sorted(sinr_values)
    summary["mean_sinr_db"] = sum(sinr_values) / max(1, len(sinr_values))
    summary["p10_sinr_db"] = ordered[max(0, int(0.1 * len(ordered)) - 1)] if ordered else 0.0
    summary["cell_count"] = len(sinr_values)
    return summary
