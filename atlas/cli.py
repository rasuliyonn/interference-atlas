"""Command line interface: plan channels, assess coverage, render maps."""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List, Optional, Sequence

from .graph import graph_density, plan_channels
from .model import Environment, Transmitter, coverage_grid, summarize_coverage
from .plan import Plan, demo_plan, load_plan
from .render import ascii_map, render_svg


def analyse(plan: Plan, margin_db: float = 18.0, columns: int = 48, rows: int = 20) -> Dict[str, object]:
    result = plan_channels(plan.environment, plan.transmitters, margin_db, plan.forced_edges)
    cells = coverage_grid(
        plan.environment, result["channels"], plan.transmitters, plan.width_m, plan.height_m, columns, rows
    )
    result["coverage"] = summarize_coverage(cells)
    single_channel = {tower.name: 0 for tower in plan.transmitters}
    baseline = coverage_grid(
        plan.environment, single_channel, plan.transmitters, plan.width_m, plan.height_m, columns, rows
    )
    result["baseline"] = summarize_coverage(baseline)
    result["density"] = graph_density(result["graph"])
    return result


def format_report(plan: Plan, result: Dict[str, object]) -> str:
    channels: Dict[str, int] = result["channels"]
    coverage = result["coverage"]
    lines: List[str] = []
    lines.append(
        "Interference Atlas — %d transmitters at %.1f MHz, %.2f MHz channels"
        % (len(plan.transmitters), plan.environment.frequency_mhz, plan.environment.channel_width_mhz)
    )
    lines.append(
        "Interference graph: %d nodes, %d edges, density %.3f, noise floor %.1f dBm"
        % (
            len(result["graph"]),
            result["edges"],
            result["density"],
            plan.environment.noise_dbm,
        )
    )
    lines.append(
        "Channels: %d (DSATUR) | greedy: %d | clique lower bound: %d | %s"
        % (
            result["channel_count"],
            result["greedy_count"],
            result["lower_bound"],
            "provably optimal" if result["optimal"] else "gap of %d"
            % (result["channel_count"] - result["lower_bound"]),
        )
    )
    lines.append("Clique: " + ", ".join(result["clique"]))
    assignment = "  ".join("%s=%d" % (name, channels[name]) for name in sorted(channels))
    lines.append("Assignment: " + assignment)
    if result["reuse_pairs"]:
        first, second, distance = result["reuse_pairs"][0]
        lines.append("Closest co-channel reuse: %s / %s at %d m" % (first, second, distance))
    lines.append(
        "Planned coverage: great %.1f%%  good %.1f%%  fair %.1f%%  outage %.1f%%  mean SINR %.1f dB"
        % (
            coverage["great"],
            coverage["good"],
            coverage["fair"],
            coverage["outage"],
            coverage["mean_sinr_db"],
        )
    )
    baseline = result["baseline"]
    lines.append(
        "Reuse-1 baseline: great %.1f%%  good %.1f%%  fair %.1f%%  outage %.1f%%  mean SINR %.1f dB"
        % (
            baseline["great"],
            baseline["good"],
            baseline["fair"],
            baseline["outage"],
            baseline["mean_sinr_db"],
        )
    )
    return "\n".join(lines)


def _write(path: str, text: str) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text if text.endswith("\n") else text + "\n")
    print("wrote %s" % path)


def _run(plan: Plan, args: argparse.Namespace) -> int:
    result = analyse(plan, args.margin, args.columns, args.rows)
    print(format_report(plan, result))
    if args.ascii:
        print()
        print(
            ascii_map(
                plan.environment,
                result["channels"],
                plan.transmitters,
                plan.width_m,
                plan.height_m,
                args.columns,
                args.rows,
            )
        )
    if args.svg:
        _write(
            args.svg,
            render_svg(
                plan.environment,
                result["channels"],
                plan.transmitters,
                plan.width_m,
                plan.height_m,
                columns=64,
                rows=32,
            ),
        )
    if args.json_out:
        payload = {
            "channels": result["channels"],
            "channel_count": result["channel_count"],
            "greedy_count": result["greedy_count"],
            "lower_bound": result["lower_bound"],
            "optimal": result["optimal"],
            "edges": result["edges"],
            "coverage": result["coverage"],
            "single_channel_baseline": result["baseline"],
        }
        _write(args.json_out, json.dumps(payload, indent=2, sort_keys=True))
    if not result["optimal"] and args.strict:
        print(
            "warning: channel count exceeds the clique lower bound", file=sys.stderr
        )
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="atlas",
        description="Plan co-channel spectrum reuse and map SINR coverage.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("plan", "plan channels for a JSON scenario"),
        ("demo", "run the built-in 4x3 macro-cell demo"),
    ):
        command = sub.add_parser(name, help=help_text)
        if name == "plan":
            command.add_argument("scenario", help="path to a plan JSON file")
        command.add_argument("--margin", type=float, default=18.0, help="interference margin over noise (dB)")
        command.add_argument("--columns", type=int, default=48)
        command.add_argument("--rows", type=int, default=20)
        command.add_argument("--ascii", action="store_true", help="print an ASCII coverage map")
        command.add_argument("--svg", help="write an SVG coverage map")
        command.add_argument("--json-out", help="write a machine-readable report")
        command.add_argument("--strict", action="store_true", help="exit 2 when optimality is unproven")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    plan = demo_plan() if args.command == "demo" else load_plan(args.scenario)
    return _run(plan, args)


if __name__ == "__main__":
    raise SystemExit(main())
