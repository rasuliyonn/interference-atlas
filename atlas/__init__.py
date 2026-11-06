"""Interference Atlas — co-channel spectrum planning and SINR coverage maps."""
from .graph import (
    build_interference_graph,
    dsatur_coloring,
    greedy_coloring,
    max_clique,
    plan_channels,
    validate_coloring,
)
from .model import (
    Environment,
    ServingLink,
    Transmitter,
    coverage_grid,
    evaluate_link,
    free_space_loss_db,
    log_distance_loss_db,
    noise_floor_dbm,
    summarize_coverage,
)
from .plan import Plan, demo_plan, load_plan, plan_from_dict
from .render import ascii_map, render_svg

__all__ = [
    "Environment",
    "Plan",
    "ServingLink",
    "Transmitter",
    "ascii_map",
    "build_interference_graph",
    "coverage_grid",
    "demo_plan",
    "dsatur_coloring",
    "evaluate_link",
    "free_space_loss_db",
    "greedy_coloring",
    "load_plan",
    "log_distance_loss_db",
    "max_clique",
    "noise_floor_dbm",
    "plan_channels",
    "plan_from_dict",
    "render_svg",
    "summarize_coverage",
    "validate_coloring",
]
__version__ = "1.0.0"
