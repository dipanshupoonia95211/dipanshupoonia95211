#!/usr/bin/env python3
"""Hand-author a neofetch-style info card SVG that prints line by line.

>>> EDIT THE `CARD` DICT BELOW -- that is the only part you need to touch. <<<

Keep the *story* here. The heatmap already covers the numbers, so this panel is
for the things a contribution graph can't say.

  STATIC=1 python scripts/make_info_card.py   # frozen frame, for quick previews
"""
from __future__ import annotations

import os
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "info-card.svg"

# ============================================================== EDIT ME ======
CARD = {
    "user": "dipanshu",
    "host": "github",
    "rows": [
        ("OS",         "Windows 11 · WSL · Android Studio"),
        ("Uptime",     "since Jan 2025 on GitHub"),
        ("Now",        "Full-stack dev — Flutter + Go + SvelteKit"),
        ("Building",   "Sparq — a campus social platform"),
        ("Prev",       "Java / DSA · web tooling · CV experiments"),
        (None,         None),                      # blank spacer row
        ("Languages",  "Dart · Go · Java · JavaScript · Python"),
        ("Frontend",   "Flutter · SvelteKit · HTML/CSS"),
        ("Backend",    "Go · Node · Firebase · Redis · Postgres"),
        ("Cloud",      "AWS EC2/S3 · Cloudflare Pages · GCP"),
        ("Tools",      "git · docker · nginx · pm2 · ffmpeg"),
        (None,         None),
        ("Focus",      "realtime chat, media pipelines, mobile UX"),
        ("Learning",   "distributed systems · Rust"),
        ("Contact",    "github.com/dipanshupoonia95211"),
    ],
}
# =============================================================================

BG = "#0d1117"
BORDER = "#21262d"
KEY = "#39d353"      # neofetch key colour
VAL = "#c9d1d9"
DIM = "#7d8590"
ACCENT = "#58a6ff"

MONO = ("ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,"
        "'DejaVu Sans Mono','Liberation Mono',monospace")

PAD = 20
LINE_H = 21
KEY_W = 96           # px reserved for the key column
FONT = 13
TITLE_GAP = 10
CHIP = 12            # neofetch colour-swatch size

STEP_MS = 70         # stagger between lines
LINE_MS = 340

# Card width tuned so 370 (portrait) + 490 (card) == 860 (heatmap) in the README.
WIDTH = 490
_content_rows = len(CARD["rows"])
HEIGHT = PAD + 20 + TITLE_GAP + _content_rows * LINE_H + 14 + CHIP + PAD


def esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def build(static: bool = False) -> str:
    user, host = CARD["user"], CARD["host"]
    title = f"{user}@{host}"
    rule = "-" * len(title)

    lines: list[str] = []
    n = 0

    def anim(i: int) -> str:
        return "" if static else f' style="animation-delay:{i * STEP_MS}ms"'

    y = PAD + 14
    lines.append(
        f'<text class="ln" x="{PAD}" y="{y}"{anim(n)}>'
        f'<tspan class="k">{esc(user)}</tspan>'
        f'<tspan class="d">@</tspan>'
        f'<tspan class="a">{esc(host)}</tspan></text>'
    )
    n += 1
    y += 16
    lines.append(f'<text class="ln d" x="{PAD}" y="{y}"{anim(n)}>{rule}</text>')
    n += 1
    y += TITLE_GAP + 8

    for key, val in CARD["rows"]:
        if key is None:
            y += LINE_H
            continue
        lines.append(
            f'<text class="ln" x="{PAD}" y="{y}"{anim(n)}>'
            f'<tspan class="k">{esc(key)}</tspan>'
            f'<tspan class="d" dx="4">:</tspan>'
            f'<tspan class="v" x="{PAD + KEY_W}">{esc(val)}</tspan></text>'
        )
        n += 1
        y += LINE_H

    # neofetch's colour strip
    y += 6
    swatches = ["#161b22", "#0e4429", "#006d32", "#26a641",
                "#39d353", "#69f0a0", "#58a6ff", "#c9d1d9"]
    chips = "".join(
        f'<rect x="{PAD + i * (CHIP + 4)}" y="{y}" width="{CHIP}" height="{CHIP}" '
        f'rx="2" fill="{c}"/>'
        for i, c in enumerate(swatches)
    )
    lines.append(f'<g class="ln"{anim(n)}>{chips}</g>')
    n += 1

    tail = n * STEP_MS + LINE_MS
    play = "" if static else f"""
    .ln {{ opacity:0; animation:in {LINE_MS}ms ease-out forwards; }}
    @keyframes in {{
      from {{ opacity:0; transform:translateX(-8px) }}
      to   {{ opacity:1; transform:translateX(0) }}
    }}
    .cursor {{ opacity:0; animation:fade 1ms linear {tail}ms forwards,
                                    blink 1.05s steps(1) {tail}ms infinite; }}
    @keyframes fade {{ to {{ opacity:1 }} }}
    @keyframes blink {{ 50% {{ opacity:0 }} }}
    @media (prefers-reduced-motion: reduce) {{
      .ln {{ opacity:1; animation:none; }}
      .cursor {{ opacity:1; animation:none; }}
    }}"""

    cursor_y = HEIGHT - PAD - CHIP - 2
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}"
     viewBox="0 0 {WIDTH} {HEIGHT}" role="img"
     aria-label="neofetch-style info card for {esc(title)}">
  <style>
    text {{ font-family:{MONO}; font-size:{FONT}px; }}
    .k {{ fill:{KEY}; font-weight:700; }}
    .v {{ fill:{VAL}; }}
    .d {{ fill:{DIM}; }}
    .a {{ fill:{ACCENT}; font-weight:700; }}{play}
  </style>
  <rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{HEIGHT - 1}" rx="10"
        fill="{BG}" stroke="{BORDER}"/>
  {"".join(lines)}
  <rect class="cursor" x="{WIDTH - PAD - 9}" y="{cursor_y}" width="8" height="14" fill="{KEY}"/>
</svg>
"""


def main() -> None:
    static = os.environ.get("STATIC") == "1"
    OUT.write_text(build(static), encoding="utf-8")
    print(f"{OUT.name}: {WIDTH}x{HEIGHT}{' (static)' if static else ''}, "
          f"{OUT.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
