"""Print the parameter schema as a Markdown table (docs/Parameters.md)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from hullform.params import SCHEMA  # noqa: E402

UNIT = {'m': 'm', 'deg': 'deg', '-': '–', 'L': '× Lpp', 'B2': '× B/2', 'T': '× T', 'D': '× D', 'pct': '% Lpp',
        'bool': 'on/off', 'sel': 'choice'}
print('| Path | Label | Unit | Default | Range | Step | Abbr. | Notes |')
print('|---|---|---|---|---|---|---|---|')
for path, d, label, unit, lo, hi, step, abbr, hint in SCHEMA:
    rng = ' / '.join(lo) if unit == 'sel' else ('' if lo is None else '%g – %g' % (lo, hi))
    print('| `%s` | %s | %s | %s | %s | %s | %s | %s |' % (path, label, UNIT[unit], d, rng,
                                                        '' if step is None else '%g' % step, abbr, hint))
