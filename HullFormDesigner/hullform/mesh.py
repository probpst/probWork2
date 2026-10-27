"""Closed triangle meshes for the preview, STL export without the CAD kernel, and hydrostatics."""
import struct

import numpy as np


class TriMesh(object):
    def __init__(self, V, F, part='hull'):
        self.V = np.asarray(V, float)
        self.F = np.asarray(F, int).reshape(-1, 3)
        self.part = part

    def signed_volume(self):
        a, b, c = (self.V[self.F[:, k]] for k in range(3))
        return float(np.einsum('ij,ij->i', a, np.cross(b, c)).sum() / 6.0)

    def orient_outward(self):
        if self.signed_volume() < 0:
            self.F = self.F[:, ::-1].copy()
        return self

    def area(self):
        a, b, c = (self.V[self.F[:, k]] for k in range(3))
        return float(0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1).sum())

    def welded(self, tol=1e-9):
        ext = max(np.ptp(self.V, axis=0).max(), 1e-12)
        key = np.round(self.V / (tol * ext)).astype(np.int64)
        _, idx, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
        F = inv.reshape(-1)[self.F]
        ok = (F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])
        F = F[ok]
        # cancel coincident triangle pairs of opposite orientation (zero-thickness slivers)
        key = np.sort(F, axis=1)
        _, inv2, cnt = np.unique(key, axis=0, return_inverse=True, return_counts=True)
        F = F[cnt[inv2.reshape(-1)] == 1]
        return TriMesh(self.V[idx], F, self.part)

    def edge_report(self):
        m = self.welded()
        E = np.sort(np.r_[m.F[:, [0, 1]], m.F[:, [1, 2]], m.F[:, [2, 0]]], axis=1)
        _, cnt = np.unique(E, axis=0, return_counts=True)
        return dict(open_edges=int((cnt == 1).sum()), nonmanifold_edges=int((cnt > 2).sum()),
                    triangles=len(m.F))

    def transformed(self, M):
        V = self.V @ M[:3, :3].T + M[:3, 3]
        F = self.F if np.linalg.det(M[:3, :3]) > 0 else self.F[:, ::-1]
        return TriMesh(V, F, self.part)


def merge(meshes):
    V, F, n = [], [], 0
    for m in meshes:
        V.append(m.V)
        F.append(m.F + n)
        n += len(m.V)
    return TriMesh(np.vstack(V), np.vstack(F))


def grid_mesh(G, close_u0=False, close_u1=False):
    """Triangles of a structured grid G (nu, nv, 3) (quads split along the shorter diagonal)."""
    nu, nv = G.shape[:2]
    idx = np.arange(nu * nv).reshape(nu, nv)
    a, b = idx[:-1, :-1].ravel(), idx[1:, :-1].ravel()
    c, d = idx[1:, 1:].ravel(), idx[:-1, 1:].ravel()
    V = G.reshape(-1, 3)
    d1 = np.linalg.norm(V[a] - V[c], axis=1)
    d2 = np.linalg.norm(V[b] - V[d], axis=1)
    s = d1 <= d2
    F = np.r_[np.c_[a[s], b[s], c[s]], np.c_[a[s], c[s], d[s]],
              np.c_[a[~s], b[~s], d[~s]], np.c_[b[~s], c[~s], d[~s]]]
    return V, F


def hull_mesh(G):
    """Closed mesh of the main hull from the half grid G (stations x girth, y >= 0): starboard and
    port shells, flat deck strip between the deck edges and the transom strip."""
    Gp = G
    Gs = G * np.array([1, -1, 1])
    Vp, Fp = grid_mesh(Gp)
    Vs, Fs = grid_mesh(Gs)
    ns, nm = G.shape[:2]
    off = len(Vp)
    V = np.vstack([Vp, Vs])
    F = [Fp, Fs[:, ::-1] + off]
    idx_p = np.arange(ns * nm).reshape(ns, nm)
    idx_s = idx_p + off
    # deck: strip between the port and starboard deck edges (column nm-1)
    a, b = idx_p[:-1, -1], idx_p[1:, -1]
    c, d = idx_s[1:, -1], idx_s[:-1, -1]
    F.append(np.c_[a, b, c])
    F.append(np.c_[a, c, d])
    # transom: strip between the port and starboard first stations
    a, b = idx_p[0, :-1], idx_p[0, 1:]
    c, d = idx_s[0, 1:], idx_s[0, :-1]
    F.append(np.c_[a, b, c])
    F.append(np.c_[a, c, d])
    m = TriMesh(V, np.vstack(F), 'hull').welded()
    return m.orient_outward()


def write_stl(path, meshes, binary=True, name='hull'):
    if isinstance(meshes, TriMesh):
        meshes = [meshes]
    tris = []
    for m in meshes:
        tris.append(m.V[m.F])
    P = np.concatenate(tris) if tris else np.zeros((0, 3, 3))
    N = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    nn = np.linalg.norm(N, axis=1)
    N = N / np.where(nn > 0, nn, 1)[:, None]
    if binary:
        with open(path, 'wb') as f:
            f.write(('Parametric Hull Form Designer ' + name)[:80].ljust(80).encode('ascii', 'replace'))
            f.write(struct.pack('<I', len(P)))
            data = np.zeros(len(P), dtype=[('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')])
            data['n'] = N
            data['v'] = P
            f.write(data.tobytes())
    else:
        with open(path, 'w') as f:
            f.write('solid %s\n' % name)
            for n, t in zip(N, P):
                f.write(' facet normal %e %e %e\n  outer loop\n' % tuple(n))
                for v in t:
                    f.write('   vertex %e %e %e\n' % tuple(v))
                f.write('  endloop\n endfacet\n')
            f.write('endsolid %s\n' % name)


def read_stl(path):
    with open(path, 'rb') as f:
        head = f.read(84)
        rest = f.read()
    n = struct.unpack('<I', head[80:84])[0]
    if len(rest) == n * 50:
        d = np.frombuffer(rest, dtype=[('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')])
        P = d['v'].astype(float)
    else:
        txt = (head + rest).decode('ascii', 'replace').split()
        P = []
        for i, t in enumerate(txt):
            if t == 'vertex':
                P.append([float(txt[i + 1]), float(txt[i + 2]), float(txt[i + 3])])
        P = np.array(P).reshape(-1, 3, 3)
    V = P.reshape(-1, 3)
    return TriMesh(V, np.arange(len(V)).reshape(-1, 3)).welded()
