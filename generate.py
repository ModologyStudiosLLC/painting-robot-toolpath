#!/usr/bin/env python3
"""
FLUX → Toolpath Generator
Modology Studios Painting Robot

Generates an image from a text prompt via FLUX (Replicate), then pipes it
straight into toolpath.py to produce machine-ready G-code.

Usage:
  # Prompt → G-code (generate + convert in one step)
  python3 generate.py "noir portrait of a woman" --mode edges

  # Existing image → G-code (skip generation, just convert)
  python3 generate.py --image photo.jpg --mode dots

  # Full control
  python3 generate.py "abstract geometric cityscape" --mode hatch --line-spacing 2.0 --canny-low 30

  # Preview before saving
  python3 generate.py "bold typographic design" --mode edges --preview

Requires:
  pip install replicate requests
  export REPLICATE_API_TOKEN=your_token   (get one at replicate.com)

All toolpath.py flags (--canvas-w, --canvas-h, --canny-low, --canny-high,
--blur, --dot-spacing, --dot-radius, --line-spacing, --threshold, --invert,
--preview, --backlash, --feed-draw, --feed-travel) pass through unchanged.
"""

import argparse
import os
import sys
import time
import tempfile
import urllib.request
from pathlib import Path

FLUX_MODEL = "black-forest-labs/flux-schnell"
FLUX_ASPECT = "4:5"          # closest to 4×5ft canvas ratio
FLUX_OUTPUT_FORMAT = "png"
TOOLPATH = Path(__file__).parent / "toolpath.py"


def generate_image(prompt: str, output_path: Path) -> None:
    try:
        import replicate
    except ImportError:
        sys.exit("Error: replicate not installed. Run: pip install replicate")

    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        sys.exit("Error: REPLICATE_API_TOKEN not set. Export it or add to .env")

    print(f"Generating: {prompt!r}")
    output = replicate.run(
        FLUX_MODEL,
        input={
            "prompt": prompt,
            "aspect_ratio": FLUX_ASPECT,
            "output_format": FLUX_OUTPUT_FORMAT,
            "num_outputs": 1,
        },
    )

    # Replicate returns a list of FileOutput objects
    url = str(output[0])
    print(f"Downloading image...")
    urllib.request.urlretrieve(url, output_path)
    print(f"Saved to: {output_path}")

    # Rate limit guard (see CLAUDE.md applied learning)
    time.sleep(15)


def run_toolpath(image_path: Path, args: argparse.Namespace) -> None:
    cmd = [sys.executable, str(TOOLPATH), args.mode, str(image_path)]

    if args.output:
        cmd += ["-o", args.output]
    if args.canvas_w != 1220:
        cmd += ["--canvas-w", str(args.canvas_w)]
    if args.canvas_h != 1524:
        cmd += ["--canvas-h", str(args.canvas_h)]
    if args.feed_draw != 3000:
        cmd += ["--feed-draw", str(args.feed_draw)]
    if args.feed_travel != 8000:
        cmd += ["--feed-travel", str(args.feed_travel)]
    if args.backlash != 0.4:
        cmd += ["--backlash", str(args.backlash)]
    if args.canny_low != 50:
        cmd += ["--canny-low", str(args.canny_low)]
    if args.canny_high != 150:
        cmd += ["--canny-high", str(args.canny_high)]
    if args.blur != 3:
        cmd += ["--blur", str(args.blur)]
    if args.dot_spacing != 4.0:
        cmd += ["--dot-spacing", str(args.dot_spacing)]
    if args.dot_radius != 1.2:
        cmd += ["--dot-radius", str(args.dot_radius)]
    if args.line_spacing != 1.5:
        cmd += ["--line-spacing", str(args.line_spacing)]
    if args.threshold != 128:
        cmd += ["--threshold", str(args.threshold)]
    if args.invert:
        cmd += ["--invert"]
    if args.preview:
        cmd += ["--preview"]
    if args.no_sort:
        cmd += ["--no-sort"]

    import subprocess
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


def main():
    p = argparse.ArgumentParser(
        description="FLUX → Toolpath: generate or ingest an image and produce G-code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Source: prompt OR image
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("prompt", nargs="?", help="Text prompt for FLUX image generation")
    src.add_argument("--image", metavar="PATH", help="Skip generation, use this image directly")

    # Toolpath mode
    p.add_argument("--mode", choices=["edges", "dots", "hatch"], default="edges",
                   help="Toolpath mode (default: edges)")

    # Output
    p.add_argument("-o", "--output", help="Output .gcode path")
    p.add_argument("--save-image", metavar="PATH",
                   help="Save the generated image to this path (default: auto-named next to .gcode)")

    # Canvas / machine
    p.add_argument("--canvas-w",    type=float, default=1220,  metavar="MM")
    p.add_argument("--canvas-h",    type=float, default=1524,  metavar="MM")
    p.add_argument("--feed-draw",   type=int,   default=3000,  metavar="MM/MIN")
    p.add_argument("--feed-travel", type=int,   default=8000,  metavar="MM/MIN")
    p.add_argument("--backlash",    type=float, default=0.4,   metavar="MM")

    # Edges mode
    p.add_argument("--canny-low",  type=int,   default=50)
    p.add_argument("--canny-high", type=int,   default=150)
    p.add_argument("--blur",       type=int,   default=3)

    # Dots mode
    p.add_argument("--dot-spacing", type=float, default=4.0, metavar="MM")
    p.add_argument("--dot-radius",  type=float, default=1.2, metavar="MM")

    # Hatch mode
    p.add_argument("--line-spacing", type=float, default=1.5, metavar="MM")

    # Shared
    p.add_argument("--threshold", type=int,   default=128)
    p.add_argument("--invert",    action="store_true")
    p.add_argument("--preview",   action="store_true")
    p.add_argument("--no-sort",   action="store_true")

    args = p.parse_args()

    if not TOOLPATH.exists():
        sys.exit(f"Error: toolpath.py not found at {TOOLPATH}")

    if args.image:
        # Direct image mode — skip generation
        image_path = Path(args.image)
        if not image_path.exists():
            sys.exit(f"Error: image not found: {image_path}")
        run_toolpath(image_path, args)

    else:
        # FLUX generation mode
        if args.save_image:
            image_path = Path(args.save_image)
        else:
            # Auto-name: slug of prompt next to the gcode output
            slug = args.prompt[:40].lower().replace(" ", "_")
            slug = "".join(c for c in slug if c.isalnum() or c == "_")
            image_path = Path(f"generated_{slug}.png")

        generate_image(args.prompt, image_path)
        run_toolpath(image_path, args)


if __name__ == "__main__":
    main()
