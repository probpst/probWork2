import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from hullform.params import SCHEMA, SPEC, defaults, new_params  # noqa: E402
from hullform.curves import end_fullness, solve_b, fillet_polyline  # noqa: E402
from hullform.sections import sigma, quadrant_shape  # noqa: E402
from hullform.hull import HullForm  # noqa: E402
from hullform.build import Design  # noqa: E402
from hullform.mesh import TriMesh, hull_mesh  # noqa: E402
from hullform import hydro, cad  # noqa: E402
from hullform.presets import PRESETS  # noqa: E402

HERE = os.path.dirname(__file__)
needs_occ = pytest.mark.skipif(not cad.HAVE_OCC, reason='cadquery-ocp not installed')


def test_schema_unique_and_defaults_in_range():
    abbr = [e[7].lower() for e in SCHEMA]
    assert len(abbr) == len(set(abbr))
    for path, e in SPEC.items():
        if e['unit'] in ('bool', 'sel'):
            continue
        assert e['lo'] <= e['default'] <= e['hi'], path


def test_end_curve_inverse():
    for a in (0.6, 1.0, 1.7):
        for f in (0.55, 0.7, 0.85):
            b = solve_b(f, a)
            assert abs(end_fullness(a, b) - f) < 1e-8


def test_quadrant_fullness():
    assert abs(sigma(2.0, 2.0) - np.pi / 4) < 1e-12           # circle
    for sig in (0.3, 0.5, 0.7, 0.95):
        n, m = quadrant_shape(np.array([0.6]), np.array([sig]))
        assert abs(sigma(n, m)[0] - sig) < 1e-6 and m[0] >= 1.0


def test_fillet_polyline_tangent():
    P = fillet_polyline([(0, 0), (10, 0), (10, 10)], [0, 3, 0])
    assert np.allclose(P[0], [0, 0]) and np.allclose(P[-1], [10, 10])
    d = np.linalg.norm(P - [7, 3], axis=1)
    arc = (P[:, 0] > 7 - 1e-9) & (P[:, 1] < 3 + 1e-9)
    assert np.allclose(d[arc], 3.0, atol=1e-6)


def test_main_hull_hits_targets_and_is_closed():
    p = defaults()
    p['bulb']['on'] = False
    p['boss']['on'] = False
    d = Design(p)
    m = d.meshes()[0]
    assert m.edge_report()['open_edges'] == 0
    h = d.hydrostatics()
    assert abs(h['Cb'] - p['form']['Cb']) < 0.003
    assert abs(h['LCB_pct'] - p['form']['LCB']) < 0.1
    assert abs(h['Cm'] - p['form']['Cm']) < 0.003
    assert abs(h['Cwp'] - p['form']['Cwp']) < 0.005


def test_union_counting_two_boxes():
    def box(x0, x1):
        V = np.array([[x0, -1, 0], [x1, -1, 0], [x1, 1, 0], [x0, 1, 0],
                      [x0, -1, 2], [x1, -1, 2], [x1, 1, 2], [x0, 1, 2]], float)
        F = [[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4],
             [1, 2, 6], [1, 6, 5], [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]]
        return TriMesh(V, F).orient_outward()
    r = hydro.hydrostatics([box(0, 4), box(2, 6)], T=1.0, L=6, B=2, nx=601, nz=50)
    assert abs(r['volume'] - 12.0) < 0.05                     # union 6 x 2 x 1, not 16


def test_complete_hull_cb_correction():
    p = defaults()
    d = Design(p, correct=True)
    h = d.hydrostatics(nx=161, nz=100)
    assert abs(h['Cb'] - p['form']['Cb']) < 0.002
    assert abs(h['LCB_pct'] - p['form']['LCB']) < 0.05


@pytest.mark.parametrize('name', list(PRESETS))
def test_presets_closed_and_close_to_reference(name):
    from hullform.reference import Reference
    p = new_params(name)
    d = Design(p, correct=True)
    for m in d.meshes():
        assert m.edge_report()['open_edges'] == 0
    ref = Reference(os.path.join(HERE, '..', 'references', name + '.npz'))
    h = d.hydrostatics(nx=161, nz=100)
    rh = ref.meta['hydro']
    assert abs(h['Cb'] - rh['Cb']) < 0.004
    assert abs(h['LCB_pct'] - rh['LCB_pct']) < 0.15
    assert PRESETS[name]['rms'] < 0.06


def test_twin_skeg_has_tunnel():
    if 'KLNG2' not in PRESETS:
        pytest.skip('preset missing')
    d = Design(new_params('KLNG2'))
    T = d.hull.T
    W, H = hydro.sections(d.meshes(), [0.06 * d.hull.L], [0.1 * T])
    _, _, iv = hydro.line_widths(np.concatenate([hydro._cut(m.V, m.F, 0.06 * d.hull.L) for m in d.meshes()]),
                                 [0.1 * T])
    assert len(iv[0]) == 2                                   # two skegs, water in between


@needs_occ
@pytest.mark.parametrize('name', [None] + list(PRESETS))
def test_cad_export_closed(tmp_path, name):
    from hullform.export import export
    p = new_params(name) if name else defaults()
    rep = export(p, str(tmp_path), ('iges', 'stl'), log=lambda *a: None)
    assert rep['solid']['valid'] and rep['solid']['closed']
    assert rep['iges_check']['closed']
    assert rep['stl_check']['open_edges'] == 0 and rep['stl_check']['nonmanifold_edges'] == 0
    # exact (CAD) and mesh displacement agree
    assert abs(rep['hydro_exact']['volume'] / rep['hydro']['volume'] - 1) < 0.006
