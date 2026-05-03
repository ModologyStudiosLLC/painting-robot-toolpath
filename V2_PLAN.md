# Painting Robot V2 — Build Plan

Improvements over Nerdtronic's original design. V1 is the current build (C-beam XY, single Molotow marker, GRBL 1.1). V2 addresses the three main limitations: speed, multi-color, and canvas feedback.

---

## Priority 1 — CoreXY Kinematics

**What:** Replace the standard XY gantry (one motor per axis) with CoreXY (both motors contribute to every move). Diagonal moves at full speed instead of reduced speed. ~40% faster travel, better acceleration at this canvas size.

**Why it matters:** At 4×5ft, long diagonal strokes are slow on standard XY. CoreXY eliminates that bottleneck without changing the C-beam frame geometry significantly.

**Changes required:**
- Reposition motors to back corners (both fixed, no moving motor mass)
- New belt path: two belts cross in the center, each anchored to the carriage
- New carriage design (CoreXY belt attachment points)
- Update GRBL firmware: no changes needed — GRBL CoreXY mode via `$32` is built in
- Update toolpath.py: no changes needed — G-code is the same

**Effort:** Medium — mechanical redesign of belt/motor layout, same electronics

---

## Priority 2 — 2-Pen Rocker Arm

**What:** Two Molotow markers mounted on a servo-driven rocker. One pen down = other pen up. Pen A for detail/edges, Pen B for fill/hatch. Automated swap mid-painting with no human intervention.

**Why it matters:** Eliminates the manual pen swap between passes. Run a full 2-color painting overnight unattended.

**Changes required:**
- New carriage design: wider bracket with rocker pivot + second pen bore
- Second servo (PCA9685 I²C board on spare Arduino pins — ~$5)
- Firmware: add `M3 S500` for Pen B down / `M3 S0` for Pen A down (map to rocker positions)
- toolpath.py: add `--pen` flag (A/B) that emits the correct servo command
- server.py: expose pen selection in the UI

**Effort:** Medium — carriage redesign + one extra $5 board

---

## Priority 3 — Airbrush Background Layer

**What:** Mount a small airbrush (Iwata Neo or similar) alongside the marker. Solenoid valve triggered by GRBL spindle, compressor on/off via relay. Use for background washes and large fill areas. Marker handles detail.

**Why it matters:** Airbrush covers large canvas areas 10× faster than hatch fill with a marker. Background in airbrush (5 min), detail edges in marker (60 min) = much faster multi-layer paintings.

**Changes required:**
- Airbrush mount on carriage (beside marker, separate servo for Z)
- Solenoid valve (12V, normally closed) on GRBL spindle PWM
- Air compressor (small pancake, ~$60) on relay triggered by RPi GPIO
- toolpath.py: add `airbrush` mode — large-area flood fill at high feed rate
- New pass type in job file: `{"name": "Background wash", "tool": "airbrush", ...}`

**Effort:** Medium-Hard — new hardware, paint containment for overspray

---

## Priority 4 — Camera Feedback Loop

**What:** Wide-angle USB camera mounted above canvas. Between passes, capture canvas state, compare to target image, identify registration drift or missed strokes. Flag issues before the next pass starts.

**Why it matters:** A 3-hour painting pass that drifts 5mm halfway through is 3 wasted hours. Camera verification after pass 1 catches drift before pass 2 starts.

**Changes required:**
- USB webcam mount (corner of frame, fixed position)
- `verify.py`: capture frame → align to target image via homography → compute diff → report drift
- server.py: add `/verify` endpoint, show diff overlay in UI
- Integrate into job flow: auto-capture between passes, show result before prompting user to continue

**Effort:** Medium — mostly software (OpenCV homography is well-documented)

---

## Priority 5 — Optical Endstops

**What:** Replace mechanical endstop switches with optical sensors (slotted or reflective). No contact bounce, more reliable homing, better repeatability.

**Why it matters:** Registration between multi-pass paintings depends on homing accuracy. Mechanical switches have 0.1–0.3mm repeatability variance. Optical is <0.05mm.

**Effort:** Low — direct swap, same wiring, same GRBL config

---

## Priority 6 — Drag Chain Cable Management

**What:** Printed or off-the-shelf cable chain (e-chain) on both X and Y axes. Cables routed inside chain instead of hanging loose.

**Why it matters:** On a 4×5ft machine, loose cables catch on the carriage mid-painting. Drag chain eliminates this entirely. Nerdtronic's build has no cable management.

**Effort:** Low — printable, bolt-on

---

## Build Order

1. Optical endstops + drag chain (low effort, immediate improvement to V1)
2. CoreXY kinematics (biggest performance gain, do before adding more weight)
3. 2-pen rocker arm (enables overnight 2-color paintings)
4. Camera verification (enables unattended multi-pass jobs)
5. Airbrush layer (biggest quality jump, most complex)

---

## Software Already Done (V1 → V2 carryover)

- `generate.py` — FLUX → G-code pipeline
- `server.py` — multi-pass job system + ntfy.sh completion notifications
- `toolpath.py` — edges / dots / hatch modes

V2 software additions: `--pen A/B` flag in toolpath.py, `airbrush` mode, `verify.py` camera diff tool.
