"""Parametric Hull Form Designer — desktop GUI (PySide6 + pyqtgraph)."""
import copy
import json
import os
import sys
import traceback

import numpy as np
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QSettings
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
                               QSlider, QDoubleSpinBox, QCheckBox, QComboBox, QScrollArea, QToolButton, QSplitter,
                               QTabWidget, QPushButton, QLineEdit, QFileDialog, QMessageBox, QTextBrowser,
                               QSizePolicy, QFrame)
import pyqtgraph as pg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from hullform import __version__  # noqa: E402
from hullform.params import SCHEMA, SPEC, new_params, merge, save_json, load_json, get, put  # noqa: E402
from hullform.presets import PRESETS  # noqa: E402
from hullform.build import Design  # noqa: E402
from hullform.offsets import outer_halfbreadth, section_curves  # noqa: E402
from hullform import cad  # noqa: E402
from hullform_gui.view3d import HullView  # noqa: E402

GROUPS = [
    ('main', 'Principal dimensions', True), ('form', 'Form coefficients (targets)', True),
    ('mid', 'Midship section', False), ('sac', 'Sectional area curve', False),
    ('dwl', 'Design waterline', False), ('fob', 'Flat of bottom', False), ('fos', 'Flat of side', False),
    ('sec', 'Section shape', False), ('stem', 'Stem', False), ('stern', 'Stern profile', False),
    ('deck', 'Deck and topside', False), ('bulb', 'Bulbous bow / sonar dome', True),
    ('boss', 'Stern tube boss', False), ('skeg', 'Skegs', True), ('cad', 'CAD', False),
    ('mesh', 'Preview resolution', False),
]
UNIT_TEXT = {'m': 'm', 'deg': '°', '-': '', 'L': '× Lpp', 'B2': '× B/2', 'T': '× T', 'D': '× D', 'pct': '% Lpp'}
RHO = 1.025


def visible(p, path):
    g = path.split('.')[0]
    if g == 'bulb' and path != 'bulb.on':
        return p['bulb']['on']
    if g == 'boss' and path != 'boss.on':
        return p['boss']['on'] and p['skeg']['mode'] != 'open'
    if g == 'skeg' and path != 'skeg.mode':
        return p['skeg']['mode'] == 'twin'
    return True


class ParamRow(QWidget):
    changed = Signal(str, object)

    def __init__(self, spec):
        super().__init__()
        self.spec = spec
        self.path = spec['path']
        lay = QGridLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setHorizontalSpacing(6)
        self.label = QLabel(spec['label'])
        self.label.setToolTip(spec['hint'] or spec['path'])
        u = spec['unit']
        if u == 'bool':
            self.w = QCheckBox(spec['label'])
            self.w.toggled.connect(lambda v: self.changed.emit(self.path, bool(v)))
            lay.addWidget(self.w, 0, 0, 1, 3)
            self.slider = None
        elif u == 'sel':
            lay.addWidget(self.label, 0, 0, 1, 3)
            self.w = QComboBox()
            self.w.addItems(spec['lo'])
            self.w.currentTextChanged.connect(lambda v: self.changed.emit(self.path, v))
            lay.addWidget(self.w, 1, 0, 1, 3)
            self.slider = None
        else:
            lay.addWidget(self.label, 0, 0, 1, 3)
            self.slider = QSlider(Qt.Horizontal)
            self.slider.setRange(0, 1000)
            self.w = QDoubleSpinBox()
            step = spec['step']
            dec = max(0, -int(np.floor(np.log10(step)))) if step < 1 else 0
            self.w.setDecimals(dec)
            self.w.setSingleStep(step)
            self.w.setRange(spec['lo'], spec['hi'])
            self.w.setSuffix(' ' + UNIT_TEXT[u] if UNIT_TEXT[u] else '')
            self.w.setFixedWidth(118)
            self.w.setKeyboardTracking(False)
            self.slider.valueChanged.connect(self._from_slider)
            self.w.valueChanged.connect(self._from_box)
            lay.addWidget(self.slider, 1, 0)
            lay.addWidget(self.w, 1, 1)
            self.info = QLabel('')
            self.info.setStyleSheet('color:#6b6b6b; font-size:11px')
            self.info.setFixedWidth(90)
            lay.addWidget(self.info, 1, 2)
        self._busy = False

    def _from_slider(self, i):
        if self._busy:
            return
        s = self.spec
        v = s['lo'] + (s['hi'] - s['lo']) * i / 1000.0
        v = round(v / s['step']) * s['step']
        self._busy = True
        self.w.setValue(v)
        self._busy = False
        self.changed.emit(self.path, float(self.w.value()))

    def _from_box(self, v):
        if self._busy:
            return
        self._busy = True
        s = self.spec
        self.slider.setValue(int(round((v - s['lo']) / (s['hi'] - s['lo']) * 1000)))
        self._busy = False
        self.changed.emit(self.path, float(v))

    def set_value(self, v):
        self._busy = True
        self.w.blockSignals(True)
        u = self.spec['unit']
        if u == 'bool':
            self.w.setChecked(bool(v))
        elif u == 'sel':
            self.w.setCurrentText(v)
        else:
            self.w.setValue(float(v))
            s = self.spec
            self.slider.setValue(int(round((float(v) - s['lo']) / (s['hi'] - s['lo']) * 1000)))
        self.w.blockSignals(False)
        self._busy = False

    def set_info(self, p):
        if self.slider is None:
            return
        u = self.spec['unit']
        v = get(p, self.path)
        m = p['main']
        f = {'L': m['Lpp'], 'B2': m['B'] / 2, 'T': m['T'], 'D': m['D'], 'pct': m['Lpp'] / 100}.get(u)
        self.info.setText('= %.3f m' % (v * f) if f else '')


class Group(QWidget):
    def __init__(self, title, open_=False):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.btn = QToolButton()
        self.btn.setText(title)
        self.btn.setCheckable(True)
        self.btn.setChecked(open_)
        self.btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.btn.setArrowType(Qt.DownArrow if open_ else Qt.RightArrow)
        self.btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn.setStyleSheet('QToolButton{font-weight:600; padding:6px; text-align:left;'
                               'border:none; border-bottom:1px solid #c9ced0; background:#eef1f2}')
        self.body = QWidget()
        self.bl = QVBoxLayout(self.body)
        self.bl.setContentsMargins(2, 2, 2, 6)
        self.bl.setSpacing(0)
        self.body.setVisible(open_)
        self.btn.toggled.connect(self._toggle)
        lay.addWidget(self.btn)
        lay.addWidget(self.body)

    def _toggle(self, on):
        self.body.setVisible(on)
        self.btn.setArrowType(Qt.DownArrow if on else Qt.RightArrow)


class Worker(QThread):
    done = Signal(object, int)
    failed = Signal(str, int)

    def __init__(self, p, gen):
        super().__init__()
        self.p, self.gen = copy.deepcopy(p), gen

    def run(self):
        try:
            d = Design(self.p, correct=True)
            h = d.hydrostatics(nx=181, nz=120)
            S, parts = d.wetted_surface()
            h['S'] = S
            self.done.emit((d, h), self.gen)
        except Exception:
            self.failed.emit(traceback.format_exc(), self.gen)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Parametric Hull Form Designer %s' % __version__)
        self.resize(1600, 960)
        self.settings = QSettings('probPST', 'HullFormDesigner')
        self.p = new_params(next(iter(PRESETS), None))
        last = self.settings.value('last_params')
        if last:
            try:
                self.p = merge(json.loads(last))
            except Exception:
                pass
        self.rows = {}
        self.gen = 0
        self.workers = []
        self.design = None
        self.hydro = None
        self.reference = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.rebuild)
        self._build()
        self.load_all()
        self.rebuild()

    # ------------------------------------------------------------------ layout
    def _build(self):
        mb = self.menuBar()
        fm = mb.addMenu('&File')
        for text, key, fn in (('Open parameters…', QKeySequence.Open, self.open_params),
                              ('Save parameters…', QKeySequence.Save, self.save_params),
                              ('Export geometry…', 'Ctrl+E', self.export), (None, None, None),
                              ('Quit', QKeySequence.Quit, self.close)):
            if text is None:
                fm.addSeparator()
                continue
            a = QAction(text, self)
            a.setShortcut(key)
            a.triggered.connect(fn)
            fm.addAction(a)
        hm = mb.addMenu('&Help')
        a = QAction('About', self)
        a.triggered.connect(self.about)
        hm.addAction(a)

        top = QWidget()
        tl = QHBoxLayout(top)
        tl.setContentsMargins(8, 6, 8, 6)
        tl.addWidget(QLabel('Type preset'))
        self.preset = QComboBox()
        self.preset.addItem('(custom)', '')
        for k, v in PRESETS.items():
            self.preset.addItem('%s — %s' % (k, v['label']), k)
        self.preset.setMinimumWidth(520)
        self.preset.activated.connect(self.apply_preset)
        tl.addWidget(self.preset)
        tl.addSpacing(16)
        tl.addWidget(QLabel('Design name'))
        self.name = QLineEdit()
        self.name.setFixedWidth(200)
        self.name.textEdited.connect(lambda t: self.p.__setitem__('name', t))
        tl.addWidget(self.name)
        tl.addStretch(1)
        eb = QPushButton('Export geometry…')
        eb.setObjectName('primary')
        eb.clicked.connect(self.export)
        tl.addWidget(eb)

        # left: parameters
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        il = QVBoxLayout(inner)
        il.setContentsMargins(4, 4, 4, 4)
        il.setSpacing(4)
        self.groups = {}
        for g, title, open_ in GROUPS:
            box = Group(title, open_)
            self.groups[g] = box
            il.addWidget(box)
        for e in SCHEMA:
            spec = SPEC[e[0]]
            r = ParamRow(spec)
            r.changed.connect(self.edit)
            self.rows[e[0]] = r
            self.groups[e[0].split('.')[0]].bl.addWidget(r)
        il.addStretch(1)
        scroll.setWidget(inner)
        ll.addWidget(scroll)
        left.setMinimumWidth(400)

        # centre: 3-D view
        centre = QWidget()
        cl = QVBoxLayout(centre)
        cl.setContentsMargins(4, 0, 4, 0)
        bar = QHBoxLayout()
        for v in ('Iso', 'Side', 'Bow', 'Stern', 'Top', 'Bottom'):
            b = QPushButton(v)
            b.clicked.connect(lambda _=False, v=v: self.view.preset_view(v))
            bar.addWidget(b)
        self.chk_wl = QCheckBox('Waterline')
        self.chk_wl.setChecked(True)
        self.chk_edges = QCheckBox('Mesh lines')
        self.chk_ref = QCheckBox('Reference overlay')
        self.chk_ref.setChecked(True)
        for c in (self.chk_wl, self.chk_edges, self.chk_ref):
            c.toggled.connect(self.update_views)
            bar.addWidget(c)
        bar.addStretch(1)
        cl.addLayout(bar)
        self.view = HullView()
        cl.addWidget(self.view, 1)
        self.summary = QLabel('')
        self.summary.setStyleSheet('font-family: monospace; color:#333; padding:4px')
        cl.addWidget(self.summary)
        note = QLabel('x forward from AP · y to port · z up from baseline · design waterline z = T')
        note.setStyleSheet('color:#777; font-size:11px')
        cl.addWidget(note)

        # right: plots and tables
        self.tabs = QTabWidget()
        self.p_body = pg.PlotWidget(background='w')
        self.p_body.setAspectLocked(True)
        self.p_body.showGrid(True, True, 0.2)
        self.p_prof = pg.GraphicsLayoutWidget()
        self.p_prof.setBackground('w')
        self.ax_prof = self.p_prof.addPlot(row=0, col=0, title='Profile (silhouette)')
        self.ax_plan = self.p_prof.addPlot(row=1, col=0, title='Half-breadths: DWL, deck, flat of bottom')
        self.ax_plan.setXLink(self.ax_prof)
        for a in (self.ax_prof, self.ax_plan):
            a.showGrid(True, True, 0.2)
        self.p_sac = pg.PlotWidget(background='w', title='Sectional area curve below T')
        self.p_sac.showGrid(True, True, 0.2)
        self.p_sac.addLegend()
        self.hydro_txt = QTextBrowser()
        self.tabs.addTab(self.p_body, 'Body plan')
        self.tabs.addTab(self.p_prof, 'Profile && lines')
        self.tabs.addTab(self.p_sac, 'Area curve')
        self.tabs.addTab(self.hydro_txt, 'Hydrostatics')

        split = QSplitter()
        split.addWidget(left)
        split.addWidget(centre)
        split.addWidget(self.tabs)
        split.setSizes([420, 650, 560])
        root = QWidget()
        rl = QVBoxLayout(root)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(top)
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        rl.addWidget(line)
        rl.addWidget(split, 1)
        self.setCentralWidget(root)
        self.statusBar().showMessage('CAD kernel: %s' % ('OpenCASCADE ready (IGES + exact solid)' if cad.HAVE_OCC
                                                         else 'not available (STL from preview mesh only)'))

    # ------------------------------------------------------------------ parameters
    def load_all(self):
        for path, r in self.rows.items():
            r.set_value(get(self.p, path))
        self.name.setText(self.p.get('name', ''))
        i = self.preset.findData(self.p.get('preset', ''))
        self.preset.setCurrentIndex(max(i, 0))
        self.refresh()
        self.load_reference()

    def refresh(self):
        for path, r in self.rows.items():
            r.setVisible(visible(self.p, path))
            r.set_info(self.p)

    def edit(self, path, v):
        put(self.p, path, v)
        if path in ('bulb.on', 'boss.on', 'skeg.mode') or path.startswith('main.'):
            self.refresh()
        else:
            self.rows[path].set_info(self.p)
        self.timer.start(120)

    def apply_preset(self, i):
        k = self.preset.itemData(i)
        if not k:
            return
        self.p = new_params(k)
        self.load_all()
        self.rebuild()

    def load_reference(self):
        self.reference = None
        k = self.p.get('preset')
        path = os.path.join(ROOT, 'references', '%s.npz' % k)
        if k and os.path.exists(path):
            from hullform.reference import Reference
            self.reference = Reference(path)

    # ------------------------------------------------------------------ rebuild
    def rebuild(self):
        try:
            self.design = Design(self.p)
        except Exception as ex:
            self.statusBar().showMessage('Geometry error: %s' % ex)
            return
        self.update_views()
        self.gen += 1
        w = Worker(self.p, self.gen)
        w.done.connect(self.worker_done)
        w.failed.connect(lambda msg, g: self.statusBar().showMessage('Hydrostatics failed'))
        w.finished.connect(lambda w=w: self.workers.remove(w) if w in self.workers else None)
        self.workers.append(w)
        w.start()
        self.summary.setText('computing hydrostatics (complete hull, Cb/LCB correction)…')

    def worker_done(self, res, gen):
        if gen != self.gen:
            return
        self.design, self.hydro = res
        self.update_views()
        self.update_hydro()

    def update_views(self):
        d = self.design
        if d is None:
            return
        h = d.hull
        v = self.view
        v.clear_model()
        for m in d.meshes():
            v.add_mesh(m, edges=self.chk_edges.isChecked())
        V = np.vstack([m.V for m in d.meshes()])
        lo, hi = V.min(0), V.max(0)
        lo[1] = -hi[1]
        if self.chk_wl.isChecked():
            v.add_waterline(lo[0] - 0.05 * h.L, hi[0] + 0.05 * h.L, 0.7 * h.B, h.T)
        if abs(v.extent - float(np.max(hi - lo))) > 1e-6 * h.L:
            v.frame(lo, hi)
        v.relight()
        self.plot_lines()

    def plot_lines(self):
        d = self.design
        h = d.hull
        L, T = h.L, h.T
        zq = np.linspace(min(0.0, float(np.vstack([m.V for m in d.meshes()])[:, 2].min())), h.D_fwd, 160)
        ref = self.reference if self.chk_ref.isChecked() else None
        st = np.arange(-0.5, 21.0, 0.5) / 20 * L
        self.p_body.clear()
        for x in st:
            sg = -1 if x < L / 2 else 1
            if ref is not None:
                j = np.argmin(np.abs(ref.x - x))
                mr = ref.H[j] > 0
                self.p_body.plot(sg * ref.H[j][mr], ref.z[mr], pen=pg.mkPen('#7a7a7a', width=1))
            col = '#B5523F' if sg > 0 else '#2F5D73'
            for name, P in section_curves(d, x):
                if name == 'hull':
                    self.p_body.plot(sg * P[:, 0], P[:, 1], pen=pg.mkPen(col, width=1.4))
                elif not name.endswith('_s'):          # starboard twin bodies mirror the port ones
                    self.p_body.plot(np.abs(P[:, 0]) * sg, P[:, 1], pen=pg.mkPen(col, width=1.0, style=Qt.DotLine))
        self.p_body.plot([-0.6 * h.B, 0.6 * h.B], [T, T], pen=pg.mkPen('#4a7fc1', style=Qt.DashLine))
        self.p_body.setXRange(-0.62 * h.B, 0.62 * h.B, padding=0)
        self.p_body.setYRange(zq[0] - 0.03 * h.D, h.D_fwd * 1.03, padding=0)
        self.p_body.setTitle('Body plan (aft half left, forward half right; dotted: add-on bodies)' +
                             ('; grey = reference %s' % ref.name if ref is not None else ''))
        # profile and lines
        xq = np.linspace(h.x_tr - 0.01 * L, h.x_stem_deck + 0.05 * L, 300)
        Hx = outer_halfbreadth(d, xq, zq)
        self.ax_prof.clear()
        self.ax_plan.clear()
        top = np.array([zq[r > 0].max() if (r > 0).any() else np.nan for r in Hx])
        bot = np.array([zq[r > 0].min() if (r > 0).any() else np.nan for r in Hx])
        if ref is not None:
            rt = np.array([ref.z[r > 0].max() if (r > 0).any() else np.nan for r in ref.H])
            rb = np.array([ref.z[r > 0].min() if (r > 0).any() else np.nan for r in ref.H])
            for y in (rt, rb):
                self.ax_prof.plot(ref.x, y, pen=pg.mkPen('#7a7a7a', width=1), connect='finite')
        for y in (top, bot):
            self.ax_prof.plot(xq, y, pen=pg.mkPen('#B5523F', width=1.6), connect='finite')
        self.ax_prof.plot([xq[0], xq[-1]], [T, T], pen=pg.mkPen('#4a7fc1', style=Qt.DashLine))
        jT = np.argmin(np.abs(zq - T))
        lines = (('DWL', Hx[:, jT], '#4a7fc1'), ('deck', h.deck(xq)[0], '#B5523F'),
                 ('flat of bottom', h.y_fob(xq), '#8A5A0B'))
        for name, y, c in lines:
            self.ax_plan.plot(xq, y, pen=pg.mkPen(c, width=1.5), name=name)
        if ref is not None:
            jr = np.argmin(np.abs(ref.z - T))
            self.ax_plan.plot(ref.x, ref.H[:, jr], pen=pg.mkPen('#7a7a7a', width=1))

    def update_hydro(self):
        h, d = self.hydro, self.design
        if h is None:
            return
        hf = d.hull
        p = self.p
        self.p_sac.clear()
        self.p_sac.plot(h['SAC'][:, 0], h['SAC'][:, 1], pen=pg.mkPen('#B5523F', width=2), name='complete hull')
        x = np.linspace(hf.x_u0, hf.x_u1, 300)
        self.p_sac.plot(x, hf.area(x), pen=pg.mkPen('#2F5D73', style=Qt.DashLine), name='main hull (target curve)')
        if self.reference is not None and self.chk_ref.isChecked():
            s = np.array(self.reference.meta['hydro']['SAC'])
            self.p_sac.plot(s[:, 0], s[:, 1], pen=pg.mkPen('#7a7a7a', width=1), name='reference')
        rows = [('Length between perpendiculars Lpp', '%.3f m' % hf.L), ('Breadth B', '%.3f m' % hf.B),
                ('Draught T', '%.3f m' % hf.T), ('Depth D', '%.3f m' % hf.D),
                ('Waterline length Lwl', '%.3f m' % h.get('Lwl', np.nan)),
                ('Waterline breadth Bwl', '%.3f m' % h.get('Bwl', np.nan)),
                ('Displacement volume ∇', '%.2f m³' % h['volume']),
                ('Displacement Δ (ρ = 1.025 t/m³)', '%.1f t' % (h['volume'] * RHO)),
                ('Block coefficient Cb', '%.4f (target %.4f)' % (h['Cb'], p['form']['Cb'])),
                ('Prismatic coefficient Cp', '%.4f' % h['Cp']),
                ('Midship coefficient Cm', '%.4f (target %.4f)' % (h['Cm'], p['form']['Cm'])),
                ('Waterplane coefficient Cwp', '%.4f (target %.4f)' % (h['Cwp'], p['form']['Cwp'])),
                ('LCB fwd of midship', '%.3f %% Lpp (target %.3f)' % (h['LCB_pct'], p['form']['LCB'])),
                ('LCF fwd of midship', '%.3f %% Lpp (target %.3f)' % (h['LCF_pct'], p['form']['LCF'])),
                ('KB', '%.3f m' % h['VCB']), ('BMt', '%.3f m' % h['BMt']), ('KMt', '%.3f m' % h['KMt']),
                ('Waterplane area', '%.1f m²' % h['Awp']), ('Wetted surface (mesh)', '%.1f m²' % h['S']),
                ('Bilge radius (from Cm)', '%.3f m' % hf.r_bilge)]
        html = '<h3>Hydrostatics at the design draught</h3><table cellpadding=3>'
        html += ''.join('<tr><td>%s</td><td><b>%s</b></td></tr>' % r for r in rows) + '</table>'
        if self.reference is not None:
            rh = self.reference.meta['hydro']
            html += ('<h3>Reference %s</h3><p>Cb %.4f · Cm %.4f · Cwp %.4f · LCB %.2f %% · LCF %.2f %%</p>'
                     '<p style="color:#666">%s</p>' % (self.reference.name, rh['Cb'], rh['Cm'], rh['Cwp'],
                                                       rh['LCB_pct'], rh['LCF_pct'], self.reference.meta['note']))
        if d.warnings:
            html += '<h3 style="color:#A63E2C">Warnings</h3><ul>%s</ul>' % ''.join('<li>%s</li>' % w for w in d.warnings)
        self.hydro_txt.setHtml(html)
        self.summary.setText('∇ %.1f m³   Δ %.0f t   Cb %.4f   Cp %.4f   Cm %.4f   Cwp %.4f   LCB %+.2f %%   S %.0f m²' % (
            h['volume'], h['volume'] * RHO, h['Cb'], h['Cp'], h['Cm'], h['Cwp'], h['LCB_pct'], h['S']))

    # ------------------------------------------------------------------ files
    def open_params(self):
        f, _ = QFileDialog.getOpenFileName(self, 'Open parameters', '', 'Parameters (*.json)')
        if f:
            self.p = load_json(f)
            self.load_all()
            self.rebuild()

    def save_params(self):
        f, _ = QFileDialog.getSaveFileName(self, 'Save parameters', self.p.get('name', 'hull') + '.json',
                                           'Parameters (*.json)')
        if f:
            save_json(self.p, f)

    def export(self):
        from hullform_gui.export_dialog import ExportDialog
        ExportDialog(self.p, self).exec()

    def about(self):
        QMessageBox.about(self, 'About', 'Parametric Hull Form Designer %s\nCAD kernel: %s' % (
            __version__, 'OpenCASCADE (cadquery-ocp)' if cad.HAVE_OCC else 'not available'))

    def closeEvent(self, ev):
        self.settings.setValue('last_params', json.dumps(self.p))
        for w in self.workers:
            w.wait(5000)
        super().closeEvent(ev)


STYLE = """
QWidget { font-size: 12px; }
QPushButton#primary { background:#A63E2C; color:white; font-weight:600; padding:6px 14px; border-radius:3px; }
QPushButton#primary:hover { background:#8f3424; }
"""


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
