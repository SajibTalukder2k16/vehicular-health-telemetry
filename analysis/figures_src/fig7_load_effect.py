#!/usr/bin/env python3
"""Fig. 7 -- the load result: the load bites, the margin does not move.

Two panels, because those are two different questions and one axis each:

  (a) Where the controller operates, unloaded -> loaded. A dumbbell per
      corridor per stream. The job is magnitude-and-direction of a paired
      change, so a connected pair beats two bar groups: the eye reads the
      segment, not the difference of two heights.

  (b) Did the margin over the per-seed oracle change? A forest plot -- point
      estimate and 95% interval per corridor, with the pooled estimate and a
      reference line at zero. This is the correct form for "is the change
      distinguishable from nothing", and it shows the answer (no, for six of
      six except c11) without the reader doing arithmetic.

Both panels use ONE x-axis each, never two scales. Panel (a) can put vitals and
camera on a shared axis honestly because both are the same unit -- a timely
fraction in percent.

Significance in (b) is encoded by marker FILL, not by colour: colour would
repaint an entity according to a property of its interval, and fill survives
grayscale.

Data comes from the same helpers as analyze_load_effect.py, so the figure and
the load numbers in the text cannot drift apart.

Usage: python fig7_load_effect.py [out-dir]
"""
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt          # noqa: E402
from matplotlib.lines import Line2D      # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from analyze_ablation import mean_ci                       # noqa: E402
from analyze_load_effect import arms, per_seed_margins     # noqa: E402

SURFACE = '#ffffff'
INK = '#0b0b0b'
INK_SOFT = '#52514e'
GRID = '#dedede'
VITALS = '#2a78d6'       # categorical slot 1
CAMERA = '#eb6834'       # categorical slot 2

plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['DejaVu Serif'],
    'font.size': 6.6,
    'axes.labelsize': 7.0,
    'axes.titlesize': 7.4,
    'legend.fontsize': 6.4,
    'xtick.labelsize': 6.2,
    'ytick.labelsize': 6.4,
    'axes.edgecolor': '#9a9a9a',
    'axes.linewidth': 0.5,
    'figure.facecolor': SURFACE,
    'axes.facecolor': SURFACE,
})

CORRIDORS = ['c08', 'c09', 'c10', 'c11', 'c12', 'c13', 'c14']
MIN_SEEDS = 2


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        ROOT, 'manuscript', 'figures')
    os.makedirs(outdir, exist_ok=True)
    base = os.path.join(ROOT, 'simulations', 'corridorpop')
    data = {'unloaded': arms(os.path.join(base, 'results_seeds10')),
            'loaded': arms(os.path.join(base, 'results_loaded'))}

    fig, (axa, axb) = plt.subplots(
        1, 2, figsize=(7.16, 2.65), constrained_layout=True,
        gridspec_kw={'width_ratios': [1.05, 1.0]})

    # ---- panel (a): operating point shift -----------------------------------
    ys = list(range(len(CORRIDORS)))[::-1]
    for y, c in zip(ys, CORRIDORS):
        for off, col, key in ((+0.17, VITALS, 'timely_vitals'),
                              (-0.17, CAMERA, 'timely_camera')):
            vals = {}
            for lab in ('unloaded', 'loaded'):
                cells = data[lab][1][(c, 'aimd')]
                # kpis() already returns percent -- analyze_static_oracle
                # prints these straight as 96.8. Do not scale again.
                vals[lab] = sum(x[key] for x in cells.values()) / len(cells)
            axa.plot([vals['unloaded'], vals['loaded']], [y + off] * 2,
                     '-', color=col, linewidth=1.1, zorder=2, solid_capstyle='round')
            axa.plot([vals['unloaded']], [y + off], 'o', color=col,
                     markersize=3.6, markerfacecolor=SURFACE,
                     markeredgewidth=0.9, zorder=3)
            axa.plot([vals['loaded']], [y + off], 'o', color=col,
                     markersize=3.6, zorder=3)

    axa.set_yticks(ys, CORRIDORS)
    axa.set_xlabel('timely fraction (%)', color=INK)
    axa.set_title('(a) controller operating point, unloaded $\\rightarrow$ loaded',
                  color=INK, pad=4)
    axa.grid(True, axis='x', color=GRID, linewidth=0.4)
    axa.set_axisbelow(True)
    axa.set_ylim(-0.6, len(CORRIDORS) - 0.4)

    axa.legend(handles=[
        Line2D([], [], color=VITALS, marker='o', markersize=3.6, linewidth=1.1,
               markerfacecolor=SURFACE, markeredgewidth=0.9, label='vitals'),
        Line2D([], [], color=CAMERA, marker='o', markersize=3.6, linewidth=1.1,
               markerfacecolor=SURFACE, markeredgewidth=0.9, label='camera'),
        Line2D([], [], color=INK_SOFT, marker='o', markersize=3.6, linestyle='none',
               markerfacecolor=SURFACE, markeredgewidth=0.9, label='unloaded'),
        Line2D([], [], color=INK_SOFT, marker='o', markersize=3.6, linestyle='none',
               label='loaded'),
    ], loc='upper left', frameon=False, ncol=2, handlelength=1.6,
        columnspacing=1.0, borderpad=0.2)

    # ---- panel (b): forest plot of the paired change ------------------------
    rows, diffs = [], []
    for c in CORRIDORS:
        du = per_seed_margins(*data['unloaded'], c)[0]
        dl = per_seed_margins(*data['loaded'], c)[0]
        common = sorted(set(du) & set(dl))
        if len(common) < MIN_SEEDS:
            continue
        m, ci, _n = mean_ci([dl[s] - du[s] for s in common])
        rows.append(c)
        diffs.append((m, ci))

    pooled_m, pooled_ci, _ = mean_ci([m for m, _ in diffs])

    yy = list(range(len(rows) + 1))[::-1]
    axb.axvline(0, color=INK_SOFT, linewidth=0.7, linestyle='--', zorder=1)
    for y, c, (m, ci) in zip(yy, rows, diffs):
        sig = abs(m) > ci
        axb.plot([m - ci, m + ci], [y, y], '-', color=VITALS, linewidth=1.0,
                 zorder=2, solid_capstyle='butt')
        axb.plot([m], [y], 'o', color=VITALS, markersize=4.0, zorder=3,
                 markerfacecolor=VITALS if sig else SURFACE, markeredgewidth=0.9)

    yp = yy[len(rows)]
    axb.plot([pooled_m - pooled_ci, pooled_m + pooled_ci], [yp] * 2, '-',
             color=INK, linewidth=1.3, zorder=2)
    axb.plot([pooled_m], [yp], 'D', color=INK, markersize=4.2, zorder=3)

    axb.set_yticks(yy, rows + ['all'])
    axb.set_xlabel('change in margin over the per-seed oracle (pp)', color=INK)
    axb.set_title('(b) matched-seed paired change under load', color=INK, pad=4)
    axb.grid(True, axis='x', color=GRID, linewidth=0.4)
    axb.set_axisbelow(True)
    axb.set_ylim(-0.7, len(rows) + 0.4)
    axb.annotate(f'{pooled_m:+.1f} $\\pm$ {pooled_ci:.1f} pp',
                 xy=(pooled_m, yp), xytext=(0, -11),
                 textcoords='offset points', ha='center', va='top',
                 fontsize=6.2, color=INK)
    axb.legend(handles=[
        Line2D([], [], color=VITALS, marker='o', markersize=4.0, linewidth=1.0,
               label='interval excludes 0'),
        Line2D([], [], color=VITALS, marker='o', markersize=4.0, linewidth=1.0,
               markerfacecolor=SURFACE, markeredgewidth=0.9, label='includes 0'),
    ], loc='lower right', frameon=False, handlelength=1.6, borderpad=0.2)

    for ax in (axa, axb):
        for s in ('top', 'right'):
            ax.spines[s].set_visible(False)
        ax.tick_params(colors=INK_SOFT, length=2, pad=1.5)

    for ext in ('pdf', 'png'):
        path = os.path.join(outdir, f'fig7_load_effect.{ext}')
        fig.savefig(path, dpi=400, bbox_inches='tight', facecolor=SURFACE)
        print('wrote', path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
