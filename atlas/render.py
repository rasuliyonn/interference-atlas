"""ASCII and SVG renderers for coverage maps."""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from .model import CoverageCell, Environment, Transmitter, coverage_grid, summarize_coverage

QUALITY_GLYPH = {"great": "#", "good": "+", "fair": ".", "outage": " "}
QUALITY_COLOR = {
    "great": "#1f9d55",
    "good": "#86c76a",
    "fair": "#e8b84b",
    "outage": "#4b5563",
}
QUALITY_LABEL = {
    "great": "SINR >= 20 dB",
    "good": "10-20 dB",
    "fair": "0-10 dB",
    "outage": "under 0 dB",
}


def _buckets(
    environment: Environment,
    channels: Dict[str, int],
    transmitters: Sequence[Transmitter],
    width: float,
    height: float,
    columns: int,
    rows: int,
) -> List[List[CoverageCell]]:
    cells = coverage_grid(environment, channels, transmitters, width, height, columns, rows)
    grid: List[List[CoverageCell]] = []
    for row in range(rows):
        grid.append(cells[row * columns : (row + 1) * columns])
    return grid


def ascii_map(
    environment: Environment,
    channels: Dict[str, int],
    transmitters: Sequence[Transmitter],
    width: float,
    height: float,
    columns: int = 48,
    rows: Optional[int] = None,
) -> str:
    if rows is None:
        rows = max(8, int(round(columns * (height / width) * 0.5)))
    grid = _buckets(environment, channels, transmitters, width, height, columns, rows)
    marks = {}
    for tower in transmitters:
        column = min(columns - 1, max(0, int(tower.x / width * columns)))
        row = min(rows - 1, max(0, int((height - tower.y) / height * rows)))
        marks[(row, column)] = "@"

    lines: List[str] = []
    for row in range(rows):
        line = []
        for column in range(columns):
            line.append(marks.get((row, column), QUALITY_GLYPH[grid[row][column].link.quality]))
        lines.append("".join(line))
    legend = "legend: # great   + good   . fair   (space) outage   @ transmitter"
    lines.append("")
    lines.append(legend)
    return "\n".join(lines)


def render_svg(
    environment: Environment,
    channels: Dict[str, int],
    transmitters: Sequence[Transmitter],
    width: float,
    height: float,
    columns: int = 64,
    rows: int = 32,
    cell: int = 18,
) -> str:
    grid = _buckets(environment, channels, transmitters, width, height, columns, rows)
    summary = summarize_coverage(cell for row in grid for cell in row)
    pad = 24
    header = 74
    svg_width = columns * cell + 2 * pad
    svg_height = rows * cell + 2 * pad + header
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
        'font-family="ui-monospace,SFMono-Regular,Menlo,monospace">'
        % (svg_width, svg_height, svg_width, svg_height),
        '<rect width="100%" height="100%" fill="#0b1120"/>',
        '<text x="%d" y="28" fill="#f8fafc" font-size="16">Interference Atlas — %d channels, '
        '%.0f m grid</text>' % (pad, len(set(channels.values())), cell),
        '<text x="%d" y="50" fill="#94a3b8" font-size="11">great %.1f%% · good %.1f%% · '
        'fair %.1f%% · outage %.1f%% · mean SINR %.1f dB</text>'
        % (
            pad,
            summary["great"],
            summary["good"],
            summary["fair"],
            summary["outage"],
            summary["mean_sinr_db"],
        ),
    ]
    top = header
    for row in range(rows):
        for column in range(columns):
            quality = grid[row][column].link.quality
            parts.append(
                '<rect x="%d" y="%d" width="%d" height="%d" fill="%s"/>'
                % (pad + column * cell, top + row * cell, cell + 1, cell + 1, QUALITY_COLOR[quality])
            )
            marker = channels.get(grid[row][column].link.serving, 0)
            parts.append(
                '<text x="%d" y="%d" fill="#0b1120" font-size="8" opacity="0.55">%d</text>'
                % (pad + column * cell + 2, top + row * cell + 8, marker)
            )
    for tower in transmitters:
        cx = pad + tower.x / width * columns * cell
        cy = top + (height - tower.y) / height * rows * cell
        parts.append(
            '<circle cx="%.1f" cy="%.1f" r="7" fill="#f8fafc" stroke="#0b1120" stroke-width="2"/>'
            % (cx, cy)
        )
        parts.append(
            '<text x="%.1f" y="%.1f" fill="#0b1120" font-size="9" text-anchor="middle">%s</text>'
            % (cx, cy + 3, tower.name)
        )
    legend_y = top + rows * cell + 22
    offset = pad
    for quality in ("great", "good", "fair", "outage"):
        parts.append(
            '<rect x="%d" y="%d" width="12" height="12" fill="%s"/>'
            % (offset, legend_y - 10, QUALITY_COLOR[quality])
        )
        parts.append(
            '<text x="%d" y="%d" fill="#cbd5e1" font-size="10">%s</text>'
            % (offset + 18, legend_y, QUALITY_LABEL[quality])
        )
        offset += 22 + len(QUALITY_LABEL[quality]) * 6
    parts.append("</svg>")
    return "\n".join(parts)
