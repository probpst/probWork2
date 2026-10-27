"""Fit the presets to the reference hulls and write hullform/presets_fitted.json + comparison plots.

Usage: python tools/fit_presets.py <out folder> [names...] [--nofit]
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from hullform.params import defaults, put, SPEC  # noqa: E402
from hullform.reference import Reference  # noqa: E402
from hullform.fit import apply_reference, fit_staged  # noqa: E402
from hullform.build import Design  # noqa: E402
from hullform.report import compare_figure  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

# initial guesses read off the reference offsets (tools: features in the analysis notes)
GUESS = {
    'KVLCC2': {
        'main.D': 28.0, 'sac.xpa': 0.33, 'sac.xpf': 0.74, 'dwl.xwa': 0.24, 'dwl.xwf': 0.80, 'dwl.ytr': 0.2,
        'fob.xa0': 0.05, 'fob.xa1': 0.40, 'fob.xf1': 0.71, 'fob.xf0': 1.0,
        'fos.xa0': 0.0, 'fos.xa1': 0.25, 'fos.xf1': 0.80, 'fos.xf0': 1.0,
        'sec.naft': 0.6, 'sec.nfwd': 1.5, 'stem.rake': 22.7, 'stem.rff': 0.5,
        'stern.xtr': -0.017, 'stern.ztr': 0.91, 'stern.xck': 0.02, 'stern.zck': 0.70, 'stern.xh': 0.045,
        'stern.rck': 0.15, 'stern.rh': 0.1,
        'deck.ytr': 0.31, 'deck.xda': 0.24, 'deck.xdf': 0.80, 'deck.flare_f': 10, 'deck.flare_a': 5,
        'bulb.on': True, 'bulb.lpr': 0.025, 'bulb.xr': 0.95, 'bulb.xm': 1.0, 'bulb.zt': 0.85, 'bulb.zb': 0.0,
        'bulb.zn': 0.5, 'bulb.bb': 0.25, 'bulb.shape': 0.0, 'bulb.pn': 2.0,
        'boss.on': True, 'boss.zs': 0.3, 'boss.rs': 0.06, 'boss.xe': 0.015, 'boss.len': 0.04,
        'skeg.mode': 'single',
    },
    'JBC': {
        'main.D': 25.22, 'sac.xpa': 0.30, 'sac.xpf': 0.78, 'dwl.xwa': 0.19, 'dwl.xwf': 0.81, 'dwl.ytr': 0.17,
        'fob.xa0': 0.05, 'fob.xa1': 0.29, 'fob.xf1': 0.81, 'fob.xf0': 1.0,
        'fos.xa0': 0.0, 'fos.xa1': 0.2, 'fos.xf1': 0.82, 'fos.xf0': 1.0,
        'sec.naft': 0.6, 'sec.nfwd': 1.5, 'stem.rake': 23.9, 'stem.rff': 0.5,
        'stern.xtr': -0.0176, 'stern.ztr': 0.94, 'stern.xck': 0.01, 'stern.zck': 0.75, 'stern.xh': 0.04,
        'stern.rck': 0.15, 'stern.rh': 0.1,
        'deck.ytr': 0.57, 'deck.xda': 0.19, 'deck.xdf': 0.81, 'deck.flare_f': 10, 'deck.flare_a': 5,
        'bulb.on': True, 'bulb.lpr': 0.0214, 'bulb.xr': 0.95, 'bulb.xm': 1.0, 'bulb.zt': 0.75, 'bulb.zb': 0.0,
        'bulb.zn': 0.42, 'bulb.bb': 0.21, 'bulb.shape': -0.2, 'bulb.pn': 2.0,
        'boss.on': True, 'boss.zs': 0.3, 'boss.rs': 0.06, 'boss.xe': 0.012, 'boss.len': 0.04,
        'skeg.mode': 'single',
    },
    'KCS': {
        'main.D': 17.04, 'deck.shf': 0.38, 'deck.xsf': 0.75, 'sac.xpa': 0.42, 'sac.xpf': 0.52,
        'dwl.xwa': 0.19, 'dwl.xwf': 0.61, 'dwl.ytr': 0.0,
        'fob.xa0': 0.05, 'fob.xa1': 0.44, 'fob.xf1': 0.50, 'fob.xf0': 1.0,
        'fos.xa0': 0.02, 'fos.xa1': 0.3, 'fos.xf1': 0.6, 'fos.xf0': 1.0,
        'sec.naft': 0.5, 'sec.nfwd': 1.0, 'stem.rake': 27.0, 'stem.rff': 0.8,
        'stern.xtr': -0.026, 'stern.ztr': 1.05, 'stern.xck': 0.016, 'stern.zck': 0.85, 'stern.xh': 0.065,
        'stern.rck': 0.15, 'stern.rh': 0.2,
        'deck.ytr': 0.998, 'deck.xda': 0.0, 'deck.xdf': 0.75, 'deck.flare_f': 35, 'deck.flare_a': 10,
        'bulb.on': True, 'bulb.lpr': 0.0297, 'bulb.xr': 0.95, 'bulb.xm': 1.0, 'bulb.zt': 0.85, 'bulb.zb': 0.0,
        'bulb.zn': 0.45, 'bulb.bb': 0.145, 'bulb.shape': 0.1, 'bulb.pn': 2.0,
        'boss.on': True, 'boss.zs': 0.42, 'boss.rs': 0.07, 'boss.xe': 0.012, 'boss.len': 0.04,
        'skeg.mode': 'single',
    },
    'DTC': {
        'main.D': 34.0, 'sac.xpa': 0.40, 'sac.xpf': 0.55, 'dwl.xwa': 0.17, 'dwl.xwf': 0.65, 'dwl.ytr': 0.0,
        'fob.xa0': 0.05, 'fob.xa1': 0.42, 'fob.xf1': 0.50, 'fob.xf0': 1.0,
        'fos.xa0': 0.02, 'fos.xa1': 0.3, 'fos.xf1': 0.62, 'fos.xf0': 1.0,
        'sec.naft': 0.5, 'sec.nfwd': 1.0, 'stem.rake': 13.9, 'stem.rff': 0.6,
        'stern.xtr': -0.0355, 'stern.ztr': 1.055, 'stern.xck': 0.006, 'stern.zck': 0.85, 'stern.xh': 0.06,
        'stern.rck': 0.15, 'stern.rh': 0.2,
        'deck.ytr': 1.0, 'deck.xda': 0.0, 'deck.xdf': 0.86, 'deck.flare_f': 25, 'deck.flare_a': 5,
        'bulb.on': True, 'bulb.lpr': 0.010, 'bulb.xr': 0.95, 'bulb.xm': 0.995, 'bulb.zt': 1.0, 'bulb.zb': 0.3,
        'bulb.zn': 0.65, 'bulb.bb': 0.13, 'bulb.shape': 0.3, 'bulb.pn': 2.0,
        'boss.on': True, 'boss.zs': 0.42, 'boss.rs': 0.07, 'boss.xe': 0.01, 'boss.len': 0.04,
        'skeg.mode': 'single',
    },
    'KLNG2': {
        'main.D': 26.5, 'sac.xpa': 0.38, 'sac.xpf': 0.65, 'dwl.xwa': 0.20, 'dwl.xwf': 0.77, 'dwl.ytr': 0.0,
        'fob.xa0': 0.10, 'fob.xa1': 0.40, 'fob.xf1': 0.62, 'fob.xf0': 1.0,
        'fos.xa0': 0.02, 'fos.xa1': 0.25, 'fos.xf1': 0.75, 'fos.xf0': 1.0,
        'sec.naft': 1.5, 'sec.nfwd': 1.2, 'stem.rake': 18.8, 'stem.rff': 0.6,
        'stern.xtr': 0.0, 'stern.ztr': 1.02, 'stern.xck': 0.05, 'stern.zck': 0.5, 'stern.xh': 0.25,
        'stern.rck': 1.0, 'stern.rh': 2.0,
        'deck.ytr': 0.6, 'deck.xda': 0.15, 'deck.xdf': 0.82, 'deck.flare_f': 20, 'deck.flare_a': 5,
        'bulb.on': True, 'bulb.lpr': 0.0208, 'bulb.xr': 0.95, 'bulb.xm': 1.0, 'bulb.zt': 0.95, 'bulb.zb': 0.1,
        'bulb.zn': 0.55, 'bulb.bb': 0.125, 'bulb.shape': 0.1, 'bulb.pn': 2.0,
        'boss.on': True, 'boss.zs': 0.39, 'boss.rs': 0.07, 'boss.xe': 0.02, 'boss.len': 0.04,
        'skeg.mode': 'twin', 'skeg.ys': 0.35, 'skeg.bw': 0.10, 'skeg.xf': 0.30, 'skeg.xa': 0.03,
        'skeg.zb': 0.0, 'skeg.ze': 0.2, 'skeg.pf': 2.0,
    },
    'DTMB5415': {
        'main.D': 10.89, 'deck.shf': 0.485, 'deck.xsf': 0.45, 'deck.sha': -0.05, 'deck.xsa': 0.3,
        'mid.rof': 0.12, 'sac.xpa': 0.45, 'sac.xpf': 0.50, 'sac.sig_tr': 0.5,
        'dwl.xwa': 0.45, 'dwl.xwf': 0.52, 'dwl.ytr': 0.63, 'dwl.af': 1.0, 'dwl.aa': 1.0,
        'fob.xa0': 0.15, 'fob.xa1': 0.47, 'fob.xf1': 0.49, 'fob.xf0': 0.95,
        'fos.xa0': 0.0, 'fos.xa1': 0.45, 'fos.xf1': 0.52, 'fos.xf0': 0.95,
        'sec.naft': 1.0, 'sec.nfwd': 0.9, 'stem.rake': 35.0, 'stem.rff': 1.0,
        'stern.xtr': -0.010, 'stern.ztr': 0.89, 'stern.xck': 0.10, 'stern.zck': 0.55, 'stern.xh': 0.32,
        'stern.rck': 1.0, 'stern.rh': 3.0,
        'deck.ymid': 1.077, 'deck.ytr': 0.8, 'deck.xda': 0.4, 'deck.xdf': 0.55, 'deck.flare_f': 25,
        'deck.flare_a': 15,
        'bulb.on': True, 'bulb.lpr': 0.002, 'bulb.xr': 0.88, 'bulb.xm': 0.97, 'bulb.zt': 0.25, 'bulb.zb': -0.49,
        'bulb.zn': -0.15, 'bulb.bb': 0.21, 'bulb.shape': 0.0, 'bulb.pn': 2.0,
        'boss.on': False, 'skeg.mode': 'open',
    },
}

# regions of the reference geometry that are not hull, in (x/Lpp, x/Lpp, z/T, z/T)
MASKS = {
    'KLNG2': [(-0.06, 0.035, 0.0, 1.05)],          # propellers and rudders
    'DTC': [(-0.06, 0.02, 0.0, 1.2)],              # rudder
    'KCS': [(0.295, 0.31, 0.0, 3.0)],              # stray transverse face in the IGES file
    'JBC': [(-0.06, -0.005, 0.0, 0.6)],            # shaft end / duct fitting
}

LABELS = {
    'KVLCC2': 'VLCC tanker: full form, bulbous bow, single skeg (KVLCC2 type)',
    'JBC': 'Bulk carrier: full form, bulbous bow, single skeg (JBC type)',
    'KCS': 'Container ship: fine form, bulbous bow, transom, single skeg (KCS type)',
    'DTC': 'Ultra-large container ship: raised bulb, transom, single skeg (DTC type)',
    'KLNG2': 'LNG carrier: twin skeg, bulbous bow (KLNG2 type)',
    'DTMB5415': 'Naval combatant: sonar dome, transom, open shafts (DTMB 5415 type)',
}


def start_params(name, ref):
    p = defaults()
    apply_reference(p, ref)
    for k, v in GUESS[name].items():
        put(p, k, v)
    p['name'] = name
    return p


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    out = args[0]
    names = args[1:] or list(GUESS)
    os.makedirs(out, exist_ok=True)
    store = os.path.join(HERE, '..', 'hullform', 'presets_fitted.json')
    fitted = json.load(open(store)) if os.path.exists(store) else {}
    for name in names:
        ref = Reference(os.path.join(HERE, '..', 'references', name + '.npz'))
        p = start_params(name, ref)
        if name in fitted and '--restart' not in sys.argv:
            for k, v in fitted[name]['values'].items():
                put(p, k, v)
        for a in sys.argv:
            if a.startswith('--set='):
                k, v = a[6:].split('=')
                put(p, k, float(v))
        t = time.time()
        info = {}
        if '--nofit' not in sys.argv:
            p, info = fit_staged(p, ref, cycles=int(os.environ.get('CYCLES', '2')),
                                 maxfev=int(os.environ.get('MAXFEV', '250')),
                                 log=lambda s: print(name, s, flush=True), mask=MASKS.get(name, ()))
        d = Design(p, correct=True)
        rep = compare_figure(d, ref, os.path.join(out, 'compare_%s.png' % name), name, MASKS.get(name, ()))
        print('%-9s rms %.4f -> %.4f (fit), body-plan rms %.4f B/2, nfev %s, %.0f s, Cb %.4f LCB %.2f' % (
            name, info.get('rms0', 0), info.get('rms', 0), rep['rms_halfbreadth'], info.get('nfev'),
            time.time() - t, rep['hydro']['Cb'], rep['hydro']['LCB_pct']), flush=True)
        vals = {k: (round(v, 5) if isinstance(v, float) else v) for k, v in
                ((k, p[k.split('.')[0]][k.split('.')[1]]) for k in SPEC) if not k.startswith('mesh.')}
        if '--nofit' not in sys.argv:
            fitted = json.load(open(store)) if os.path.exists(store) else {}
            fitted[name] = dict(label=LABELS[name], values=vals, rms=rep['rms_halfbreadth'], rms_all=rep['rms_all'],
                                cb=rep['hydro']['Cb'], lcb=rep['hydro']['LCB_pct'], cm=rep['hydro']['Cm'],
                                cwp=rep['hydro']['Cwp'], lcf=rep['hydro']['LCF_pct'])
            json.dump(fitted, open(store, 'w'), indent=1, sort_keys=True)


if __name__ == '__main__':
    main()
