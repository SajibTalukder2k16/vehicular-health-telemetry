#!/usr/bin/env python3
"""Fig. 4 — Age of Information of vitals at the cloud, urban vs rural (seed 0).

The AoI staircase runs over the full configured observation window, so a final
outage that never ends before the cutoff is shown at its true height. The rural
panel also carries the superseded site selection (all operators pooled, 8
densest clusters of 88) as a dashed curve, because that selection -- not the
cell data -- is what produced the multi-minute staleness reported earlier.

Run: python3 fig4_aoi_timeseries.py
"""
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared import aoi_series, aoi_stats, load_vec, save, sim_time_limit

# ===== STYLE — edit freely ==================================================
BLUE, RED, GREY = '#1f77b4', '#d62728', '#8c8c8c'
FONT_FAMILY = ['Liberation Serif', 'Times New Roman', 'Times', 'DejaVu Serif']
FS = 9
LW = 1.0
BUDGET_S = 10                          # vitals freshness budget (s)
YLIM = (0.01, 400)                     # log scale range (s)
SEED = 0
DC_INI = 'simulations/dc_case/omnetpp.ini'
VA_INI = 'simulations/va_case/omnetpp.ini'
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


def curve(config, ini):
    """Full-horizon AoI staircase and its summary stats for one config."""
    horizon = sim_time_limit(ini)
    t, d = load_vec(config, 'e2eDelayVitals:vector', seeds=[SEED])[0]
    xs, ys = aoi_series(t, d, horizon)
    return xs, ys, aoi_stats(t, d, horizon, BUDGET_S)


fig, axes = plt.subplots(2, 1, figsize=(7.0, 4.2), sharex=False)

panels = [
    (axes[0], DC_INI, 'DcDriveAtt', BLUE,
     '(a) Urban (Washington, DC), one operator', None),
    (axes[1], VA_INI, 'VaDriveAtt', RED,
     '(b) Rural (Virginia), one operator', 'VaDriveLegacy8'),
]

for ax, ini, cfg, color, label, legacy in panels:
    xs, ys, st = curve(cfg, ini)
    if legacy:                       # superseded selection, for contrast
        lx, ly, lst = curve(legacy, ini)
        ax.plot(lx, ly, color=GREY, lw=LW, ls='--',
                label=f'superseded 8-of-88-site selection '
                      f'(peak {lst["peak"]:.0f} s, {lst["frac_above"]*100:.0f}% '
                      f'of drive stale)')
    ax.plot(xs, ys, color=color, lw=LW,
            label=f'per-operator sites (peak {st["peak"]:.0f} s, '
                  f'{st["frac_above"]*100:.1f}% of drive stale)')
    ax.axhline(BUDGET_S, color='black', lw=0.7, ls=':')
    ax.text(6, BUDGET_S * 1.15, f'Vitals freshness budget ({BUDGET_S} s)',
            fontsize=FS - 2, color='black')
    ax.set_yscale('log')
    ax.set_ylim(*YLIM)
    ax.set_ylabel('AoI (s)')
    ax.set_title(label, fontsize=FS, loc='left')
    ax.grid(True, axis='y', alpha=0.6)
    ax.legend(fontsize=FS - 2.5, loc='upper left', framealpha=0.9)
    for spine in ax.spines.values():
        spine.set_visible(True)

axes[1].set_xlabel('Drive time (s)')
fig.tight_layout()
save(fig, 'fig4_aoi_timeseries')
