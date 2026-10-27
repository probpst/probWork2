"""Build the reference offset files references/<name>.npz from the benchmark hull geometry files.

Usage: python tools/make_reference.py <folder with the hull files> [names...]
The geometry files themselves are not stored in the repository (about 48 MB); only their offsets,
hydrostatics and the transforms below.
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from hullform import reference as ref  # noqa: E402

# file, transform into the design frame (x fwd from AP, z up from baseline, m, full scale), particulars
REFS = {
    'KCS': dict(file='KCS.igs', tf=dict(scale=1e-3), Lpp=230.0, B=32.2, T=10.8,
                note='KRISO Container Ship, full scale (Tribon lines), SIMMAN/Tokyo/Gothenburg benchmark'),
    'DTC': dict(file='DTC.stl', tf=dict(x_shift=-5.9136 / 59.407, model_scale=59.407), Lpp=355.0, B=51.0, T=14.5,
                note='Duisburg Test Case 14000 TEU container ship, model 1:59.407 (STL incl. rudder)'),
    'KVLCC2': dict(file='KVLCC2.igs', tf=dict(flip_x=True, flip_z=True), Lpp=320.0, B=58.0, T=20.8,
                   note='KRISO VLCC (second variant), full scale'),
    'JBC': dict(file='JBC.igs', tf=dict(scale=1e-3, x_shift=3.5, model_scale=40.0), Lpp=280.0, B=45.0, T=16.5,
                note='Japan Bulk Carrier, model 1:40 (Tokyo 2015 workshop)'),
    'DTMB5415': dict(file='DTMB5415.igs', tf=dict(scale=1e-3, flip_x=True, x_shift=5.72, model_scale=24.824),
                     Lpp=142.0, B=19.06, T=6.15,
                     note='US Navy combatant DTMB 5415, model 1:24.824, sonar dome, transom stern, bare hull'),
    'KLNG2': dict(file='KLNG2.igs', tf=dict(scale=1e-3), Lpp=None, B=46.2, T=11.5,
                  note='LNG carrier, twin skeg, full scale, incl. propellers; design draught 11.5 m ASSUMED'),
}


def measure(mesh, L, B, T, nx=301, nz=200):
    V = mesh.V
    xs = np.linspace(V[:, 0].min(), V[:, 0].max(), nx + 2)[1:-1]
    zmin = V[:, 2].min()
    dz = (T - zmin) / nz
    Z = zmin + (np.arange(nz) + 0.5 + 1e-3 * np.pi) * dz
    _, W = ref.offsets(mesh, xs, np.r_[Z, T * (1 - 1e-5)])
    A = W[:, :-1].sum(1) * dz
    wl = W[:, -1]
    vol = np.trapezoid(A, xs)
    Awp = np.trapezoid(wl, xs)
    imid = np.argmin(abs(xs - L / 2))
    wet = np.where(wl > 0)[0]
    return dict(Lpp=L, B=B, T=T, volume=float(vol), Cb=float(vol / (L * B * T)),
                LCB_pct=float((np.trapezoid(A * xs, xs) / vol - L / 2) / L * 100),
                Cm=float(A[imid] / (B * T)), Cwp=float(Awp / (L * B)),
                LCF_pct=float((np.trapezoid(wl * xs, xs) / Awp - L / 2) / L * 100),
                Lwl=float(xs[wet[-1]] - xs[wet[0]]), Bwl=float(wl.max()),
                SAC=np.c_[xs, A].tolist())


def main():
    folder = sys.argv[1]
    names = sys.argv[2:] or list(REFS)
    for name in names:
        r = REFS[name]
        mesh = ref.load(os.path.join(folder, r['file']), r['tf'])
        V = mesh.V
        T = r['T']
        L = r['Lpp']
        if L is None:      # AP at the file origin, FP where the stem meets the design waterline
            xs = np.linspace(V[:, 0].max() - 0.06 * np.ptp(V[:, 0]), V[:, 0].max(), 600)
            H, _ = ref.offsets(mesh, xs, np.array([T * (1 - 1e-4)]))
            L = float(xs[np.where(H[:, 0] > 0)[0][-1]])
        D = float(V[:, 2].max())
        zmin = float(min(V[:, 2].min(), 0.0))
        xq, zq = ref.standard_grid(L, T, D, zlo=zmin)
        H, W = ref.offsets(mesh, xq, zq)
        hy = measure(mesh, L, r['B'], T)
        meta = dict(name=name, file=r['file'], transform=r['tf'], note=r['note'], Lpp=L, B=r['B'], T=T,
                    D_max=D, z_min=zmin, x_min=float(V[:, 0].min()), x_max=float(V[:, 0].max()),
                    half_model=bool(V[:, 1].min() > -1e-3 * np.ptp(V[:, 1])), hydro=hy)
        out = os.path.join(os.path.dirname(__file__), '..', 'references', name + '.npz')
        np.savez_compressed(out, x=xq.astype(np.float32), z=zq.astype(np.float32), H=H.astype(np.float32),
                            W=W.astype(np.float32), meta=json.dumps(meta))
        print('%-9s L=%.3f D=%.2f Cb=%.4f LCB=%.2f%% Cm=%.4f Cwp=%.4f LCF=%.2f%%' % (
            name, L, D, hy['Cb'], hy['LCB_pct'], hy['Cm'], hy['Cwp'], hy['LCF_pct']))


if __name__ == '__main__':
    main()
