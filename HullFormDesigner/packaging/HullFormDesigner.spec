# PyInstaller spec: one-folder build of the Parametric Hull Form Designer.
# Build from the HullFormDesigner folder:  pyinstaller --noconfirm packaging/HullFormDesigner.spec
import os
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs, collect_submodules, collect_data_files

ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))
datas = [(os.path.join(ROOT, 'references'), 'references'),
         (os.path.join(ROOT, 'hullform', 'presets_fitted.json'), 'hullform'),
         (os.path.join(ROOT, 'README.md'), '.'),
         (os.path.join(ROOT, 'docs'), 'docs')]
binaries, hidden = [], ['hullform', 'hullform_gui', 'OpenGL', 'OpenGL.GL']
# OCP: everything except the VTK visualisation bindings (IVtk*), which would pull in ~600 MB of VTK
d, b, h = collect_all('OCP', filter_submodules=lambda n: 'IVtk' not in n)
datas += d
binaries += [x for x in b if 'IVtk' not in os.path.basename(x[0])]
hidden += h
for pkg in ('OpenGL',):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hidden += h
# pyqtgraph: skip the examples and the notebook/remote modules (importing them needs a display)
hidden += collect_submodules('pyqtgraph', filter=lambda n: not any(
    k in n for k in ('examples', 'jupyter', 'multiprocess', 'canvas', 'flowchart')))
datas += collect_data_files('pyqtgraph', excludes=['examples/**'])
# the CAD kernel's own shared libraries (OCCT, TBB, FreeType ...) live next to the OCP package
for pkg in ('cadquery_ocp', 'cadquery_ocp_proxy'):
    try:
        binaries += collect_dynamic_libs(pkg)
    except Exception:
        pass
for libdir in ('cadquery_ocp.libs',):
    import site
    for sp in site.getsitepackages():
        p = os.path.join(sp, libdir)
        if os.path.isdir(p):
            binaries += [(os.path.join(p, f), libdir) for f in os.listdir(p)]

a = Analysis([os.path.join(ROOT, 'main.py')], pathex=[ROOT], binaries=binaries, datas=datas,
             hiddenimports=hidden, excludes=['matplotlib', 'tkinter', 'vtk', 'vtkmodules', 'PySide6.QtWebEngineCore',
                                             'PySide6.Qt3DCore', 'PySide6.QtQuick', 'PySide6.QtQml'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='HullFormDesigner', console=False,
          icon=None)
coll = COLLECT(exe, a.binaries, a.datas, name='HullFormDesigner')
