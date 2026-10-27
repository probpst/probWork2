# Parameters (generated from hullform/params.py SCHEMA)

Shape parameters are stored non-dimensionally (× Lpp, × B/2, × T, × D) so a design keeps its form when the principal dimensions change. x positions are measured from the AP, forward positive.

| Path | Label | Unit | Default | Range | Step | Abbr. | Notes |
|---|---|---|---|---|---|---|---|
| `main.Lpp` | Length between perpendiculars | m | 230.0 | 20 – 450 | 0.1 | Lpp |  |
| `main.B` | Moulded breadth | m | 32.2 | 4 – 80 | 0.01 | B |  |
| `main.T` | Design draught | m | 10.8 | 1 – 30 | 0.01 | T |  |
| `main.D` | Depth to deck at side | m | 19.0 | 2 – 45 | 0.01 | D | Top of the generated surface (flat deck). |
| `form.Cb` | Block coefficient Cb | – | 0.65 | 0.35 – 0.9 | 0.0005 | Cb | Target for the complete hull including the bulb, skegs and boss. |
| `form.LCB` | LCB forward of midship | % Lpp | -1.5 | -6 – 6 | 0.01 | LCB |  |
| `form.Cm` | Midship coefficient Cm | – | 0.985 | 0.7 – 0.998 | 0.0005 | Cm | Sets the bilge radius. |
| `form.Cwp` | Waterplane coefficient Cwp | – | 0.83 | 0.6 – 0.97 | 0.0005 | Cwp | Of the main hull. |
| `form.LCF` | LCF forward of midship | % Lpp | -3.0 | -10 – 6 | 0.01 | LCF |  |
| `mid.rof` | Rise of floor at B/2 | × T | 0.0 | 0 – 0.3 | 0.001 | RoF | Deadrise height at the side, in T. |
| `sac.xpa` | Parallel body aft end | × Lpp | 0.4 | 0.1 – 0.6 | 0.001 | PmbA |  |
| `sac.xpf` | Parallel body forward end | × Lpp | 0.55 | 0.4 – 0.9 | 0.001 | PmbF |  |
| `sac.aa` | Run end exponent | – | 1.4 | 0.4 – 3 | 0.01 | SacEndA | 1 finite slope, >1 hollow, <1 blunt. |
| `sac.af` | Entrance end exponent | – | 1.2 | 0.4 – 3 | 0.01 | SacEndF |  |
| `sac.sig_tr` | Immersed transom area coefficient | – | 0.6 | 0.3 – 1 | 0.01 | TrSig |  |
| `dwl.xwa` | Parallel waterline aft end | × Lpp | 0.36 | 0 – 0.6 | 0.001 | WlA |  |
| `dwl.xwf` | Parallel waterline forward end | × Lpp | 0.6 | 0.4 – 0.95 | 0.001 | WlF |  |
| `dwl.aa` | Waterline aft end exponent | – | 1.0 | 0.3 – 3 | 0.01 | WlEndA |  |
| `dwl.af` | Waterline entrance exponent | – | 1.0 | 0.3 – 3 | 0.01 | WlEndF | 1 straight entrance, >1 hollow. |
| `dwl.ytr` | Transom half-breadth at DWL | × B/2 | 0.6 | 0 – 1 | 0.001 | TrB | Used when the transom is immersed. |
| `fob.xa0` | Flat bottom aft end | × Lpp | 0.15 | -0.05 – 0.6 | 0.001 | FobA0 |  |
| `fob.xa1` | Flat bottom full width from | × Lpp | 0.38 | 0 – 0.7 | 0.001 | FobA1 |  |
| `fob.xf1` | Flat bottom full width to | × Lpp | 0.58 | 0.3 – 1 | 0.001 | FobF1 |  |
| `fob.xf0` | Flat bottom forward end | × Lpp | 0.9 | 0.4 – 1.05 | 0.001 | FobF0 |  |
| `fob.pa` | Flat bottom aft taper | – | 1.5 | 0.5 – 4 | 0.01 | FobPa |  |
| `fob.pf` | Flat bottom forward taper | – | 1.5 | 0.5 – 4 | 0.01 | FobPf |  |
| `fos.xa0` | Flat side aft end | × Lpp | 0.1 | -0.05 – 0.6 | 0.001 | FosA0 |  |
| `fos.xa1` | Flat side full depth from | × Lpp | 0.36 | 0 – 0.7 | 0.001 | FosA1 |  |
| `fos.xf1` | Flat side full depth to | × Lpp | 0.6 | 0.3 – 1 | 0.001 | FosF1 |  |
| `fos.xf0` | Flat side forward end | × Lpp | 0.92 | 0.4 – 1.05 | 0.001 | FosF0 |  |
| `fos.pa` | Flat side aft taper | – | 1.5 | 0.5 – 4 | 0.01 | FosPa |  |
| `fos.pf` | Flat side forward taper | – | 1.5 | 0.5 – 4 | 0.01 | FosPf |  |
| `sec.naft` | Keel exponent aft (skeg) | – | 0.6 | 0.2 – 4 | 0.01 | SecNa | <1 hollow / skeg-like, 1 V, >1 U. |
| `sec.nfwd` | Keel exponent forward | – | 1.2 | 0.2 – 4 | 0.01 | SecNf |  |
| `sec.fla` | Waterline flare aft | deg | 0.0 | 0 – 60 | 0.1 | WlFlA | Side slope at the DWL in the run (0 = vertical). |
| `sec.flf` | Waterline flare forward | deg | 0.0 | 0 – 60 | 0.1 | WlFlF | Side slope at the DWL in the entrance. |
| `stem.rake` | Stem rake above DWL | deg | 20.0 | 0 – 50 | 0.1 | StemRake | From the vertical, forward +. |
| `stem.rff` | Forefoot radius | × T | 0.8 | 0 – 3 | 0.01 | FfR |  |
| `stern.xtr` | Transom x | × Lpp | -0.025 | -0.1 – 0.05 | 0.0005 | TrX |  |
| `stern.ztr` | Transom bottom height | × T | 0.85 | 0 – 2 | 0.001 | TrZ | <1: immersed transom. |
| `stern.xck` | Counter knuckle x | × Lpp | 0.0 | -0.1 – 0.2 | 0.0005 | CkX | Where the counter meets the skeg aft edge. |
| `stern.zck` | Counter knuckle height | × T | 0.55 | 0 – 2 | 0.001 | CkZ |  |
| `stern.xh` | Skeg heel x (keel rise starts) | × Lpp | 0.03 | -0.05 – 0.4 | 0.0005 | HeelX |  |
| `stern.rck` | Knuckle radius | × T | 0.3 | 0 – 2 | 0.01 | CkR |  |
| `stern.rh` | Heel radius | × T | 0.2 | 0 – 2 | 0.01 | HeelR |  |
| `deck.ymid` | Deck half-breadth amidships | × B/2 | 1.0 | 0.8 – 1.3 | 0.001 | DkB | >1: flared topside (deck wider than B). |
| `deck.ytr` | Deck half-breadth at transom | × B/2 | 0.9 | 0 – 1.1 | 0.001 | DkTrB |  |
| `deck.xda` | Deck parallel aft end | × Lpp | 0.2 | 0 – 0.6 | 0.001 | DkA |  |
| `deck.xdf` | Deck parallel forward end | × Lpp | 0.75 | 0.4 – 1 | 0.001 | DkF |  |
| `deck.aa` | Deck aft end exponent | – | 1.0 | 0.3 – 3 | 0.01 | DkAa |  |
| `deck.ba` | Deck aft shoulder exponent | – | 2.0 | 1 – 8 | 0.01 | DkBa |  |
| `deck.af` | Deck forward end exponent | – | 0.8 | 0.3 – 3 | 0.01 | DkAf |  |
| `deck.bf` | Deck forward shoulder exponent | – | 2.0 | 1 – 8 | 0.01 | DkBf |  |
| `deck.shf` | Sheer at the stem | × D | 0.0 | -0.2 – 0.8 | 0.001 | SheerF | Deck rise at the stem, in D. |
| `deck.xsf` | Forward sheer starts at | × Lpp | 0.6 | 0.2 – 1 | 0.001 | SheerXf |  |
| `deck.sha` | Sheer at the transom | × D | 0.0 | -0.3 – 0.5 | 0.001 | SheerA |  |
| `deck.xsa` | Aft sheer starts at | × Lpp | 0.3 | 0 – 0.8 | 0.001 | SheerXa |  |
| `deck.flare_f` | Bow flare at deck | deg | 30.0 | -10 – 60 | 0.1 | FlareF |  |
| `deck.flare_a` | Stern flare at deck | deg | 10.0 | -10 – 60 | 0.1 | FlareA |  |
| `bulb.on` | Bulbous bow / sonar dome | on/off | True |  |  | Bulb |  |
| `bulb.lpr` | Protrusion beyond FP | × Lpp | 0.02 | 0 – 0.08 | 0.0001 | BulbLpr | Kracht L_PR / Lpp. |
| `bulb.xr` | Bulb root x (aft end, inside hull) | × Lpp | 0.94 | 0.75 – 1 | 0.0005 | BulbRoot |  |
| `bulb.xm` | x of maximum bulb section | × Lpp | 0.995 | 0.85 – 1.05 | 0.0005 | BulbXm |  |
| `bulb.zt` | Bulb top height | × T | 0.6 | 0.1 – 1.1 | 0.001 | BulbTop | Kracht Z_B / T. |
| `bulb.zb` | Bulb bottom height | × T | 0.0 | -0.6 – 0.4 | 0.001 | BulbBot | Negative: below the keel (sonar dome). |
| `bulb.zn` | Nose height | × T | 0.35 | -0.5 – 1 | 0.001 | BulbNoseZ |  |
| `bulb.bb` | Bulb max half-breadth | × B/2 | 0.15 | 0.02 – 0.5 | 0.0005 | BulbB | Kracht B_B / B. |
| `bulb.shape` | Section shape (-1 delta, 0 oval, +1 nabla) | – | 0.0 | -1 – 1 | 0.01 | BulbShape | Delta: widest low; nabla: widest high. |
| `bulb.pn` | Nose fullness exponent | – | 2.0 | 1.2 – 4 | 0.01 | BulbNoseP | 2 elliptic, higher blunter. |
| `boss.on` | Stern tube boss | on/off | True |  |  | Boss |  |
| `boss.zs` | Shaft height | × T | 0.42 | 0.1 – 1 | 0.001 | ShaftZ |  |
| `boss.rs` | Boss radius | × T | 0.07 | 0.01 – 0.3 | 0.0005 | BossR |  |
| `boss.xe` | Boss aft end x | × Lpp | 0.012 | -0.05 – 0.2 | 0.0005 | BossX |  |
| `boss.len` | Boss length | × Lpp | 0.04 | 0.005 – 0.2 | 0.0005 | BossL |  |
| `skeg.mode` | Stern arrangement | choice | single | single / twin / open |  | Skeg | single: centreline skeg; twin: two skegs + tunnel; open: no skeg (open shafts). |
| `skeg.ys` | Twin skeg centre (shaft) offset | × B/2 | 0.36 | 0.1 – 0.8 | 0.001 | SkegY |  |
| `skeg.bw` | Twin skeg max half-width | × B/2 | 0.12 | 0.02 – 0.4 | 0.0005 | SkegW |  |
| `skeg.xf` | Twin skeg forward end | × Lpp | 0.35 | 0.1 – 0.7 | 0.001 | SkegXf |  |
| `skeg.xa` | Twin skeg aft end | × Lpp | 0.02 | -0.05 – 0.2 | 0.0005 | SkegXa |  |
| `skeg.zb` | Twin skeg bottom height | × T | 0.0 | -0.1 – 0.5 | 0.001 | SkegZ |  |
| `skeg.ze` | Twin skeg aft end bottom height | × T | 0.25 | 0 – 1 | 0.001 | SkegZe |  |
| `skeg.pf` | Twin skeg forward fairing exponent | – | 2.0 | 1 – 5 | 0.01 | SkegPf |  |
| `cad.fillet` | Appendage junction fillet radius | m | 0.0 | 0 – 5 | 0.01 | Fillet | Constant-radius fillet between the main hull and bulb / skegs (CAD kernel; skipped if it fails). |
| `mesh.ns` | Stations (preview) | – | 121 | 30 – 400 | 1 | Ns |  |
| `mesh.nm` | Girth points per section (preview) | – | 61 | 20 – 200 | 1 | Nm |  |
