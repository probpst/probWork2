# Parametric Hull Form Designer — Technical Design

Clean rewrite (no code from TwistedRudderDesigner 2.2.0), geometry only, in-house tool. Output
formats are IGES and STL. This document explains the geometry model, the algorithms, the
verification and the known limits. User instructions are in `../README.md`. All parameters are
listed in `Parameters.md`, generated from the schema.

## 1. Architecture

```
hullform/            geometry core (numpy/scipy; OCP optional)
  params.py          SCHEMA: the single list of parameters (label, unit, range, step, abbreviation,
                     hint); file I/O, merge of old/partial files, schema version
  presets.py         presets fitted to the six reference hulls (presets_fitted.json)
  curves.py          end-curve family, plateau curves, fillet polylines, arc-length resampling
  sections.py        transverse section family (deadrise + oblique superellipse bilge + flat side
                     + topside Bezier), area solve
  hull.py            HullForm: profile, midship, DWL, SAC, flat of bottom/side, deck, stations, grid
  appendages.py      ring bodies: bulbous bow / sonar dome, stern tube boss(es), twin skegs
  build.py           Design = main hull + bodies + meshes; complete-hull Cb/LCB correction
  mesh.py            TriMesh, closed hull mesh, welding, STL read/write
  hydro.py           union hydrostatics by oriented section counting, wetted surface
  offsets.py         outer half-breadth tables, section curves for drawing
  bspline.py         kernel-neutral global cubic interpolation (Piegl–Tiller)
  cad.py             OCC: B-spline faces, sewing, solid, union, fillet, IGES, STL, exact hydrostatics
  export.py          export + read-back verification
  reference.py       import IGES/STL reference hulls, offsets by crossing parity
  fit.py             fit shape parameters to a reference (staged Powell)
  report.py          comparison plots
  __main__.py        command line (presets / build / hydro)
hullform_gui/        PySide6 + pyqtgraph desktop GUI (panels generated from SCHEMA)
references/          offsets + hydrostatics of the six supplied hulls (not the geometry files)
tools/               make_reference.py, fit_presets.py, schema_table.py, gui_screenshot.py
tests/               pytest
```

The GUI, the command line, the parameter file format and the batch/fit code all read the same
`SCHEMA`. Adding a parameter is one line plus its use in the geometry.

## 2. Frame and units
x forward from the AP (FP at x = Lpp), y to port, z up from the baseline, metres. Shape parameters
are dimensionless (× Lpp, × B/2, × T, × D, % Lpp), so a preset keeps its form when L, B, T or D
change.

## 3. Main hull (`hull.py`)

1. **Profile (centreline, lower edge of the sections)**: two filleted polylines. Forward: keel →
   stem foot → stem top, where the stem passes through (FP, T) with rake θ and a forefoot radius.
   Aft: transom bottom → counter knuckle → skeg heel → keel, with two radii. For a twin-skeg hull
   the same polyline is the tunnel roof on the centreline. z0(x) must be single-valued; a warning
   is raised otherwise.
2. **Midship**: the bilge radius r is solved from Cm with the rise of floor, using a flat bottom
   and a circular bilge.
3. **Longitudinal design curves**: each is a plateau (parallel part) with end curves
   g(t) = 1 − (1 − tᵃ)ᵇ. The end exponent `a` is a parameter (1 = finite slope, > 1 hollow,
   < 1 blunt). The shoulder exponents `b` aft and forward are **solved** so that:
   * the DWL half-breadth curve gives the target **Cwp** and **LCF**,
   * the sectional area curve gives the target **Cb** and **LCB** (main hull),
   with the immersed-transom values as end values.
   Flat-of-bottom width, flat-of-side lower edge, deck line, sheer, flare, keel exponent n(x) and
   waterline flare φ(x) are plateau or blend curves of their own parameters.
4. **Sections** (`sections.py`): from the centreline point (0, z0), a deadrise line to the
   flat-of-bottom edge (yf, zb). Then a superellipse quadrant in an oblique frame (horizontal at the
   bottom, along the waterline flare direction at the top) up to the flat side. The flat side runs to
   the DWL point (b, T), then a tangent-continuous cubic Bezier topside reaches the deck edge with
   the deck flare angle. The quadrant fullness σ(n, m) = Γ(1+1/n)Γ(1+1/m)/Γ(1+1/n+1/m) is solved
   for m ≥ 1 so that **every section area equals the SAC value**; n < 1 gives hollow, skeg-like
   S-sections, n = 1 a V, n > 1 a U. The corner area cancels the obliquity, so the solve stays
   analytic.
5. **Stations** are distributed by profile arc length with clustering at the ends. Each section is
   resampled at equal girth arc length, which gives a structured grid. The last station is the stem
   top (collapsed onto the centreline).

## 4. Add-on bodies (`appendages.py`)
Ring grids (stations × closed loop):
* **Bulbous bow / sonar dome**: from a root buried in the hull, through the maximum section near
  the FP, to the nose. The loop is a superellipse with Δ/O/∇ bias (`shape`); top, bottom, nose
  height, protrusion and breadth follow Kracht's parameters. A bulb bottom at keel level is lifted
  just inside the hull, because a tangential contact makes a non-manifold union. A sonar dome
  (bottom below the keel) is left untouched.
* **Stern tube boss**: body of revolution on the shaft line (centreline, or the twin shaft lines),
  with a rounded aft end.
* **Twin skegs**: rounded-U loops centred at ±ys, maximum width at 25 % of the skeg length, an
  elliptic aft end carrying the boss, a power-law forward fairing, and a raked bottom at the aft end.

## 5. Complete hull and hydrostatics
`Design(p, correct=True)` iterates the main-hull Cb/LCB targets (secant-like, ≤ 3 iterations) until
the **union** meets the requested Cb within 2·10⁻⁴ and LCB within 0.01 % L.

Union hydrostatics (`hydro.py`): every closed, outward-oriented mesh is cut at x = const, and each
section segment carries the orientation of its triangle. On a horizontal line a crossing counts
+1 when entering and −1 when leaving, and the running sum over **all** bodies tells whether a point
is inside the union. This gives exact union widths without Booleans, so overlapping bodies are
never counted twice. From these widths come the volume, LCB, KB, waterplane, LCF, BMt and
coefficients. The wetted surface is the triangle area below T, excluding triangles inside another
body (ray parity test).

## 6. CAD model (`cad.py`, OCP)
* Main hull: the grid is interpolated by a bicubic B-spline with our own Piegl–Tiller solver (OCC's
  `PointsToBSplineSurface` oscillates on the collapsed stem row). It is mirrored for the other side.
  The deck is ruled between the two deck-edge iso-curves, and the transom is planar on the first
  iso-curves, so the edges coincide exactly. Sewing gives a shell, which becomes a solid.
* Bodies: two **non-periodic** half surfaces per body (split at the bottom and top of the loops) and
  a planar cap. A periodic surface would leave a seam that shows up as free edges after IGES
  read-back.
* Union `BRepAlgoAPI_Fuse` (fuzzy 1e-6·L), face-origin history, and an optional constant-radius
  junction fillet on hull/body edges. If the fillet fails, the solid is kept without it and a
  warning is given.
* **Volume/area integration uses adaptive precision** (`BRepGProp` with eps). The default Gauss
  scheme was ~1 % off on these faces.
* Exact hydrostatics: `BRepAlgoAPI_Common` with the half-space z ≤ T; the waterline cut face is
  excluded from the wetted surface.
* STL: one `BRepMesh` pass on the whole solid, then nodes are merged **topologically** through the
  `PolygonOnTriangulation` of every edge (union-find). Coincident opposite triangles are cancelled.
* IGES: trimmed surfaces (entity 144) or B-rep (186), m or mm. **Every file is read back**: IGES
  faces are sewn and free edges counted; for STL, open and non-manifold edges are counted.

## 7. Reference hulls and presets
`tools/make_reference.py` reads the six supplied files (transforms in the script), measures
hydrostatics by slicing (crossing parity of the mirrored section, because the files are open half
hulls) and stores outer half-breadth/width tables on a 225 × 121 grid in `references/*.npz`.

`tools/fit_presets.py` takes the principal dimensions and coefficients from the reference. It then
fits the remaining ~65 shape parameters by **staged Powell** (parameter groups: stern, bow/bulb,
DWL, SAC, flat of bottom, flat of side, sections, deck, skegs; 2–3 cycles) on the half-breadth
error. Gradient-based least squares stalled because the error is only piecewise smooth (profile
edges switch on and off). Regions that are not hull (propellers and rudders in KLNG2 and DTC, a
stray transverse face in the KCS file) are masked out.

## 8. Verification (all automated, `pytest -q tests`)
* end-curve inversion; section fullness; fillet tangency;
* main hull hits Cb, LCB, Cm and Cwp, and its mesh is closed;
* union counting on two overlapping boxes (volume 12, not 16);
* complete-hull Cb/LCB correction;
* every preset: closed meshes, Cb within 0.004 and LCB within 0.15 % of the reference, fit RMS
  < 6 % B/2;
* twin-skeg tunnel present (two separate intervals near the stern);
* CAD export for the default design and every preset: valid closed solid, IGES read-back closed,
  STL without open or non-manifold edges, exact and mesh displacement within 0.6 %.

## 9. Problems met and their fixes (keep these when modifying)

| Problem | Cause | Fix |
|---|---|---|
| Main-hull B-spline wildly wrong (volume ×10⁹) | OCC `GeomAPI_PointsToBSplineSurface` on a grid with a collapsed stem row | own Piegl–Tiller interpolation (`bspline.py`) |
| OCC volumes ~1 % off | default Gauss integration in `BRepGProp` | adaptive integration (eps 1e-7) |
| 2 free edges after IGES read-back | periodic bulb surface → seam edge | bodies as two non-periodic half surfaces + cap |
| Non-manifold STL edge at the keel | bulb bottom lying tangentially on the flat keel | bulb/skeg bottoms lifted 0.05 T inside the hull where they meet the keel (not for a sonar dome) |
| Non-manifold STL edges in general | coordinate welding of per-face meshes | topological welding through `PolygonOnTriangulation` (union-find) |
| Invalid transom face (self-intersecting wire) | hollow sections leave the keel vertically → cusp between port/starboard outlines | transom as a ruled face; keel rounding `sec.rk` for hollow sections |
| Waterline Boolean returns an empty solid | the cutting plane grazes a face | exact clipping of a fine tessellation as fallback (`method: mesh`) |
| Bulb union fails / folded bulb surface | fitted root forward of the max section | generator enforces root < max section < nose |
| Zero-length free edges at the stem top | last station almost, but not exactly, a point | collapse it exactly when its extent < 1e-3 L |
| Fitted "filler" bodies (huge boss, bulb below baseline) | unconstrained optimiser | realistic schema ranges; bottoms ≥ baseline when the reference has nothing below it |
| Infeasible stations (σ > 1) | parallel waterline shorter than the parallel body | waterline plateau forced to contain the SAC plateau; fit penalty for unreachable stations |
| Hydrostatics depend on resolution (±0.4 %) | trapezoidal slicing near steep profile parts | exact divergence-theorem volume of the clipped meshes; slicing only for body overlaps |
| Junction fillet fails on the bulb | intersection crosses the sharp stem line on the centreline | fillet body by body; bodies that fail stay sharp (warning) |

## 10. Limits and next steps
* The presets are **parametric approximations** of the benchmark hulls (body-plan RMS in the
  README), not the original lines. Use the supplied files when the exact benchmark geometry is
  required.
* Not yet covered: inverted/axe bows and stems overhanging aft, raked transoms, knuckles/chines,
  tumblehome above the deck, propeller apertures cut into a solid skeg, ducts/ESDs, bilge keels.
* KLNG2 draught/Lpp were assumed (11.5 m, AP at the file origin).
* Wake data (5-hole Pitot, PIV, CFD) is not used by the hull geometry. It is planned for the rudder
  tool rewrite and for nominal-wake visualisation at the propeller plane.
* Planned: GUI import of any IGES/STL hull + one-click fit (the core functions exist:
  `reference.load`, `fit.fit_staged`), batch sweeps of unlocked parameters, half-hull export for
  CFD, named CFD patches.
