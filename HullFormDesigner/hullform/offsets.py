"""Offset tables (outer half-breadth y(x, z)) of a design, fast and directly from the section data.

Used for comparison with a reference hull, for fitting, and for the offset-table export.
"""
import numpy as np


def _section_hb(P, zq):
    """Half-breadth of a half-section polyline P (k, 2) [y, z] at heights zq (0 outside)."""
    z = np.maximum.accumulate(P[:, 1])
    out = np.interp(zq, z, P[:, 0], left=np.nan, right=np.nan)
    out[(zq < z[0]) | (zq > z[-1])] = np.nan
    return out


def _loop_hb(Lp, zq):
    """Maximum y of a closed loop (k, 2) [y, z] on each horizontal line zq (nan if not crossed)."""
    a = Lp
    b = np.roll(Lp, -1, axis=0)
    za, zb = a[:, 1][:, None], b[:, 1][:, None]
    lo, hi = np.minimum(za, zb), np.maximum(za, zb)
    c = (lo <= zq[None]) & (hi > zq[None])
    t = (zq[None] - za) / np.where(zb != za, zb - za, 1.0)
    y = a[:, 0][:, None] + t * (b[:, 0] - a[:, 0])[:, None]
    y = np.where(c, y, -np.inf)
    m = y.max(0)
    return np.where(np.isfinite(m), m, np.nan)


def _along_x(xs, H, xq):
    """Interpolate a station table H (n_st, nz) to xq; undefined (nan) where the neighbours are."""
    out = np.full((len(xq), H.shape[1]), np.nan)
    i = np.clip(np.searchsorted(xs, xq) - 1, 0, len(xs) - 2)
    t = (xq - xs[i]) / np.maximum(xs[i + 1] - xs[i], 1e-12)
    inside = (xq >= xs[0]) & (xq <= xs[-1])
    a, b = H[i], H[i + 1]
    v = a + (b - a) * t[:, None]
    v = np.where(np.isnan(a), np.where(t[:, None] > 0.5, b, np.nan), v)
    v = np.where(np.isnan(b), np.where(t[:, None] <= 0.5, a, np.nan), v)
    out[inside] = v[inside]
    return out


def outer_halfbreadth(design, xq, zq):
    """Outer half-breadth of the union of main hull and add-on bodies on the grid (xq, zq)."""
    G = design.grid
    xs = G[:, 0, 0]
    Hm = np.array([_section_hb(G[i, :, 1:], zq) for i in range(len(G))])
    H = _along_x(xs, Hm, xq)
    for body in design.bodies:
        R = body.R
        if R[:, :, 1].max() <= 1e-9:
            continue                        # starboard body; the half-breadth is taken on the port side
        bx = R[:, 0, 0]
        Hb = np.array([_loop_hb(R[i, :, 1:], zq) for i in range(len(R))])
        o = np.argsort(bx)
        Hb = _along_x(bx[o], Hb[o], xq)
        H = np.fmax(H, Hb)
    return np.nan_to_num(H, nan=0.0)


def section_curves(design, x):
    """Curves of the transverse section at x for drawing: the main-hull half section (y >= 0) and
    the cross-section loops of the add-on bodies cut at x (full loops, both sides)."""
    from .sections import section_polyline
    h = design.hull
    out = []
    if h.x_tr <= x <= h.x_stem_deck:
        st = h.stations(np.array([x]))[0]
        out.append(('hull', section_polyline(st, h.T)))
    for b in design.bodies:
        R = b.R
        bx = R[:, 0, 0]
        o = np.argsort(bx)
        bx, Rs = bx[o], R[o]
        if x < bx[0] or x > bx[-1]:
            continue
        i = min(np.searchsorted(bx, x) - 1, len(bx) - 2)
        i = max(i, 0)
        t = (x - bx[i]) / max(bx[i + 1] - bx[i], 1e-12)
        loop = (1 - t) * Rs[i, :, 1:] + t * Rs[i + 1, :, 1:]
        out.append((b.name, np.vstack([loop, loop[:1]])))
    return out
