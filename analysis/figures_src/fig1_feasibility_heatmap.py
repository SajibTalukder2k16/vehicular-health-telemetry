#!/usr/bin/env python3
"""Fig. 1 — Feasibility heatmap: timely vitals delivery over ISD x speed,
one panel per camera payload.   Run: python3 fig1_feasibility_heatmap.py
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from _shared import load_family_a, save

# ===== STYLE — edit freely ==================================================
CMAP = 'viridis'                # standard perceptually-uniform sequential map
VMIN, VMAX = 0.75, 1.0          # color range (fraction timely)
WHITE_TEXT_BELOW = 0.86         # cell values darker than this get white text
FONT_FAMILY = ['Liberation Serif', 'Times New Roman', 'Times', 'DejaVu Serif']
FS = 9                          # base font size (pt)
DPI = 300
plt.rcParams.update({
    'font.family': 'serif', 'font.serif': FONT_FAMILY,
    'font.size': FS, 'text.color': 'black', 'axes.labelcolor': 'black',
    'axes.edgecolor': 'black', 'axes.linewidth': 0.8,
    'xtick.color': 'black', 'ytick.color': 'black',
    'xtick.direction': 'in', 'ytick.direction': 'in',
    'figure.facecolor': 'white', 'savefig.facecolor': 'white',
    'pdf.fonttype': 42, 'ps.fonttype': 42,
})
# ============================================================================

fam = load_family_a()
isds = [500, 1000, 2000, 5000, 10000]
speeds = [30, 55, 80, 105]

fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.1), sharey=True)
for ax, payload in zip(axes, (4, 60)):
    M = np.full((len(isds), len(speeds)), np.nan)
    for i, isd in enumerate(isds):
        for j, sp in enumerate(speeds):
            sel = fam[(fam.isd == isd) & (fam.speed == sp)
                      & (fam.payload == payload)]
            M[i, j] = sel['timely_vitals'].mean()
    im = ax.imshow(M, cmap=CMAP, vmin=VMIN, vmax=VMAX, aspect='auto',
                   origin='lower')
    for i in range(len(isds)):
        for j in range(len(speeds)):
            v = M[i, j]
            ax.text(j, i, f'{100*v:.0f}', ha='center', va='center',
                    fontsize=FS - 1.5,
                    color='white' if v < WHITE_TEXT_BELOW else 'black')
    ax.set_xticks(range(len(speeds)), [str(s) for s in speeds])
    ax.set_yticks(range(len(isds)), ['0.5', '1', '2', '5', '10'])
    ax.set_xlabel('Vehicle speed (km/h)')
    ax.set_title(f'({"a" if payload == 4 else "b"}) {payload} KiB payload',
                 fontsize=FS, loc='center')
    for spine in ax.spines.values():
        spine.set_visible(True)
    ax.tick_params(length=3)

axes[0].set_ylabel('Inter-site distance (km)')
for ax in axes:
    ax.axhline(2.5, color='black', lw=0.8, ls='--')  # urban/rural divider
axes[1].annotate('Rural', (1.05, 0.78), xycoords='axes fraction',
                  fontsize=FS - 1, color='black', rotation=90,
                  ha='center', va='center')
axes[1].annotate('Urban', (1.05, 0.28), xycoords='axes fraction',
                  fontsize=FS - 1, color='black', rotation=90,
                  ha='center', va='center')
cb = fig.colorbar(im, ax=axes, fraction=0.035, pad=0.08)
cb.set_label('Vitals delivered within 10 s budget (%)', fontsize=FS - 1)
cb.set_ticks([0.75, 0.80, 0.85, 0.90, 0.95, 1.0],
             labels=['75', '80', '85', '90', '95', '100'])
cb.outline.set_linewidth(0.8)
save(fig, 'fig1_feasibility_heatmap', dpi=DPI)
