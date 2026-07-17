"""Convert any image into a Windows .ico for the MacroEngine build.

Usage:
    python tools/make_icon.py path/to/your_image.png
    python tools/make_icon.py path/to/your_image.png -o assets/MacroEngine.ico

The image is centered and padded to a square (transparent padding) so it is not
distorted, then saved as a multi-resolution .ico containing every size Windows
uses (16/24/32/48/64/128/256). Requires Pillow (`pip install Pillow`).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ICON_SIZES = [16, 24, 32, 48, 64, 128, 256]


def make_ico(src: Path, dest: Path) -> None:
    from PIL import Image

    img = Image.open(src).convert("RGBA")

    # Pad to a centered square on a transparent canvas (avoids stretching).
    side = max(img.width, img.height)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(img, ((side - img.width) // 2, (side - img.height) // 2), img)

    # Master 256px, then let Pillow embed all requested sizes.
    master = canvas.resize((256, 256), Image.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    master.save(dest, format="ICO", sizes=[(s, s) for s in ICON_SIZES])
    print(f"Wrote {dest}  (sizes: {', '.join(str(s) for s in ICON_SIZES)})")


def main() -> int:
    ap = argparse.ArgumentParser(description="Make a Windows .ico from an image.")
    ap.add_argument("image", help="Source image (PNG/JPG/etc.)")
    ap.add_argument(
        "-o", "--output", default="assets/MacroEngine.ico",
        help="Output .ico path (default: assets/MacroEngine.ico)",
    )
    args = ap.parse_args()

    src = Path(args.image)
    if not src.exists():
        print(f"Error: image not found: {src}", file=sys.stderr)
        return 1
    try:
        make_ico(src, Path(args.output))
    except ModuleNotFoundError:
        print("Error: Pillow is required. Run:  pip install Pillow", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
