# Interference Atlas

Co-channel spectrum planning for a field of transmitters: link budgets, an
interference graph, channel assignment with provable bounds, and SINR coverage
maps as ASCII or SVG. Pure Python, no third-party dependencies.

Most "channel planning" tools stop at drawing dots on a map. This one models the
physics, proves when a channel plan is optimal, and quantifies what the plan
buys you over naive co-channel reuse.

## What it actually computes

**Link budget.** Free-space or log-distance path loss with configurable exponent,
antenna gain, and a thermal noise floor of `-174 dBm/Hz + 10·log10(BW) + NF`.
Every number in the report comes from these formulas, not from a lookup table.

**Interference graph.** Two sites are connected when co-channel leakage at
either receiver exceeds the noise floor by a protection margin (default 18 dB).
An edge means "these two must not share a channel", so the graph is exactly the
conflict structure of the planning problem.

**Channel assignment.** DSATUR colouring gives the channel count, greedy
largest-degree ordering is kept as a baseline, and a Bron–Kerbosch maximum clique
gives a lower bound. When the two bounds meet, the report says **provably
optimal**; otherwise it reports the exact gap.

**SINR coverage.** A grid of probes picks the strongest server at each point and
sums interference from co-channel and adjacent-channel sites, applying
configured isolation (0 dB co-channel, 30 dB adjacent, 70 dB out-of-band).

## Demo

```
$ python -m atlas.cli demo --ascii --svg out/coverage.svg
Interference Atlas — 20 transmitters at 900.0 MHz, 0.20 MHz channels
Interference graph: 20 nodes, 111 edges, density 0.584, noise floor -114.0 dBm
Channels: 9 (DSATUR) | greedy: 10 | clique lower bound: 7 | gap of 2
Clique: T01, T02, T03, T06, T07, T08, T12
Assignment: T01=1  T02=5  T03=6  T04=4  ...
Closest co-channel reuse: T01 / T13 at 7071 m
Planned coverage: great 94.9%  good 5.1%  fair 0.0%  outage 0.0%  mean SINR 28.8 dB
Reuse-1 baseline: great 6.1%  good 20.8%  fair 56.5%  outage 16.6%  mean SINR 6.9 dB
```

The last two lines are the point of the project: the same twenty sites, planned
across nine channels instead of one, move from a network that is mostly
interference-limited to one that is noise-limited.

The SVG renderer writes a heat map with per-cell server channel numbers, tower
markers, a legend and a summary header — suitable for a README or a design review.

## Planning your own field

```json
{
  "width_m": 16000,
  "height_m": 12000,
  "environment": { "frequency_mhz": 1800, "channel_width_mhz": 0.2, "exponent": 3.1 },
  "transmitters": [
    { "name": "N1", "x": 2000, "y": 2000, "power_dbm": 33, "gain_dbi": 15 },
    { "name": "C1", "x": 4200, "y": 6200, "power_dbm": 28, "gain_dbi": 12 }
  ],
  "forced_edges": [["N1", "C1"]]
}
```

```
python -m atlas.cli plan examples/tower_plan.json --margin 18 \
  --ascii --svg out/plan.svg --json-out out/plan.json --strict
```

`--strict` exits with status 2 when the planner cannot prove optimality, which
makes the tool usable in CI for a spectrum plan that must be reviewed.

## Layout

```
atlas/model.py    propagation, noise floor, link evaluation, coverage grid
atlas/graph.py    interference graph, DSATUR, greedy, clique bound, plan report
atlas/plan.py     JSON scenario loading, validation, demo field
atlas/render.py   ASCII and SVG coverage maps
atlas/cli.py      plan / demo commands
tests/            29 unit and integration tests
```

## Tests

```
python -m unittest discover -s tests -v
```

The suite checks the free-space reference value (91.5 dB at 1 km, 900 MHz),
noise-floor arithmetic, monotonic path loss, SINR behaviour with co-channel and
adjacent-channel interferers, colouring validity on triangles, odd cycles,
bipartite and complete graphs, the clique lower bound, SVG well-formedness and
cell counts, CLI artifact generation, and scenario validation errors.

## Limitations

- Two-dimensional sites with omnidirectional patterns; no antenna azimuth or
  terrain/shadowing model.
- Path loss is deterministic: no fading margin or Monte-Carlo reliability layer.
- DSATUR is a heuristic; the reported gap is honest, not hidden.
- Channel width is uniform across the plan and adjacent-channel isolation is a
  single configured value.

## License

MIT
