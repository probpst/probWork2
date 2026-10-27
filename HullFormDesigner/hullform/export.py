"""IGES / STL export with closure verification and hydrostatics report."""
import os
import time

from .build import Design
from . import cad
from .mesh import write_stl, read_stl, merge

# STL chordal deviation as a fraction of Lpp, per resolution level
LEVELS = {1: 2e-3, 2: 1e-3, 3: 5e-4, 4: 2.5e-4, 5: 1.25e-4}


def safe_name(s):
    return ''.join(c if c.isalnum() or c in '-_.' else '_' for c in s) or 'hull'


def export(p, folder, formats=('iges', 'stl'), units='m', level=3, stl_binary=True, iges_mode='faces',
           name=None, design=None, log=print):
    """Write the complete hull (main hull united with the add-on bodies) as one closed solid."""
    t0 = time.time()
    os.makedirs(folder, exist_ok=True)
    base = safe_name(name or p.get('name') or 'hull')
    d = design or Design(p, correct=True)
    rep = dict(files=[], warnings=list(d.warnings))
    L, T = d.hull.L, d.hull.T
    if cad.HAVE_OCC:
        solid, srep = cad.build_solid(d, log=log)
        rep['solid'] = srep
        rep['warnings'] += srep['warnings']
        if not (srep['valid'] and srep['closed']):
            rep['warnings'].append('CAD solid is not valid/closed')
        rep['hydro_exact'] = cad.submerged(solid, T, L)
        if 'iges' in formats:
            path = os.path.join(folder, base + '.igs')
            cad.write_iges(solid, path, units, iges_mode)
            rep['files'].append(path)
            rep['iges_check'] = cad.verify_iges(path, units)
            if not rep['iges_check'].get('closed'):
                rep['warnings'].append('IGES read-back: %s free edges' % rep['iges_check'].get('free_edges'))
        if 'stl' in formats:
            m = cad.tessellate(solid, LEVELS[level] * L)
            if units == 'mm':
                m.V = m.V * 1000.0
            path = os.path.join(folder, base + '.stl')
            write_stl(path, m, stl_binary, base)
            rep['files'].append(path)
            rep['stl_check'] = read_stl(path).edge_report()
    else:
        rep['warnings'].append('CAD kernel not available: STL from the preview mesh, bodies not united')
        if 'stl' in formats:
            m = merge(d.meshes())
            if units == 'mm':
                m.V = m.V * 1000.0
            path = os.path.join(folder, base + '.stl')
            write_stl(path, m, stl_binary, base)
            rep['files'].append(path)
            rep['stl_check'] = read_stl(path).edge_report()
    h = d.hydrostatics()
    h.pop('SAC', None)
    rep['hydro'] = h
    rep['seconds'] = time.time() - t0
    for f in rep['files']:
        log('wrote %s' % f)
    return rep
