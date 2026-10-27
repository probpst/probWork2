"""Presets: parameter sets fitted to six public benchmark hulls (see tools/fit_presets.py).

They are representative parametric approximations of the benchmark geometries, not the original
lines; the fit quality is listed in docs/ and by `python -m hullform presets`.
"""
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
ORDER = ['KCS', 'DTC', 'KVLCC2', 'JBC', 'KLNG2', 'DTMB5415']


def _load():
    path = os.path.join(_HERE, 'presets_fitted.json')
    if not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    return {k: data[k] for k in ORDER if k in data}


PRESETS = _load()
