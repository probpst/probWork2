"""One-dimensional form-parameter curves.

Every longitudinal design curve of the hull (sectional area, design waterline, flat of bottom, flat of
side, deck line) is built from the same end-curve family on a normalised run t in [0, 1]
(t = 0 at the hull end, t = 1 where the curve joins its parallel part):

    g(t; a, b) = 1 - (1 - t**a)**b

* a controls the end: a = 1 finite slope (entrance angle), a > 1 hollow, a < 1 blunt;
* b controls the shoulder: b > 1 joins the parallel part with zero slope (tangent continuous).
The integral of g is a fullness coefficient in (0, 1); `solve_b` inverts it for a target.
"""
import numpy as np
from scipy.optimize import brentq

_GX, _GW = np.polynomial.legendre.leggauss(64)
_GX = 0.5 * (_GX + 1.0)
_GW = 0.5 * _GW


def end_curve(t, a, b):
    t = np.clip(np.asarray(t, float), 0.0, 1.0)
    return 1.0 - (1.0 - t ** a) ** b


def end_fullness(a, b, moment=False):
    """Integral of g over [0, 1] (and optionally its first moment about t = 0)."""
    g = end_curve(_GX, a, b)
    if moment:
        return float(np.dot(_GW, g)), float(np.dot(_GW, g * _GX))
    return float(np.dot(_GW, g))


def solve_b(fullness, a, lo=0.05, hi=60.0):
    """b such that the integral of g(t; a, b) equals `fullness` (clamped to the reachable range)."""
    f_lo, f_hi = end_fullness(a, lo), end_fullness(a, hi)
    if fullness <= f_lo:
        return lo
    if fullness >= f_hi:
        return hi
    return brentq(lambda b: end_fullness(a, b) - fullness, lo, hi, xtol=1e-10)


def plateau_curve(x, x0a, x1a, x1f, x0f, va, vf, aa=1.0, ba=2.0, af=1.0, bf=2.0, vmax=1.0):
    """Curve equal to `vmax` on [x1a, x1f], falling to `va` at x0a (aft) and `vf` at x0f (forward)
    with end curves (aa, ba) aft and (af, bf) forward; undefined outside [x0a, x0f] (returns the end
    values there)."""
    x = np.asarray(x, float)
    out = np.full(x.shape, float(vmax))
    ma = x < x1a
    if np.any(ma):
        t = (x[ma] - x0a) / max(x1a - x0a, 1e-12)
        out[ma] = va + (vmax - va) * end_curve(t, aa, ba)
    mf = x > x1f
    if np.any(mf):
        t = (x0f - x[mf]) / max(x0f - x1f, 1e-12)
        out[mf] = vf + (vmax - vf) * end_curve(t, af, bf)
    return out


def smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * t * (t * (6.0 * t - 15.0) + 10.0)


def fillet_polyline(pts, radii, n_arc=24):
    """Polyline with circular fillets of the given radius at the interior vertices.
    pts (k, 2), radii (k,) (end values ignored). Returns a dense (m, 2) polyline."""
    pts = np.asarray(pts, float)
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        p0, p1, p2 = pts[i - 1], pts[i], pts[i + 1]
        r = float(radii[i])
        d1 = p0 - p1
        d2 = p2 - p1
        l1, l2 = np.linalg.norm(d1), np.linalg.norm(d2)
        d1, d2 = d1 / l1, d2 / l2
        cosang = np.clip(np.dot(d1, d2), -1.0, 1.0)
        ang = np.arccos(cosang)
        if r <= 0 or ang > np.pi - 1e-6 or ang < 1e-6:
            out.append(p1)
            continue
        dist = r / np.tan(ang / 2.0)
        dist = min(dist, 0.49 * l1, 0.49 * l2)
        r = dist * np.tan(ang / 2.0)
        a = p1 + d1 * dist
        b = p1 + d2 * dist
        bis = d1 + d2
        bis /= np.linalg.norm(bis)
        c = p1 + bis * (r / np.sin(ang / 2.0))
        va, vb = a - c, b - c
        th0 = np.arctan2(va[1], va[0])
        th1 = np.arctan2(vb[1], vb[0])
        dth = (th1 - th0 + np.pi) % (2 * np.pi) - np.pi
        th = th0 + dth * np.linspace(0, 1, n_arc)
        out.extend(c + r * np.c_[np.cos(th), np.sin(th)])
    out.append(pts[-1])
    P = np.array(out)
    keep = np.r_[True, np.linalg.norm(np.diff(P, axis=0), axis=1) > 1e-12]
    return P[keep]


def resample_arclength(P, n):
    """n points evenly spaced in arc length along polyline P (k, d)."""
    s = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    if s[-1] <= 0:
        return np.repeat(P[:1], n, axis=0)
    u = np.linspace(0.0, s[-1], n)
    return np.stack([np.interp(u, s, P[:, k]) for k in range(P.shape[1])], 1)
