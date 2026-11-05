#!/usr/bin/env python3
"""Fig. 3 — Delivery vs inter-site distance with 95% CIs, by camera payload.
Run: python3 fig3_delivery_vs_isd.py
"""
import math

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from _shared import load_family_a, save

# ===== STYLE — edit freely ==================================================
BLUE, RED = '#1f77b4', '#d62728'      # matplotlib tab:blue / tab:red
FONT_FAMILY = ['Liberation Serif', 'Times New Roman', 'Times', 'DejaVu Serif']
FS = 9
SERIES = ((4, BLUE, 'o', '-', '4 KiB frames'),
          (60, RED, 's', '--', '60 KiB frames'))
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


def ci95(x):
    x = x.dropna()
    return 1.96 * x.std() / math.sqrt(len(x)) if len(x) > 1 else float('nan')


fam = load_family_a()
fig, ax = plt.subplots(figsize=(3.5, 2.9))
for payload, color, marker, ls, label in SERIES:
    g = (fam[fam.payload == payload].groupby('isd')['delivery_e2e']
         .agg(['mean', ci95]).reset_index())
    ax.errorbar(g.isd / 1000, 100 * g['mean'], yerr=100 * g['ci95'],
                color=color, marker=marker, ls=ls, lw=1.3, ms=5,
                markerfacecolor='white', markeredgewidth=1.0, capsize=3,
                label=label)
ax.axvline(2.8, color='black', lw=0.7, ls=':')
# grouping labels placed just below the axis line (blended transform: data
# x, axes-fraction y), clear of both the curves and the in-plot legend
blend = ax.get_xaxis_transform()
ax.text(1.0, -0.13, 'Urban ISDs', fontsize=FS - 1.5, color='black',
        transform=blend, ha='center', va='top', clip_on=False)
ax.text(7.07, -0.13, 'Rural ISDs', fontsize=FS - 1.5, color='black',
        transform=blend, ha='center', va='top', clip_on=False)
ax.set_xscale('log')
ax.set_xticks([0.5, 1, 2, 5, 10], ['0.5', '1', '2', '5', '10'])
ax.set_xlabel('Inter-site distance (km)')
ax.set_ylabel('Packets delivered (%)')
ax.grid(True, axis='y', alpha=0.6)
ax.legend(loc='lower left', frameon=True, fontsize=FS - 1.5,
          edgecolor='black', fancybox=False)
for spine in ax.spines.values():
    spine.set_visible(True)
save(fig, 'fig3_delivery_vs_isd')
