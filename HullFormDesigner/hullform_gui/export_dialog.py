"""Export dialog: IGES and/or STL of the complete closed hull, with read-back verification."""
import copy
import os
import traceback

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QCheckBox, QComboBox, QLabel,
                               QSlider, QLineEdit, QPushButton, QFileDialog, QPlainTextEdit, QGridLayout)
from PySide6.QtCore import Qt

from hullform.export import export, LEVELS


class ExportWorker(QThread):
    message = Signal(str)
    finished_ok = Signal(object)

    def __init__(self, p, folder, formats, units, level, name):
        super().__init__()
        self.args = (copy.deepcopy(p), folder, formats, units, level)
        self.name = name

    def run(self):
        try:
            rep = export(*self.args, name=self.name, log=self.message.emit)
            self.finished_ok.emit(rep)
        except Exception:
            self.message.emit(traceback.format_exc())


class ExportDialog(QDialog):
    def __init__(self, p, parent=None):
        super().__init__(parent)
        self.p = p
        self.setWindowTitle('Export geometry')
        self.resize(640, 560)
        lay = QVBoxLayout(self)
        g1 = QGroupBox('File format')
        l1 = QHBoxLayout(g1)
        self.iges = QCheckBox('IGES (trimmed B-spline surfaces)')
        self.iges.setChecked(True)
        self.stl = QCheckBox('STL (binary, watertight)')
        self.stl.setChecked(True)
        l1.addWidget(self.iges)
        l1.addWidget(self.stl)
        lay.addWidget(g1)
        g2 = QGroupBox('Units and resolution')
        l2 = QGridLayout(g2)
        self.units = QComboBox()
        self.units.addItems(['m', 'mm'])
        l2.addWidget(QLabel('Units'), 0, 0)
        l2.addWidget(self.units, 0, 1)
        self.level = QSlider(Qt.Horizontal)
        self.level.setRange(1, 5)
        self.level.setValue(3)
        self.level_lbl = QLabel('')
        self.level.valueChanged.connect(self._lvl)
        l2.addWidget(QLabel('STL resolution'), 1, 0)
        l2.addWidget(self.level, 1, 1)
        l2.addWidget(self.level_lbl, 1, 2)
        self._lvl(3)
        lay.addWidget(g2)
        g3 = QGroupBox('Destination')
        l3 = QGridLayout(g3)
        self.folder = QLineEdit(os.path.expanduser('~'))
        b = QPushButton('Browse…')
        b.clicked.connect(self._browse)
        self.fname = QLineEdit(p.get('name') or 'hull')
        l3.addWidget(QLabel('Folder'), 0, 0)
        l3.addWidget(self.folder, 0, 1)
        l3.addWidget(b, 0, 2)
        l3.addWidget(QLabel('File name'), 1, 0)
        l3.addWidget(self.fname, 1, 1)
        lay.addWidget(g3)
        lay.addWidget(QLabel('The exported solid is the complete hull (main hull united with bulb, skegs and boss), '
                             'closed by deck and transom. Every file is read back and checked for closure.'))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        lay.addWidget(self.log, 1)
        bl = QHBoxLayout()
        bl.addStretch(1)
        self.go = QPushButton('Export')
        self.go.clicked.connect(self.run)
        c = QPushButton('Close')
        c.clicked.connect(self.close)
        bl.addWidget(self.go)
        bl.addWidget(c)
        lay.addLayout(bl)
        self.worker = None

    def _lvl(self, v):
        L = self.p['main']['Lpp']
        self.level_lbl.setText('%d: chordal deviation %.0f mm' % (v, LEVELS[v] * L * 1000))

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, 'Export folder', self.folder.text())
        if d:
            self.folder.setText(d)

    def run(self):
        fm = [f for f, c in (('iges', self.iges), ('stl', self.stl)) if c.isChecked()]
        if not fm:
            return
        self.go.setEnabled(False)
        self.log.appendPlainText('Building the CAD solid…')
        self.worker = ExportWorker(self.p, self.folder.text(), fm, self.units.currentText(), self.level.value(),
                                   self.fname.text())
        self.worker.message.connect(self.log.appendPlainText)
        self.worker.finished_ok.connect(self.done)
        self.worker.finished.connect(lambda: self.go.setEnabled(True))
        self.worker.start()

    def done(self, rep):
        h = rep.get('hydro_exact') or {}
        if 'iges_check' in rep:
            c = rep['iges_check']
            self.log.appendPlainText('IGES read-back: %d faces, %d free edges -> %s' % (
                c.get('faces', 0), c.get('free_edges', -1), 'closed' if c.get('closed') else 'NOT closed'))
        if 'stl_check' in rep:
            c = rep['stl_check']
            self.log.appendPlainText('STL read-back: %d triangles, %d open edges, %d non-manifold edges' % (
                c['triangles'], c['open_edges'], c['nonmanifold_edges']))
        if h:
            self.log.appendPlainText('Exact solid below T: volume %.3f m³, wetted surface %.2f m², LCB x %.3f m' % (
                h['volume'], h['wetted'], h['LCB_x']))
        for w in rep.get('warnings', []):
            self.log.appendPlainText('warning: ' + w)
        self.log.appendPlainText('done in %.1f s' % rep['seconds'])
