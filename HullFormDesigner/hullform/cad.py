"""Exact CAD model with the OpenCASCADE kernel (cadquery-ocp): B-spline surfaces, closed solid,
union with the add-on bodies, optional junction fillet, IGES and STL output, exact hydrostatics.

Without OCP the program still runs (preview, mesh hydrostatics, STL from the preview mesh).
"""
import numpy as np

try:
    from OCP.gp import gp_Pnt, gp_Trsf, gp_Ax2, gp_Dir, gp_Vec
    from OCP.TColgp import TColgp_Array2OfPnt, TColgp_HArray1OfPnt
    from OCP.TColStd import TColStd_Array1OfReal, TColStd_Array1OfInteger
    from OCP.Geom import Geom_BSplineSurface
    from OCP.GeomAPI import GeomAPI_PointsToBSplineSurface, GeomAPI_Interpolate
    from OCP.GeomAbs import GeomAbs_C2
    from OCP.BRepBuilderAPI import (BRepBuilderAPI_MakeFace, BRepBuilderAPI_Sewing, BRepBuilderAPI_MakeEdge,
                                    BRepBuilderAPI_MakeWire, BRepBuilderAPI_Transform,
                                    BRepBuilderAPI_MakeVertex)
    from OCP.BRepFill import BRepFill
    from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse, BRepAlgoAPI_Common
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.BRep import BRep_Tool, BRep_Builder
    from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_SHELL, TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer, TopExp
    from OCP.TopoDS import TopoDS, TopoDS_Compound
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopTools import TopTools_ListOfShape, TopTools_IndexedDataMapOfShapeListOfShape
    from OCP.ShapeFix import ShapeFix_Solid, ShapeFix_Shape
    from OCP.IGESControl import IGESControl_Writer, IGESControl_Reader
    from OCP.Interface import Interface_Static
    from OCP.ShapeAnalysis import ShapeAnalysis_FreeBounds
    from OCP.TopTools import TopTools_HSequenceOfShape
    from OCP.TopTools import TopTools_ShapeMapHasher  # noqa: F401
    HAVE_OCC = True
except Exception:          # pragma: no cover
    HAVE_OCC = False

from .mesh import TriMesh


def _pnt(v):
    return gp_Pnt(float(v[0]), float(v[1]), float(v[2]))


def _faces(shape):
    out = []
    e = TopExp_Explorer(shape, TopAbs_FACE)
    while e.More():
        out.append(TopoDS.Face_s(e.Current()))
        e.Next()
    return out


def _props(shape, kind='volume', eps=1e-7):
    # adaptive integration: the default Gauss scheme is ~1 % off on large B-spline faces
    g = GProp_GProps()
    if kind == 'volume':
        BRepGProp.VolumeProperties_s(shape, g, eps)
    else:
        BRepGProp.SurfaceProperties_s(shape, g, eps)
    return g


def _knots(U):
    vals, mults = [], []
    for k in U:
        if vals and abs(k - vals[-1]) < 1e-12:
            mults[-1] += 1
        else:
            vals.append(float(k))
            mults.append(1)
    kv = TColStd_Array1OfReal(1, len(vals))
    km = TColStd_Array1OfInteger(1, len(vals))
    for i, (a, m) in enumerate(zip(vals, mults)):
        kv.SetValue(i + 1, a)
        km.SetValue(i + 1, m)
    return kv, km


def occ_surface(S):
    P = S['poles']
    nu, nv = P.shape[:2]
    arr = TColgp_Array2OfPnt(1, nu, 1, nv)
    for i in range(nu):
        for j in range(nv):
            arr.SetValue(i + 1, j + 1, _pnt(P[i, j]))
    ku, mu = _knots(S['U'])
    kv, mv = _knots(S['V'])
    return Geom_BSplineSurface(arr, ku, kv, mu, mv, S['p'], S['q'])


def grid_surface(G, tol=None):
    """Bicubic B-spline surface interpolating the grid G (nu, nv, 3)."""
    from .bspline import interp_surface
    return occ_surface(interp_surface(G))


def _mirror_y(shape):
    t = gp_Trsf()
    t.SetMirror(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 1, 0)))
    return BRepBuilderAPI_Transform(shape, t, True).Shape()


def _iso_edges(face):
    """The four boundary edges of a face built on a full surface, keyed by their position."""
    out = []
    e = TopExp_Explorer(face, TopAbs_EDGE)
    while e.More():
        out.append(TopoDS.Edge_s(e.Current()))
        e.Next()
    return out


def _edge_mid(edge):
    c, a, b = BRep_Tool.Curve_s(edge, 0.0, 1.0)
    if c is None:
        return None
    p = c.Value(0.5 * (a + b))
    return np.array([p.X(), p.Y(), p.Z()])


def _polyline_edge(P):
    """Interpolated B-spline edge through points P (k, 3)."""
    P = np.asarray(P, float)
    keep = np.r_[True, np.linalg.norm(np.diff(P, axis=0), axis=1) > 1e-9 * max(np.ptp(P), 1e-9)]
    P = P[keep]
    arr = TColgp_HArray1OfPnt(1, len(P))
    for i, v in enumerate(P):
        arr.SetValue(i + 1, _pnt(v))
    it = GeomAPI_Interpolate(arr, False, 1e-9)
    it.Perform()
    return BRepBuilderAPI_MakeEdge(it.Curve()).Edge()


def main_hull_solid(design, log=print):
    """Closed solid of the main hull: two B-spline side faces, deck, transom."""
    G = design.grid
    L = design.hull.L
    tol = 2e-5 * L
    srf = grid_surface(G)
    f_p = BRepBuilderAPI_MakeFace(srf, 1e-7).Face()
    f_s = TopoDS.Face_s(_mirror_y(f_p))
    # deck: ruled between the deck-edge iso curves; transom: planar between the first sections
    deck_p = BRepBuilderAPI_MakeEdge(srf.VIso(1.0)).Edge()
    deck_s = TopoDS.Edge_s(_mirror_y(deck_p))
    deck = BRepFill.Face_s(deck_p, deck_s)
    # transom: ruled between the port and starboard first sections (a planar face from a wire fails
    # when the sections leave the keel vertically: the two outlines form a cusp)
    tr_p = BRepBuilderAPI_MakeEdge(srf.UIso(0.0)).Edge()
    tr_s = TopoDS.Edge_s(_mirror_y(tr_p))
    faces = {'side': [f_p, f_s], 'deck': [deck]}
    if np.linalg.norm(G[0, -1] - G[0, 0]) > 1e-6 * L:
        faces['transom'] = [BRepFill.Face_s(tr_p, tr_s)]
    sew = BRepBuilderAPI_Sewing(1e-4 * L)
    for fl in faces.values():
        for f in fl:
            sew.Add(f)
    sew.Perform()
    shell = sew.SewedShape()
    return _make_solid(shell), faces


def _make_solid(shape):
    shells = []
    e = TopExp_Explorer(shape, TopAbs_SHELL)
    while e.More():
        shells.append(TopoDS.Shell_s(e.Current()))
        e.Next()
    if not shells:
        return None
    sf = ShapeFix_Solid()
    solid = sf.SolidFromShell(shells[0])
    if _props(solid).Mass() < 0:
        solid.Reverse()
    return solid


def ring_body_solid(body, tol=1e-6):
    """Closed solid of an add-on body: two non-periodic B-spline half surfaces (split at the bottom
    and top of the rings, so there is no seam edge) plus a planar cap at the start ring. The end ring
    must collapse to a point (nose)."""
    R = body.R
    nj = R.shape[1]
    h = nj // 2
    halves = [R[:, :h + 1], np.concatenate([R[:, h:], R[:, :1]], axis=1)]
    faces = []
    caps = []
    for H in halves:
        srf = grid_surface(H)
        faces.append(BRepBuilderAPI_MakeFace(srf, 1e-7).Face())
        caps.append(BRepBuilderAPI_MakeEdge(srf.UIso(0.0)).Edge())
    w = BRepBuilderAPI_MakeWire()
    for e in caps:
        w.Add(e)
    faces.append(BRepBuilderAPI_MakeFace(w.Wire(), True).Face())
    sew = BRepBuilderAPI_Sewing(tol * max(np.ptp(R.reshape(-1, 3), axis=0).max(), 1.0) * 10)
    for f in faces:
        sew.Add(f)
    sew.Perform()
    return _make_solid(sew.SewedShape())


def _thin(R, step):
    idx = np.unique(np.r_[np.arange(0, len(R), step), len(R) - 1])
    return R[idx]


def build_solid(design, fillet=None, log=print):
    """Main hull fused with the add-on bodies; returns (solid, report)."""
    rep = dict(warnings=[])
    hull, hfaces = main_hull_solid(design, log)
    if hull is None:
        raise RuntimeError('main hull did not sew into a closed shell')
    L = design.hull.L
    tools = []
    from .appendages import RingBody
    for b in design.bodies:
        R = _thin(b.R, 2).copy()
        R[-1] = R[-1].mean(0)
        rb = RingBody(b.name, R, b.start, b.end)
        try:
            s = ring_body_solid(rb)
            if _props(s).Mass() < 0:
                s.Reverse()
            tools.append((b.name, s))
        except Exception as ex:            # pragma: no cover
            rep['warnings'].append('%s body failed: %s' % (b.name, ex))
    solid = hull
    origin = {_key(f): 'hull' for f in _faces(hull)}
    # fuse the bodies one at a time; a body that breaks the solid is skipped with a warning
    for name, body in tools:
        fu = BRepAlgoAPI_Fuse()
        a, t = TopTools_ListOfShape(), TopTools_ListOfShape()
        a.Append(solid)
        t.Append(body)
        fu.SetArguments(a)
        fu.SetTools(t)
        fu.SetFuzzyValue(1e-6 * L)
        fu.Build()
        res = fu.Shape() if fu.IsDone() else None
        ok = res is not None and _solid_ok(res)
        if not ok and res is not None:
            fx = ShapeFix_Shape(res)
            fx.Perform()
            res = fx.Shape()
            ok = _solid_ok(res)
        if not ok:
            rep['warnings'].append('union with %s failed; body left out of the solid' % name)
            continue
        new_origin = {}
        for src_name, src in (('?', solid), (name, body)):
            for f in _faces(src):
                nm = origin.get(_key(f), 'hull') if src_name == '?' else name
                mods = _iter(fu.Modified(f))
                if not mods and not fu.IsDeleted(f):
                    new_origin[_key(f)] = nm
                for mo in mods:
                    new_origin[_key(mo)] = nm
        origin = new_origin
        solid = res
    r = design.p['cad']['fillet'] if fillet is None else fillet
    rep['fillet'] = 0.0
    rep['filleted'] = []
    if r > 0 and tools:
        fs, done = fillet_junction(solid, origin, r, [n for n, _ in tools])
        missing = [n for n, _ in tools if n not in done]
        if fs is not None:
            solid = fs
            rep['fillet'] = r
            rep['filleted'] = done
        if missing:
            rep['warnings'].append('junction fillet r = %.3f m not possible for: %s (kept sharp)'
                                   % (r, ', '.join(missing)))
    rep.update(check(solid))
    return solid, rep


def _solid_ok(shape):
    c = check(shape)
    return c['valid'] and c['closed'] and c['volume'] > 0


def _key(shape):
    return shape.HashCode(2 ** 31 - 1) if hasattr(shape, 'HashCode') else hash(shape)


def _iter(lst):
    out = []
    it = lst.cbegin() if hasattr(lst, 'cbegin') else None
    if it is not None:
        while it.More():
            out.append(it.Value())
            it.Next()
        return out
    for s in lst:
        out.append(s)
    return out


def _junction_edges(solid, origin, body=None):
    m = TopTools_IndexedDataMapOfShapeListOfShape()
    TopExp.MapShapesAndAncestors_s(solid, TopAbs_EDGE, TopAbs_FACE, m)
    out = []
    for i in range(1, m.Extent() + 1):
        fl = _iter(m.FindFromIndex(i))
        if len(fl) != 2:
            continue
        o = {origin.get(_key(f), '?') for f in fl}
        others = o - {'hull', '?'}
        if 'hull' in o and len(others) == 1 and (body is None or body in others):
            out.append(TopoDS.Edge_s(m.FindKey(i)))
    return out


def _try_fillet(solid, edges, r):
    if not edges:
        return None
    mk = BRepFilletAPI_MakeFillet(solid)
    for e in edges:
        mk.Add(r, e)
    try:
        mk.Build()
        if not mk.IsDone():
            return None
        s = mk.Shape()
        return s if _solid_ok(s) else None
    except Exception:
        return None


def fillet_junction(solid, origin, r, bodies=None):
    """Constant-radius fillet on the hull/body intersection edges. All bodies at once first, then
    body by body (a bulb whose junction crosses a sharp stem line may fail on its own).
    Returns (solid or None, list of filleted bodies)."""
    s = _try_fillet(solid, _junction_edges(solid, origin), r)
    if s is not None:
        return s, sorted({v for v in origin.values() if v not in ('hull', '?')})
    done = []
    for b in bodies or []:
        s2 = _try_fillet(solid, _junction_edges(solid, origin, b), r)
        if s2 is not None:
            solid = s2
            done.append(b)
            # face identities change after a fillet: map the remaining bodies' faces again by area match
            origin = _reorigin(solid, origin)
    return (solid if done else None), done


def _reorigin(solid, origin):
    # faces untouched by the fillet keep their hash; new fillet faces default to unknown
    return {_key(f): origin.get(_key(f), '?') for f in _faces(solid)}


def check(solid):
    ana = BRepCheck_Analyzer(solid)
    closed = True
    e = TopExp_Explorer(solid, TopAbs_SHELL)
    while e.More():
        sh = TopoDS.Shell_s(e.Current())
        closed &= BRep_Tool.IsClosed_s(sh)
        e.Next()
    return dict(valid=bool(ana.IsValid()), closed=bool(closed), volume=float(_props(solid).Mass()),
                area=float(_props(solid, 'surface').Mass()), faces=len(_faces(solid)))


def submerged(solid, T, L):
    """Displaced volume, centre and wetted surface below z = T. Exact Boolean with the half space;
    if OCC fails on the cut (it can, when the plane grazes a face), the solid is tessellated finely
    and the triangles are clipped exactly instead (method 'mesh')."""
    from .hydro import clipped_volume, clip_below
    m = tessellate(solid, 2e-4 * L, 0.15)
    v_m, mom = clipped_volume(m, T)
    P = clip_below(m.V[m.F], T)
    S_m = float(0.5 * np.linalg.norm(np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]), axis=1).sum())
    mesh_res = dict(volume=v_m, LCB_x=float(mom[0] / v_m), VCB=float(mom[2] / v_m), wetted=S_m, method='mesh')
    try:
        big = 10 * L
        box = BRepPrimAPI_MakeBox(gp_Pnt(-big, -big, -big), gp_Pnt(big, big, T)).Shape()
        com = BRepAlgoAPI_Common(solid, box)
        com.Build()
        sub = com.Shape()
        g = _props(sub)
        if not com.IsDone() or abs(g.Mass() / v_m - 1) > 0.01:
            return mesh_res
        c = g.CentreOfMass()
        S = 0.0
        for f in _faces(sub):
            gf = _props(f, 'surface')
            cf = gf.CentreOfMass()
            if abs(cf.Z() - T) < 1e-7 * L and BRep_Tool.Surface_s(f).DynamicType().Name() == 'Geom_Plane':
                continue
            S += gf.Mass()
        return dict(volume=g.Mass(), LCB_x=c.X(), VCB=c.Z(), wetted=S, method='exact')
    except Exception:
        return mesh_res


def tessellate(solid, lin, ang=0.25):
    """Watertight triangulation: one BRepMesh pass on the whole solid (shared edges get one
    discretisation), then nodes are merged topologically through the edge polygons of the adjacent
    faces (union-find), plus a tiny coordinate weld for poles and degenerate edges."""
    BRepMesh_IncrementalMesh(solid, lin, False, ang, True)
    V, F, n = [], [], 0
    base = {}
    tri_of = {}
    for f in _faces(solid):
        loc = TopLoc_Location()
        t = BRep_Tool.Triangulation_s(f, loc)
        if t is None:
            continue
        tr = loc.Transformation()
        rev = f.Orientation() == 1
        base[_key(f)] = n
        tri_of[_key(f)] = (t, loc)
        for i in range(1, t.NbNodes() + 1):
            p = t.Node(i).Transformed(tr)
            V.append((p.X(), p.Y(), p.Z()))
        for i in range(1, t.NbTriangles() + 1):
            a, b, c = t.Triangle(i).Get()
            F.append((a - 1 + n, c - 1 + n, b - 1 + n) if rev else (a - 1 + n, b - 1 + n, c - 1 + n))
        n += t.NbNodes()
    V = np.array(V)
    parent = np.arange(len(V))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    m = TopTools_IndexedDataMapOfShapeListOfShape()
    TopExp.MapShapesAndAncestors_s(solid, TopAbs_EDGE, TopAbs_FACE, m)
    for k in range(1, m.Extent() + 1):
        edge = TopoDS.Edge_s(m.FindKey(k))
        lists = []
        for f in _iter(m.FindFromIndex(k)):
            fk = _key(f)
            if fk not in tri_of:
                continue
            t, loc = tri_of[fk]
            poly = BRep_Tool.PolygonOnTriangulation_s(edge, t, loc)
            if poly is None:
                continue
            nodes = poly.Nodes()
            lists.append([base[fk] + nodes.Value(i) - 1 for i in range(nodes.Lower(), nodes.Upper() + 1)])
        for other in lists[1:]:
            if len(other) != len(lists[0]):
                continue
            a0 = lists[0]
            same = np.linalg.norm(V[a0[0]] - V[other[0]]) <= np.linalg.norm(V[a0[0]] - V[other[-1]])
            for a, b in zip(a0, other if same else other[::-1]):
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[rb] = ra
    roots = np.array([find(i) for i in range(len(V))])
    F = roots[np.array(F)]
    msh = TriMesh(V, F, 'hull')
    ext = max(np.ptp(V, axis=0).max(), 1e-9)
    return msh.welded(tol=1e-9 / 1.0).orient_outward() if ext > 0 else msh


def write_iges(shape, path, units='m', mode='faces'):
    Interface_Static.SetCVal_s('write.iges.unit', 'M' if units == 'm' else 'MM')
    Interface_Static.SetIVal_s('write.iges.brep.mode', 0 if mode == 'faces' else 1)
    w = IGESControl_Writer('M' if units == 'm' else 'MM', 0 if mode == 'faces' else 1)
    if units == 'mm':
        t = gp_Trsf()
        t.SetScaleFactor(1000.0)
        shape = BRepBuilderAPI_Transform(shape, t, True).Shape()
    w.AddShape(shape)
    w.ComputeModel()
    return bool(w.Write(path))


def verify_iges(path, units='m'):
    """Read back an IGES file, sew all faces and report closure and volume."""
    r = IGESControl_Reader()
    if r.ReadFile(path) != 1:
        return dict(ok=False, closed=False)
    r.TransferRoots()
    s = r.OneShape()
    sew = BRepBuilderAPI_Sewing(1e-3 if units == 'm' else 1.0)
    for f in _faces(s):
        sew.Add(f)
    sew.Perform()
    sh = sew.SewedShape()
    free = sew.NbFreeEdges()
    solid = _make_solid(sh)
    vol = _props(solid).Mass() if solid is not None else 0.0
    return dict(ok=True, faces=len(_faces(s)), free_edges=int(free), closed=free == 0, volume=float(vol))
