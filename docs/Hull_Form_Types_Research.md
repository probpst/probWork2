# Commercial Vessel Hull Forms — Types, Variable Geometry and Parametrisation

Background research for the **Parametric Hull Form Designer** (in-house tool, geometry only,
IGES/STL output). It summarises how hull forms of commercial ships vary worldwide, with and without
a bulbous bow, with a single skeg or twin skegs. It also explains how each feature maps onto the
tool's parameters. Section 6 analyses the six reference hulls supplied with the request
(`6hulls.zip`).

Sources: standard ship-design literature (Schneekluth & Bertram, *Ship Design for Efficiency and
Economy*; Watson, *Practical Ship Design*; Papanikolaou, *Ship Design*; Kracht 1978 on bulbous bows;
Harries 1998 and Abt/Harries on form-parameter design; Lackenby 1950 on parent-hull variation) and
the published particulars of the public CFD benchmark hulls (KRISO KCS/KVLCC2, NMRI JBC, the
Duisburg Test Case and DTMB 5415). The numbers in section 6 were **measured directly from the
supplied geometry files**. They are not taken from the literature.

---

## 1. How hull forms are classified

A commercial hull is usually described by five largely independent choices:

| Choice | Options seen in service | Driven by |
|---|---|---|
| Fullness (Cb, Cp) | fine (0.50–0.65), medium (0.65–0.75), full (0.78–0.88) | Froude number Fn = V/√(gL) |
| Bow | bulbous (Δ, O, ∇ section; raised or keel-attached; goose-neck) · conventional raked stem · vertical/straight stem · inverted / axe / X-bow (offshore, small craft) | Fn, loading condition, operating profile |
| Stern / afterbody | single skeg (open stern or with stern bulb) · twin skeg (gondola) · open twin shafts with brackets · pram/barge stern · transom (immersed or dry) or cruiser stern | number of propellers, draught limits, wake quality |
| Midship section | flat bottom + bilge radius, with or without rise of floor; vertical side, flare or tumblehome | Cm, structure, stability |
| Parallel middle body | long (tankers, bulkers, LNG) to none (naval, fast ferries) | Cb, construction cost |

### Typical form coefficients by ship type (design draught)

| Ship type | Fn | Cb | Cm | Cwp | LCB (% L fwd of mid) | L/B | B/T | Bow | Stern |
|---|---|---|---|---|---|---|---|---|---|
| VLCC / Suezmax tanker | 0.12–0.15 | 0.80–0.84 | 0.995–0.998 | 0.88–0.92 | +2.5 … +3.8 | 5.3–5.8 | 2.7–3.0 | large O/Δ bulb at keel | single skeg, small dry transom |
| Bulk carrier (Capesize–Handymax) | 0.13–0.16 | 0.82–0.87 | 0.995–0.998 | 0.88–0.93 | +2.0 … +3.5 | 5.5–6.5 | 2.5–3.0 | large bulb, often blunt / “ax” | single skeg |
| LNG carrier (membrane, 174k m³) | 0.18–0.20 | 0.72–0.76 | 0.985–0.99 | 0.84–0.88 | −1 … +0.5 | 6.0–6.3 | 3.7–4.2 | raised bulb | **twin skeg** (shallow draught, 2 shafts) |
| Container ship (feeder–ULCS) | 0.20–0.26 | 0.60–0.70 | 0.97–0.99 | 0.80–0.86 | −3 … −1 | 6.5–7.5 | 2.6–3.5 | raised Δ/∇ bulb (slow-steaming bulbs are shorter) | single skeg, wide transom near/above DWL |
| Ro-ro / car carrier | 0.22–0.28 | 0.55–0.65 | 0.95–0.98 | 0.75–0.82 | −3 … 0 | 6–7 | 3.5–4.5 | bulb | twin screw, open shafts or twin skeg, immersed transom |
| General cargo / multipurpose | 0.18–0.22 | 0.65–0.75 | 0.97–0.99 | 0.80–0.86 | −1 … +1.5 | 6–7 | 2.2–2.8 | bulb or conventional | single skeg |
| Naval combatant / patrol | 0.30–0.45 | 0.45–0.52 | 0.75–0.83 | 0.72–0.78 | −2 … −0.5 | 7.5–9 | 3.0–3.5 | sonar dome (bulb below keel) | open twin shafts with struts, immersed transom, deadrise |
| Ferry / RoPax | 0.25–0.35 | 0.55–0.62 | 0.90–0.97 | 0.75–0.80 | −3 … −1 | 6–7 | 3.5–4.5 | bulb | twin screw, immersed transom |

## 2. Bows

### 2.1 Bulbous bow
A bulb works by wave cancellation, and by reducing the bow wave and the pitch damping of full ships
in ballast. Kracht's parameters are the industry standard:

| Kracht parameter | Meaning | Typical range | Tool parameter |
|---|---|---|---|
| C_LPR = L_PR / Lpp | protrusion beyond FP | 0.018–0.031 | `bulb.lpr` |
| C_BB = B_B / B | max bulb breadth at FP | 0.17–0.20 (full) / 0.10–0.15 (fine) | `bulb.bb` (× B/2) |
| C_ZB = Z_B / T | height of the bulb's foremost point / top | 0.35–0.55 | `bulb.zn`, `bulb.zt` |
| C_ABT = A_BT / A_M | bulb section area at FP / midship area | 0.064–0.122 | result of `bb`, `zt`, `zb`, `shape` |
| section shape | Δ (widest low: good in ballast), O (oval), ∇ (widest high: good for slamming, high Fn) | — | `bulb.shape` (−1 … +1) |
| nose shape | elliptic / blunt | — | `bulb.pn` |

Variants: **keel-attached** bulbs (tankers, bulkers: the bottom runs straight into the keel),
**raised** bulbs (container ships: the lower profile rises to the bulb, `bulb.zb > 0`) and the
**sonar dome** of naval ships (`bulb.zb < 0`: below the keel, little or no protrusion). All three use
the same parametric body in the tool.

### 2.2 Without a bulb
A conventional raked stem with a forefoot radius (`stem.rake`, `stem.rff`), used for slow coasters,
tugs, and some ships optimised for ballast/partial loading. Setting `bulb.on = false` on any preset
gives the bulbless version; the main-hull sectional area curve still meets the Cb/LCB targets
(automatic correction). A vertical stem is `stem.rake = 0`. Inverted and axe bows are outside the
present scope (they need a stem that overhangs aft above the waterline).

## 3. Sterns and afterbodies

| Arrangement | Description | Where used | Tool |
|---|---|---|---|
| **Single skeg** (open stern) | sections narrow to a skeg on the centreline; propeller in an aperture above the skeg heel; often a stern tube boss | almost all single-screw cargo ships | `skeg.mode = single`, `sec.naft < 1`, stern profile (`stern.*`), `boss.*` |
| Single skeg with stern bulb (Hogner) | U-shaped / bulbous afterbody around the shaft for a more uniform wake | tankers, bulkers | boss radius/length, `sec.naft`, `sec.fla` |
| **Twin skeg** (gondola) | two skegs each carrying a shaft, a flat “tunnel” between them, very full afterbody | LNG carriers, large ro-ro, shallow-draught tankers, some ULCS designs | `skeg.mode = twin` + `skeg.*`, tunnel height via the stern profile |
| Open twin shafts | no skeg; shafts on brackets/struts; slender V afterbody with deadrise | naval, ferries, cruise | `skeg.mode = open`, `mid.rof`, `sec.naft ≈ 1` |
| Transom | flat stern face; immersed (fast ships, wetted transom area) or dry (above DWL) | container, naval, ro-ro | `stern.xtr`, `stern.ztr` (< 1 immersed), `dwl.ytr`, `sac.sig_tr` |

Twin skegs give lower resistance for full, wide, shallow ships, more redundancy and a better wake
for each propeller. They cost more steel and have a larger wetted surface. The key geometric
variables are the skeg centre (shaft) offset (≈0.30–0.40 B/2 from the centreline in LNG carriers),
the skeg width, the skeg length (0.25–0.35 L), the tunnel height at the transom, and the skeg
bottom (normally the baseline).

## 4. Midship section and parallel body
* Bilge radius from Cm: with a flat bottom and vertical sides, `Cm = 1 − 0.4292 r² / (B T)` (plus a
  rise-of-floor term). Tankers and bulkers r ≈ 2.5–3.5 m (Cm ≈ 0.997), container ships r ≈ 3–5 m
  (Cm ≈ 0.98), naval ships with deadrise Cm ≈ 0.82.
* Parallel middle body: 25–60 % L for full ships, 0–15 % for fine ships. In the tool it is the
  plateau of the sectional area curve (`sac.xpa`/`sac.xpf`) and of the waterline (`dwl.xwa`/`dwl.xwf`),
  with the flat-of-bottom and flat-of-side extents (`fob.*`, `fos.*`).

## 5. Ways to make a hull parametric (and the choice made)

| Approach | Idea | Pros | Cons |
|---|---|---|---|
| Parent-hull transformation (Lackenby, affine scaling) | distort an existing hull to new Cp/LCB/L/B/T | exact parent quality | needs a parent per type; no topology changes (bulb/skeg on/off) |
| Statistical series (Series 60, BSRA, Taylor, SSPA) | offsets from systematic series | quick | outdated forms, no modern bulbs/skegs |
| **Fully parametric, form-parameter design** (Harries/CAESES, NAPA, FRIENDSHIP) | design curves (SAC, DWL, flat of bottom/side, profile, deck) from form parameters; sections are generated to satisfy them; appendage-like features as separate parametric surfaces | intuitive engineering parameters, guaranteed coefficients, any type | more parameters; fairness must be built in |

The tool uses the **form-parameter approach**. A clean main hull is defined by longitudinal design
curves solved to hit Cb, LCB, Cm, Cwp and LCF exactly. It is united (CAD Boolean) with parametric
bodies for the bulbous bow / sonar dome, stern tube boss(es) and twin skegs. The union is closed by
the deck and transom into one watertight solid. The complete-hull Cb and LCB are re-targeted
iteratively so they are met after the union. The six presets come from fitting the parameters to
the supplied hulls (section 6). The same fitting procedure can turn any imported hull into an
editable design.

## 6. The six supplied reference hulls

All six files were read, put into one frame (x forward from AP, y to port, z up from the baseline,
full scale in metres) and measured by slicing at 300 stations. Particulars and coefficients are
measured at the design draught.

| Hull | File / scale | Type | Lpp × B × T × D [m] | Cb | Cm | Cwp | LCB % | Bow | Stern |
|---|---|---|---|---|---|---|---|---|---|
| **KCS** | IGES, full scale, half hull | 3600 TEU container ship | 230 × 32.2 × 10.8 × 17.0 (bow 23.5) | 0.6501 | 0.984 | 0.831 | −1.49 | raised bulb, 3.0 % protrusion | single skeg, boss, dry transom (≈1.05 T) |
| **DTC** | STL, model 1:59.407, full hull incl. rudder | 14 000 TEU ULCS | 355 × 51.0 × 14.5 × 34.0 | 0.6605 | 0.987 | 0.846 | −2.64 | high raised bulb (bottom ≈0.35 T), 1 % protrusion | single skeg, dry transom |
| **KVLCC2** | IGES, full scale, half hull (axes reversed) | VLCC | 320 × 58.0 × 20.8 × 28.0 | 0.8095 | 0.997 | 0.901 | +3.51 | large keel-attached O bulb, 2.5 % | single skeg, stern bulb, small transom |
| **JBC** | IGES, model 1:40, full hull | Capesize bulk carrier | 280 × 45.0 × 16.5 × 25.2 | 0.8575 | 0.998 | 0.924 | +2.54 | large bulb, 2.1 % | single skeg (duct fitting) |
| **DTMB 5415** | IGES, model 1:24.824, half hull | naval combatant | 142 × 19.06 × 6.15 × 10.9 (bow 16.2) | 0.4994 | 0.817 | 0.762 | −1.06 | **sonar dome** 3.0 m below keel | open twin shafts, immersed transom, deadrise, flare |
| **KLNG2** | IGES, full scale, full hull incl. propellers/rudders | LNG carrier | 286.0 × 46.2 × 11.5* × 26.5 | 0.7500* | 0.987 | 0.861 | −0.49 | raised bulb, 2.1 % | **twin skeg** (skegs at ±0.35 B/2), tunnel, dry transom |

\* The KLNG2 file states no design draught. 11.5 m (typical for a 174k m³ membrane carrier) was
assumed, with the AP at the file origin. **Please confirm the KLNG2 draught and Lpp.** All KLNG2
coefficients scale with them.

Literature cross-check: KCS Cb 0.6505, KVLCC2 0.8098, JBC 0.858 and DTC 0.661 agree with the
measured values within 0.1 %. DTMB 5415 measures 0.499 against a published 0.507. The difference
probably comes from the geometry variant in the file (the model length matches).

Classification of the six by the features the tool must cover:

| Feature | KCS | DTC | KVLCC2 | JBC | DTMB5415 | KLNG2 |
|---|---|---|---|---|---|---|
| Fullness | fine | fine | full | full | very fine | medium |
| Bulbous bow | raised | high raised | keel-attached | keel-attached | sonar dome | raised |
| Stern | single skeg | single skeg | single skeg | single skeg | open shafts | twin skeg |
| Transom | dry | dry | small, at WL | small, at WL | immersed | dry |
| Parallel middle body | short | short | long | long | none | long |
| Deck sheer / flare | bow sheer, flare | flare | — | — | large sheer, flare | flare |

The tool's presets reproduce each of them; the fit quality is reported in `HullFormDesigner/README.md`.
