# Twisted Bulb Rudder Designer 2.2.0 — Analysis for a New, Similar Program

Inputs reviewed: `TwistedRudderDesigner_2.2.0_Reproduction_Handbook.md` (14,345 lines; Part I prose
and Part II verbatim source), `TwistedRudderDesigner_v2.2.0_source.zip`, and a GUI screenshot (Promas
preset).

## 1. Verification

| Check | Result |
|---|---|
| Handbook extractor (Appendix A) → 47 files, SHA-256 | **ALL OK**, 0 mismatches |
| Extracted tree vs. zip | identical; the zip only adds `docs/*.png` (4 illustrations, as the handbook says) |
| `pytest -q tests` (Python 3.13, numpy 2.5, scipy 1.18, cadquery-ocp 7.8.x) | **38 passed** in 17 s |
| Reference S/V (handbook §14), level 3 | becker 155.77535 m² / 60.18248 m³, promas 157.78959 / 60.59306, molfin 163.62861 / 64.32956, plain 151.73470 / 55.94239 — **exact match to 5 decimals** |
| becker at draft 4 m (waterline pierced) | 50.50443 m² / 16.58577 m³ — matches |
| GUI (PySide6 / pyqtgraph) | not launched here (headless container); geometry and CAD core verified via tests |
| Grasshopper component | not testable without Rhino (the handbook also says it is untested in Rhino) |

So the handbook is a reliable spec: the core is deterministic and reproducible.

## 2. What the program is

A parametric **geometry** tool for a twisted spade rudder with a rudder bulb behind a propeller.
Its outputs are CAD solids (IGES/STL), wetted surface and displaced volume, and a design check table.
It does **not** predict rudder forces, propulsive gain, or cavitation.

Codebase: ≈6.8 k lines of Python.

| Layer | Modules (lines) | Role |
|---|---|---|
| Parameters | `trd/params.py` (192) | nested JSON dict, 13 presets stored per unit propeller diameter D, `rescale_D`, `merge` for old files |
| Frames | `trd/frames.py` (105) | 4×4 matrices: steer, heel (applied first), design offset (WL z=0, stock x=0, hub y=0), ship / propeller export frames |
| Geometry | `geometry.py` (368), `sections.py` (160) | planform, elliptic keel-side tip, NACA 00xx or custom sections, 8-parameter twist law (C2 blend), TE thickness, bulb body of revolution, fins, hub cap |
| Inflow | `slipstream.py` (67), `wake.py` (130), `model.local_inflow` | actuator-disk slipstream; scattered (x,y,z,u,v,w) wake table with rank-adaptive interpolation |
| Twist optimiser | `twist_design.py` (142) | bounded least squares (`scipy` TRF), multi-start, dynamic-pressure weights, bulb band masked |
| Exact CAD | `bspline.py` (170), `model.cad_description`, `cad_occ.py` (547) | Piegl–Tiller cubic interpolation, exact Boehm-insertion splits, OCC sewing → solid → fuse → junction fillet → part tagging |
| Hydrostatics | `hydro.py` (74) | S and V below z = 0 by OCC Boolean common with a half-space box |
| Export / batch | `export.py` (152), `batch.py` (193), `mesh.py` (205) | IGES/STL, 1 file or 4 parts (side/bottom/top/bulb) + hub, read-back closure check, Cartesian batch sweep ≤ 100,000 cases |
| GUI | `trd_gui/*` (≈2.7 k; `app.py` 951) | PySide6 + pyqtgraph; custom Number Slider (lock / step / batch ticks), 3-D view with CPU lighting, 6 tabs |
| Rhino | `grasshopper/TwistedBulbRudder_GH.py` (801) | Grasshopper component on the same `trd` core |
| Packaging | `packaging/*` | Linux cross-build: embedded CPython 3.12 + pinned wheels, C launcher, NSIS per-user installer, portable zip |

Pipeline: **params → frames → section grid → (preview mesh | B-spline description → OCC solid) →
S/V, checks, export**. The B-spline description is kernel-neutral, so the same data goes to OCC and to
RhinoCommon. That is the most reusable design idea in the code.

## 3. Strengths worth keeping

1. **Kernel-neutral B-spline layer.** Grid → exact cubic interpolation → exact knot-insertion splits.
   Part boundaries are exact iso-curves, so faces sew without gaps.
2. **Robust closure.** Half-cosine chord stations (non-zero parametric speed at the TE), a fold row at the
   tip, a TE strip with the same v-parameters, topological STL welding through
   `PolygonOnTriangulation`, and read-back verification of every exported file. Handbook §16 lists the
   failure modes behind each of these; treat it as a checklist.
3. **Clear coordinate conventions.** Separate internal, design, ship and propeller frames. Heel is applied
   before steering, and the code shows this equals steering about the tilted stock.
4. **Graceful degradation.** Without OCC it still runs: preview meshes, approximate S/V, STL only.
5. **Batch engineering.** Unique abbreviations enforced by a test, deterministic file names, CSV
   manifest with S/V, and re-optimised twist per case.
6. **Fast, meaningful tests** (geometry closure, exact split, tangent continuity, frames, S/V references).

## 4. Weaknesses and gaps (what a new program should do differently)

### 4.1 Engineering scope
* **No hydrodynamic performance model.** There is no lift/drag/stock-torque estimate, no propulsive-gain
  estimate, and no cavitation check, even though cavitation is the main reason to twist a rudder. The
  `Checks` tab is geometric only. This is the biggest functional gap.
* **Class-rule check is minimal.** Only the DNV-type lateral-area guideline. Rudder force/torque for
  scantlings (e.g. IACS/DNV `C_R = 132·K1·K2·K3·A·V²·K_t`) and stock diameter are missing.
* **Simple slipstream.** Momentum-theory axial induction with contraction, plus swirl from torque with a
  fixed √(x(1−x)) circulation. It ignores the hull wake non-uniformity and the rudder's blockage. The
  alignment factor η (0.5–1.0) compensates by hand. Fine as a first estimate; a new program should
  import measured/CFD wakes as first-class data and could add a lifting-line propeller model.
* **Twist parametrisation is fixed** (8 parameters, LE bend or whole-section rotation). There is no free
  spanwise B-spline twist and no camber/thickness distribution optimisation.
* **Presets use manufacturer names** (Becker, Wärtsilä, Kongsberg, HHI, MHI, …) with parameters invented
  from public descriptions ("not maker data"). Rename them generically in a commercial product to avoid
  trademark and liability issues.

### 4.2 Software architecture
* **Three parallel parameter tables:** GUI `SCHEMA` (`trd_gui/app.py`), batch `ABBR` (`trd/batch.py`)
  and Grasshopper `SPEC` (`grasshopper/…_GH.py`) repeat paths, labels and ranges. Adding a parameter
  means editing three places. Use **one schema in the core** (path, label, unit, kind, range, step,
  abbreviation, visibility rule, sweepable) and generate the GUI, batch and Rhino interfaces from it.
* **Untyped nested dicts.** No validation, units or schema version (`merge` copies keys of the same
  type). Use dataclasses/pydantic with a `schema_version` and explicit migrations.
* **GUI monolith.** `app.py` (951 lines) holds the schema, layout, checks HTML, the worker and settings.
  Split it into view model, panels and report generator.
* **Live S/V is slow.** Every change rebuilds the full OCC solid at level 3 (1.5–3 s, background thread).
  A mesh-based S/V or caching unchanged parts would make it near-instant.
* **Heavy distribution.** The portable zip is ≈223 MB, and the pins are tied to Wine workarounds (numpy
  1.26, PySide6 6.8, OCP 7.8.1; OCP 8.x breaks `TColgp_Array2OfPnt`). Plan the OCC version upgrade
  early and build on native Windows CI rather than cross-building with Wine.
* **Grasshopper version never ran in Rhino.** Treat it as unverified.
* **No GUI tests and no CI.** All 38 tests are core tests.
* **No licence file** in the source. If the new program will reuse this code, settle ownership and
  licensing first. Dependency licences: PySide6 and OCCT/cadquery-ocp are LGPL (dynamic linking OK,
  ship sources/relinking notice), pyqtgraph MIT, numpy/scipy BSD.

## 5. Recommended plan for the new program

**Keep (port or reuse):** frames and sign conventions (§3 of the handbook), the planform/tip/twist/
section formulas (§5), B-spline interpolation and split (§7.1), the OCC solid recipe and fillet
fallback (§7.3), topological STL welding (§7.4), the S/V method (§8), batch naming (§10), and the §16
pitfall list as regression tests. Use §14 reference values as acceptance tests.

**Change:**
1. A single declarative parameter schema in the core, typed, versioned and unit-aware; the GUI, CLI,
   batch and Rhino adapters are generated from it.
2. Separate core / service / UI packages, plus a **headless CLI** (`design.json → IGES/STL + report`)
   so batch jobs and CI need no GUI.
3. Add a performance module, at minimum:
   * rudder lift/drag/stock torque (empirical, e.g. Whicker–Fehlner / Söding, or a lifting-line or
     vortex-lattice model in the slipstream),
   * a cavitation check (−Cp_min vs. local cavitation number along the span, using the same inflow),
   * class-rule rudder force/torque and stock diameter.
4. Wake input as a first-class dataset (import 5-hole Pitot or CFD planes; show the interpolation
   rank and coverage).
5. A free-form twist option (spanwise B-spline), with the current 8-parameter law kept as a preset.
6. Generic preset names.
7. CI on Windows and Linux, GUI smoke tests (pytest-qt), and a reproducible build (PyInstaller or
   Briefcase on native Windows) instead of the Wine cross-build.

**Tech stack:** Python + numpy/scipy + OCP (OCCT) + PySide6 is proven here and fine for an
engineering desktop tool. Two alternatives to weigh: a web front end (three.js) over a Python geometry
service, which v1 of this tool already used, or a C++/OCCT core if CAD speed becomes the bottleneck.

## 6. Open questions to settle before starting

1. Is "similar" a **rewrite** (own IP; code is reference only) or an **extension** of this code
   (needs ownership/licence confirmed)?
2. Scope: geometry/CAD only (like 2.2.0), or with hydrodynamic performance and cavitation?
3. Target users and platforms: in-house engineers on Windows, or a product (licensing, installer,
   updates, trademarks)?
4. CAD integration priorities: IGES/STL only, or also STEP, Rhino, and CFD meshers (e.g. STAR-CCM+ or
   OpenFOAM surfaces with named patches)?
5. Wake data sources and formats you actually have (5-hole Pitot, CFD, model-test files).

## 7. How to reproduce the baseline

```bash
python3 extract_handbook.py TwistedRudderDesigner_2.2.0_Reproduction_Handbook.md out/   # ALL OK
cd out/TwistedRudderDesigner
pip install numpy scipy pytest "cadquery-ocp>=7.8.1,<7.10" PySide6 pyqtgraph PyOpenGL
python -m pytest -q tests        # 38 passed
python main.py                   # GUI (needs a display; Linux also needs libxcb-cursor0)
```
