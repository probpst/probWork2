"""Main hull: form-parameter curves -> stations -> offset grid.

Frame: x forward from the aft perpendicular (AP, x = 0; FP at x = Lpp), y to port, z up from the
baseline, metres. The main hull is the bare hull without the add-on bodies (bulbous bow / sonar dome,
stern boss, twin skegs, see appendages.py). Its sectional area curve is solved so that the main hull
alone has the requested block coefficient and LCB; `build.py` corrects the targets for the add-ons.
"""
import numpy as np
from scipy.optimize import least_squares, brentq

from .curves import end_curve, end_fullness, plateau_curve, smoothstep, fillet_polyline
from .sections import quadrant_shape, section_points


class HullForm(object):
    def __init__(self, p, cb_main=None, lcb_main=None):
        self.p = p
        m = p['main']
        self.L, self.B, self.T, self.D = L, B, T, D = m['Lpp'], m['B'], m['T'], m['D']
        self.B2 = B / 2.0
        f = p['form']
        self.cb_target = f['Cb'] if cb_main is None else cb_main
        self.lcb_target = f['LCB'] if lcb_main is None else lcb_main
        self.warnings = []
        self._profile()
        self._midship()
        self._dwl()
        self._sac()

    # ------------------------------------------------------------------ profile (centreline)
    def _profile(self):
        p, L, T, D = self.p, self.L, self.T, self.D
        st, sn = p['stem'], p['stern']
        th = np.radians(st['rake'])
        dk = p['deck']
        self.D_fwd = D * (1 + dk['shf'])
        self.x_stem_keel = L - T * np.tan(th)
        self.x_stem_deck = L + (self.D_fwd - T) * np.tan(th)
        fore = fillet_polyline([(0.5 * L, 0.0), (self.x_stem_keel, 0.0), (self.x_stem_deck + 1e-9 * L, self.D_fwd)],
                               [0, st['rff'] * T, 0], 40)
        self.x_tr = sn['xtr'] * L
        self.z_tr = sn['ztr'] * T
        # keep the stern profile single-valued: transom -> knuckle -> heel, x increasing, z falling
        x_ck = max(sn['xck'] * L, self.x_tr + 0.002 * L)
        x_h = max(sn['xh'] * L, x_ck + 0.004 * L)
        z_ck = min(sn['zck'] * T, self.z_tr - 1e-3 * T)
        if (x_ck, x_h, z_ck) != (sn['xck'] * L, sn['xh'] * L, sn['zck'] * T):
            self.warnings.append('stern profile adjusted to stay single-valued (transom/knuckle/heel order)')
        aft = fillet_polyline([(self.x_tr, self.z_tr), (x_ck, z_ck), (x_h, 0.0),
                               (0.5 * L, 0.0)], [0, sn['rck'] * T, sn['rh'] * T, 0], 40)
        self.prof_fore, self.prof_aft = fore, aft
        if np.any(np.diff(aft[:, 0]) <= 0) or np.any(np.diff(fore[:, 0]) <= 0):
            self.warnings.append('profile is not single-valued in x (vertical or overhanging segment)')
        # underwater extent of the main hull
        self.x_u1 = float(np.interp(T, fore[:, 1], fore[:, 0]))
        if self.z_tr < T:
            self.x_u0 = self.x_tr
        else:
            za = aft[::-1]
            self.x_u0 = float(np.interp(T, za[:, 1], za[:, 0]))

    def z0(self, x):
        x = np.asarray(x, float)
        fa, ff = self.prof_aft, self.prof_fore
        z = np.zeros_like(x)
        ma = x < fa[-1, 0]
        z[ma] = np.interp(x[ma], fa[:, 0], fa[:, 1])
        mf = x > ff[0, 0]
        z[mf] = np.interp(x[mf], ff[:, 0], ff[:, 1])
        return z

    # ------------------------------------------------------------------ midship
    def _midship(self):
        B2, T = self.B2, self.T
        Am = self.p['form']['Cm'] * self.B * self.T
        h = self.p['mid']['rof'] * T

        def half_area(r):
            yf = max(B2 - r, 0.0)
            zb = h * yf / B2
            return yf * zb / 2 + yf * r + r * r * np.pi / 4 + B2 * (T - zb - r)
        lo, hi = 1e-4 * T, min(B2, T - h) * 0.999
        if half_area(lo) <= Am / 2:
            r = lo
        elif half_area(hi) >= Am / 2:
            r = hi
            self.warnings.append('Cm too low for a circular bilge; bilge radius limited')
        else:
            r = brentq(lambda r: half_area(r) - Am / 2, lo, hi)
        self.r_bilge = r
        self.Am = Am
        self.h_rof = h

    # ------------------------------------------------------------------ waterline
    def _end_lengths(self, x1a, x1f):
        return max(x1a - self.x_u0, 1e-6), max(self.x_u1 - x1f, 1e-6)

    def _fit_ends(self, va_rel, aa, af, x1a, x1f, area_t, mom_t):
        """Solve shoulder exponents (ba, bf) of a plateau curve (plateau value 1, aft end value va_rel,
        forward end 0) for a target integral and first moment (about x = 0)."""
        La, Lf = self._end_lengths(x1a, x1f)
        x0a, x0f = x1a - La, x1f + Lf

        def parts(lb):
            ba, bf = np.exp(lb)
            Fa, Ma = end_fullness(aa, ba, True)
            Ff, Mf = end_fullness(af, bf, True)
            # aft: value va + (1-va) g(t), t from x0a; forward: g(t), t from x0f backwards
            Ia = La * (va_rel + (1 - va_rel) * Fa)
            Ma_x = La * (va_rel * (x0a + La / 2) + (1 - va_rel) * (x0a * Fa + La * Ma))
            If = Lf * Ff
            Mf_x = Lf * (x0f * Ff - Lf * Mf)
            Ip = x1f - x1a
            Mp = Ip * (x1a + x1f) / 2
            return Ia + If + Ip, Ma_x + Mf_x + Mp

        def res(lb):
            I, M = parts(lb)
            return [(I - area_t) / max(area_t, 1e-9), (M / I - mom_t / area_t) / self.L]
        sol = least_squares(res, [np.log(2.0), np.log(2.0)], bounds=([np.log(0.05)] * 2, [np.log(60.0)] * 2),
                            xtol=1e-12, ftol=1e-12)
        if np.max(np.abs(sol.fun)) > 1e-4:
            self.warnings.append('target fullness/centroid not reachable (residual %.2g)' % np.max(np.abs(sol.fun)))
        return np.exp(sol.x)

    def _dwl(self):
        p, L, B2 = self.p, self.L, self.B2
        d = p['dwl']
        # the parallel waterline must contain the parallel body of the sectional area curve,
        # otherwise full sections are asked for where the waterline is already narrowing
        self.wl_x1a = min(d['xwa'], p['sac']['xpa']) * L
        self.wl_x1f = max(d['xwf'], p['sac']['xpf']) * L
        self.wl_va = d['ytr'] if self.z_tr < self.T else 0.0
        area = p['form']['Cwp'] * L * B2          # half waterplane, normalised by B2 below
        xcf = L / 2 + p['form']['LCF'] / 100.0 * L
        self.wl_ba, self.wl_bf = self._fit_ends(self.wl_va, d['aa'], d['af'], self.wl_x1a, self.wl_x1f,
                                                area / B2, xcf * area / B2)

    def y_wl(self, x):
        d = self.p['dwl']
        x = np.asarray(x, float)
        La, Lf = self._end_lengths(self.wl_x1a, self.wl_x1f)
        y = plateau_curve(x, self.wl_x1a - La, self.wl_x1a, self.wl_x1f, self.wl_x1f + Lf, self.wl_va, 0.0,
                          d['aa'], self.wl_ba, d['af'], self.wl_bf) * self.B2
        return np.where((x >= self.x_u0) & (x <= self.x_u1), y, 0.0)

    # ------------------------------------------------------------------ sectional area
    def _sac(self):
        p, L, B, T = self.p, self.L, self.B, self.T
        s = p['sac']
        self.sa_x1a, self.sa_x1f = s['xpa'] * L, s['xpf'] * L
        if self.z_tr < T:
            A_tr = 2 * p['dwl']['ytr'] * self.B2 * (T - self.z_tr) * s['sig_tr']
        else:
            A_tr = 0.0
        self.sa_va = A_tr / self.Am
        vol = self.cb_target * L * B * T
        xcb = L / 2 + self.lcb_target / 100.0 * L
        self.sa_ba, self.sa_bf = self._fit_ends(self.sa_va, s['aa'], s['af'], self.sa_x1a, self.sa_x1f,
                                                vol / self.Am, xcb * vol / self.Am)

    def area(self, x):
        s = self.p['sac']
        x = np.asarray(x, float)
        La, Lf = self._end_lengths(self.sa_x1a, self.sa_x1f)
        A = plateau_curve(x, self.sa_x1a - La, self.sa_x1a, self.sa_x1f, self.sa_x1f + Lf, self.sa_va, 0.0,
                          s['aa'], self.sa_ba, s['af'], self.sa_bf) * self.Am
        return np.where((x >= self.x_u0) & (x <= self.x_u1), A, 0.0)

    # ------------------------------------------------------------------ flat of bottom / side, deck
    def y_fob(self, x):
        f, L = self.p['fob'], self.L
        F = plateau_curve(x, f['xa0'] * L, f['xa1'] * L, f['xf1'] * L, f['xf0'] * L, 0.0, 0.0, 1.0, f['pa'], 1.0, f['pf'])
        F = np.where((x > f['xa0'] * L) & (x < f['xf0'] * L), F, 0.0)
        return F * (self.B2 - self.r_bilge)

    def fos_weight(self, x):
        f, L = self.p['fos'], self.L
        G = plateau_curve(x, f['xa0'] * L, f['xa1'] * L, f['xf1'] * L, f['xf0'] * L, 0.0, 0.0, 1.0, f['pa'], 1.0, f['pf'])
        return np.where((x > f['xa0'] * L) & (x < f['xf0'] * L), G, 0.0)

    def deck(self, x):
        d, L = self.p['deck'], self.L
        x = np.asarray(x, float)
        y = plateau_curve(x, self.x_tr, d['xda'] * L, d['xdf'] * L, self.x_stem_deck, d['ytr'], 0.0,
                          d['aa'], d['ba'], d['af'], d['bf'], vmax=d['ymid']) * self.B2
        wf = smoothstep((x - d['xsf'] * L) / max(self.x_stem_deck - d['xsf'] * L, 1e-9))
        wa = smoothstep((d['xsa'] * L - x) / max(d['xsa'] * L - self.x_tr, 1e-9))
        z = self.D * (1 + d['shf'] * wf + d['sha'] * wa)
        return y, z

    def flare(self, x):
        d, L = self.p['deck'], self.L
        wf = smoothstep((x - d['xdf'] * L) / max(self.x_stem_deck - d['xdf'] * L, 1e-9))
        wa = smoothstep((d['xda'] * L - x) / max(d['xda'] * L - self.x_tr, 1e-9))
        return d['flare_f'] * wf + d['flare_a'] * wa

    def keel_exponent(self, x):
        s, L = self.p['sec'], self.L
        x = np.asarray(x, float)
        ln = np.full(x.shape, np.log(2.0))
        ta = smoothstep((self.sa_x1a - x) / max(self.sa_x1a - self.x_u0, 1e-9))
        tf = smoothstep((x - self.sa_x1f) / max(self.x_u1 - self.sa_x1f, 1e-9))
        ln = ln + (np.log(s['naft']) - np.log(2.0)) * ta + (np.log(s['nfwd']) - np.log(2.0)) * tf
        return np.exp(ln)

    def wl_flare(self, x):
        s = self.p['sec']
        x = np.asarray(x, float)
        ta = smoothstep((self.sa_x1a - x) / max(self.sa_x1a - self.x_u0, 1e-9))
        tf = smoothstep((x - self.sa_x1f) / max(self.x_u1 - self.sa_x1f, 1e-9))
        return s['fla'] * ta + s['flf'] * tf

    # ------------------------------------------------------------------ stations
    def station_x(self, ns):
        x = np.linspace(self.x_tr, self.x_stem_deck, 4000)
        z = self.z0(x)
        w = np.sqrt(1 + (np.gradient(z, x)) ** 2)
        # extra density at both ends and around the transitions of the parallel body
        span = self.x_stem_deck - self.x_tr
        u = (x - self.x_tr) / span
        w = w * (1 + 1.5 * np.exp(-((u - 0) / 0.05) ** 2) + 2.5 * np.exp(-((u - 1) / 0.06) ** 2))
        c = np.r_[0, np.cumsum(0.5 * (w[1:] + w[:-1]) * np.diff(x))]
        return np.interp(np.linspace(0, c[-1], ns), c, x)

    def stations(self, xs):
        xs = np.asarray(xs, float)
        T = self.T
        z0 = self.z0(xs)
        b = self.y_wl(xs)
        A = self.area(xs)
        yd, zd = self.deck(xs)
        yf = self.y_fob(xs)
        yf = np.minimum(yf, 0.97 * b)
        tanb = self.h_rof / self.B2
        zb = z0 + yf * tanb
        G = self.fos_weight(xs)
        zs_t = zb + self.r_bilge
        zs = T - (T - zs_t) * G
        zs = np.clip(zs, zb + 1e-3 * T, T)
        n = self.keel_exponent(xs)
        # waterline flare: the section side leans out by phi at the waterline
        tp0 = np.tan(np.radians(self.wl_flare(xs)))
        wet = (z0 < T - 1e-9) & (b > 1e-9)

        def solve(r):
            # quadrant from (yf + r, zb + r): a keel rounding of radius r replaces the cusp of a
            # hollow (n < 1) section, so a skeg has a finite, round bottom
            yq, zq = yf + r, zb + r
            tp = np.minimum(tp0, 0.9 * (b - yq) / np.maximum(T - zq, 1e-9))
            cy = b - (T - zq) * tp
            psy = b - (T - zs) * tp
            zr = np.zeros_like(b)
            Y = np.stack([zr, yf, yq, cy, psy, b, zr])
            Z = np.stack([z0, zb, zq, zq, zs, np.full_like(b, T), np.full_like(b, T)])
            poly = 0.5 * np.abs(np.sum(Y * np.roll(Z, -1, 0) - np.roll(Y, -1, 0) * Z, axis=0))
            poly = poly + r * r * (np.pi / 4 - 0.5)
            sig = np.full(xs.shape, 0.5)
            den = (cy - yq) * (zs - zq)
            sig[wet] = 1.0 - (poly[wet] - A[wet] / 2) / np.maximum(den[wet], 1e-12)
            n_eff, m = quadrant_shape(n, sig)
            return sig, n_eff, m, np.degrees(np.arctan(tp))
        sig, n_eff, m, phi = solve(np.zeros_like(b))
        rk = np.where(wet & (n_eff < 1.0),
                      np.minimum(self.p['sec']['rk'] * T, np.minimum(0.3 * (zs - zb), 0.3 * (b - yf))), 0.0)
        rk = np.maximum(rk, 0.0)
        if np.any(rk > 0):
            sig, n_eff, m, phi = solve(rk)
        bad = wet & ((sig > 0.9995) | (sig < 0.02))
        self.n_bad = int(bad.sum())
        # near the ends of the waterline the area tends to zero and a clamped section is harmless
        bad = bad & (xs > self.x_u0 + 0.02 * self.L) & (xs < self.x_u1 - 0.02 * self.L)
        if bad.sum() > 0.02 * len(xs) and not any(w.startswith('sectional area') for w in self.warnings):
            self.warnings.append('sectional area not reachable at %d stations (x = %.1f … %.1f m): waterline, '
                                 'flat of bottom/side and area curve are inconsistent there'
                                 % (bad.sum(), xs[bad].min(), xs[bad].max()))
        out = []
        fl = self.flare(xs)
        for i in range(len(xs)):
            out.append(dict(x=xs[i], z0=z0[i], b=b[i], A=A[i], yd=yd[i], zd=zd[i], yf=yf[i], zb=zb[i], zs=zs[i],
                            n=n_eff[i], m=m[i], sig=sig[i], flare=fl[i], phi=phi[i], rk=rk[i]))
        return out

    def grid(self, ns=None, nm=None):
        ns = ns or self.p['mesh']['ns']
        nm = nm or self.p['mesh']['nm']
        xs = self.station_x(ns)
        sts = self.stations(xs)
        G = np.zeros((ns, nm, 3))
        for i, st in enumerate(sts):
            P = section_points(st, self.T, nm)
            G[i, :, 0] = st['x']
            G[i, :, 1] = P[:, 0]
            G[i, :, 2] = P[:, 1]
        # last station is the stem top: collapse it onto the centreline, and to one point when it
        # is (almost) degenerate, so the CAD faces get a clean pole instead of tiny edges
        G[-1, :, 1] = 0.0
        if np.ptp(G[-1, :, 2]) < 1e-3 * self.L:
            G[-1] = G[-1, -1]
        return G, sts
