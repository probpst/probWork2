"""Parameter schema (single source of truth) and parameter files.

Every parameter is declared once in SCHEMA; the GUI, the command line, batch sweeps and the file
format are all derived from it. Shape parameters are stored non-dimensionally so that a design keeps
its form when the principal dimensions change:

    unit 'm'   metres            'deg' degrees           '-'  plain number
    unit 'L'   fraction of Lpp (x positions from the AP, forward +)
    unit 'B2'  fraction of the half breadth B/2
    unit 'T'   fraction of the design draught T (heights above the baseline, lengths)
    unit 'D'   fraction of the depth D
    unit 'pct' percent of Lpp (LCB / LCF forward of midship +)
"""
import copy
import json

SCHEMA_VERSION = 1

# (path, default, label, unit, lo, hi, step, abbreviation, hint)
SCHEMA = [
    # ---------------------------------------------------------------- principal dimensions
    ('main.Lpp', 230.0, 'Length between perpendiculars', 'm', 20, 450, 0.1, 'Lpp', ''),
    ('main.B', 32.2, 'Moulded breadth', 'm', 4, 80, 0.01, 'B', ''),
    ('main.T', 10.8, 'Design draught', 'm', 1, 30, 0.01, 'T', ''),
    ('main.D', 19.0, 'Depth to deck at side', 'm', 2, 45, 0.01, 'D', 'Top of the generated surface (flat deck).'),
    # ---------------------------------------------------------------- form coefficients (targets)
    ('form.Cb', 0.65, 'Block coefficient Cb', '-', 0.35, 0.90, 0.0005, 'Cb',
     'Target for the complete hull including the bulb, skegs and boss.'),
    ('form.LCB', -1.5, 'LCB forward of midship', 'pct', -6, 6, 0.01, 'LCB', ''),
    ('form.Cm', 0.985, 'Midship coefficient Cm', '-', 0.70, 0.998, 0.0005, 'Cm', 'Sets the bilge radius.'),
    ('form.Cwp', 0.83, 'Waterplane coefficient Cwp', '-', 0.60, 0.97, 0.0005, 'Cwp', 'Of the main hull.'),
    ('form.LCF', -3.0, 'LCF forward of midship', 'pct', -10, 6, 0.01, 'LCF', ''),
    ('mid.rof', 0.0, 'Rise of floor at B/2', 'T', 0, 0.3, 0.001, 'RoF', 'Deadrise height at the side, in T.'),
    # ---------------------------------------------------------------- sectional area curve
    ('sac.xpa', 0.40, 'Parallel body aft end', 'L', 0.1, 0.6, 0.001, 'PmbA', ''),
    ('sac.xpf', 0.55, 'Parallel body forward end', 'L', 0.4, 0.9, 0.001, 'PmbF', ''),
    ('sac.aa', 1.4, 'Run end exponent', '-', 0.4, 3.0, 0.01, 'SacEndA', '1 finite slope, >1 hollow, <1 blunt.'),
    ('sac.af', 1.2, 'Entrance end exponent', '-', 0.4, 3.0, 0.01, 'SacEndF', ''),
    ('sac.sig_tr', 0.6, 'Immersed transom area coefficient', '-', 0.3, 1.0, 0.01, 'TrSig', ''),
    # ---------------------------------------------------------------- design waterline
    ('dwl.xwa', 0.36, 'Parallel waterline aft end', 'L', 0.0, 0.6, 0.001, 'WlA', ''),
    ('dwl.xwf', 0.60, 'Parallel waterline forward end', 'L', 0.4, 0.95, 0.001, 'WlF', ''),
    ('dwl.aa', 1.0, 'Waterline aft end exponent', '-', 0.3, 3.0, 0.01, 'WlEndA', ''),
    ('dwl.af', 1.0, 'Waterline entrance exponent', '-', 0.3, 3.0, 0.01, 'WlEndF', '1 straight entrance, >1 hollow.'),
    ('dwl.ytr', 0.6, 'Transom half-breadth at DWL', 'B2', 0.0, 1.0, 0.001, 'TrB', 'Used when the transom is immersed.'),
    # ---------------------------------------------------------------- flat of bottom / flat of side
    ('fob.xa0', 0.15, 'Flat bottom aft end', 'L', -0.05, 0.6, 0.001, 'FobA0', ''),
    ('fob.xa1', 0.38, 'Flat bottom full width from', 'L', 0.0, 0.7, 0.001, 'FobA1', ''),
    ('fob.xf1', 0.58, 'Flat bottom full width to', 'L', 0.3, 1.0, 0.001, 'FobF1', ''),
    ('fob.xf0', 0.90, 'Flat bottom forward end', 'L', 0.4, 1.05, 0.001, 'FobF0', ''),
    ('fob.pa', 1.5, 'Flat bottom aft taper', '-', 0.5, 4, 0.01, 'FobPa', ''),
    ('fob.pf', 1.5, 'Flat bottom forward taper', '-', 0.5, 4, 0.01, 'FobPf', ''),
    ('fos.xa0', 0.10, 'Flat side aft end', 'L', -0.05, 0.6, 0.001, 'FosA0', ''),
    ('fos.xa1', 0.36, 'Flat side full depth from', 'L', 0.0, 0.7, 0.001, 'FosA1', ''),
    ('fos.xf1', 0.60, 'Flat side full depth to', 'L', 0.3, 1.0, 0.001, 'FosF1', ''),
    ('fos.xf0', 0.92, 'Flat side forward end', 'L', 0.4, 1.05, 0.001, 'FosF0', ''),
    ('fos.pa', 1.5, 'Flat side aft taper', '-', 0.5, 4, 0.01, 'FosPa', ''),
    ('fos.pf', 1.5, 'Flat side forward taper', '-', 0.5, 4, 0.01, 'FosPf', ''),
    # ---------------------------------------------------------------- section shape
    ('sec.naft', 0.6, 'Keel exponent aft (skeg)', '-', 0.2, 4, 0.01, 'SecNa', '<1 hollow / skeg-like, 1 V, >1 U.'),
    ('sec.nfwd', 1.2, 'Keel exponent forward', '-', 0.2, 4, 0.01, 'SecNf', ''),
    ('sec.rk', 0.02, 'Keel rounding of hollow sections', 'T', 0.0, 0.1, 0.001, 'KeelR',
     'Radius of the round skeg / keel bottom where the sections are hollow (no zero-thickness fin).'),
    ('sec.fla', 0.0, 'Waterline flare aft', 'deg', 0, 60, 0.1, 'WlFlA', 'Side slope at the DWL in the run (0 = vertical).'),
    ('sec.flf', 0.0, 'Waterline flare forward', 'deg', 0, 60, 0.1, 'WlFlF', 'Side slope at the DWL in the entrance.'),
    # ---------------------------------------------------------------- stem and stern profile
    ('stem.rake', 20.0, 'Stem rake above DWL', 'deg', 0, 50, 0.1, 'StemRake', 'From the vertical, forward +.'),
    ('stem.rff', 0.8, 'Forefoot radius', 'T', 0.0, 3.0, 0.01, 'FfR', ''),
    ('stern.xtr', -0.025, 'Transom x', 'L', -0.1, 0.05, 0.0005, 'TrX', ''),
    ('stern.ztr', 0.85, 'Transom bottom height', 'T', 0.0, 2.0, 0.001, 'TrZ', '<1: immersed transom.'),
    ('stern.xck', 0.0, 'Counter knuckle x', 'L', -0.1, 0.2, 0.0005, 'CkX', 'Where the counter meets the skeg aft edge.'),
    ('stern.zck', 0.55, 'Counter knuckle height', 'T', 0.0, 2.0, 0.001, 'CkZ', ''),
    ('stern.xh', 0.03, 'Skeg heel x (keel rise starts)', 'L', -0.05, 0.4, 0.0005, 'HeelX', ''),
    ('stern.rck', 0.3, 'Knuckle radius', 'T', 0.0, 2.0, 0.01, 'CkR', ''),
    ('stern.rh', 0.2, 'Heel radius', 'T', 0.0, 2.0, 0.01, 'HeelR', ''),
    # ---------------------------------------------------------------- deck and topside
    ('deck.ymid', 1.0, 'Deck half-breadth amidships', 'B2', 0.8, 1.3, 0.001, 'DkB', '>1: flared topside (deck wider than B).'),
    ('deck.ytr', 0.9, 'Deck half-breadth at transom', 'B2', 0.0, 1.1, 0.001, 'DkTrB', ''),
    ('deck.xda', 0.2, 'Deck parallel aft end', 'L', 0.0, 0.6, 0.001, 'DkA', ''),
    ('deck.xdf', 0.75, 'Deck parallel forward end', 'L', 0.4, 1.0, 0.001, 'DkF', ''),
    ('deck.aa', 1.0, 'Deck aft end exponent', '-', 0.3, 3, 0.01, 'DkAa', ''),
    ('deck.ba', 2.0, 'Deck aft shoulder exponent', '-', 1.0, 8, 0.01, 'DkBa', ''),
    ('deck.af', 0.8, 'Deck forward end exponent', '-', 0.3, 3, 0.01, 'DkAf', ''),
    ('deck.bf', 2.0, 'Deck forward shoulder exponent', '-', 1.0, 8, 0.01, 'DkBf', ''),
    ('deck.shf', 0.0, 'Sheer at the stem', 'D', -0.2, 0.8, 0.001, 'SheerF', 'Deck rise at the stem, in D.'),
    ('deck.xsf', 0.6, 'Forward sheer starts at', 'L', 0.2, 1.0, 0.001, 'SheerXf', ''),
    ('deck.sha', 0.0, 'Sheer at the transom', 'D', -0.3, 0.5, 0.001, 'SheerA', ''),
    ('deck.xsa', 0.3, 'Aft sheer starts at', 'L', 0.0, 0.8, 0.001, 'SheerXa', ''),
    ('deck.flare_f', 30.0, 'Bow flare at deck', 'deg', -10, 60, 0.1, 'FlareF', ''),
    ('deck.flare_a', 10.0, 'Stern flare at deck', 'deg', -10, 60, 0.1, 'FlareA', ''),
    # ---------------------------------------------------------------- bulbous bow / sonar dome
    ('bulb.on', True, 'Bulbous bow / sonar dome', 'bool', None, None, None, 'Bulb', ''),
    ('bulb.lpr', 0.02, 'Protrusion beyond FP', 'L', 0.0, 0.08, 0.0001, 'BulbLpr', 'Kracht L_PR / Lpp.'),
    ('bulb.xr', 0.94, 'Bulb root x (aft end, inside hull)', 'L', 0.80, 0.99, 0.0005, 'BulbRoot', ''),
    ('bulb.xm', 0.995, 'x of maximum bulb section', 'L', 0.93, 1.03, 0.0005, 'BulbXm', ''),
    ('bulb.zt', 0.6, 'Bulb top height', 'T', 0.1, 1.1, 0.001, 'BulbTop', 'Kracht Z_B / T.'),
    ('bulb.zb', 0.0, 'Bulb bottom height', 'T', -0.6, 0.4, 0.001, 'BulbBot', 'Negative: below the keel (sonar dome).'),
    ('bulb.zn', 0.35, 'Nose height', 'T', -0.5, 1.0, 0.001, 'BulbNoseZ', ''),
    ('bulb.bb', 0.15, 'Bulb max half-breadth', 'B2', 0.02, 0.35, 0.0005, 'BulbB', 'Kracht B_B / B.'),
    ('bulb.shape', 0.0, 'Section shape (-1 delta, 0 oval, +1 nabla)', '-', -1, 1, 0.01, 'BulbShape',
     'Delta: widest low; nabla: widest high.'),
    ('bulb.pn', 2.0, 'Nose fullness exponent', '-', 1.2, 4, 0.01, 'BulbNoseP', '2 elliptic, higher blunter.'),
    # ---------------------------------------------------------------- stern boss (shaft exit)
    ('boss.on', True, 'Stern tube boss', 'bool', None, None, None, 'Boss', ''),
    ('boss.zs', 0.42, 'Shaft height', 'T', 0.15, 0.8, 0.001, 'ShaftZ', ''),
    ('boss.rs', 0.07, 'Boss radius', 'T', 0.01, 0.15, 0.0005, 'BossR', ''),
    ('boss.xe', 0.012, 'Boss aft end x', 'L', -0.03, 0.1, 0.0005, 'BossX', ''),
    ('boss.len', 0.04, 'Boss length', 'L', 0.005, 0.1, 0.0005, 'BossL', ''),
    # ---------------------------------------------------------------- skegs
    ('skeg.mode', 'single', 'Stern arrangement', 'sel', ['single', 'twin', 'open'], None, None, 'Skeg',
     'single: centreline skeg; twin: two skegs + tunnel; open: no skeg (open shafts).'),
    ('skeg.ys', 0.36, 'Twin skeg centre (shaft) offset', 'B2', 0.1, 0.8, 0.001, 'SkegY', ''),
    ('skeg.bw', 0.12, 'Twin skeg max half-width', 'B2', 0.02, 0.4, 0.0005, 'SkegW', ''),
    ('skeg.xf', 0.35, 'Twin skeg forward end', 'L', 0.1, 0.7, 0.001, 'SkegXf', ''),
    ('skeg.xa', 0.02, 'Twin skeg aft end', 'L', -0.05, 0.2, 0.0005, 'SkegXa', ''),
    ('skeg.zb', 0.0, 'Twin skeg bottom height', 'T', -0.1, 0.5, 0.001, 'SkegZ', ''),
    ('skeg.ze', 0.25, 'Twin skeg aft end bottom height', 'T', 0.0, 1.0, 0.001, 'SkegZe', ''),
    ('skeg.pf', 2.0, 'Twin skeg forward fairing exponent', '-', 1.0, 5, 0.01, 'SkegPf', ''),
    # ---------------------------------------------------------------- CAD / mesh
    ('cad.fillet', 0.0, 'Appendage junction fillet radius', 'm', 0, 5, 0.01, 'Fillet',
     'Constant-radius fillet between the main hull and bulb / skegs (CAD kernel; skipped if it fails).'),
    ('mesh.ns', 121, 'Stations (preview)', '-', 30, 400, 1, 'Ns', ''),
    ('mesh.nm', 61, 'Girth points per section (preview)', '-', 20, 200, 1, 'Nm', ''),
]

SPEC = {e[0]: dict(zip(('path', 'default', 'label', 'unit', 'lo', 'hi', 'step', 'abbr', 'hint'), e)) for e in SCHEMA}


def get(p, path):
    g, k = path.split('.')
    return p[g][k]


def put(p, path, v):
    g, k = path.split('.')
    p.setdefault(g, {})[k] = v


def defaults():
    p = {'version': SCHEMA_VERSION, 'name': 'hull', 'preset': ''}
    for e in SCHEMA:
        put(p, e[0], copy.deepcopy(e[1]))
    return p


def new_params(preset=None):
    from .presets import PRESETS
    p = defaults()
    if preset:
        for k, v in PRESETS[preset]['values'].items():
            put(p, k, v)
        p['preset'] = preset
        p['name'] = preset
    return p


def merge(src):
    """Load a (possibly older or partial) parameter dict onto the defaults of its preset."""
    p = new_params(src.get('preset') or None)
    for e in SCHEMA:
        g, k = e[0].split('.')
        if g in src and k in src[g]:
            p[g][k] = src[g][k]
    p['name'] = src.get('name', p['name'])
    return p


def save_json(p, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(p, f, indent=1)


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return merge(json.load(f))
