"""3-D view (pyqtgraph OpenGL) with CPU lighting.

Lighting is computed on the CPU and stored as vertex colours (no custom GLSL shader), so the view
works with every OpenGL driver, remote desktop and software OpenGL. The light follows the camera.
"""
import numpy as np
import pyqtgraph.opengl as gl
from PySide6.QtGui import QVector3D

PART_COLOURS = {'hull': (0.74, 0.30, 0.24), 'bulb': (0.36, 0.50, 0.58), 'skeg_p': (0.36, 0.50, 0.58),
                'skeg_s': (0.36, 0.50, 0.58), 'boss': (0.55, 0.55, 0.50), 'boss_p': (0.55, 0.55, 0.50),
                'boss_s': (0.55, 0.55, 0.50)}


def vertex_normals(V, F, crease_deg=35.0):
    """Split vertices at creases so sharp edges (deck, transom) shade correctly."""
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    fn = np.cross(b - a, c - a)
    fl = np.linalg.norm(fn, axis=1)
    fn = fn / np.where(fl > 0, fl, 1)[:, None]
    vn = np.zeros_like(V)
    for k in range(3):
        np.add.at(vn, F[:, k], fn * fl[:, None])
    vn /= np.maximum(np.linalg.norm(vn, axis=1), 1e-12)[:, None]
    cosc = np.cos(np.radians(crease_deg))
    Vo, No, Fo = [], [], np.zeros_like(F)
    for k in range(3):
        sharp = np.einsum('ij,ij->i', vn[F[:, k]], fn) < cosc
        Fo[:, k] = F[:, k]
        idx = np.where(sharp)[0]
        if len(idx):
            Fo[idx, k] = len(V) + len(Vo) + np.arange(len(idx))
            Vo.append(V[F[idx, k]])
            No.append(fn[idx])
    if Vo:
        V = np.vstack([V] + Vo)
        vn = np.vstack([vn] + No)
    return V, Fo, vn


class HullView(gl.GLViewWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackgroundColor('#E3E8EA')
        self.opts['fov'] = 30
        self.items3d = []
        self.lit = []          # (item, V, N, base colour)
        self.grid_item = None
        self.extent = 100.0
        self.center = np.zeros(3)

    def clear_model(self):
        for it in self.items3d:
            self.removeItem(it)
        self.items3d, self.lit = [], []

    def light_dir(self):
        az, el = np.radians(self.opts['azimuth']), np.radians(self.opts['elevation'])
        d = np.array([np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), np.sin(el)])
        up = np.array([0, 0, 1.0])
        right = np.cross(d, up)
        right /= max(np.linalg.norm(right), 1e-9)
        L = d + 0.45 * up - 0.3 * right
        return L / np.linalg.norm(L)

    def _colours(self, N, base):
        L = self.light_dir()
        nd = np.abs(N @ L)
        c = np.asarray(base)[None, :] * (0.36 + 0.64 * nd[:, None]) + 0.18 * (nd ** 24)[:, None]
        return np.c_[np.clip(c, 0, 1), np.ones(len(N))]

    def relight(self):
        for it, V, N, base in self.lit:
            it.setMeshData(vertexes=V, faces=it._F, vertexColors=self._colours(N, base))

    def add_mesh(self, mesh, colour=None, edges=False, alpha=1.0):
        V, F, N = vertex_normals(mesh.V, mesh.F)
        base = colour or PART_COLOURS.get(mesh.part, (0.7, 0.35, 0.28))
        it = gl.GLMeshItem(vertexes=V, faces=F, vertexColors=self._colours(N, base), smooth=True,
                           shader=None, drawEdges=edges, edgeColor=(0.2, 0.2, 0.2, 0.35), glOptions='opaque')
        it._F = F
        self.addItem(it)
        self.items3d.append(it)
        self.lit.append((it, V, N, base))

    def add_waterline(self, x0, x1, B, T):
        V = np.array([[x0, -B, T], [x1, -B, T], [x1, B, T], [x0, B, T]], float)
        it = gl.GLMeshItem(vertexes=V, faces=np.array([[0, 1, 2], [0, 2, 3]]), color=(0.35, 0.6, 0.9, 0.25),
                           smooth=False, shader=None, glOptions='translucent')
        self.addItem(it)
        self.items3d.append(it)
        ln = gl.GLLinePlotItem(pos=np.vstack([V, V[:1]]), color=(0.2, 0.4, 0.8, 1), width=1.5)
        self.addItem(ln)
        self.items3d.append(ln)

    def frame(self, lo, hi):
        self.center = 0.5 * (lo + hi)
        self.extent = float(np.max(hi - lo))
        self.opts['center'] = QVector3D(*self.center)
        self.opts['distance'] = 2.6 * self.extent
        if self.grid_item is None:
            self.grid_item = gl.GLGridItem()
            self.grid_item.setColor((150, 160, 165, 120))
            self.addItem(self.grid_item)
        s = 10 ** np.floor(np.log10(max(self.extent / 10, 1e-3)))
        self.grid_item.setSize(self.extent * 1.4, self.extent * 0.6)
        self.grid_item.setSpacing(s, s)
        self.grid_item.resetTransform()
        self.grid_item.translate(self.center[0], self.center[1], lo[2] - 0.02 * self.extent)

    def preset_view(self, name):
        az, el = {'Iso': (-125, 22), 'Side': (-90, 0), 'Bow': (0, 2), 'Stern': (180, 2), 'Top': (-90, 89),
                  'Bottom': (-90, -89)}[name]
        self.setCameraPosition(azimuth=az, elevation=el)
        self.relight()

    def mouseReleaseEvent(self, ev):
        super().mouseReleaseEvent(ev)
        self.relight()

    def wheelEvent(self, ev):
        super().wheelEvent(ev)
