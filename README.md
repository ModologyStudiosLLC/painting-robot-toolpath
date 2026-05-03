# painting-robot-toolpath

G-code toolpath generator for XY gantry painting robots. Converts images into machine-ready G-code with three output modes: edge contours, Ben-Day dot stipple, and raster hatch fill.

Built for the Modology Studios painting robot — C-beam V-slot frame, NEMA 17 steppers, GRBL 1.1, T5 acrylic paint pens on a 4×5ft canvas.

---

## Install

```bash
pip install -r requirements.txt
```

Requires Python 3.9+.

---

## Usage

```bash
# Edge contours from a photo
python3 toolpath.py edges photo.jpg

# Ben-Day dot stipple fill
python3 toolpath.py dots photo.jpg --dot-spacing 4 --dot-radius 1.2

# Raster hatch for solid fills
python3 toolpath.py hatch photo.jpg --line-spacing 1.5

# Preview toolpath before saving (requires display)
python3 toolpath.py edges photo.jpg --preview

# Custom canvas size
python3 toolpath.py edges photo.jpg --canvas-w 1220 --canvas-h 1524
```

Output is a `.gcode` file named `<input>_<mode>.gcode` by default. Pass `-o output.gcode` to specify.

---

## Modes

### `edges` — contour lines from photo edges

Uses Canny edge detection to extract outlines from a photo. Best for portraits, logos, and high-contrast images.

```bash
python3 toolpath.py edges photo.jpg --canny-low 50 --canny-high 150 --blur 3
```

| Flag | Default | Description |
|---|---|---|
| `--canny-low` | 50 | Canny low threshold — lower = more edges |
| `--canny-high` | 150 | Canny high threshold |
| `--blur` | 3 | Gaussian blur kernel before edge detection (0 = off) |

### `dots` — Ben-Day dot stipple

Fills dark areas with a grid of dots. Replicates the halftone dot technique used in comic book printing and pop art. Dark pixels get dots; light pixels get nothing.

```bash
python3 toolpath.py dots photo.jpg --dot-spacing 4 --dot-radius 1.2 --threshold 128
```

| Flag | Default | Description |
|---|---|---|
| `--dot-spacing` | 4.0 mm | Distance between dot centers |
| `--dot-radius` | 1.2 mm | Radius of each dot (drawn as concentric circles) |
| `--threshold` | 128 | Pixel darkness (0–255) below which a dot is placed |

### `hatch` — raster scan fill

Fills dark areas with horizontal lines using a boustrophedon (snake) scan pattern. Good for solid color areas and backgrounds. Minimizes pen travel by alternating scan direction each row.

```bash
python3 toolpath.py hatch photo.jpg --line-spacing 1.5 --threshold 128
```

| Flag | Default | Description |
|---|---|---|
| `--line-spacing` | 1.5 mm | Distance between scan lines |
| `--threshold` | 128 | Pixel darkness below which to draw |

---

## Machine Config

Edit the constants at the top of `toolpath.py` to match your machine:

```python
CANVAS_W_MM   = 1220    # 48 inches = 4 feet
CANVAS_H_MM   = 1524    # 60 inches = 5 feet
FEED_DRAW     = 3000    # mm/min while pen is down
FEED_TRAVEL   = 8000    # mm/min while pen is up
BACKLASH_MM   = 0.4     # pre-approach distance for belt backlash compensation
PEN_DOWN_DWELL = 0.10   # seconds for servo to reach canvas
PEN_UP_DWELL   = 0.05   # seconds for servo to clear canvas
```

Or pass them as CLI flags: `--canvas-w`, `--canvas-h`, `--feed-draw`, `--feed-travel`, `--backlash`.

### Pen control

The generator uses GRBL spindle commands for pen up/down:

- `M3 S1000` — pen down (servo to contact position)
- `M5` — pen up (servo to raised position)

Wire your pen lift servo to the GRBL spindle PWM output. In GRBL, set `$30=1000` (max spindle speed) and `$31=0` (min). The `M3 S1000` command sends full PWM to the servo.

### Backlash compensation

Belt-driven gantries have backlash — the carriage lands at a slightly different position depending on which direction it approached from. This generator always pre-approaches each contour from the same direction (a small overshoot move before the pen-down), which eliminates the visual artifact.

Tune `--backlash` by drawing a test circle and measuring any gap at the seam. A value of 0.3–0.5mm is typical for GT2 belt + NEMA 17 at this scale.

---

## Workflow

1. Run edge/dots/hatch to generate `.gcode`
2. Open in [Universal G-Code Sender](https://winder.github.io/ugs_website/) (free)
3. Jog machine to home position, zero X and Y
4. Run `$H` to home (or manually zero if no homing switches)
5. Load `.gcode`, verify toolpath in visualizer
6. Send to machine

For multi-color paintings: run one mode per color, re-home between passes. Absolute coordinates mean every pass aligns to the same origin.

---

## Hardware

This toolpath generator was built for:

- **Frame:** OpenBuilds C-beam V-slot linear actuators (same as Nerdtronic's painting robot)
- **Motion:** NEMA 17 17HS19-2004S × 3, GT2 belt, A4988 drivers, GRBL 1.1 on Arduino Uno
- **Pen carriage:** Sheet metal flat blank (5052-H32 aluminum, 1.5mm, laser-cut + 3× 90° bends) — see `pen_carriage_sheetmetal.dxf` for SendCutSend upload
- **Pen:** Molotow acrylic pump markers 2mm (recommended) or T5 pens with valve mod
- **Compliance:** Rubber band looped around marker and carriage frame — absorbs Z-axis contact force
- **Canvas:** 4×5ft (1220 × 1524 mm) pre-stretched or MDF + gesso
- **Controller:** CNC Shield v3 on Arduino Uno, Universal G-Code Sender on Raspberry Pi 4B

Full build plan and BOM: [Modology Studios](https://modologystudios.com)

---

## License

CC BY 4.0 — free to use, modify, and build on with attribution.

Built by [Modology Studios](https://modologystudios.com) · Tucker, GA
