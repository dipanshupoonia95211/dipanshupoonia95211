#!/usr/bin/env python3
"""Turn source-prepped.png into a self-typing monochrome ASCII-art SVG.

Design rules that keep it looking like art instead of static:
  * ONE colour. Per-character rainbow is what makes most ASCII portraits noisy.
  * High contrast in, so the background washes out to the space glyph and only
    the subject prints.
  * Row-by-row left-to-right wipe with a block cursor riding the edge. It prints
    once and freezes -- no looping.

The motion is SMIL inside the SVG, which GitHub plays even though it strips
<script> and external CSS from READMEs.

    python scripts/make_ascii_svg.py                    # uses source-prepped.png
    python scripts/make_ascii_svg.py --text "DIPANSHU"  # wordmark, no photo needed
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source-prepped.png"
OUT = ROOT / "ascii-portrait.svg"

#        bright (sparse) ------------------------------> dark (dense)
RAMP = " .`:-=+*cs#%@"
#      ^ the leading space clears the background to nothing

INK = "#c9d1d9"          # one light-grey fill for every glyph
BG = "#0d1117"
BORDER = "#21262d"
CURSOR = "#39d353"

MONO = ("ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,"
        "'DejaVu Sans Mono','Liberation Mono',monospace")

# A monospace cell is roughly 0.6em wide by 1.0em tall.
CHAR_W_EM = 0.60
CHAR_ASPECT = 1.0 / CHAR_W_EM     # how much taller than wide a cell is

FONT_PX = 7.0
LINE_H = FONT_PX * 1.0
PAD = 16

ROW_MS = 42               # stagger between rows
WIPE_MS = 460             # how long one row takes to print

WORDMARK_FONTS = [
    "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/consolab.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def wordmark(lines: list[str], width: int = 900) -> Image.Image:
    """Render text to a grayscale image so the same ASCII pipeline can produce a
    placeholder wordmark when there is no photo yet."""
    font_path = next((p for p in WORDMARK_FONTS if Path(p).exists()), None)
    size = int(width / (max(len(l) for l in lines) * 0.62))
    font = ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default(size)

    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    widths, heights = [], []
    for line in lines:
        box = probe.textbbox((0, 0), line, font=font)
        widths.append(box[2] - box[0])
        heights.append(box[3] - box[1])
    lh = int(max(heights) * 1.45)
    w = max(widths) + 40
    h = lh * len(lines) + 40

    im = Image.new("L", (w, h), 255)          # white paper
    dr = ImageDraw.Draw(im)
    for i, line in enumerate(lines):
        box = dr.textbbox((0, 0), line, font=font)
        dr.text(((w - (box[2] - box[0])) / 2 - box[0], 20 + i * lh - box[1]),
                line, font=font, fill=20)     # near-black ink
    return im


def to_grid(im: Image.Image, cols: int, invert: bool, gamma: float) -> list[str]:
    rows = max(1, round(cols * (im.height / im.width) / CHAR_ASPECT))
    small = im.convert("L").resize((cols, rows), Image.LANCZOS)
    a = np.asarray(small).astype(np.float32) / 255.0     # 0 = black, 1 = white
    if invert:
        a = 1.0 - a
    if abs(gamma - 1.0) > 1e-3:
        a = np.clip(a, 0, 1) ** (1.0 / gamma)
    # brightness -> ramp index (bright picks the sparse end)
    idx = np.clip(((1.0 - a) * (len(RAMP) - 1)).round().astype(int), 0, len(RAMP) - 1)
    return ["".join(RAMP[i] for i in row) for row in idx]


def trim(grid: list[str]) -> list[str]:
    """Drop fully blank border rows/columns so the art fills the frame."""
    while grid and not grid[0].strip():
        grid.pop(0)
    while grid and not grid[-1].strip():
        grid.pop()
    if not grid:
        return grid
    cols = len(grid[0])
    left = min((len(r) - len(r.lstrip()) for r in grid if r.strip()), default=0)
    right = min((len(r) - len(r.rstrip()) for r in grid if r.strip()), default=0)
    grid = [r[left:cols - right] for r in grid]
    width = max(len(r) for r in grid)
    return [r.ljust(width) for r in grid]


def build(grid: list[str], caption: str | None) -> str:
    cols = max(len(r) for r in grid)
    char_w = FONT_PX * CHAR_W_EM
    art_w = cols * char_w
    art_h = len(grid) * LINE_H

    cap_h = 22 if caption else 0
    width = round(art_w + PAD * 2)
    height = round(art_h + PAD * 2 + cap_h)

    defs, body = [], []
    for i, row in enumerate(grid):
        y = PAD + i * LINE_H
        begin = f"{i * ROW_MS / 1000:.3f}s"
        dur = f"{WIPE_MS / 1000:.3f}s"
        defs.append(
            f'<clipPath id="w{i}"><rect x="{PAD}" y="{y:.2f}" width="0" '
            f'height="{LINE_H:.2f}">'
            f'<animate attributeName="width" from="0" to="{art_w:.2f}" dur="{dur}" '
            f'begin="{begin}" fill="freeze" calcMode="spline" keyTimes="0;1" '
            f'keySplines="0.22 1 0.36 1"/></rect></clipPath>'
        )
        body.append(
            f'<g clip-path="url(#w{i})"><text x="{PAD}" y="{y + FONT_PX * 0.82:.2f}" '
            f'textLength="{art_w:.2f}" lengthAdjust="spacingAndGlyphs">'
            f"{esc(row.ljust(cols))}</text></g>"
        )
        body.append(
            f'<rect class="cur" x="{PAD}" y="{y:.2f}" width="{char_w:.2f}" '
            f'height="{LINE_H:.2f}" opacity="0">'
            f'<animate attributeName="x" from="{PAD}" to="{PAD + art_w:.2f}" dur="{dur}" '
            f'begin="{begin}" fill="freeze" calcMode="spline" keyTimes="0;1" '
            f'keySplines="0.22 1 0.36 1"/>'
            f'<set attributeName="opacity" to="0.85" begin="{begin}"/>'
            f'<set attributeName="opacity" to="0" '
            f'begin="{(i * ROW_MS + WIPE_MS) / 1000:.3f}s"/></rect>'
        )

    tail = (len(grid) * ROW_MS + WIPE_MS) / 1000
    cap_svg = ""
    if caption:
        cap_svg = (
            f'<text class="cap" x="{width / 2:.1f}" y="{height - PAD + 2:.1f}" '
            f'text-anchor="middle" opacity="0">{esc(caption)}'
            f'<animate attributeName="opacity" from="0" to="1" dur="0.5s" '
            f'begin="{tail:.2f}s" fill="freeze"/></text>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"
     viewBox="0 0 {width} {height}" role="img" aria-label="ASCII art portrait">
  <style>
    text {{ font-family:{MONO}; font-size:{FONT_PX}px; fill:{INK};
            white-space:pre; letter-spacing:0; }}
    .cur {{ fill:{CURSOR}; }}
    .cap {{ font-size:11px; fill:#7d8590; letter-spacing:1.5px; }}
  </style>
  <defs>{"".join(defs)}</defs>
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10"
        fill="{BG}" stroke="{BORDER}"/>
  {"".join(body)}
  {cap_svg}
</svg>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-i", "--input", default=str(SRC))
    ap.add_argument("-o", "--out", default=str(OUT))
    ap.add_argument("-c", "--cols", type=int, default=100, help="character columns")
    ap.add_argument("--gamma", type=float, default=1.0,
                    help=">1 thins the art, <1 makes it denser")
    ap.add_argument("--invert", action="store_true",
                    help="use for light-on-dark source images")
    ap.add_argument("--caption", default=None, help="small caption under the art")
    ap.add_argument("--text", nargs="*", default=None,
                    help="render a wordmark instead of a photo (placeholder mode)")
    args = ap.parse_args()

    if args.text is not None:
        im = wordmark(list(args.text) or ["DIPANSHU"])
        print("wordmark mode: " + " / ".join(args.text))
    else:
        src = Path(args.input)
        if not src.exists():
            print("error: %s not found.\n"
                  "       run:  python scripts/prep_photo.py your-photo.jpg\n"
                  "       or:   python scripts/make_ascii_svg.py --text DIPANSHU"
                  % src.name, file=sys.stderr)
            return 1
        im = Image.open(src)

    grid = trim(to_grid(im, args.cols, args.invert, args.gamma))
    if not grid:
        print("error: everything washed out -- try --gamma 0.8 or re-run prep_photo",
              file=sys.stderr)
        return 1

    out = Path(args.out)
    out.write_text(build(grid, args.caption), encoding="utf-8")
    ink = sum(1 for r in grid for ch in r if ch != " ")
    print(f"{out.name}: {len(grid[0])}x{len(grid)} chars, {ink:,} inked, "
          f"{out.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
