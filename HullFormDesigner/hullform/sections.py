"""Transverse sections of the main hull.

A half section (y >= 0) runs from the centreline point (0, z0) to the deck edge (yd, zd):

    deadrise line   (0, z0) -> (yf, zb)                       zb = z0 + yf tan(beta)
    bilge quadrant  (yf, zb) -> (b, zs)   y = yf + (b - yf) (1 - s^m)^(1/n),  s = (zs - z)/(zs - zb)
    flat side       (b, zs)  -> (b, T)
    topside         (b, T)   -> (yd, zd)  cubic Bezier, tangent-continuous at T, flare angle at deck

b is the design-waterline half-breadth, yf the flat-of-bottom half-width, zs the lower end of the
flat side. The keel exponent n sets the bottom: n > 1 flat (U), n = 1 deadrise V, n < 1 hollow /
skeg-like (S-shaped with m > 1). m >= 1 is solved so that the section area below T equals the
sectional-area-curve value: the quadrant fullness is
    sigma(n, m) = Gamma(1 + 1/n) Gamma(1 + 1/m) / Gamma(1 + 1/n + 1/m).
Stations whose centreline point is above the waterline (raked stem, counter) have only a topside.
"""
import numpy as np
from scipy.special import gammaln

from .curves import resample_arclength


def sigma(n, m):
    return np.exp(gammaln(1 + 1 / n) + gammaln(1 + 1 / m) - gammaln(1 + 1 / n + 1 / m))


def solve_m(n, sig, m_max=400.0):
    """Vectorised bisection (in log m) for sigma(n, m) = sig with m in [1, m_max]."""
    n = np.asarray(n, float)
    sig = np.asarray(sig, float)
    lo = np.zeros_like(sig)
    hi = np.full_like(sig, np.log(m_max))
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        f = sigma(n, np.exp(mid)) - sig
        lo = np.where(f < 0, mid, lo)
        hi = np.where(f < 0, hi, mid)
    return np.exp(0.5 * (lo + hi))


def quadrant_shape(n, sig):
    """(n, m) realising quadrant fullness sig; n is lowered when sig is below sigma(n, 1) = n/(n+1)."""
    sig = np.clip(sig, 0.02, 0.9995)
    n_eff = np.where(sig < n / (n + 1.0), sig / (1.0 - sig), n)
    m = solve_m(n_eff, sig)
    return n_eff, m


def _bezier(P0, P1, P2, P3, k):
    t = np.linspace(0, 1, k)[:, None]
    return ((1 - t) ** 3) * P0 + 3 * ((1 - t) ** 2) * t * P1 + 3 * (1 - t) * t * t * P2 + t ** 3 * P3


def section_polyline(st, T, k=160):
    """Dense half-section polyline for one station dictionary `st` (see hull.HullForm.stations)."""
    z0, b, zd, yd = st['z0'], st['b'], st['zd'], st['yd']
    flare = np.radians(st['flare'])
    t3 = np.array([np.sin(flare), np.cos(flare)])
    if z0 >= T - 1e-9 or b <= 1e-9:
        P0 = np.array([0.0, min(z0, zd)])
        P3 = np.array([yd, zd])
        L = np.linalg.norm(P3 - P0)
        if L < 1e-9:
            return np.repeat(P0[None], 2, axis=0)
        ang = np.radians(st.get('stem_angle', 50.0))
        t0 = np.array([np.sin(ang), np.cos(ang)])
        return _bezier(P0, P0 + 0.4 * L * t0, P3 - 0.4 * L * t3, P3, k)
    yf, zb, zs, n, m = st['yf'], st['zb'], st['zs'], st['n'], st['m']
    tp = np.tan(np.radians(st.get('phi', 0.0)))
    r = st.get('rk', 0.0)
    parts = []
    if yf > 1e-9:
        parts.append(np.c_[np.linspace(0, yf, 12), np.linspace(z0, zb, 12)])
    if r > 1e-9:
        th = np.linspace(-np.pi / 2, 0, 16)
        parts.append(np.c_[yf + r * np.cos(th), zb + r + r * np.sin(th)])
    yq, zq = yf + r, zb + r
    s = np.linspace(1, 0, k) ** 1.0
    # cluster near both ends of the quadrant
    s = 0.5 - 0.5 * np.cos(np.pi * s)
    q = np.clip(1 - s ** m, 0, 1) ** (1 / n)
    # superellipse quadrant in the oblique frame: horizontal at the bottom, along the waterline
    # flare direction (tan phi, 1) at the top; corner C = (b - (T - zq) tan phi, zq)
    cy = b - (T - zq) * tp
    a = cy - yq
    parts.append(np.c_[cy - a * (1 - q) + (zs - zq) * (1 - s) * tp, zq + (zs - zq) * (1 - s)])
    e2 = np.array([tp, 1.0]) / np.hypot(tp, 1.0)
    if zs < T - 1e-9:
        parts.append(np.c_[np.linspace(b - (T - zs) * tp, b, 8), np.linspace(zs, T, 8)])
        t0 = e2
    else:
        # quadrant reaches the waterline: tangent from the end of the quadrant
        t0 = parts[-1][-1] - parts[-1][-3]
        t0 = t0 / max(np.linalg.norm(t0), 1e-12)
    P0 = np.array([b, T])
    P3 = np.array([yd, zd])
    L = np.linalg.norm(P3 - P0)
    if L > 1e-9 and zd > T:
        parts.append(_bezier(P0, P0 + 0.38 * L * t0, P3 - 0.38 * L * t3, P3, 60))
    P = np.vstack(parts)
    keep = np.r_[True, np.linalg.norm(np.diff(P, axis=0), axis=1) > 1e-12]
    return P[keep]


def section_points(st, T, nm):
    return resample_arclength(section_polyline(st, T), nm)
