"""Command line: python -m hullform <command> ...

  presets                                   list the presets
  build  [--preset P] [--params file.json] [--set path=value ...] [--out folder]
         [--iges] [--stl] [--units m|mm] [--level 1-5] [--name NAME] [--save-params]
  hydro  [--preset P] [--params file.json] [--set ...]   print hydrostatics
"""
import argparse
import json
import sys

from .params import new_params, load_json, save_json, put, SPEC
from .presets import PRESETS


def _params(a):
    p = load_json(a.params) if a.params else new_params(a.preset)
    for s in a.set or []:
        k, v = s.split('=', 1)
        if k not in SPEC:
            sys.exit('unknown parameter %s' % k)
        u = SPEC[k]['unit']
        if u == 'bool':
            v = v.lower() in ('1', 'true', 'yes', 'on')
        elif u != 'sel':
            v = float(v)
        put(p, k, v)
    return p


def main(argv=None):
    ap = argparse.ArgumentParser(prog='hullform')
    sub = ap.add_subparsers(dest='cmd')
    sub.add_parser('presets')
    for c in ('build', 'hydro'):
        b = sub.add_parser(c)
        b.add_argument('--preset', default='KCS')
        b.add_argument('--params')
        b.add_argument('--set', action='append')
        if c == 'build':
            b.add_argument('--out', default='out')
            b.add_argument('--iges', action='store_true')
            b.add_argument('--stl', action='store_true')
            b.add_argument('--units', default='m', choices=['m', 'mm'])
            b.add_argument('--level', type=int, default=3)
            b.add_argument('--name')
            b.add_argument('--save-params', action='store_true')
    a = ap.parse_args(argv)
    if a.cmd == 'presets':
        for k, v in PRESETS.items():
            print('%-9s %s  (fit rms %.3f B/2)' % (k, v['label'], v.get('rms', float('nan'))))
        return
    if a.cmd in ('build', 'hydro'):
        p = _params(a)
        from .build import Design
        d = Design(p, correct=True)
        h = d.hydrostatics()
        h.pop('SAC', None)
        print(json.dumps({k: round(float(v), 5) for k, v in h.items()}, indent=1))
        for w in d.warnings:
            print('warning:', w)
        if a.cmd == 'build':
            fm = [f for f, on in (('iges', a.iges), ('stl', a.stl)) if on] or ['iges', 'stl']
            from .export import export
            rep = export(p, a.out, fm, a.units, a.level, name=a.name, design=d)
            for k in ('iges_check', 'stl_check', 'hydro_exact', 'warnings'):
                if k in rep:
                    print(k, rep[k])
            if a.save_params:
                save_json(p, '%s/%s_params.json' % (a.out, a.name or p['name']))
        return
    ap.print_help()


if __name__ == '__main__':
    main()
