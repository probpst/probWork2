# Parametric Hull Form Designer 0.1

In-house parametric design tool for commercial-vessel hull forms (geometry only), written from
scratch. It generates fine and full hulls, with or without a bulbous bow or sonar dome, with a
single skeg, twin skegs or open shafts, and transom or closed sterns. The result is one closed
solid exported as **IGES** and/or **STL**.

Six presets reproduce the six supplied benchmark hulls (KCS, DTC, KVLCC2, JBC, KLNG2, DTMB 5415).

![GUI](docs/gui_klng2.png)

## Start

```bash
pip install -r requirements.txt        # numpy scipy PySide6 pyqtgraph PyOpenGL cadquery-ocp (+ matplotlib)
python main.py                         # GUI
python -m hullform presets             # list presets
python -m hullform build --preset KLNG2 --out out/ --iges --stl          # export
python -m hullform build --preset KCS --set bulb.on=false --set main.Lpp=200 --out out/
python -m hullform hydro --preset JBC  # hydrostatics only
python -m pytest -q tests              # tests
```

`run_designer.bat` (Windows) and `run_designer.sh` create a virtual environment on first start.
On Linux, Qt needs `libegl1 libxcb-cursor0`. Without `cadquery-ocp` the program still runs: preview,
hydrostatics and STL from the preview mesh (bodies not united, no IGES).

## What you control

About 90 parameters in 16 groups (full list: `docs/Parameters.md`):

| Group | Main parameters |
|---|---|
| Principal dimensions | Lpp, B, T, D |
| Form coefficients (targets, met exactly) | **Cb** and **LCB** of the complete hull, Cm, Cwp, LCF |
| Midship | rise of floor (bilge radius follows from Cm) |
| Sectional area curve | parallel body extent, run/entrance end shape, immersed transom area |
| Design waterline | parallel extent, entrance/run shape, transom half-breadth |
| Flat of bottom / flat of side | extents and tapers |
| Section shape | keel exponent aft/forward (hollow-skeg / V / U), waterline flare aft/forward |
| Stem / stern profile | stem rake, forefoot radius; transom x and height (immersed or dry), counter knuckle, skeg heel, radii |
| Deck and topside | deck half-breadth amidships and at the transom, deck line shape, sheer fwd/aft, flare |
| Bulbous bow / sonar dome | on/off, protrusion (Kracht L_PR), top/bottom/nose height, breadth, Δ-O-∇ shape, nose fullness; bottom below the keel makes a sonar dome |
| Stern tube boss | shaft height, radius, aft end, length |
| Skegs | single / **twin** / open; twin: shaft offset, width, length, bottom, aft rake, fairing |
| CAD | junction fillet radius (bulb/skegs) |

Shape parameters are dimensionless (× Lpp, × B/2, × T, × D), so changing L, B, T or D keeps the
form. The GUI shows the value in metres next to each one.

## How the hull is built (short)

Longitudinal design curves (area curve, waterline, flat of bottom/side, profile, deck) are solved so
the main hull meets Cb, LCB, Cm, Cwp and LCF. Every transverse section is solved to have exactly the
area-curve value. The main hull is united with the parametric bulb/dome, boss and skeg bodies, and
the Cb/LCB targets are then corrected so that the **complete** hull meets them. Details:
`docs/Design.md`.

## Export

*Export geometry…* (GUI) or `python -m hullform build`:
* **IGES**: trimmed B-spline surfaces (or B-rep), m or mm.
* **STL**: binary, watertight, 5 resolution levels (chordal deviation 2·10⁻³ … 1.25·10⁻⁴ Lpp).
* Every file is read back and checked: IGES faces sewn → free edges; STL → open / non-manifold
  edges. The exact displaced volume, LCB and wetted surface of the solid are logged.

## Presets fitted to the supplied hulls

| Preset | Type | Lpp × B × T [m] | Cb ref / gen | LCB % ref / gen | Cm ref / gen | Cwp ref / gen | Body-plan RMS |
|---|---|---|---|---|---|---|---|
| KCS | Container ship: fine form, bulbous bow, transom, single skeg (KCS type) | 230.0 × 32.20 × 10.80 | 0.6501 / 0.6501 | -1.49 / -1.49 | 0.9840 / 0.9839 | 0.8305 / 0.8303 | 2.7 % |
| DTC | Ultra-large container ship: raised bulb, transom, single skeg (DTC type) | 355.0 × 51.00 × 14.50 | 0.6605 / 0.6605 | -2.64 / -2.64 | 0.9870 / 0.9867 | 0.8459 / 0.8455 | 2.4 % |
| KVLCC2 | VLCC tanker: full form, bulbous bow, single skeg (KVLCC2 type) | 320.0 × 58.00 × 20.80 | 0.8095 / 0.8097 | +3.51 / +3.52 | 0.9971 / 0.9981 | 0.9009 / 0.9007 | 5.4 % |
| JBC | Bulk carrier: full form, bulbous bow, single skeg (JBC type) | 280.0 × 45.00 × 16.50 | 0.8575 / 0.8576 | +2.54 / +2.55 | 0.9981 / 0.9978 | 0.9244 / 0.9240 | 1.7 % |
| KLNG2 | LNG carrier: twin skeg, bulbous bow (KLNG2 type) | 286.0 × 46.20 × 11.50 | 0.7500 / 0.7500 | -0.49 / -0.50 | 0.9868 / 0.9878 | 0.8613 / 0.8609 | 5.1 % |
| DTMB5415 | Naval combatant: sonar dome, transom, open shafts (DTMB 5415 type) | 142.0 × 19.06 × 6.15 | 0.4994 / 0.4994 | -1.06 / -1.06 | 0.8171 / 0.8166 | 0.7623 / 0.7619 | 2.1 % |

Body-plan RMS = RMS of the half-breadth difference below 1.05 T over the whole length, in % of B/2
(propellers/rudders in the reference files masked). Comparison plots: `docs/compare_*.png`.
**KLNG2: the design draught (11.5 m) and Lpp (AP at the file origin) were assumed. Please
confirm them.**

## Limits (version 0.1)

The presets are parametric approximations, not the original benchmark lines. Not yet supported:
inverted/axe bows, raked transoms, chines/knuckles, propeller apertures, ducts and other ESDs,
bilge keels. The GUI does not yet import arbitrary IGES/STL hulls for fitting (the core functions
exist: `hullform.reference`, `hullform.fit`). See `docs/Design.md` §9.
