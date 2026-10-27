"""Reference hulls: read an IGES or STL hull, bring it into the design frame, and measure offsets and
hydrostatics.

Reference files are often open half hulls (no centreplane, deck or transom faces), so the cuts here
use crossing parity of the mirrored section instead of the oriented counting in hydro.py.
"""
import json

import numpy as np

from .mesh import TriMesh, read_stl


def load_iges_mesh(path, rel_defl=2e-4):
    from OCP.IGESControl import IGESControl_Reader
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopoDS import TopoDS
    from OCP.BRep import BRep_Tool
    from OCP.TopLoc import TopLoc_Location
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    r = IGESControl_Reader()
    if r.ReadFile(path) != 1:
        raise IOError('cannot read IGES file %s' % path)
    r.TransferRoots()
    s = r.OneShape()
    b = Bnd_Box()
    BRepBndLib.Add_s(s, b)
    x0, y0, z0, x1, y1, z1 = b.Get()
    BRepMesh_IncrementalMesh(s, max(x1 - x0, y1 - y0, z1 - z0) * rel_defl, False, 0.2, True)
    V, F, n = [], [], 0
    e = TopExp_Explorer(s, TopAbs_FACE)
    while e.More():
        f = TopoDS.Face_s(e.Current())
        loc = TopLoc_Location()
        t = BRep_Tool.Triangulation_s(f, loc)
        if t is not None:
            tr = loc.Transformation()
            for i in range(1, t.NbNodes() + 1):
                p = t.Node(i).Transformed(tr)
                V.append((p.X(), p.Y(), p.Z()))
            for i in range(1, t.NbTriangles() + 1):
                a, b_, c = t.Triangle(i).Get()
                F.append((a - 1 + n, b_ - 1 + n, c - 1 + n))
            n += t.NbNodes()
        e.Next()
    return TriMesh(np.array(V), np.array(F))


def load(path, transform=None):
    """Mesh of a reference file in the design frame. `transform` = dict(scale, flip_x, flip_z,
    x_shift, z_shift, model_scale) applied as: V * scale, optional sign flips, + shifts, * model_scale."""
    m = read_stl(path) if path.lower().endswith('.stl') else load_iges_mesh(path)
    V = m.V.copy()
    t = dict(scale=1.0, flip_x=False, flip_z=False, x_shift=0.0, z_shift=0.0, model_scale=1.0)
    t.update(transform or {})
    V *= t['scale']
    if t['flip_x']:
        V[:, 0] = -V[:, 0]
    if t['flip_z']:
        V[:, 2] = -V[:, 2]
    V[:, 0] += t['x_shift']
    V[:, 2] += t['z_shift']
    V *= t['model_scale']
    F = m.F[:, ::-1] if t['flip_x'] != t['flip_z'] else m.F
    return TriMesh(V, F, 'reference')


def _segments(V, F, x):
    P = V[F]
    d = P[:, :, 0] - x
    m = (d.min(1) < 0) & (d.max(1) > 0)
    P, d = P[m], d[m]
    out = np.zeros((len(P), 2, 2))
    cnt = np.zeros(len(P), int)
    for e0, e1 in ((0, 1), (1, 2), (2, 0)):
        a, b = d[:, e0], d[:, e1]
        c = (a * b) < 0
        t = a[c] / (a[c] - b[c])
        q = P[c, e0, 1:] + (P[c, e1, 1:] - P[c, e0, 1:]) * t[:, None]
        idx = np.where(c)[0]
        out[idx, np.minimum(cnt[idx], 1)] = q
        cnt[idx] += 1
    return out[cnt == 2]


def _parity_intervals(segs, z, mirror):
    S = segs
    if mirror:
        M = S.copy()
        M[:, :, 0] *= -1
        S = np.concatenate([S, M])
    a, b = S[:, 0], S[:, 1]
    lo, hi = np.minimum(a[:, 1], b[:, 1]), np.maximum(a[:, 1], b[:, 1])
    c = (lo <= z) & (hi > z)
    if not c.any():
        return np.zeros((0, 2))
    t = (z - a[c, 1]) / (b[c, 1] - a[c, 1])
    y = np.sort(a[c, 0] + t * (b[c, 0] - a[c, 0]))
    keep = []
    for v in y:
        if keep and abs(v - keep[-1]) < 1e-6 * (1 + abs(v)):
            keep.pop()
        else:
            keep.append(v)
    y = np.array(keep)
    if len(y) % 2:
        y = np.array([y[0], y[-1]])
    return y.reshape(-1, 2)


def offsets(mesh, xq, zq):
    """Outer half-breadth H and total width W of a reference mesh on (xq, zq)."""
    V, F = mesh.V, mesh.F
    mirror = V[:, 1].min() > -1e-3 * np.ptp(V[:, 1])
    H = np.zeros((len(xq), len(zq)))
    W = np.zeros_like(H)
    for i, x in enumerate(xq):
        sg = _segments(V, F, x)
        if not len(sg):
            continue
        for j, z in enumerate(zq):
            iv = _parity_intervals(sg, z, mirror)
            if len(iv):
                H[i, j] = iv[:, 1].max()
                W[i, j] = (iv[:, 1] - iv[:, 0]).sum()
    return H, W


def standard_grid(L, T, D, x0=-0.06, x1=1.06, nx=225, nz=121, zlo=None):
    xq = np.linspace(x0, x1, nx) * L
    zq = np.linspace(zlo if zlo is not None else 0.0, D, nz)
    zq[0] += 1e-4 * T
    zq[-1] -= 1e-4 * T
    return xq, zq


class Reference(object):
    """Offsets of a reference hull stored in an .npz file (see tools/make_reference.py)."""

    def __init__(self, path):
        o = np.load(path)
        self.meta = json.loads(str(o['meta']))
        self.x, self.z, self.H, self.W = o['x'], o['z'], o['H'], o['W']
        self.name = self.meta['name']

    def summary(self):
        return self.meta.get('hydro', {})
