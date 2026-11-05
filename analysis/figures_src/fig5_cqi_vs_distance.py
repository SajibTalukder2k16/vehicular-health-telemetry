#!/usr/bin/env python3
"""Fig. 5 — Mean uplink CQI vs distance to the serving site (calibration).
Run: python3 fig5_cqi_vs_distance.py
"""
import math

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from _shared import load_vec, save, towers_from_ini, trace_positions

# ===== STYLE — edit freely ==================================================
BLUE, RED = '#1f77b4', '#d62728'      # matplotlib tab:blue / tab:red
FONT_FAMILY = ['Liberation Serif', 'Times New Roman', 'Times', 'DejaVu Serif']
FS = 9
SERIES = (('DcDriveAtt', 'simulations/dc_case/towers_dc_att.ini',
           'osm/dc_ego.bonnmotion', BLUE, 'o', '-', 'Urban (UMa)'),
          ('VaDriveAtt', 'simulations/va_case/towers_va_att.ini',
           'osm/va_ego.bonnmotion', RED, 's', '--', 'Rural (RMa)'))
BINS = np.logspace(np.log10(50), np.log10(6000), 14)   # distance bins (m)
plt.rcParams.update({
    'font.family': 'serif', 'font.serif': FONT_FAMILY,
    'font.size': FS, 'text.color': 'black', 'axes.labelcolor': 'black',
    'axes.edgecolor': 'black', 'axes.linewidth': 0.8,
    'xtick.color': 'black', 'ytick.color': 'black',
    'xtick.direction': 'in', 'ytick.direction': 'in',
    'grid.color': '#cccccc', 'grid.linewidth': 0.5,
    'figure.facecolor': 'white', 'savefig.facecolor': 'white',
    'pdf.fonttype': 42, 'ps.fonttype': 42,
})
# ============================================================================

fig, ax = plt.subplots(figsize=(3.5, 2.9))
for case, tow_ini, trace, color, marker, ls, label in SERIES:
    towers = towers_from_ini(tow_ini)
    tt, tx, ty = trace_positions(trace)
    ct, cv = load_vec(case, 'servingCell:vector', seeds=[0])[0]
    qt, qv = load_vec(case, 'averageCqiUl:vector', seeds=[0])[0]
    px = np.interp(qt, tt, tx)
    py = np.interp(qt, tt, ty)
    cell = np.interp(qt, ct, cv)
    cellidx = np.clip(np.round(cell).astype(int) - 1, 0, len(towers) - 1)
    dist = np.hypot(px - towers[cellidx, 0], py - towers[cellidx, 1])
    mids, means = [], []
    for lo, hi in zip(BINS[:-1], BINS[1:]):
        m = (dist >= lo) & (dist < hi)
        if m.sum() >= 5:
            mids.append(math.sqrt(lo * hi))
            means.append(qv[m].mean())
    ax.plot(np.array(mids) / 1000, means, color=color, marker=marker, ls=ls,
            lw=1.3, ms=5, markerfacecolor='white', markeredgewidth=1.0,
            label=label)
ax.set_xscale('log')
ax.set_xticks([0.1, 0.3, 1, 3], ['0.1', '0.3', '1', '3'])
ax.set_xlabel('Distance to serving site (km)')
ax.set_ylabel('Mean uplink CQI')
ax.set_ylim(0, 15.5)
ax.grid(True, axis='y', alpha=0.6)
ax.legend(loc='upper right', frameon=True, fontsize=FS - 1.5,
          edgecolor='black', fancybox=False)
for spine in ax.spines.values():
    spine.set_visible(True)
save(fig, 'fig5_cqi_vs_distance')
