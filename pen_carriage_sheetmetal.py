#!/usr/bin/env python3
"""
Pen Carriage Sheet Metal Flat Pattern
Modology Studios Painting Robot
SendCutSend: 5052 Aluminum, 1.5mm, deburr + bend

Generates DXF flat pattern + bend annotation SVG.

Usage:
    python3 pen_carriage_sheetmetal.py
    → pen_carriage_sheetmetal.dxf   (upload to sendcutsend.com)
    → pen_carriage_sheetmetal.svg   (assembly reference)

Design concept (from Nerdtronic's Roybot unibody):
  - Single flat blank, laser-cut, then bend 4 tabs
  - Back plate mounts to OpenBuilds gantry plate via 4× M5 holes
  - Left + right flanges (bent 90°) form the side walls
  - Top flange (bent 90°) is the servo mount platform
  - Center: 14mm pen bore + 4× M3 holes for pen clamp
  - Pen slides on two 4mm linear rods through rod holes in flanges

Material: 5052-H32 aluminum, 1.5mm
Bend radius: 2.0mm (1.33× material thickness — SendCutSend standard)
Minimum flange height: 9mm (6× material thickness)
"""

import math
import ezdxf
from ezdxf import colors
from ezdxf.enums import TextEntityAlignment
import svgwrite

OUT_DXF = "/Users/mflanigan/Desktop/Modology Studios/Build Plans/painting-robot/pen_carriage_sheetmetal.dxf"
OUT_SVG = "/Users/mflanigan/Desktop/Modology Studios/Build Plans/painting-robot/pen_carriage_sheetmetal.svg"

# ── Dimensions (mm) ──────────────────────────────────────────────────────────

T   = 1.5    # material thickness
BR  = 2.0    # bend radius (inside radius)
K   = 0.33   # K-factor for 5052-H32 at 1.5mm
BA  = (BR + K * T) * math.pi / 2   # bend allowance for 90° bend

# Back plate (body) — matches existing gantry footprint
BP_W = 80.0   # width
BP_H = 80.0   # height (taller than old 60mm: adds servo platform above gantry)

# Side flanges (left + right, bent 90° forward)
SF_H = 25.0   # flange height when bent (wall depth = carriage depth)
SF_W = 20.0   # flange width

# Top flange (servo mount, bent 90° forward)
TF_H = 28.0   # flange height when bent
TF_W = BP_W   # full width

# Pen bore
PEN_D   = 14.0   # pen bore diameter (T5 pen OD ~12.5mm + clearance)
PEN_X   = BP_W / 2   # centered
PEN_Y   = BP_H / 2   # centered on back plate

# Pen clamp M3 holes (4× around bore, for clamp block)
CLAMP_R = 12.0   # bolt circle radius from bore center
CLAMP_N = 4

# Linear rod holes (2 rods, 4mm diameter, in side flanges)
# Rods pass through left+right flanges, pen holder slides on them
ROD_D   = 4.2    # clearance for 4mm rod
ROD_Y1  = 8.0    # from flange edge (inner)
ROD_Y2  = SF_H - 8.0

# Gantry mounting holes — 4× M5, matching OpenBuilds gantry plate pattern
# OpenBuilds universal gantry plate: 20mm grid, 4× M5 on 40mm sq
GANTRY_HOLES = [
    (BP_W/2 - 20, 20),
    (BP_W/2 + 20, 20),
    (BP_W/2 - 20, 60),
    (BP_W/2 + 20, 60),
]
GANTRY_D = 5.3   # M5 clearance

# Servo (SG90) mount holes on top flange
# SG90 body: 23.1mm × 12.5mm, M2 mount tabs 5mm from body face
SERVO_HOLES = [
    (TF_W/2 - 14.5, TF_H - 5),
    (TF_W/2 + 14.5, TF_H - 5),
]
SERVO_SLOT_W = 6.0    # servo output shaft slot
SERVO_SLOT_L = 12.0
SERVO_D      = 2.2    # M2 clearance

# ── Flat pattern layout (unfolded) ──────────────────────────────────────────
# Layout from bottom to top:
#   [left flange] | [back plate] | [right flange]
#   [top flange above back plate]
#
# Flat width  = SF_W + BA + BP_W + BA + SF_W
# Flat height = TF_H + BA + BP_H

FLAT_W = SF_W + BA + BP_W + BA + SF_W
FLAT_H = TF_H + BA + BP_H

# Origin offsets for each zone
LEFT_FLANGE_X  = 0
BACK_PLATE_X   = SF_W + BA
RIGHT_FLANGE_X = SF_W + BA + BP_W + BA

TOP_FLANGE_Y   = 0
BACK_PLATE_Y   = TF_H + BA


def add_circle(msp, cx, cy, r, layer="CUT"):
    msp.add_circle((cx, cy), r, dxfattribs={"layer": layer})

def add_slot(msp, cx, cy, w, h, layer="CUT"):
    """Rounded rectangle (slot)."""
    r = min(w, h) / 2
    if w > h:
        msp.add_line((cx - w/2 + r, cy - h/2), (cx + w/2 - r, cy - h/2), dxfattribs={"layer": layer})
        msp.add_line((cx + w/2 - r, cy + h/2), (cx - w/2 + r, cy + h/2), dxfattribs={"layer": layer})
        msp.add_arc((cx - w/2 + r, cy), r, 90, 270, dxfattribs={"layer": layer})
        msp.add_arc((cx + w/2 - r, cy), r, 270, 90, dxfattribs={"layer": layer})
    else:
        msp.add_line((cx - w/2, cy - h/2 + r), (cx - w/2, cy + h/2 - r), dxfattribs={"layer": layer})
        msp.add_line((cx + w/2, cy + h/2 - r), (cx + w/2, cy - h/2 + r), dxfattribs={"layer": layer})
        msp.add_arc((cx, cy - h/2 + r), r, 180, 360, dxfattribs={"layer": layer})
        msp.add_arc((cx, cy + h/2 - r), r, 0, 180, dxfattribs={"layer": layer})

def add_rect(msp, x0, y0, w, h, layer="CUT"):
    pts = [(x0,y0),(x0+w,y0),(x0+w,y0+h),(x0,y0+h),(x0,y0)]
    msp.add_lwpolyline(pts, dxfattribs={"layer": layer})

def add_bend_line(msp, x0, y0, x1, y1):
    msp.add_line((x0, y0), (x1, y1), dxfattribs={"layer": "BEND", "linetype": "DASHED"})


def build_dxf():
    doc = ezdxf.new("R2010")
    doc.layers.new("CUT",  dxfattribs={"color": colors.RED,    "lineweight": 35})
    doc.layers.new("BEND", dxfattribs={"color": colors.BLUE,   "lineweight": 18, "linetype": "DASHED"})
    doc.layers.new("NOTES",dxfattribs={"color": colors.YELLOW, "lineweight": 9})
    try:
        doc.linetypes.add("DASHED", pattern="A,.5,-.25")
    except Exception:
        pass

    msp = doc.modelspace()

    # ── Outer profile ────────────────────────────────────────────────────────
    # Left flange zone: x=0..SF_W, y=BACK_PLATE_Y..BACK_PLATE_Y+SF_H
    # Right flange: x=RIGHT_FLANGE_X..FLAT_W, same Y
    # Top flange: x=BACK_PLATE_X..BACK_PLATE_X+BP_W, y=0..TF_H
    # Back plate: x=BACK_PLATE_X..BACK_PLATE_X+BP_W, y=BACK_PLATE_Y..BACK_PLATE_Y+BP_H

    # Build outline as a polyline with corners
    pts = [
        # Start bottom-left of left flange
        (LEFT_FLANGE_X,              BACK_PLATE_Y),
        (LEFT_FLANGE_X,              BACK_PLATE_Y + SF_H),
        (BACK_PLATE_X,               BACK_PLATE_Y + SF_H),
        (BACK_PLATE_X,               BACK_PLATE_Y + BP_H),
        # Top flange
        (BACK_PLATE_X,               TF_H),
        (BACK_PLATE_X,               0),
        (BACK_PLATE_X + BP_W,        0),
        (BACK_PLATE_X + BP_W,        TF_H),
        (BACK_PLATE_X + BP_W,        BACK_PLATE_Y + BP_H),
        # Right side going down
        (RIGHT_FLANGE_X + SF_W,      BACK_PLATE_Y + SF_H),
        (RIGHT_FLANGE_X,             BACK_PLATE_Y + SF_H),
        (RIGHT_FLANGE_X,             BACK_PLATE_Y),
        # Bottom: connect back to start
        (LEFT_FLANGE_X,              BACK_PLATE_Y),
    ]
    msp.add_lwpolyline(pts, dxfattribs={"layer": "CUT"})

    # ── Bend lines ───────────────────────────────────────────────────────────
    # Left flange bend (vertical line at x = BACK_PLATE_X)
    add_bend_line(msp, BACK_PLATE_X, BACK_PLATE_Y, BACK_PLATE_X, BACK_PLATE_Y + SF_H)
    # Right flange bend
    add_bend_line(msp, RIGHT_FLANGE_X, BACK_PLATE_Y, RIGHT_FLANGE_X, BACK_PLATE_Y + SF_H)
    # Top flange bend (horizontal line at y = TF_H)
    add_bend_line(msp, BACK_PLATE_X, TF_H, BACK_PLATE_X + BP_W, TF_H)

    # ── Back plate features ──────────────────────────────────────────────────
    bx = BACK_PLATE_X
    by = BACK_PLATE_Y

    # Gantry M5 holes
    for (hx, hy) in GANTRY_HOLES:
        add_circle(msp, bx + hx, by + hy, GANTRY_D/2)

    # Pen bore (center of back plate)
    add_circle(msp, bx + PEN_X, by + PEN_Y, PEN_D/2)

    # Pen clamp M3 holes (4× around bore)
    for i in range(CLAMP_N):
        ang = math.pi/4 + i * math.pi/2
        cx = bx + PEN_X + CLAMP_R * math.cos(ang)
        cy = by + PEN_Y + CLAMP_R * math.sin(ang)
        add_circle(msp, cx, cy, 1.6)   # M3 clearance

    # ── Top flange features (servo) ──────────────────────────────────────────
    tx = BACK_PLATE_X
    ty = 0  # top flange starts at y=0

    # Servo output shaft slot (centered)
    add_slot(msp, tx + TF_W/2, ty + TF_H/2, SERVO_SLOT_L, SERVO_SLOT_W)

    # Servo M2 mount holes
    for (sx, sy) in SERVO_HOLES:
        add_circle(msp, tx + sx, ty + sy, SERVO_D/2)

    # ── Side flange features (rod holes) ────────────────────────────────────
    # Left flange: x = 0..SF_W, y = BACK_PLATE_Y..BACK_PLATE_Y+SF_H
    lx = 0
    ly = BACK_PLATE_Y
    add_circle(msp, lx + SF_W/2, ly + ROD_Y1, ROD_D/2)
    add_circle(msp, lx + SF_W/2, ly + ROD_Y2, ROD_D/2)

    # Right flange
    rx = RIGHT_FLANGE_X
    ry = BACK_PLATE_Y
    add_circle(msp, rx + SF_W/2, ry + ROD_Y1, ROD_D/2)
    add_circle(msp, rx + SF_W/2, ry + ROD_Y2, ROD_D/2)

    # ── Dimension / notes ────────────────────────────────────────────────────
    notes = [
        f"MAT: 5052-H32 Aluminum 1.5mm",
        f"FINISH: Deburr all edges",
        f"BENDS: 3× 90°, inside radius {BR}mm",
        f"Flat blank: {FLAT_W:.1f} × {FLAT_H:.1f} mm",
        f"BLUE DASHED = bend lines (fold toward you / viewer side)",
        f"Qty: 1",
    ]
    for i, note in enumerate(notes):
        msp.add_text(note, height=3.0, dxfattribs={
            "layer": "NOTES",
            "insert": (FLAT_W + 10, FLAT_H - 10 - i * 8),
        })

    doc.saveas(OUT_DXF)
    print(f"DXF saved: {OUT_DXF}")
    print(f"Flat blank: {FLAT_W:.1f} × {FLAT_H:.1f} mm")
    print(f"Bend allowance: {BA:.2f} mm per bend")


def build_svg():
    """Assembly reference SVG showing bent shape (side view)."""
    W, H = 400, 300
    dwg = svgwrite.Drawing(OUT_SVG, size=(f"{W}px", f"{H}px"))
    dwg.add(dwg.rect((0,0),(W,H), fill="white"))

    # Draw isometric-ish 3D sketch of bent carriage
    # Back plate (rectangle)
    ox, oy = 100, 80
    bw, bh = 120, 120
    dwg.add(dwg.rect((ox, oy), (bw, bh),
        fill="none", stroke="#e74c3c", stroke_width=2))

    # Left flange (bent forward = drawn to the left)
    fl = 35
    pts_l = [(ox,oy+20),(ox-fl,oy+20),(ox-fl,oy+20+37),(ox,oy+20+37)]
    dwg.add(dwg.polygon(pts_l, fill="#eaf0fb", stroke="#2980b9", stroke_width=2))

    # Right flange
    pts_r = [(ox+bw,oy+20),(ox+bw+fl,oy+20),(ox+bw+fl,oy+20+37),(ox+bw,oy+20+37)]
    dwg.add(dwg.polygon(pts_r, fill="#eaf0fb", stroke="#2980b9", stroke_width=2))

    # Top flange
    pts_t = [(ox,oy),(ox,oy-42),(ox+bw,oy-42),(ox+bw,oy)]
    dwg.add(dwg.polygon(pts_t, fill="#eaf0fb", stroke="#2980b9", stroke_width=2))

    # Pen bore circle on back plate
    dwg.add(dwg.circle((ox+bw//2, oy+bh//2), 10, fill="none", stroke="#27ae60", stroke_width=2))

    # Servo rectangle on top flange
    dwg.add(dwg.rect((ox+bw//2-17, oy-35), (34, 19), fill="none", stroke="#8e44ad", stroke_width=1.5))

    # Labels
    style = "font:bold 11px sans-serif"
    dwg.add(dwg.text("Back plate (gantry mount)", insert=(ox+bw+8, oy+bh//2), style="font:10px sans-serif;fill:#e74c3c"))
    dwg.add(dwg.text("Side flange (rod holes)", insert=(ox-fl-5, oy+38), style="font:10px sans-serif;fill:#2980b9", text_anchor="end"))
    dwg.add(dwg.text("Top flange (servo)", insert=(ox+bw//2, oy-48), style="font:10px sans-serif;fill:#8e44ad", text_anchor="middle"))
    dwg.add(dwg.text("Pen bore Ø14", insert=(ox+bw//2, oy+bh//2+24), style="font:10px sans-serif;fill:#27ae60", text_anchor="middle"))

    dwg.add(dwg.text("Pen Carriage — Sheet Metal — SendCutSend",
        insert=(W//2, 270), style="font:bold 13px sans-serif;fill:#333", text_anchor="middle"))
    dwg.add(dwg.text("5052-H32 Alum 1.5mm · 3× 90° bends",
        insert=(W//2, 288), style="font:11px sans-serif;fill:#666", text_anchor="middle"))

    dwg.save()
    print(f"SVG saved: {OUT_SVG}")


if __name__ == "__main__":
    build_dxf()
    try:
        import svgwrite
        build_svg()
    except ImportError:
        print("svgwrite not installed, skipping SVG reference drawing")
