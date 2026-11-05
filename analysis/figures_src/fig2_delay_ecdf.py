#!/usr/bin/env python3
"""Fig. 2 — End-to-end delay ECDFs, DC vs VA case studies (3 seeds pooled).
Run: python3 fig2_delay_ecdf.py
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from _shared import load_vec, save

# ===== STYLE — edit freely ==================================================
BLUE, RED = '#1f77b4', '#d62728'      # matplotlib tab:blue / tab:red
FONT_FAMILY = ['Liberation Serif', 'Times New Roman', 'Times', 'DejaVu Serif']
FS = 9
LW = 1.3
# (case, color, marker, linestyle, legend label)
SERIES = (('DcDriveAtt', BLUE, 'o', '-', 'Urban (Washington, DC)'),
          ('VaDriveAtt', RED, 's', '--', 'Rural (Virginia)'))
BUDGETS = ((5, 'Alarm budget (5 s)'), (10, 'Vitals budget (10 s)'))
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
for case, color, marker, ls, label in SERIES:
    vals = np.concatenate([v for _, v in load_vec(case, 'e2eDelay:vector')])
    xs = np.sort(vals)
    ys = np.arange(1, len(xs) + 1) / len(xs)
    # subsample markers so they don't overplot on a log-x ECDF
    every = max(1, len(xs) // 12)
    ax.plot(xs, ys, color=color, lw=LW, ls=ls, marker=marker,
            markevery=every, markersize=4.5, markerfacecolor='white',
            markeredgewidth=0.9, label=label)
for budget, name in BUDGETS:
    ax.axvline(budget, color='black', lw=0.7, ls=':')
ax.set_xscale('log')
ax.set_xlabel('End-to-end delay of delivered packets (s)')
ax.set_ylabel('Fraction of packets')
ax.set_ylim(0, 1.02)
ax.grid(True, axis='both', alpha=0.6)
ax.legend(loc='lower right', frameon=True, fontsize=FS - 1.5,
          edgecolor='black', fancybox=False)
for spine in ax.spines.values():
    spine.set_visible(True)
save(fig, 'fig2_delay_ecdf')
