# 3D Printed Parts

STL files for the painting robot. Print in PETG at 0.20mm layer height, 4–5 walls, 25–30% gyroid infill unless noted.

| File | Qty | Material | Notes |
|---|---|---|---|
| `pen_carriage_body.stl` | 1 | PETG | 80×60mm plate; M5 gantry holes (20mm grid) + M3 clamp and servo holes |
| `pen_holder_clamp.stl` | 1 | PETG | 13.2mm bore for T5 paint pens; 1mm split slot + M3 thumbscrew |
| `pen_servo_mount.stl` | 1 | PETG | Flat bracket for SG90 servo on pen carriage; M2.5 ear holes + M3 carriage holes |
| `shock_absorber_bracket.stl` | 1 | PETG | Rubber band compliance arm; two 4mm posts for band loops + M3 carriage mount |
| `motor_mount_nema17.stl` | 3 | PETG | NEMA 17 face plate (31mm bolt circle, 22mm shaft hole); M5 slots for C-beam |
| `belt_tensioner.stl` | 4 | PETG | GT2 idler pulley block; M5 shaft bore |
| `frame_corner_bracket.stl` | 4 | PETG | L-bracket for C-beam corner joints; M5 holes on both legs |
| `endstop_trigger_flag.stl` | 4 | PLA | L-bracket trigger for mechanical endstop switches; M3 mount hole |
| `cable_chain_mount.stl` | 6 | PLA | Base + arm bracket; M5 adjustment slot for V-slot T-nut, M3 peg holes for chain clip |

## Dimensions used

- **Pen bore:** 13.2mm — fits T5 acrylic paint pens (modified for constant flow per HARDWARE.md)
- **NEMA 17 bolt circle:** 31mm (M3 × 4), shaft hole: 22mm
- **SG90 ear span:** 32.4mm (M2.5 × 2)
- **M3 clearance holes:** 3.2mm diameter throughout
- **M5 slots:** 5.5mm wide for V-slot T-nuts

## Heat-set inserts

Embed M3 brass heat-set inserts in the pen holder clamp fastener points to prevent warping and improve thread retention over repeated use. Required — the pen carriage bearing load will strip printed threads.
