#!/usr/bin/env python3
"""Prepare a photo so it converts to *readable* ASCII art.

A flatly-lit face becomes a dark unreadable blob when you map pixels straight
onto a density ramp. Three steps fix that:

  1. cut the background out (rembg) so only the subject prints
  2. boost local contrast with CLAHE so a flat face gets real highs and lows
  3. composite onto pure white, so the background lands on the blank end
     of the ramp (white -> space)

    python scripts/prep_photo.py source-photo.jpg

Writes source-prepped.png (grayscale). Run once per photo, then run
make_ascii_svg.py. Needs pillow + numpy; rembg and opencv are optional and the
script degrades gracefully (with a warning) if either is missing.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "source-prepped.png"


def cut_background(im: Image.Image) -> Image.Image:
    """RGBA with the subject isolated. Falls back to the original if rembg is absent."""
    try:
        from rembg import remove
    except ImportError:
        print("note: rembg not installed -- skipping background removal.\n"
              "      pip install rembg   (or use a photo that already has a plain "
              "background)", file=sys.stderr)
        return im.convert("RGBA")
    print("removing background (first run downloads the u2net model)...")
    return remove(im.convert("RGBA"))


def on_white(im: Image.Image) -> Image.Image:
    """Flatten RGBA onto pure white so transparent areas map to blank glyphs."""
    if im.mode != "RGBA":
        return im.convert("RGB")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    return Image.alpha_composite(bg, im).convert("RGB")


def local_contrast(gray: np.ndarray, clip: float, grid: int) -> np.ndarray:
    """CLAHE via OpenCV, with a plain histogram-equalisation fallback."""
    try:
        import cv2
    except ImportError:
        print("note: opencv-python not installed -- using global equalisation instead "
              "of CLAHE.", file=sys.stderr)
        eq = ImageOps.equalize(Image.fromarray(gray))
        return np.asarray(eq)
    clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(grid, grid))
    return clahe.apply(gray)


def stretch(gray: np.ndarray, lo_pct: float, hi_pct: float) -> np.ndarray:
    """Percentile stretch -- pins the darkest ink dark and the paper truly white."""
    lo, hi = np.percentile(gray, [lo_pct, hi_pct])
    if hi - lo < 1:
        return gray
    out = (gray.astype(np.float32) - lo) * (255.0 / (hi - lo))
    return np.clip(out, 0, 255).astype(np.uint8)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("photo", help="source photo (jpg/png)")
    ap.add_argument("-o", "--out", default=str(DEFAULT_OUT))
    ap.add_argument("--width", type=int, default=900,
                    help="working width in px before ASCII downsampling (default 900)")
    ap.add_argument("--no-rembg", action="store_true", help="skip background removal")
    ap.add_argument("--clip", type=float, default=2.6, help="CLAHE clip limit")
    ap.add_argument("--grid", type=int, default=8, help="CLAHE tile grid")
    ap.add_argument("--lo", type=float, default=2.0, help="black-point percentile")
    ap.add_argument("--hi", type=float, default=97.0, help="white-point percentile")
    ap.add_argument("--gamma", type=float, default=1.0,
                    help=">1 brightens midtones (thins the art), <1 darkens")
    args = ap.parse_args()

    src = Path(args.photo)
    if not src.exists():
        print(f"error: {src} not found", file=sys.stderr)
        return 1

    im = ImageOps.exif_transpose(Image.open(src))
    if args.width and im.width > args.width:
        im = im.resize((args.width, round(im.height * args.width / im.width)),
                       Image.LANCZOS)

    if not args.no_rembg:
        im = cut_background(im)
    im = on_white(im)

    gray = np.asarray(im.convert("L"))
    gray = local_contrast(gray, args.clip, args.grid)
    gray = stretch(gray, args.lo, args.hi)
    if abs(args.gamma - 1.0) > 1e-3:
        gray = (255.0 * (gray / 255.0) ** (1.0 / args.gamma)).clip(0, 255).astype(np.uint8)

    out = Path(args.out)
    Image.fromarray(gray).save(out)
    print(f"{out.name}: {out.stat().st_size:,} bytes, {gray.shape[1]}x{gray.shape[0]} grayscale")
    print("next:  python scripts/make_ascii_svg.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
