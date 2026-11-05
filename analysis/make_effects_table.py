#!/usr/bin/env python3
"""Main-effects table (Table of the manuscript): differences with 95% CIs.
Writes main_effects.csv and prints the table.
Run: python3 make_effects_table.py
"""
import math
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
runs = pd.read_csv(os.path.join(HERE, 'runs_detailed.csv'))
fam = runs[runs.config.isin(['Urban', 'Rural'])].copy()
for c in ('isd', 'speed', 'bgues', 'payload'):
    fam[c] = pd.to_numeric(fam[c], errors='coerce')
fam['camlink'] = fam['camlink'].str.strip('"\\\\')

rows = []


def eff(name, a, b):
    # delivery_e2e (generated-to-received), not the old rcv/sentToCloud ratio:
    # the latter excludes sensor-link loss from its denominator, which flatters
    # the BLE edge by >13 pp and reversed the sign of the edge-type effect.
    da, db = a['delivery_e2e'], b['delivery_e2e']
    d = da.mean() - db.mean()
    ci = 1.96 * math.sqrt(da.var() / len(da) + db.var() / len(db))
    ta, tb = a['timely_vitals'], b['timely_vitals']
    dt = ta.mean() - tb.mean()
    cit = 1.96 * math.sqrt(ta.var() / len(ta) + tb.var() / len(tb))
    rows.append((name, 100 * d, 100 * ci, 100 * dt, 100 * cit))
    print(f'{name:42s} delivery {100*d:+6.2f} ± {100*ci:.2f} pp   '
          f'timely vitals {100*dt:+6.2f} ± {100*cit:.2f} pp')


r = fam[fam.config == 'Rural']
u = fam[fam.config == 'Urban']
eff('rural ISD 10 km vs 5 km', r[r.isd == 10000], r[r.isd == 5000])
eff('urban ISD 2 km vs 0.5 km', u[u.isd == 2000], u[u.isd == 500])
eff('payload 60 KiB vs 4 KiB (rural)', r[r.payload == 60], r[r.payload == 4])
eff('payload 60 KiB vs 4 KiB (urban)', u[u.payload == 60], u[u.payload == 4])
eff('speed 105 vs 30 km/h (rural)', r[r.speed == 105], r[r.speed == 30])
eff('speed 105 vs 30 km/h (urban)', u[u.speed == 105], u[u.speed == 30])
eff('load 20 vs 0 bg UEs (all)', fam[fam.bgues == 20], fam[fam.bgues == 0])
eff('smartphone(BLE) vs embedded(wired) edge',
    fam[fam.camlink == 'BleLink'], fam[fam.camlink == 'WiredLink'])

pd.DataFrame(rows, columns=['effect', 'delivery_pp', 'delivery_ci95',
                            'timely_pp', 'timely_ci95']).to_csv(
    os.path.join(HERE, 'main_effects.csv'), index=False)
print('\nwrote main_effects.csv')
