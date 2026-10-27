"""Headless screenshot of the GUI: xvfb-run -s '-screen 0 1700x1000x24' python tools/gui_screenshot.py out.png [preset] [tab]"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from PySide6.QtWidgets import QApplication  # noqa: E402
from hullform_gui.app import MainWindow, STYLE  # noqa: E402

app = QApplication(sys.argv)
app.setStyle('Fusion')
app.setStyleSheet(STYLE)
w = MainWindow()
if len(sys.argv) > 2:
    i = w.preset.findData(sys.argv[2])
    w.preset.setCurrentIndex(i)
    w.apply_preset(i)
if len(sys.argv) > 3:
    w.tabs.setCurrentIndex(int(sys.argv[3]))
w.resize(1700, 1000)
w.show()
t = time.time()
while time.time() - t < 90:
    app.processEvents()
    time.sleep(0.05)
    if w.hydro is not None and not w.workers:
        break
w.view.preset_view('Iso')
for _ in range(20):
    app.processEvents()
    time.sleep(0.05)
w.grab().save(sys.argv[1])
print('saved', sys.argv[1], 'hydro', w.hydro is not None)
for wk in list(w.workers):
    wk.wait(60000)
