"""Comparison plots of a design against a reference hull (matplotlib, optional dependency)."""
import numpy as np

from .offsets import outer_halfbreadth


def compare_figure(design, ref, path, title='', mask=()):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    h = design.hull
    L, T, B2 = h.L, h.T, h.B2
    xq, zq = ref.x.astype(float), ref.z.astype(float)
    H = outer_halfbreadth(design, xq, zq)
    Hr = ref.H.astype(float)
    fig = plt.figure(figsize=(18, 10))
    ax1 = fig.add_axes([0.03, 0.08, 0.3, 0.84])
    for st in np.arange(-0.5, 21.0, 1.0) / 20:
        i = np.argmin(np.abs(xq - st * L))
        sgn = -1 if st < 0.5 else 1
        for HH, c, lw in ((Hr, 'k', 0.9), (H, 'C3', 0.9)):
            y = HH[i]
            m = y > 0
            ax1.plot(sgn * y[m], zq[m], c, lw=lw)
    ax1.axhline(T, color='b', lw=0.5, ls='--')
    ax1.set_aspect('equal')
    ax1.set_title('Body plan: reference black, generated red (aft left, forward right)')
    ax2 = fig.add_axes([0.37, 0.55, 0.6, 0.37])
    ax2.contour(xq / L * 20, zq, (Hr > 0).T.astype(float), [0.5], colors='k', linewidths=1.0)
    ax2.contour(xq / L * 20, zq, (H > 0).T.astype(float), [0.5], colors='C3', linewidths=1.0)
    for f, c in ((0.15, 'C0'), (0.5, 'C2'), (1.0, 'C1')):
        j = np.argmin(np.abs(zq - f * T))
        ax2.plot(xq / L * 20, Hr[:, j] / B2 * T * 0.9 - 1.6 * T, 'k', lw=0.8)
        ax2.plot(xq / L * 20, H[:, j] / B2 * T * 0.9 - 1.6 * T, c, lw=0.8, label='%.2f T' % f)
    ax2.axhline(T, color='b', lw=0.5)
    ax2.legend(loc='lower center', ncol=3, fontsize=8)
    ax2.set_title('Profile (silhouette) and half-breadths at 0.15/0.5/1.0 T (scaled, below)')
    ax2.set_xlabel('station (AP = 0, FP = 20)')
    ax3 = fig.add_axes([0.37, 0.08, 0.6, 0.37])
    hy = design.hydrostatics(nx=181, nz=120)
    ax3.plot(np.array(ref.meta['hydro']['SAC'])[:, 0] / L * 20, np.array(ref.meta['hydro']['SAC'])[:, 1], 'k',
             label='reference')
    ax3.plot(hy['SAC'][:, 0] / L * 20, hy['SAC'][:, 1], 'C3', label='generated')
    ax3.legend()
    rh = ref.meta['hydro']
    txt = ('%s   reference / generated:  Cb %.4f / %.4f   LCB %.2f / %.2f %%   Cm %.4f / %.4f   '
           'Cwp %.4f / %.4f   LCF %.2f / %.2f %%' % (
               title, rh['Cb'], hy['Cb'], rh['LCB_pct'], hy['LCB_pct'], rh['Cm'], hy['Cm'], rh['Cwp'], hy['Cwp'],
               rh['LCF_pct'], hy['LCF_pct']))
    ax3.set_title('Sectional area curve below T\n' + txt, fontsize=9)
    fig.savefig(path, dpi=60)
    plt.close(fig)
    w = np.ones_like(H)
    for x0, x1, z0, z1 in mask:
        w[np.ix_((xq >= x0 * L) & (xq <= x1 * L), (zq >= z0 * T) & (zq <= z1 * T))] = 0.0
    sel = zq <= T * 1.05
    err = ((H - Hr) / B2)[:, sel]
    ww = w[:, sel]
    return dict(rms_halfbreadth=float(np.sqrt(np.sum(ww * err ** 2) / np.sum(ww))),
                rms_all=float(np.sqrt(np.mean(err ** 2))), hydro=hy)
