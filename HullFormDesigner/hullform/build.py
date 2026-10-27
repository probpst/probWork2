"""A complete design: main hull + add-on bodies, preview meshes and hydrostatics.

`Design(p)` builds the geometry. With `correct=True` the main-hull targets are iterated so that the
complete hull (union with the bulb, skegs and boss) has the requested Cb and LCB.
"""
import numpy as np

from .hull import HullForm
from . import appendages, hydro
from .mesh import hull_mesh


class Design(object):
    def __init__(self, p, correct=False, iterations=3, cb_main=None, lcb_main=None):
        self.p = p
        self.cb_main = p['form']['Cb'] if cb_main is None else cb_main
        self.lcb_main = p['form']['LCB'] if lcb_main is None else lcb_main
        self._build()
        self.correction = []
        if correct:
            for _ in range(iterations):
                h = self.hydrostatics(nx=161, nz=100)
                dcb = p['form']['Cb'] - h['Cb']
                dlcb = p['form']['LCB'] - h['LCB_pct']
                self.correction.append((h['Cb'], h['LCB_pct']))
                if abs(dcb) < 2e-4 and abs(dlcb) < 0.01:
                    break
                self.cb_main += dcb
                self.lcb_main += dlcb
                self._build()

    def _build(self):
        p = self.p
        self.hull = HullForm(p, self.cb_main, self.lcb_main)
        self.grid, self.stations = self.hull.grid()
        self.bodies = appendages.bodies(p, self.hull)
        self._meshes = None

    @property
    def warnings(self):
        return self.hull.warnings

    def meshes(self):
        if self._meshes is None:
            self._meshes = [hull_mesh(self.grid)] + [b.mesh() for b in self.bodies]
        return self._meshes

    def hydrostatics(self, T=None, nx=241, nz=160):
        h = self.hull
        return hydro.hydrostatics(self.meshes(), T or h.T, h.L, h.B, nx=nx, nz=nz)

    def wetted_surface(self, T=None):
        return hydro.wetted_surface(self.meshes(), T or self.hull.T)
