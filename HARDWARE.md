# Hardware Build List

Everything you need to build a 4×5ft XY painting robot. Total estimated cost: **~$668**.

This list matches the Modology Studios build exactly. Substitutions are noted where available.

---

## Frame & Motion

| Part | Qty | Est. Cost | Notes |
|---|---|---|---|
| OpenBuilds C-beam linear actuator 1500mm | 1 | $65 | X-axis — openbuildspartstore.com |
| OpenBuilds C-beam linear actuator 1200mm | 2 | $55 ea | Y-axis (both sides) |
| OpenBuilds V-slot gantry plate (universal) | 3 | $10 ea | 1× X-carriage, 2× Y-carriage |
| GT2 timing belt 6mm, 3m length | 2 | $9 ea | Any reputable brand |
| GT2 20T pulley, 5mm bore | 3 | $3 ea | 1× X-motor, 2× Y-motors |
| GT2 20T idler pulley (no teeth), 5mm bore | 4 | $2 ea | Belt tensioner return points |
| M5 T-nuts (bag of 50) | 1 | $8 | For all V-slot connections |
| M5 × 8mm button head bolts (bag of 50) | 1 | $7 | Frame assembly |
| M3 × 8mm socket head bolts (bag of 50) | 1 | $6 | Motor mounts, brackets |
| M3 × 16mm socket head bolts (bag of 20) | 1 | $5 | Printhead assembly |
| M3 hex nuts (bag of 50) | 1 | $4 | — |

---

## Electronics

| Part | Qty | Est. Cost | Notes |
|---|---|---|---|
| Arduino Uno R3 | 1 | $12 | Official or clone — both work with GRBL |
| CNC Shield v3 for Arduino | 1 | $10 | Fits directly on top of Uno |
| A4988 stepper driver module | 3 | $4 ea | Set Vref to 0.64V for NEMA 17 @ 1.5A |
| NEMA 17 stepper motor 17HS19-2004S (2A) | 3 | $12 ea | X-axis × 1, Y-axis × 2 |
| Micro servo SG90 or MG90S | 1 | $5 | Pen lift — wired to GRBL spindle PWM |
| Mechanical end stop switch w/ PCB | 4 | $2 ea | X-min, X-max, Y-min, Y-max |
| 12V 5A power supply (5.5×2.1mm barrel) | 1 | $18 | Powers steppers + Arduino via CNC shield |
| Raspberry Pi 4B 2GB | 1 | $45 | Runs Universal G-Code Sender + toolpath scripts |
| MicroSD card 32GB (Class 10) | 1 | $8 | Pi OS |
| USB-A to USB-B cable (2m) | 1 | $6 | Pi to Arduino |
| 22 AWG stranded wire assortment (black/red/green) | 1 | $12 | Motor and endstop wiring |
| JST-XH 2.54mm connectors (assortment) | 1 | $8 | Clean motor connections |
| Ferrite choke cores | 4 | $5 | Slip over motor cables — reduces stepper noise |

---

## 3D Printed Parts

Print all parts on a Bambu Lab X1C (or equivalent). PETG for structural parts, PLA for covers and cable management.

| Part | Material | Print Settings | Approx. Print Time |
|---|---|---|---|
| Pen carriage body | PETG | 0.20mm, 4 walls, 25% gyroid | 2h |
| Pen servo mount | PETG | 0.20mm, 5 walls, 30% gyroid | 1h |
| Pen holder clamp (thumb screw version) | PETG | 0.20mm, 4 walls, 30% gyroid | 45min |
| Rubber band shock absorber bracket | PETG | 0.20mm, 4 walls, 20% gyroid | 30min |
| Motor mount × 3 | PETG | 0.20mm, 5 walls, 30% gyroid | 1.5h each |
| Belt tensioner × 4 | PETG | 0.20mm, 4 walls, 25% gyroid | 30min each |
| Endstop trigger flags × 4 | PLA | 0.20mm, 3 walls | 15min each |
| Frame corner brackets × 4 | PETG | 0.20mm, 5 walls, 30% gyroid | 45min each |
| Cable chain mounts × 6 | PLA | 0.20mm, 3 walls | 20min each |

> **Nerdtronic lesson:** the pen carriage warps under its own weight after extended use, causing 1–2mm registration error. Embed M3 brass heat-set inserts for all fastener points, or upgrade to an aluminum plate carriage for long paintings.

**Total filament:** ~600g PETG, ~100g PLA

---

## Paint & Canvas

| Part | Qty | Est. Cost | Notes |
|---|---|---|---|
| T5 acrylic paint pens 0.7mm (12-pack) | 2 | $28 ea | **Modify for constant flow** — see below |
| Pre-stretched canvas 48×60 inch | 1 | $45 | Museum quality; or use MDF + gesso |
| Gesso (if using MDF) | 1 | $12 | 2 coats, let dry 24h before painting |

### Paint pen modification (required)

T5 pens have a valve that only flows when the tip is pressed. The robot can't press hard enough without damaging the canvas. Fix:

1. Remove the nib and the small sponge behind it
2. Use a 1mm drill bit to puncture the internal membrane — 3 holes in a triangle pattern
3. Reassemble carefully
4. Test: invert pen — paint should flow freely without pressing

This is the same modification Nerdtronic used on his painting robot.

---

## Tools Required

| Tool | Notes |
|---|---|
| 3D printer (Bambu Lab X1C or equivalent) | For all printed parts |
| Hex key set (M3, M4, M5) | Frame and motor assembly |
| Soldering iron | Endstop wiring, ferrite cores |
| Multimeter | Setting A4988 Vref (critical — skip this and you'll fry a driver) |
| 1mm drill bit + pin vise | Paint pen modification |
| Calipers | Measuring belt tension, backlash |
| Raspberry Pi imager | Flashing Pi OS |

---

## Software (all free)

| Software | Purpose | Link |
|---|---|---|
| GRBL 1.1 | Motion controller firmware — flash to Arduino Uno | github.com/gnea/grbl |
| Universal G-Code Sender (UGS) | Send G-code, jog machine, set home | winder.github.io/ugs_website |
| toolpath.py (this repo) | Generate G-code from images | — |
| Raspberry Pi OS Lite | Headless Pi OS | raspberrypi.com/software |
| Python 3.9+ | Required for toolpath.py | python.org |

---

## Assembly Order

1. Assemble C-beam frame and install linear actuators
2. Install motors, pulleys, and belt — tension to ~3Hz pluck frequency
3. Print and install pen carriage on X-axis actuator
4. Wire motors to CNC shield (note coil pairs — wrong wiring = motor hums and won't turn)
5. Set A4988 Vref: 0.64V for NEMA 17 @ 1.5A (Vref = I × 0.8 × Rsense; Rsense = 0.1Ω on most A4988 boards → Vref = 1.5 × 0.8 × 0.1 = 0.12V... actually use 0.64V for 0.7Ω Rsense boards — measure your board)
6. Flash GRBL to Arduino, configure `$100`/`$101` steps/mm for your pulley/belt combo
7. Install endstops, test homing cycle (`$H`)
8. Mount servo, wire to spindle PWM, configure `$30=1000`, `$31=0`
9. Install canvas on frame
10. Run first toolpath test at low feed (1000 mm/min) to verify registration

---

## GRBL Configuration Reference

Key settings for this machine:

```
$0=10      ; step pulse, microseconds
$1=25      ; step idle delay
$2=0       ; step port invert mask
$3=2       ; direction port invert (flip Y if moving wrong direction)
$4=0       ; step enable invert
$5=0       ; limit pins invert
$6=0       ; probe pin invert
$10=1      ; status report mask
$11=0.010  ; junction deviation
$12=0.002  ; arc tolerance
$13=0      ; report in mm (not inches)
$20=0      ; soft limits (enable after calibration)
$21=1      ; hard limits (enable once endstops are wired)
$22=1      ; homing cycle enable
$23=3      ; homing direction invert (depends on your wiring)
$24=25.0   ; homing feed, mm/min (slow approach)
$25=500.0  ; homing seek, mm/min (fast approach)
$26=250    ; homing debounce, ms
$27=1.0    ; homing pull-off, mm
$30=1000   ; max spindle speed (for M3 S1000 pen-down command)
$31=0      ; min spindle speed
$32=1      ; laser mode (enables M3/M5 without requiring motion — needed for pen control)
$100=80.0  ; X steps/mm (GT2 belt, 20T pulley, 1/16 microstepping = 80 steps/mm)
$101=80.0  ; Y steps/mm
$102=80.0  ; Z steps/mm (unused — set anyway)
$110=8000  ; X max rate, mm/min
$111=8000  ; Y max rate, mm/min
$120=200   ; X acceleration, mm/s²
$121=200   ; Y acceleration, mm/s²
$130=1524  ; X max travel, mm (canvas width)
$131=1220  ; Y max travel, mm (canvas height)
```

> **Important:** `$32=1` (laser mode) is required so M3/M5 fire without needing a G1 move. Without this, your pen commands will be silently ignored.

---

## Backlash Tuning

Run this test after first assembly:

```bash
python3 toolpath.py edges test_circle.png --canvas-w 200 --canvas-h 200 --canny-low 10 --canny-high 30
```

Use any image with a clear circle. Send to machine, examine where the circle closes. If there's a visible step or gap at the seam, increase `--backlash` by 0.1mm until the circle closes cleanly. Typical range: 0.2–0.6mm.

---

*Build by Modology Studios LLC — Tucker, GA — modologystudios.com*
*License: CC BY 4.0*
