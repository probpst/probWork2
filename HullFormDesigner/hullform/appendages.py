"""Add-on bodies united with the main hull: bulbous bow / sonar dome, stern tube boss(es), twin skegs.

Each body is described as a ring grid R[i, j] (stations i along x, closed loop j around the body,
first point == no repeat) with an end treatment at either end: 'point' (the ring collapses to a nose
point) or 'cap' (a flat end, normally buried inside the main hull). The same ring grids feed the
preview mesh and the CAD surfaces.
"""
import numpy as np

from .curves import smoothstep
from .mesh import TriMesh, grid_mesh


class RingBody(object):
    def __init__(self, name, R, start='cap', end='point'):
        self.name, self.R, self.start, self.end = name, R, start, end

    def mesh(self):
        R = self.R
        ni, nj = R.shape[:2]
        G = np.concatenate([R, R[:, :1]], axis=1)          # close the loop for gridding
        V, F = grid_mesh(G)
        V, F = list(V), [F]
        n = len(V)
        nj1 = nj + 1
        for side, row in ((self.start, 0), (self.end, ni - 1)):
            c = R[row].mean(0)
            V.append(c)
            ci = n
            n += 1
            idx = row * nj1 + np.arange(nj1)
            tri = np.c_[np.full(nj, ci), idx[:-1], idx[1:]]
            F.append(tri if row == 0 else tri[:, ::-1])
        m = TriMesh(np.array(V), np.vstack(F), self.name).welded()
        return m.orient_outward()


def _loop(nj, shape=0.0, e=2.5):
    """Unit closed loop (y, z) in [-1, 1]^2, superellipse exponent e, widest low for shape < 0
    (delta bulb) and high for shape > 0 (nabla bulb). Starts at the bottom, runs over starboard."""
    th = np.linspace(-np.pi / 2, 3 * np.pi / 2, nj, endpoint=False)
    c, s = np.cos(th), np.sin(th)
    y = np.sign(c) * np.abs(c) ** (2.0 / e)
    z = np.sign(s) * np.abs(s) ** (2.0 / e)
    k = 0.35 * shape
    y = y * (1 + k * z) / (1 + abs(k))
    return np.c_[y, z]


def bulb(p, hull, ni=48, nj=48):
    """Bulbous bow (or sonar dome when its bottom is below the keel)."""
    b, L, T, B2 = p['bulb'], hull.L, hull.T, hull.B2
    xr, xm = b['xr'] * L, b['xm'] * L
    xn = L + b['lpr'] * L
    # keep root < max section < nose so the rings never run backwards
    xm = min(xm, xn - 0.01 * L)
    xr = min(xr, xm - 0.02 * L)
    zb, zt, zn = b['zb'] * T, b['zt'] * T, b['zn'] * T
    w = b['bb'] * B2
    loop = _loop(nj, b['shape'])
    # stations: aft root -> max section -> nose (clustered at the nose)
    ua = np.linspace(0, 1, ni // 3, endpoint=False)
    uf = 1 - np.cos(0.5 * np.pi * np.linspace(0, 1, ni - len(ua)))
    xs = np.r_[xr + (xm - xr) * ua, xm + (xn - xm) * uf]
    R = np.zeros((len(xs), nj, 3))
    pn = b['pn']
    for i, x in enumerate(xs):
        if x <= xm:
            f = 1.0 - 0.35 * smoothstep((xm - x) / max(xm - xr, 1e-9))
            lo, hi, ww = zb, zt, w * f
        else:
            s = (x - xm) / (xn - xm)
            f = (1 - min(s, 1.0) ** pn) ** (1 / pn)
            lo, hi, ww = zn - (zn - zb) * f, zn + (zt - zn) * f, w * f
        # never lie tangentially on the keel: where the bulb bottom is at (or above) the hull bottom,
        # lift it just inside the hull; a sonar dome hanging below the keel is left alone
        z0h = float(hull.z0(np.array([x]))[0])
        wl = smoothstep((lo - z0h + 0.06 * T) / (0.04 * T))
        lo = min(lo + wl * max(z0h + 0.05 * T - lo, 0.0), 0.5 * (lo + hi))
        zc, hz = 0.5 * (lo + hi), 0.5 * (hi - lo)
        R[i, :, 0] = x
        R[i, :, 1] = loop[:, 0] * ww
        R[i, :, 2] = zc + loop[:, 1] * hz
    return RingBody('bulb', R, start='cap', end='point')


def boss(p, hull, ys=0.0, ni=24, nj=32, name='boss'):
    o, L, T = p['boss'], hull.L, hull.T
    zs, r = o['zs'] * T, o['rs'] * T
    xe = o['xe'] * L
    xf = xe + o['len'] * L
    # rounded aft end over one radius, cylinder forward
    t = np.linspace(0, 1, ni)
    xs = xe + (xf - xe) * t
    rr = np.full(ni, r)
    lend = min(0.8 * r, 0.4 * (xf - xe))
    m = xs < xe + lend
    u = (xs[m] - xe) / lend
    rr[m] = r * np.sqrt(np.clip(1 - (1 - u) ** 2, 0, 1))
    th = np.linspace(-np.pi / 2, 3 * np.pi / 2, nj, endpoint=False)
    R = np.zeros((ni, nj, 3))
    R[:, :, 0] = xs[:, None]
    R[:, :, 1] = ys + rr[:, None] * np.cos(th)[None]
    R[:, :, 2] = zs + rr[:, None] * np.sin(th)[None]
    R = R[::-1]                                  # forward (buried cap) -> aft end point
    R[-1, :, 1:] = R[-1, :, 1:].mean(0)
    return RingBody(name, R, start='cap', end='point')


def skeg(p, hull, side=1, ni=60, nj=40):
    """One skeg of a twin-skeg stern, centred on y = side * ys."""
    s, L, T, B2 = p['skeg'], hull.L, hull.T, hull.B2
    yc = side * s['ys'] * B2
    xa, xf = s['xa'] * L, s['xf'] * L
    w = s['bw'] * B2
    xmx = xa + 0.25 * (xf - xa)                  # station of maximum width
    t = np.linspace(0, 1, ni)
    xs = xa + (xf - xa) * (0.5 - 0.5 * np.cos(np.pi * t))
    loop = _loop(nj, 0.0, e=3.0)
    R = np.zeros((ni, nj, 3))
    for i, x in enumerate(xs):
        if x <= xmx:
            u = (xmx - x) / max(xmx - xa, 1e-9)
            f = np.sqrt(np.clip(1 - u ** 2, 0.0, 1.0)) * 0.85 + 0.15
            zb = s['zb'] * T + (s['ze'] - s['zb']) * T * smoothstep(u)
        else:
            u = (x - xmx) / max(xf - xmx, 1e-9)
            f = (1 - min(u, 1.0) ** s['pf']) ** (1 / s['pf'])
            zb = s['zb'] * T
        z0h = float(max(hull.z0(np.array([x]))[0], 0.0))
        zt = min(z0h + 0.45 * T, 0.95 * T)
        # where the hull bottom comes down to the skeg bottom, lift the skeg just inside the hull
        # (a tangential contact of two bottoms would give a non-manifold union)
        wl = smoothstep((zb + 0.06 * T - z0h) / (0.04 * T))
        zb = zb + wl * max(z0h + 0.02 * T - zb, 0.0)
        ww = max(w * f, 1e-4 * B2)
        zc, hz = 0.5 * (zb + zt), 0.5 * (zt - zb)
        R[i, :, 0] = x
        R[i, :, 1] = yc + loop[:, 0] * ww
        R[i, :, 2] = zc + loop[:, 1] * hz
    return RingBody('skeg_%s' % ('p' if side > 0 else 's'), R, start='cap', end='point')


def bodies(p, hull):
    out = []
    if p['bulb']['on']:
        out.append(bulb(p, hull))
    mode = p['skeg']['mode']
    if mode == 'twin':
        for sd in (1, -1):
            out.append(skeg(p, hull, sd))     # blunt aft end (cap) carrying the boss, faired forward
        if p['boss']['on']:
            ys = p['skeg']['ys'] * hull.B2
            out.append(boss(p, hull, ys, name='boss_p'))
            out.append(boss(p, hull, -ys, name='boss_s'))
    elif p['boss']['on'] and mode == 'single':
        out.append(boss(p, hull))
    return out
