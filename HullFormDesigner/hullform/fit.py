"""Fit the shape parameters of a design to a reference hull (offsets + form coefficients).

The principal dimensions and the coefficient targets (Cb, LCB, Cm, Cwp, LCF) are taken from the
reference; the remaining shape parameters are found by bounded least squares on the outer
half-breadth table. Used to create the presets from the benchmark hulls and, in the program, to turn
an imported IGES/STL hull into an editable parametric design.
"""
import copy

import numpy as np
from scipy.optimize import least_squares, minimize

from .params import SPEC, get, put
from .build import Design
from .offsets import outer_halfbreadth

FIXED_GROUPS = ('main', 'form', 'mesh', 'cad')


def free_paths(p, exclude=()):
    out = []
    for path, e in SPEC.items():
        g = path.split('.')[0]
        if g in FIXED_GROUPS or e['unit'] in ('bool', 'sel') or path in exclude:
            continue
        if g == 'bulb' and not p['bulb']['on']:
            continue
        if g == 'boss' and not p['boss']['on']:
            continue
        if g == 'skeg' and p['skeg']['mode'] != 'twin':
            continue
        out.append(path)
    return out


def apply_reference(p, ref):
    h = ref.meta['hydro']
    p['main'].update(Lpp=ref.meta['Lpp'], B=ref.meta['B'], T=ref.meta['T'])
    p['form'].update(Cb=round(h['Cb'], 4), LCB=round(h['LCB_pct'], 3), Cm=round(min(h['Cm'], 0.998), 4),
                     Cwp=round(h['Cwp'], 4), LCF=round(h['LCF_pct'], 3))
    return p


def residuals_factory(p0, ref, paths, xs_step=2, zs_step=2, w_low=1.0, mask=()):
    xq, zq = ref.x[::xs_step].astype(float), ref.z[::zs_step].astype(float)
    Href = ref.H[::xs_step, ::zs_step].astype(float)
    B2 = p0['main']['B'] / 2
    T = p0['main']['T']
    # weights: emphasise the underwater body, keep the topside in
    wz = np.where(zq <= 1.05 * T, 1.0, 0.5)[None, :] * np.ones((len(xq), 1))
    # regions of the reference that are not hull (propellers, rudders, stray faces): ignored
    L = p0['main']['Lpp']
    for x0, x1, z0, z1 in mask:
        wz[np.ix_((xq >= x0 * L) & (xq <= x1 * L), (zq >= z0 * T) & (zq <= z1 * T))] = 0.0
    lo = np.array([SPEC[k]['lo'] for k in paths], float)
    hi = np.array([SPEC[k]['hi'] for k in paths], float)
    # nothing below the baseline in the reference: bulb and skeg bottoms stay on or above it
    if ref.meta.get('z_min', 0.0) > -0.01 * T:
        for i, k in enumerate(paths):
            if k in ('bulb.zb', 'skeg.zb'):
                lo[i] = 0.0

    def make(u):
        p = copy.deepcopy(p0)
        for k, v in zip(paths, lo + (hi - lo) * u):
            put(p, k, float(v))
        return p

    def res(u):
        p = make(u)
        try:
            d = Design(p)
            H = outer_halfbreadth(d, xq, zq)
        except Exception:
            return np.full(Href.size + 1, 1.0)
        # stations whose sectional area cannot be met make box-corner sections: penalise them
        pen = 0.05 * np.sqrt(Href.size) * d.hull.n_bad / max(len(d.stations), 1)
        return np.r_[((H - Href) / B2 * wz).ravel(), pen]
    return res, make, lo, hi


def fit(p0, ref, paths=None, max_nfev=400, verbose=0):
    paths = paths or free_paths(p0)
    res, make, lo, hi = residuals_factory(p0, ref, paths)
    u0 = np.clip((np.array([get(p0, k) for k in paths], float) - lo) / (hi - lo), 0, 1)
    sol = least_squares(res, u0, bounds=(0, 1), diff_step=2e-3, x_scale='jac', max_nfev=max_nfev,
                        verbose=verbose)
    p = make(sol.x)
    rms = float(np.sqrt(np.mean(sol.fun ** 2)))
    return p, dict(rms=rms, rms0=float(np.sqrt(np.mean(res(u0) ** 2))), nfev=sol.nfev, paths=paths)


GROUPS = [
    ('stern', ('stern.', 'boss.')),
    ('bow', ('stem.', 'bulb.')),
    ('dwl', ('dwl.',)),
    ('sac', ('sac.',)),
    ('fob', ('fob.',)),
    ('fos', ('fos.',)),
    ('sec', ('sec.', 'mid.')),
    ('deck', ('deck.',)),
    ('skeg', ('skeg.',)),
]


def fit_staged(p0, ref, cycles=2, maxfev=250, log=print, mask=()):
    """Derivative-free fit by parameter groups (Powell), repeated `cycles` times. The offset error
    is piecewise smooth (profile edges switch on and off), so gradient methods stall."""
    p = copy.deepcopy(p0)
    allp = free_paths(p)
    res_all, _, lo0, hi0 = residuals_factory(p, ref, allp, mask=mask)
    rms0 = float(np.sqrt(np.mean(res_all(np.clip((np.array([get(p, k) for k in allp]) - lo0) / (hi0 - lo0),
                                                 0, 1)) ** 2)))
    nfev = 0
    for cyc in range(cycles):
        for gname, prefixes in GROUPS:
            paths = [k for k in allp if k.startswith(prefixes)]
            if not paths:
                continue
            res, make, lo, hi = residuals_factory(p, ref, paths, mask=mask)
            u0 = np.clip((np.array([get(p, k) for k in paths], float) - lo) / (hi - lo), 0, 1)

            def f(u):
                return float(np.mean(res(np.clip(u, 0, 1)) ** 2))
            sol = minimize(f, u0, method='Powell', bounds=[(0, 1)] * len(u0),
                           options=dict(maxfev=maxfev, xtol=1e-3, ftol=1e-6))
            nfev += sol.nfev
            if sol.fun <= f(u0):
                p = make(np.clip(sol.x, 0, 1))
            if log:
                log('  cycle %d %-6s rms %.4f' % (cyc + 1, gname, np.sqrt(min(sol.fun, f(u0)))))
    res_all, _, lo, hi = residuals_factory(p, ref, allp, mask=mask)
    u = np.clip((np.array([get(p, k) for k in allp]) - lo) / (hi - lo), 0, 1)
    return p, dict(rms0=rms0, rms=float(np.sqrt(np.mean(res_all(u) ** 2))), nfev=nfev, paths=allp)
