#!/usr/bin/env python3
"""Render data/contributions.json as an animated 53x7 contribution heatmap SVG.

The reveal is a diagonal wipe driven by CSS keyframes *inside* the SVG -- GitHub
strips <script> and external CSS from READMEs, but it happily plays animations
that live in the SVG document itself. It plays once and freezes; no looping.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "contributions.json"
OUT = ROOT / "contrib-heatmap.svg"

# ---------------------------------------------------------------- look & feel
PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"]
#           none  ->  brightest (level 5 is a neon top end for your best days)
BG = "#0d1117"
BORDER = "#21262d"
FG_DIM = "#7d8590"
FG = "#c9d1d9"
ACCENT = "#39d353"

CELL = 12          # box size
GAP = 3            # gap between boxes
PITCH = CELL + GAP
RADIUS = 2.5
COLS = 53
ROWS = 7

PAD = 18
GUTTER = 32        # left column for Mon/Wed/Fri labels
MONTH_H = 18       # month label strip above the grid

GRID_W = COLS * PITCH - GAP
GRID_H = ROWS * PITCH - GAP
GRID_X = PAD + GUTTER
GRID_Y = PAD + MONTH_H

FOOTER_H = 26
WIDTH = GRID_X + GRID_W + PAD
HEIGHT = GRID_Y + GRID_H + 16 + FOOTER_H + PAD - 8

MONO = ("ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,"
        "'DejaVu Sans Mono','Liberation Mono',monospace")

STEP_MS = 22       # delay added per diagonal
CELL_MS = 420      # how long one box takes to settle
DIAGONALS = COLS + ROWS


def esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def level_for(day: dict, max_day: int) -> int:
    """GitHub gives us 0-4; promote standout days to a neon level 5."""
    lvl = int(day.get("level", 0))
    if day["count"] > 0 and day["count"] >= max(8, max_day * 0.75):
        return 5
    return min(lvl, 4)


def ordinal(n: int) -> str:
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def build() -> str:
    stats = json.loads(DATA.read_text(encoding="utf-8"))
    days = stats["days"]
    max_day = stats.get("max_day") or 1

    first = datetime.strptime(days[0]["date"], "%Y-%m-%d").date()
    # GitHub weeks start on Sunday; python weekday() is Monday=0.
    def row_of(d):
        return (d.weekday() + 1) % 7

    start_row = row_of(first)

    parts: list[str] = []
    month_labels: list[tuple[int, str]] = []
    seen_months: set[str] = set()

    for i, day in enumerate(days):
        d = datetime.strptime(day["date"], "%Y-%m-%d").date()
        idx = start_row + i
        col, row = divmod(idx, ROWS)
        if col >= COLS:
            break
        x = GRID_X + col * PITCH
        y = GRID_Y + row * PITCH
        lvl = level_for(day, max_day)
        diag = min(col + row, DIAGONALS - 1)
        cls = f"c l{lvl} d{diag}"
        n = day["count"]
        label = "No contributions" if n == 0 else f"{n} contribution{'s' if n != 1 else ''}"
        parts.append(
            f'<g class="{cls}"><rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" '
            f'rx="{RADIUS}"><title>{esc(label)} on {d:%b} {ordinal(d.day)}, {d.year}</title>'
            f"</rect></g>"
        )
        # First cell of a month that starts a fresh column gets a month label.
        key = f"{d.year}-{d.month:02d}"
        if key not in seen_months and d.day <= 7 and col < COLS - 1:
            seen_months.add(key)
            month_labels.append((GRID_X + col * PITCH, f"{d:%b}"))

    months_svg = "".join(
        f'<text class="mo" x="{x}" y="{PAD + 11}">{m}</text>' for x, m in month_labels
    )

    day_names = {1: "Mon", 3: "Wed", 5: "Fri"}
    days_svg = "".join(
        f'<text class="dow" x="{GRID_X - 8}" y="{GRID_Y + r * PITCH + CELL - 2}">{name}</text>'
        for r, name in day_names.items()
    )

    # ------------------------------------------------------------- footer
    fy = GRID_Y + GRID_H + 16 + 14
    total = stats["total"]
    best = stats["best_day"]
    best_d = datetime.strptime(best["date"], "%Y-%m-%d").date() if best.get("date") else None
    line = (
        f"{total:,} contribution{'s' if total != 1 else ''} in the last year"
        f"   ·   {stats['active_days']} active days"
        f"   ·   streak {stats['current_streak']}d (best {stats['longest_streak']}d)"
    )
    if best_d:
        line += f"   ·   peak {best['count']} on {best_d:%b} {best_d.day}"

    legend_w = 5 * PITCH - GAP
    legend_x = WIDTH - PAD - legend_w - 42
    legend_boxes = "".join(
        f'<rect class="lg l{i + 1}" x="{legend_x + i * PITCH}" y="{fy - 10}" '
        f'width="{CELL}" height="{CELL}" rx="{RADIUS}"/>'
        for i in range(5)
    )

    level_css = "".join(f".l{i}>rect,rect.l{i}{{fill:{c};}}" for i, c in enumerate(PALETTE))
    delay_css = "".join(f".d{i}{{animation-delay:{i * STEP_MS}ms;}}" for i in range(DIAGONALS))
    tail_ms = DIAGONALS * STEP_MS + CELL_MS

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}"
     viewBox="0 0 {WIDTH} {HEIGHT}" role="img"
     aria-label="GitHub contribution heatmap for {esc(stats['username'])}">
  <style>
    .bg {{ fill:{BG}; stroke:{BORDER}; }}
    text {{ font-family:{MONO}; }}
    .mo  {{ font-size:10px; fill:{FG_DIM}; }}
    .dow {{ font-size:9px;  fill:{FG_DIM}; text-anchor:end; }}
    .ft  {{ font-size:10.5px; fill:{FG_DIM}; }}
    .ft tspan.hi {{ fill:{ACCENT}; }}
    {level_css}
    .c {{ opacity:0; animation:pop {CELL_MS}ms ease-out forwards; }}
    {delay_css}
    @keyframes pop {{
      from {{ opacity:0; transform:translateY(-7px) }}
      60%  {{ opacity:1; }}
      to   {{ opacity:1; transform:translateY(0) }}
    }}
    .fade {{ opacity:0; animation:fade 600ms ease-out {tail_ms}ms forwards; }}
    @keyframes fade {{ to {{ opacity:1 }} }}
    .mo,.dow {{ opacity:0; animation:fade 500ms ease-out 150ms forwards; }}
    @media (prefers-reduced-motion: reduce) {{
      .c,.fade,.mo,.dow {{ opacity:1; animation:none; }}
    }}
  </style>
  <rect class="bg" x="0.5" y="0.5" width="{WIDTH - 1}" height="{HEIGHT - 1}" rx="10"/>
  {months_svg}
  {days_svg}
  {"".join(parts)}
  <g class="fade">
    <text class="ft" x="{PAD}" y="{fy}">{esc(line)}</text>
    <text class="ft" x="{legend_x - 8}" y="{fy}" text-anchor="end">Less</text>
    {legend_boxes}
    <text class="ft" x="{legend_x + legend_w + 8}" y="{fy}">More</text>
  </g>
</svg>
"""


def main() -> None:
    OUT.write_text(build(), encoding="utf-8")
    print(f"{OUT.name}: {WIDTH}x{HEIGHT}, {OUT.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
