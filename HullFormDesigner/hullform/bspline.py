"""Kernel-neutral cubic B-spline interpolation (Piegl & Tiller, The NURBS Book, ch. 9).

Chord-length parameters averaged over the other direction, averaged knot vectors, global
interpolation solved with sparse collocation matrices. Degenerate rows (a collapsed stem or nose)
are allowed: they simply produce coincident poles.
"""
import numpy as np
from scipy.interpolate import BSpline


def averaged_knots(t, p=3):
    n = len(t)
    inner = [np.mean(t[j:j + p]) for j in range(1, n - p)]
    return np.r_[[0.0] * (p + 1), inner, [1.0] * (p + 1)]


def chord_params(Q, axis=0):
    """Average normalised chord-length parameters of grid Q (nu, nv, 3) along `axis`."""
    Qa = np.moveaxis(Q, axis, 0)
    d = np.linalg.norm(np.diff(Qa, axis=0), axis=-1)          # (n-1, m)
    tot = d.sum(0)
    ok = tot > 1e-12 * max(tot.max(), 1e-300)
    if not ok.any():
        return np.linspace(0, 1, Qa.shape[0])
    t = np.cumsum(np.r_[np.zeros((1, ok.sum())), d[:, ok] / tot[ok]], axis=0)
    t = t.mean(1)
    t[0], t[-1] = 0.0, 1.0
    # guard against coincident parameters
    for k in range(1, len(t)):
        if t[k] <= t[k - 1]:
            t[k] = t[k - 1] + 1e-9
    return t / t[-1]


def _solve(t, U, P, p=3):
    A = BSpline.design_matrix(np.clip(t, 0, 1 - 1e-15), U, p).toarray()
    A[-1, :] = 0.0
    A[-1, -1] = 1.0
    shp = P.shape
    X = np.linalg.solve(A, P.reshape(shp[0], -1))
    return X.reshape(shp)


def interp_surface(Q, p=3):
    """Poles, knots and parameters of the bicubic surface interpolating Q (nu, nv, 3)."""
    u = chord_params(Q, 0)
    v = chord_params(Q, 1)
    U, V = averaged_knots(u, p), averaged_knots(v, p)
    R = _solve(u, U, Q, p)                                     # along u for every column
    P = np.moveaxis(_solve(v, V, np.moveaxis(R, 1, 0), p), 0, 1)
    return dict(poles=P, U=U, V=V, u=u, v=v, p=p, q=p)


def interp_curve(Q, p=3):
    Q = np.asarray(Q, float)
    t = chord_params(Q[:, None, :], 0)
    U = averaged_knots(t, p)
    return dict(poles=_solve(t, U, Q, p), U=U, t=t, p=p)


def evaluate(S, u, v):
    """Evaluate a surface dict on parameter arrays u (n,), v (m,) -> (n, m, 3)."""
    Bu = BSpline.design_matrix(np.clip(u, 0, 1 - 1e-12), S['U'], S['p']).toarray()
    Bv = BSpline.design_matrix(np.clip(v, 0, 1 - 1e-12), S['V'], S['q']).toarray()
    return np.einsum('ia,abk,jb->ijk', Bu, S['poles'], Bv)
