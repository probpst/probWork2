"""Hydrostatics and offset tables of a union of closed, outward-oriented triangle meshes.

Each body is cut by transverse planes x = const. On every cut the section loops are oriented by the
outward normals, so a crossing of a horizontal line z = const counts +1 (entering, scanning +y) or -1
(leaving). The running sum over all bodies is the number of bodies containing the point: where it is
positive the point is inside the union. This gives exact union widths on each line without Boolean
operations, so overlapping add-on bodies (bulb, skegs, boss) are never counted twice.
"""
import numpy as np


def _cut(V, F, x):
    """Oriented section segments of mesh (V, F) with the plane x = const: array (k, 2, 2) of (y, z)."""
    P = V[F]
    d = P[:, :, 0] - x
    m = (d.min(1) < 0) & (d.max(1) > 0)
    if not m.any():
        return np.zeros((0, 2, 2))
    P, d = P[m], d[m]
    n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    pts = np.zeros((len(P), 2, 2))
    cnt = np.zeros(len(P), int)
    for e0, e1 in ((0, 1), (1, 2), (2, 0)):
        a, b = d[:, e0], d[:, e1]
        c = (a * b) < 0
        t = a[c] / (a[c] - b[c])
        q = P[c, e0, 1:] + (P[c, e1, 1:] - P[c, e0, 1:]) * t[:, None]
        idx = np.where(c)[0]
        k = np.minimum(cnt[idx], 1)
        pts[idx, k] = q
        cnt[idx] += 1
    ok = cnt == 2
    pts, n = pts[ok], n[ok]
    # direction of the section curve: e_x x n (counter-clockwise in (y, z) for outward normals)
    t = np.c_[-n[:, 2], n[:, 1]]
    s = np.einsum('ij,ij->i', pts[:, 1] - pts[:, 0], t)
    sw = s < 0
    pts[sw] = pts[sw, ::-1]
    return pts


def line_widths(segs, Z):
    """For each z in Z: (total inside width, max inside y, inside intervals list) of the union."""
    if len(segs) == 0:
        return np.zeros(len(Z)), np.full(len(Z), np.nan), [[] for _ in Z]
    a, b = segs[:, 0], segs[:, 1]
    za, zb = a[:, 1], b[:, 1]
    lo, hi = np.minimum(za, zb), np.maximum(za, zb)
    zi, si = [], []
    ys, sg = [], []
    for k, z in enumerate(Z):
        c = (lo <= z) & (hi > z)
        if not c.any():
            continue
        t = (z - za[c]) / (zb[c] - za[c])
        y = a[c, 0] + t * (b[c, 0] - a[c, 0])
        s = np.where(zb[c] > za[c], -1, 1)
        ys.append(y)
        sg.append(s)
        zi.append(np.full(len(y), k))
    W = np.zeros(len(Z))
    H = np.full(len(Z), np.nan)
    IV = [[] for _ in Z]
    if not ys:
        return W, H, IV
    y = np.concatenate(ys)
    s = np.concatenate(sg)
    zi = np.concatenate(zi)
    o = np.lexsort((y, zi))
    y, s, zi = y[o], s[o], zi[o]
    c = np.cumsum(s)
    same = zi[1:] == zi[:-1]
    inside = (c[:-1] > 0) & same
    w = np.where(inside, np.diff(y), 0.0)
    np.add.at(W, zi[:-1], w)
    # interval ends (y where the count drops to zero)
    for k in np.unique(zi):
        m = zi == k
        yk, ck = y[m], c[m]
        ivs, start = [], None
        prev = 0
        for yy, cc in zip(yk, ck):
            if prev <= 0 < cc:
                start = yy
            elif prev > 0 >= cc and start is not None:
                ivs.append((start, yy))
            prev = cc
        IV[k] = ivs
        if ivs:
            H[k] = max(e for _, e in ivs)
    return W, H, IV


def sections(meshes, xs, Z):
    """Union widths W[i, k] and outer half-breadths H[i, k] on the (x, z) grid."""
    W = np.zeros((len(xs), len(Z)))
    H = np.full((len(xs), len(Z)), np.nan)
    for i, x in enumerate(xs):
        segs = [_cut(m.V, m.F, x) for m in meshes]
        segs = np.concatenate([s for s in segs if len(s)] or [np.zeros((0, 2, 2))])
        W[i], H[i], _ = line_widths(segs, Z)
    return W, H


def clip_below(P, z0):
    """Triangles P (n, 3, 3) clipped to z <= z0 (vectorised); returns triangles (m, 3, 3)."""
    z = P[:, :, 2]
    below = z <= z0
    nb = below.sum(1)
    out = [P[nb == 3]]
    for k in (1, 2):
        Q = P[nb == k]
        if not len(Q):
            continue
        bq = Q[:, :, 2] <= z0
        # rotate each triangle so that vertex 0 is the odd one (below for k=1, above for k=2)
        odd = bq if k == 1 else ~bq
        r = np.argmax(odd, axis=1)
        idx = (r[:, None] + np.arange(3)[None]) % 3
        Q = np.take_along_axis(Q, idx[:, :, None], axis=1)
        a, b, c = Q[:, 0], Q[:, 1], Q[:, 2]
        tab = ((z0 - a[:, 2]) / (b[:, 2] - a[:, 2]))[:, None]
        tac = ((z0 - a[:, 2]) / (c[:, 2] - a[:, 2]))[:, None]
        pab, pac = a + tab * (b - a), a + tac * (c - a)
        if k == 1:
            out.append(np.stack([a, pab, pac], 1))
        else:
            out.append(np.stack([pab, b, c], 1))
            out.append(np.stack([pab, c, pac], 1))
    return np.concatenate(out) if out else np.zeros((0, 3, 3))


def clipped_volume(mesh, z0):
    """Exact volume and first moments of a closed outward mesh below z = z0 (divergence theorem with
    the apex on the cutting plane, so the missing cap contributes nothing)."""
    Pc = clip_below(mesh.V[mesh.F], z0)
    o = np.array([0.0, 0.0, z0])
    a, b, c = Pc[:, 0] - o, Pc[:, 1] - o, Pc[:, 2] - o
    v = np.einsum('ij,ij->i', a, np.cross(b, c)) / 6.0
    cen = (Pc[:, 0] + Pc[:, 1] + Pc[:, 2] + o) / 4.0
    return float(v.sum()), (v[:, None] * cen).sum(0)


def hydrostatics(meshes, T, L, B, nx=241, nz=160, x_range=None):
    """Displacement volume, centres, coefficients and waterplane properties at draught T.

    Volume and centroid are exact for the meshes (divergence theorem on the clipped meshes); the
    overlap of the bodies is removed by fine slicing over its x range only. The sectional area curve
    and the waterplane come from slicing."""
    V = np.vstack([m.V for m in meshes])
    x0, x1 = (V[:, 0].min(), V[:, 0].max()) if x_range is None else x_range
    zmin = V[:, 2].min()
    vol, mom = 0.0, np.zeros(3)
    for m in meshes:
        v, mo = clipped_volume(m, T)
        vol += v
        mom += mo
    # overlap of the bodies with each other (main hull first)
    if len(meshes) > 1:
        lo = min(m.V[:, 0].min() for m in meshes[1:])
        hi = max(m.V[:, 0].max() for m in meshes[1:])
        nzo = 120
        dz = (T - zmin) / nzo
        Z = zmin + (np.arange(nzo) + 0.5) * dz
        xo = np.linspace(lo, hi, 161)
        ov = np.zeros(len(xo))
        ovz = np.zeros(len(xo))
        for i, x in enumerate(xo):
            segs = [_cut(m.V, m.F, x) for m in meshes]
            Wsum = sum(line_widths(sg, Z)[0] for sg in segs if len(sg))
            nonempty = [sg for sg in segs if len(sg)]
            if len(nonempty) < 2:
                continue
            Wu = line_widths(np.concatenate(nonempty), Z)[0]
            d = np.maximum(Wsum - Wu, 0.0)
            ov[i] = d.sum() * dz
            ovz[i] = (d * Z).sum() * dz
        vo = np.trapezoid(ov, xo)
        vol -= vo
        mom -= np.array([np.trapezoid(ov * xo, xo), 0.0, np.trapezoid(ovz, xo)])
    res = dict(T=T, volume=float(vol))
    if vol <= 0:
        return res
    res['LCB_x'] = float(mom[0] / vol)
    res['VCB'] = float(mom[2] / vol)
    # sectional area curve and waterplane by slicing
    eps = 1e-6 * (x1 - x0)
    xs = np.linspace(x0 + eps, x1 - eps, nx)
    dz = (T - zmin) / nz
    Z = zmin + (np.arange(nz) + 0.5) * dz
    W, H = sections(meshes, xs, np.r_[Z, T - 1e-7 * T])
    Wz, Wwl = W[:, :-1], W[:, -1]
    A = Wz.sum(1) * dz
    Awp = np.trapezoid(Wwl, xs)
    res['Awp'] = float(Awp)
    res['LCF_x'] = float(np.trapezoid(Wwl * xs, xs) / Awp) if Awp > 0 else float('nan')
    # transverse inertia of the waterplane (symmetric): integral of (2/3) y^3 over the half breadth
    hb = np.nan_to_num(H[:, -1])
    res['IT'] = float(np.trapezoid(2.0 / 3.0 * hb ** 3, xs))
    res['BMt'] = res['IT'] / vol
    res['KMt'] = res['VCB'] + res['BMt']
    i = int(np.argmax(A))
    res['Amax'] = float(A[i])
    res['x_Amax'] = float(xs[i])
    imid = int(np.argmin(np.abs(xs - L / 2)))
    res['A_mid'] = float(np.interp(L / 2, xs, A))
    wet = np.where(Wwl > 0)[0]
    if len(wet):
        res['x_wl_aft'] = float(xs[wet[0]])
        res['x_wl_fwd'] = float(xs[wet[-1]])
        res['Lwl'] = res['x_wl_fwd'] - res['x_wl_aft']
        res['Bwl'] = float(Wwl.max())
    res['Cb'] = vol / (L * B * T)
    res['Cm'] = res['A_mid'] / (B * T)
    res['Cp'] = res['Cb'] / res['Cm']
    res['Cwp'] = Awp / (L * B)
    res['LCB_pct'] = (res['LCB_x'] - L / 2) / L * 100
    res['LCF_pct'] = (res['LCF_x'] - L / 2) / L * 100
    res['SAC'] = np.c_[xs, A]
    return res


def _clip_tri_area(P, z0):
    """Area of the parts of triangles P (n, 3, 3) below z = z0."""
    z = P[:, :, 2]
    below = z < z0
    nb = below.sum(1)
    area = np.zeros(len(P))
    full = nb == 3
    area[full] = 0.5 * np.linalg.norm(np.cross(P[full, 1] - P[full, 0], P[full, 2] - P[full, 0]), axis=1)
    for k in (1, 2):
        sel = np.where(nb == k)[0]
        for i in sel:
            pts = []
            tri = P[i]
            for j in range(3):
                a, b = tri[j], tri[(j + 1) % 3]
                if a[2] < z0:
                    pts.append(a)
                if (a[2] < z0) != (b[2] < z0):
                    t = (z0 - a[2]) / (b[2] - a[2])
                    pts.append(a + t * (b - a))
            pts = np.array(pts)
            s = 0.0
            for j in range(1, len(pts) - 1):
                s += 0.5 * np.linalg.norm(np.cross(pts[j] - pts[0], pts[j + 1] - pts[0]))
            area[i] = s
    return area


def points_inside(mesh, Q, chunk=512):
    """Inside test of points Q (n, 3) for a closed mesh (ray parity along +y). Points are processed
    in x-sorted chunks and only triangles overlapping a chunk's (x, z) box are tested."""
    V, F = mesh.V, mesh.F
    lo, hi = V.min(0), V.max(0)
    res = np.zeros(len(Q), bool)
    cand = np.where(np.all((Q >= lo) & (Q <= hi), axis=1))[0]
    if len(cand) == 0:
        return res
    cand = cand[np.argsort(Q[cand, 0])]
    A, Bv, C = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    txlo = np.minimum(np.minimum(A[:, 0], Bv[:, 0]), C[:, 0])
    txhi = np.maximum(np.maximum(A[:, 0], Bv[:, 0]), C[:, 0])
    tzlo = np.minimum(np.minimum(A[:, 2], Bv[:, 2]), C[:, 2])
    tzhi = np.maximum(np.maximum(A[:, 2], Bv[:, 2]), C[:, 2])
    d = np.array([1e-4, 1.0, 2.3e-4])
    d /= np.linalg.norm(d)
    for s in range(0, len(cand), chunk):
        idx = cand[s:s + chunk]
        q = Q[idx]
        sel = ((txhi >= q[:, 0].min()) & (txlo <= q[:, 0].max()) &
               (tzhi >= q[:, 2].min()) & (tzlo <= q[:, 2].max()))
        if not sel.any():
            continue
        a, e1, e2 = A[sel], Bv[sel] - A[sel], C[sel] - A[sel]
        h = np.cross(d, e2)
        det = np.einsum('ij,ij->i', e1, h)
        ok = np.abs(det) > 1e-14
        a, e1, e2, h, det = a[ok], e1[ok], e2[ok], h[ok], det[ok]
        inv = 1.0 / det
        sv = q[:, None, :] - a[None]
        u = np.einsum('nij,ij->ni', sv, h) * inv
        qv = np.cross(sv, e1[None])
        v = np.einsum('k,nik->ni', d, qv) * inv
        t = np.einsum('nik,ik->ni', qv, e2) * inv
        hit = (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 0)
        res[idx] = (hit.sum(1) % 2) == 1
    return res


def wetted_surface(meshes, T):
    """Wetted surface below z = T of the union: triangles hidden inside another body are excluded."""
    total = 0.0
    parts = {}
    for i, m in enumerate(meshes):
        P = m.V[m.F]
        keep = np.ones(len(P), bool)
        cen = P.mean(1)
        for j, o in enumerate(meshes):
            if j != i:
                keep &= ~points_inside(o, cen)
        a = _clip_tri_area(P[keep], T).sum()
        parts[m.part] = parts.get(m.part, 0.0) + a
        total += a
    return total, parts
