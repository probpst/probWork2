"""Fill the preset table of README.md from hullform/presets_fitted.json and the reference files."""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
from hullform.presets import PRESETS  # noqa: E402
from hullform.reference import Reference  # noqa: E402

rows = ['| Preset | Type | Lpp × B × T [m] | Cb ref / gen | LCB % ref / gen | Cm ref / gen | Cwp ref / gen | '
        'Body-plan RMS |', '|---|---|---|---|---|---|---|---|']
for k, v in PRESETS.items():
    r = Reference(os.path.join(HERE, '..', 'references', k + '.npz'))
    h = r.meta['hydro']
    vals = v['values']
    rows.append('| %s | %s | %.1f × %.2f × %.2f | %.4f / %.4f | %+.2f / %+.2f | %.4f / %.4f | %.4f / %.4f | %.1f %% |' % (
        k, v['label'], vals['main.Lpp'], vals['main.B'], vals['main.T'], h['Cb'], v['cb'], h['LCB_pct'], v['lcb'],
        h['Cm'], v['cm'], h['Cwp'], v['cwp'], 100 * v['rms']))
table = '\n'.join(rows)
path = os.path.join(HERE, '..', 'README.md')
s = open(path, encoding='utf-8').read()
s = re.sub(r'(## Presets fitted to the supplied hulls\n\n)(PRESET_TABLE|\| Preset.*?)(\n\nBody-plan RMS)',
           lambda m: m.group(1) + table + m.group(3), s, flags=re.S)
open(path, 'w', encoding='utf-8').write(s)
print(table)
