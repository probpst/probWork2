"""Start the Parametric Hull Form Designer GUI.

`HullFormDesigner presets|build|hydro ...` runs the command line instead (same as python -m hullform)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] in ('presets', 'build', 'hydro'):
        from hullform.__main__ import main as cli
        sys.exit(cli(sys.argv[1:]))
    from hullform_gui.app import main
    sys.exit(main())
