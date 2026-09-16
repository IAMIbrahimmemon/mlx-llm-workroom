#!/usr/bin/env python
"""Draw the Workroom app icon and build the .icns.

The mark is the same thing the welcome screen animates: a warm core held
inside concentric rings -- one model, resident, with room around it. Drawn
here rather than shipped as a binary so the colours stay tied to the design
tokens and anyone can re-render it.

    uv run python scripts/make_icon.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

# Design tokens, from design/_theme.txt.
BG_TOP = (28, 26, 24)
BG_BOTTOM = (19, 18, 17)
EMBER = (224, 138, 94)
EMBER_DEEP = (192, 96, 58)
RING = (58, 54, 51)

#: Rendered large and downsampled -- macOS icons are viewed at 32px as often
#: as at 512, and supersampling is what keeps the thin rings from breaking up.
SUPER = 4


def rounded_mask(size: int, radius_ratio: float = 0.2237) -> Image.Image:
    """macOS 'squircle', approximated with a rounded rectangle at Apple's ratio."""
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [(0, 0), (size - 1, size - 1)], radius=int(size * radius_ratio), fill=255
    )
    return mask


def draw_icon(px: int) -> Image.Image:
    """One tile. Rings are drawn in ember at low opacity rather than grey, so
    they stay visible at 32px instead of dissolving into the background."""
    s = px * SUPER
    base = Image.new("RGB", (s, s), BG_BOTTOM)
    d = ImageDraw.Draw(base)

    # Vertical warm gradient so the tile has depth without a colour wash.
    for y in range(s):
        t = y / max(1, s - 1)
        d.line([(0, y), (s, y)], fill=tuple(
            int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3)
        ))

    cx = cy = s / 2

    # Halo: an ember disc blurred just enough to bloom, composited by its own
    # alpha so it lightens the background instead of greying it out.
    halo = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    hr = s * 0.20
    ImageDraw.Draw(halo).ellipse(
        [cx - hr, cy - hr, cx + hr, cy + hr], fill=(*EMBER_DEEP, 190)
    )
    halo = halo.filter(ImageFilter.GaussianBlur(s * 0.055))
    base = Image.alpha_composite(base.convert("RGBA"), halo)

    # Three rings, matching the welcome screen's 0 / 44 / 88 insets.
    rings = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    rd = ImageDraw.Draw(rings)
    for frac, width, alpha in ((0.400, 0.006, 70), (0.300, 0.006, 95), (0.208, 0.007, 130)):
        r = s * frac
        rd.ellipse([cx - r, cy - r, cx + r, cy + r],
                   outline=(*EMBER, alpha), width=max(SUPER, int(s * width)))
    base = Image.alpha_composite(base, rings)

    # The core.
    core = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    cr = s * 0.128
    ImageDraw.Draw(core).ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=(*EMBER, 255))
    base = Image.alpha_composite(base, core)

    base = base.convert("RGB").resize((px, px), Image.LANCZOS)
    out = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    out.paste(base, (0, 0), rounded_mask(px))
    return out


def main() -> int:
    ASSETS.mkdir(exist_ok=True)
    iconset = ASSETS / "Workroom.iconset"
    if iconset.exists():
        for f in iconset.iterdir():
            f.unlink()
    iconset.mkdir(exist_ok=True)

    # The exact set iconutil expects.
    for base in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            px = base * scale
            name = f"icon_{base}x{base}{'@2x' if scale == 2 else ''}.png"
            draw_icon(px).save(iconset / name)

    draw_icon(1024).save(ASSETS / "icon.png")
    draw_icon(512).save(ASSETS / "icon-512.png")

    try:
        subprocess.run(["iconutil", "-c", "icns", str(iconset),
                        "-o", str(ASSETS / "Workroom.icns")], check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"iconutil failed: {exc}", file=sys.stderr)
        return 1

    icns = ASSETS / "Workroom.icns"
    print(f"wrote {icns.relative_to(ROOT)} ({icns.stat().st_size / 1024:.0f} KB) "
          f"and assets/icon.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
