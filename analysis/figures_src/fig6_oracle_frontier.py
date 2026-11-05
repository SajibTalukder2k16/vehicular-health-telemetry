#!/usr/bin/env python3
"""Fig. 6 -- the paper's central claim, drawn.

Per corridor: the Pareto frontier a STATIC policy can reach by choosing its
camera rate, and where the adaptive controller actually sits. The vertical
segment is the measured quantity: extra timely camera at the controller's own
vitals level, i.e. what the per-corridor oracle gives up.

Form: small multiples. Seven corridors are seven separate two-dimensional
relationships; overlaying them would put 35 static points and 7 controller
markers in one axes and the geometry -- which is the whole argument -- would be
unreadable. Two series only, inside the three-series cap that all-pairs forms
(scatter, small multiples) carry.

Colors are categorical slots 1 and 2 of the validated default palette; the pair
passes all six checks on a light surface (CVD dE 24.7 protan, normal-vision
33.6). Identity is carried by SHAPE and FILL as well as hue -- open circles on
a line against a filled marker -- so the figure survives grayscale printing and
full colour-vision deficiency, which a journal PDF has to.

Data comes through the same helpers the results tables use
(analyze_static_oracle.collect / frontier / camera_at), so the figure and
Table~\\ref{tab:frontier} cannot drift apart.

Usage: python fig6_oracle_frontier.py [out-dir]
"""
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt          # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from analyze_static_oracle import (CAPS, PCTILE, camera_at,  # noqa: E402
                                   collect, frontier, point)

# --- style (deliberately local to this script, per figures_src convention) ---
SURFACE = '#ffffff'      # journals expect white, not the web surface token
INK = '#0b0b0b'
INK_SOFT = '#52514e'
GRID = '#dedede'
STATIC = '#2a78d6'       # categorical slot 1
CTRL = '#eb6834'         # categorical slot 2

plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['DejaVu Serif'],
    'font.size': 6.4,
    'axes.labelsize': 6.8,
    'axes.titlesize': 7.0,
    'legend.fontsize': 6.6,
    'xtick.labelsize': 6.0,
    'ytick.labelsize': 6.0,
    'axes.edgecolor': '#9a9a9a',
    'axes.linewidth': 0.5,
    'xtick.major.width': 0.5,
    'ytick.major.width': 0.5,
    'figure.facecolor': SURFACE,
    'axes.facecolor': SURFACE,
})

CORRIDORS = ['c08', 'c09', 'c10', 'c11', 'c12', 'c13', 'c14']


def load(d):
    st = collect(os.path.join(d, '*.sca'), r'(c\d+)-static(\d+)-s?(\d+)$')
    ct = collect(os.path.join(d, '*.sca'), r'(c\d+)-(aimd)-s?(\d+)$')
    return st, ct


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        ROOT, 'manuscript', 'figures')
    os.makedirs(outdir, exist_ok=True)
    src = os.path.join(ROOT, 'simulations', 'corridorpop', 'results_seeds10')
    st, ct = load(src)

    # 4 x 2 grid: 7 corridors plus one cell for the legend, so the legend never
    # sits on top of data.
    # Axes are SHARED on purpose. Per-panel autoscaling makes every corridor's
    # frontier look equally steep and makes the oracle gaps -- which differ by
    # more than a factor of two across the sample -- look the same size. The
    # claim is about a population of corridors, so the panels have to be
    # comparable to each other. The cost is that the best-covered corridor's
    # five static points cluster; that is the honest picture.
    fig, axes = plt.subplots(2, 4, figsize=(7.16, 3.35), constrained_layout=True,
                             sharex=True, sharey=True)
    flat = axes.ravel()

    for i, c in enumerate(CORRIDORS):
        ax = flat[i]
        pts = [point(st[(c, str(k))]) for k in CAPS]
        pts = [p for p in pts if p]
        a = point(ct[(c, 'aimd')])
        front = frontier(pts)

        ax.grid(True, color=GRID, linewidth=0.4, zorder=0)
        ax.set_axisbelow(True)

        xs = [p[0] for p in front]
        ys = [p[1] for p in front]
        ax.plot(xs, ys, '-', color=STATIC, linewidth=1.0, zorder=2)
        ax.plot(xs, ys, 'o', color=STATIC, markersize=3.0, markerfacecolor=SURFACE,
                markeredgewidth=0.9, zorder=3,
                label='static frontier' if i == 0 else None)

        if a:
            cam, note = camera_at(pts, a[0])
            # The measured gap, drawn where it is measured.
            if cam == cam:
                ax.plot([a[0], a[0]], [cam, a[1]], ':', color=INK_SOFT,
                        linewidth=0.8, zorder=4)
                ax.plot([a[0]], [cam], 'x', color=STATIC, markersize=3.4,
                        markeredgewidth=0.9, zorder=5)
                # Selective direct labels: the extremes of the effect, not
                # every panel.
                if c in ('c08', 'c13', 'c14'):
                    ax.annotate(f'{a[1]-cam:+.0f} pp',
                                xy=(a[0], (cam + a[1]) / 2),
                                xytext=(-3, 0), textcoords='offset points',
                                ha='right', va='center', fontsize=5.8,
                                color=INK)
            ax.plot([a[0]], [a[1]], '*', color=CTRL, markersize=7.0,
                    markeredgecolor=SURFACE, markeredgewidth=0.4, zorder=6,
                    label='controller' if i == 0 else None)
            if cam != cam:
                # Place it up and to the RIGHT of the controller marker: the
                # frontier of an unreachable panel runs down-left, and the
                # obvious below-left placement lands on top of it.
                ax.annotate('no static point\nreaches this\nvitals level',
                            xy=(a[0], a[1]), xytext=(5, 6),
                            textcoords='offset points', ha='left', va='bottom',
                            fontsize=5.2, color=INK_SOFT, linespacing=1.15)

        ax.set_title(f'{c}  ({PCTILE.get(c, "?")} pct)', color=INK, pad=2.5)
        if i % 4 == 0:
            ax.set_ylabel('timely camera (%)', color=INK)
        # Bottom row, plus c11: the legend occupies the cell under it, so it is
        # the bottom-most panel of its column and needs its own tick labels
        # back (sharex would otherwise hide them for a row that never comes).
        if i >= 4 or i == 3:
            ax.set_xlabel('timely vitals (%)', color=INK)
            ax.tick_params(labelbottom=True)
        for s in ('top', 'right'):
            ax.spines[s].set_visible(False)
        ax.tick_params(colors=INK_SOFT, length=2, pad=1.5)

    # Legend occupies the spare cell.
    legend_ax = flat[7]
    legend_ax.axis('off')
    h, l = flat[0].get_legend_handles_labels()
    extra = plt.Line2D([], [], linestyle=':', color=INK_SOFT, linewidth=0.8,
                       marker='x', markersize=3.4, markeredgewidth=0.9,
                       markerfacecolor='none', markeredgecolor=STATIC)
    legend_ax.legend(h + [extra], l + ['oracle gap at\nmatched vitals'],
                     loc='center', frameon=False, handlelength=2.0,
                     borderpad=0.2, labelspacing=0.9)

    for ext in ('pdf', 'png'):
        path = os.path.join(outdir, f'fig6_oracle_frontier.{ext}')
        fig.savefig(path, dpi=400, bbox_inches='tight', facecolor=SURFACE)
        print('wrote', path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
