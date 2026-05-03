#!/usr/bin/env python3
"""
Painting Robot Toolpath Generator
Modology Studios — XY Gantry, GRBL 1.1, T5 Paint Pens

Usage:
  python3 toolpath.py edges input.jpg              # edge contours from photo
  python3 toolpath.py dots input.jpg               # Ben-Day dot stipple fill
  python3 toolpath.py hatch input.jpg              # raster hatch for solid fills
  python3 toolpath.py edges input.jpg --preview    # show edge preview before saving
  python3 toolpath.py edges input.jpg -o out.gcode --canvas-w 1220 --canvas-h 1524

Machine defaults (4x5ft canvas, C-beam V-slot, NEMA17, GRBL 1.1):
  Canvas:      1220 x 1524 mm  (48 x 60 inches)
  Pen down:    M3 S1000  (servo to contact position)
  Pen up:      M5        (servo to raised position)
  Draw feed:   3000 mm/min
  Travel feed: 8000 mm/min

Dependencies: pip install opencv-python numpy
"""

import cv2
import numpy as np
import argparse
import os
import sys
from pathlib import Path

# ── Machine config (edit these to match your build) ───────────────────────────
CANVAS_W_MM   = 1220    # 48 inches = 4 feet
CANVAS_H_MM   = 1524    # 60 inches = 5 feet
FEED_DRAW     = 3000    # mm/min while pen is down
FEED_TRAVEL   = 8000    # mm/min while pen is up (rapid)
BACKLASH_MM   = 0.4     # pre-approach overshoot to eliminate belt backlash
PEN_DOWN_DWELL = 0.10   # seconds for servo to reach canvas
PEN_UP_DWELL   = 0.05   # seconds for servo to clear canvas
MIN_CONTOUR_PX = 5      # ignore contours shorter than this (noise filter)


# ── Image loading + resizing ──────────────────────────────────────────────────

def load_gray(path):
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        sys.exit(f"Error: could not load image: {path}")
    return img


def fit_to_canvas(img, canvas_w, canvas_h):
    """Resize image to fill canvas while preserving aspect ratio. Returns (img, scale_x, scale_y, offset_x, offset_y)."""
    h, w = img.shape[:2]
    scale = min(canvas_w / w, canvas_h / h)
    nw, nh = int(w * scale), int(h * scale)
    img = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
    # Center on canvas
    ox = (canvas_w - nw * scale) / 2  # always 0 since we fit, but explicit
    oy = (canvas_h - nh * scale) / 2
    ox, oy = 0.0, 0.0
    return img, canvas_w / nw, canvas_h / nh, ox, oy


# ── Mode: edges ───────────────────────────────────────────────────────────────

def mode_edges(img, canvas_w, canvas_h, low, high, blur):
    """Canny edge detection → list of polyline contours in mm."""
    if blur > 0:
        k = blur | 1  # ensure odd
        img = cv2.GaussianBlur(img, (k, k), 0)

    edges = cv2.Canny(img, low, high)
    img_fit, sx, sy, ox, oy = fit_to_canvas(edges, canvas_w, canvas_h)

    raw, _ = cv2.findContours(img_fit, cv2.RETR_LIST, cv2.CHAIN_APPROX_TC89_L1)

    contours = []
    for c in raw:
        if len(c) < MIN_CONTOUR_PX:
            continue
        pts = [(float(p[0][0]) + ox, float(p[0][1]) + oy) for p in c]
        contours.append(pts)

    return contours, edges


# ── Mode: dots (Ben-Day stipple) ──────────────────────────────────────────────

def mode_dots(img, canvas_w, canvas_h, dot_spacing, dot_radius, threshold):
    """
    Generate Ben-Day dot fill. Dark areas get dots; light areas get nothing.
    Each dot is drawn as a tiny circle (concentric G-code arcs).
    dot_spacing: mm between dot centers
    dot_radius:  mm radius of each dot
    threshold:   pixel darkness (0-255) below which a dot is placed
    """
    img_fit, sx, sy, ox, oy = fit_to_canvas(img, canvas_w, canvas_h)
    h, w = img_fit.shape[:2]

    contours = []
    steps = max(1, int(dot_spacing / sx))  # pixel step between dots

    for py in range(0, h, steps):
        for px in range(0, w, steps):
            if img_fit[py, px] < threshold:
                cx = px * sx + ox
                cy = py * sy + oy
                # Draw dot as concentric circles from outside in
                n_rings = max(1, int(dot_radius / 0.3))
                for ring in range(n_rings, 0, -1):
                    r = dot_radius * ring / n_rings
                    circle_pts = _circle_pts(cx, cy, r, segments=16)
                    contours.append(circle_pts)

    return contours


def _circle_pts(cx, cy, r, segments=16):
    pts = []
    for i in range(segments + 1):
        angle = 2 * np.pi * i / segments
        pts.append((cx + r * np.cos(angle), cy + r * np.sin(angle)))
    return pts


# ── Mode: hatch (solid fill via raster scan) ──────────────────────────────────

def mode_hatch(img, canvas_w, canvas_h, line_spacing, threshold):
    """
    Raster scan: draw horizontal lines across dark regions.
    line_spacing: mm between scan lines
    threshold:    darkness below which to draw
    """
    img_fit, sx, sy, ox, oy = fit_to_canvas(img, canvas_w, canvas_h)
    h, w = img_fit.shape[:2]

    contours = []
    step_px = max(1, int(line_spacing / sy))
    left_to_right = True

    for py in range(0, h, step_px):
        y_mm = py * sy + oy
        row = img_fit[py, :]

        # Find runs of dark pixels
        dark = row < threshold
        runs = _find_runs(dark)

        if not left_to_right:
            runs = [(w - 1 - end, w - 1 - start) for start, end in reversed(runs)]

        for start_px, end_px in runs:
            x0 = start_px * sx + ox
            x1 = end_px * sx + ox
            if abs(x1 - x0) < 1.0:  # skip sub-mm runs
                continue
            if left_to_right:
                contours.append([(x0, y_mm), (x1, y_mm)])
            else:
                contours.append([(x1, y_mm), (x0, y_mm)])

        left_to_right = not left_to_right  # boustrophedon (snake) scan

    return contours


def _find_runs(mask):
    """Find (start, end) pixel indices of True runs in a 1D boolean array."""
    runs = []
    in_run = False
    start = 0
    for i, v in enumerate(mask):
        if v and not in_run:
            start = i
            in_run = True
        elif not v and in_run:
            runs.append((start, i - 1))
            in_run = False
    if in_run:
        runs.append((start, len(mask) - 1))
    return runs


# ── Path optimization: nearest-neighbor sort ─────────────────────────────────

def nearest_neighbor_sort(contours):
    """Reorder contours to minimize total pen travel distance."""
    if not contours:
        return contours

    result = [contours[0]]
    remaining = list(contours[1:])
    last_pt = contours[0][-1]

    while remaining:
        best_i, best_d, best_flip = 0, float('inf'), False
        for i, c in enumerate(remaining):
            d_fwd = _dist2(last_pt, c[0])
            d_rev = _dist2(last_pt, c[-1])
            d = min(d_fwd, d_rev)
            if d < best_d:
                best_d = d
                best_i = i
                best_flip = d_rev < d_fwd

        c = remaining.pop(best_i)
        if best_flip:
            c = list(reversed(c))
        result.append(c)
        last_pt = c[-1]

    return result


def _dist2(a, b):
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


# ── G-code generation ─────────────────────────────────────────────────────────

def generate_gcode(contours, out_path, feed_draw, feed_travel, backlash,
                   pen_down_dwell, pen_up_dwell, canvas_w, canvas_h, source_name):
    total_pts = sum(len(c) for c in contours)

    lines = [
        f"; Painting Robot — Modology Studios",
        f"; Source: {source_name}",
        f"; Canvas: {canvas_w} x {canvas_h} mm",
        f"; Contours: {len(contours)}  |  Points: {total_pts}",
        f"; Feed draw: {feed_draw} mm/min  |  Feed travel: {feed_travel} mm/min",
        f"; Backlash pre-approach: {backlash} mm",
        "",
        "G90           ; absolute coordinates",
        "G21           ; millimeters",
        "M5            ; pen up — ensure raised before homing",
        "$H            ; GRBL home cycle (remove if homing switches not installed)",
        "G92 X0 Y0     ; set home as origin",
        "",
    ]

    for i, contour in enumerate(contours):
        if len(contour) < 2:
            continue

        x0, y0 = contour[0]

        lines.append(f"; [{i+1}/{len(contours)}]")
        # Backlash pre-approach: overshoot to the left, then approach from left
        lines.append(f"G0 F{feed_travel} X{x0 - backlash:.3f} Y{y0:.3f}")
        lines.append(f"G0 X{x0:.3f} Y{y0:.3f}")
        if pen_down_dwell > 0:
            lines.append(f"G4 P{pen_down_dwell:.2f}")
        lines.append("M3 S1000      ; pen down")
        if pen_down_dwell > 0:
            lines.append(f"G4 P{pen_down_dwell:.2f}")

        lines.append(f"G1 F{feed_draw}")
        for x, y in contour[1:]:
            lines.append(f"G1 X{x:.3f} Y{y:.3f}")

        lines.append("M5            ; pen up")
        if pen_up_dwell > 0:
            lines.append(f"G4 P{pen_up_dwell:.2f}")
        lines.append("")

    lines += [
        "; Done",
        "M5",
        f"G0 F{feed_travel} X0 Y0  ; return home",
    ]

    with open(out_path, "w") as f:
        f.write("\n".join(lines))

    return len(lines), total_pts


# ── Preview ───────────────────────────────────────────────────────────────────

def show_preview(contours, canvas_w, canvas_h, title="Toolpath Preview"):
    pw = 900
    ph = int(pw * canvas_h / canvas_w)
    img = np.zeros((ph, pw, 3), np.uint8)
    sx = pw / canvas_w
    sy = ph / canvas_h

    for c in contours:
        pts = np.array([(int(x * sx), int(y * sy)) for x, y in c], np.int32)
        cv2.polylines(img, [pts], False, (0, 220, 100), 1)

    cv2.imshow(title, img)
    print("Preview open — press any key to continue and save G-code.")
    cv2.waitKey(0)
    cv2.destroyAllWindows()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__,
    )
    p.add_argument("mode", choices=["edges", "dots", "hatch"],
                   help="edges=contour lines  dots=stipple fill  hatch=raster scan")
    p.add_argument("image", help="Input image (JPEG, PNG, etc.)")
    p.add_argument("-o", "--output", help="Output .gcode path (default: <image>_<mode>.gcode)")
    p.add_argument("--canvas-w",    type=float, default=CANVAS_W_MM, metavar="MM", help=f"Canvas width mm (default {CANVAS_W_MM})")
    p.add_argument("--canvas-h",    type=float, default=CANVAS_H_MM, metavar="MM", help=f"Canvas height mm (default {CANVAS_H_MM})")
    p.add_argument("--feed-draw",   type=int,   default=FEED_DRAW,   metavar="MM/MIN")
    p.add_argument("--feed-travel", type=int,   default=FEED_TRAVEL, metavar="MM/MIN")
    p.add_argument("--backlash",    type=float, default=BACKLASH_MM, metavar="MM",
                   help="Backlash pre-approach distance (default 0.4mm — tune per machine)")

    # edges options
    p.add_argument("--canny-low",  type=int, default=50,  metavar="N", help="Canny low threshold (default 50)")
    p.add_argument("--canny-high", type=int, default=150, metavar="N", help="Canny high threshold (default 150)")
    p.add_argument("--blur",       type=int, default=3,   metavar="PX", help="Gaussian blur kernel before Canny (0=off, default 3)")

    # dots options
    p.add_argument("--dot-spacing", type=float, default=4.0, metavar="MM", help="Dot center spacing mm (default 4.0)")
    p.add_argument("--dot-radius",  type=float, default=1.2, metavar="MM", help="Dot radius mm (default 1.2)")

    # hatch options
    p.add_argument("--line-spacing", type=float, default=1.5, metavar="MM", help="Hatch line spacing mm (default 1.5)")

    # shared
    p.add_argument("--threshold", type=int, default=128, metavar="0-255",
                   help="Darkness threshold for dots/hatch (default 128)")
    p.add_argument("--invert",   action="store_true", help="Invert image before processing")
    p.add_argument("--preview",  action="store_true", help="Show toolpath preview before saving")
    p.add_argument("--no-sort",  action="store_true", help="Skip nearest-neighbor sort (faster for large files)")

    args = p.parse_args()

    img = load_gray(args.image)
    if args.invert:
        img = cv2.bitwise_not(img)

    print(f"Image: {args.image}  ({img.shape[1]}×{img.shape[0]} px)")
    print(f"Canvas: {args.canvas_w} × {args.canvas_h} mm")
    print(f"Mode: {args.mode}")

    # Run selected mode
    if args.mode == "edges":
        contours, _ = mode_edges(img, args.canvas_w, args.canvas_h,
                                 args.canny_low, args.canny_high, args.blur)
    elif args.mode == "dots":
        contours = mode_dots(img, args.canvas_w, args.canvas_h,
                             args.dot_spacing, args.dot_radius, args.threshold)
    elif args.mode == "hatch":
        contours = mode_hatch(img, args.canvas_w, args.canvas_h,
                              args.line_spacing, args.threshold)

    print(f"Contours: {len(contours)}")

    if not args.no_sort:
        print("Sorting (nearest-neighbor)...")
        contours = nearest_neighbor_sort(contours)

    if args.preview:
        show_preview(contours, args.canvas_w, args.canvas_h,
                     title=f"Toolpath — {args.mode} — {Path(args.image).name}")

    out = args.output or str(Path(args.image).with_suffix("")) + f"_{args.mode}.gcode"
    n_lines, n_pts = generate_gcode(
        contours, out,
        args.feed_draw, args.feed_travel, args.backlash,
        PEN_DOWN_DWELL, PEN_UP_DWELL,
        args.canvas_w, args.canvas_h,
        source_name=os.path.basename(args.image),
    )

    travel = _estimate_travel(contours)
    print(f"G-code lines: {n_lines}")
    print(f"Total points: {n_pts}")
    print(f"Pen lifts:    {len(contours)}")
    print(f"Est. travel:  {travel/1000:.1f} m")
    print(f"Est. time:    {_estimate_time(contours, args.feed_draw, args.feed_travel):.0f} min")
    print(f"Saved: {out}")


def _estimate_travel(contours):
    total = 0.0
    for c in contours:
        for i in range(1, len(c)):
            total += np.sqrt(_dist2(c[i], c[i-1]))
    return total


def _estimate_time(contours, feed_draw, feed_travel):
    draw_mm = _estimate_travel(contours)
    # travel between contours (rough: assume avg 100mm between pen lifts)
    travel_mm = len(contours) * 100
    return (draw_mm / feed_draw + travel_mm / feed_travel)


if __name__ == "__main__":
    main()
