# Painting Robot — Project Context

4×5ft (1220×1524mm) XY gantry painting robot. C-beam V-slot frame, NEMA 17 steppers, GRBL 1.1, Molotow acrylic pump markers.

## Key Files
- `README.md` — usage, modes (edges/dots/hatch), machine config
- `HARDWARE.md` — full BOM, assembly order, GRBL config reference
- `toolpath.py` — G-code generator (edges, dots, hatch modes)
- `pen_carriage_sheetmetal.py` — ezdxf script → `pen_carriage_sheetmetal.dxf` for SendCutSend
- `pen_carriage_sheetmetal.dxf` — flat pattern for SendCutSend (5052-H32 Al 1.5mm)

## Pen Carriage (Sheet Metal — Recommended)
- Flat blank: 127.8×111.9mm (includes bend allowance)
- Bends: left+right flanges 25mm, top flange 28mm, all 2mm radius, 90°
- Material: 5052-H32 Aluminum 1.5mm → SendCutSend: deburr + bend 3×90°, ~$35-45
- Pen: Molotow acrylic pump marker 2mm (no valve mod needed)
- Compliance: #64 rubber band looped around marker + carriage frame

## Fusion 360 Script
- `~/Library/Application Support/Autodesk/.../pen_carriage_sm_fusion/pen_carriage_sm_fusion.py`
- Two-sketch approach: outline only → extrude NewBody; holes only → CutFeatureOperation
- Script ran successfully: 120×108mm blank, 16 holes cut
- Personal tier = no "Convert to Sheet Metal" — DXF already done via ezdxf

## Machine Config
- Canvas: 1220×1524mm | Feed draw: 3000mm/min | Feed travel: 8000mm/min
- Pen control: M3 S1000 (down) / M5 (up) via GRBL spindle PWM → $32=1 required
- Steps/mm: $100/$101=80.0 (GT2 belt, 20T pulley, 1/16 microstepping)
- Backlash: ~0.3-0.5mm typical, tune with test circle

## Status (2026-05-03)
- DXF complete, emailed to Nerdtronic (creator) for review — awaiting feedback
- HARDWARE.md and README.md updated with Nerdtronic design elements
- Not yet fabricated
