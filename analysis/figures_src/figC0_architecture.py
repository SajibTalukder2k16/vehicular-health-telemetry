#!/usr/bin/env python3
"""F0 -- the architecture this paper actually describes.

WHY THIS IS A NEW FIGURE AND NOT AN EDIT OF arch_system.py
----------------------------------------------------------
`arch_system.py` was drawn for the withdrawn framing, and four of its five
load-bearing statements are now contradicted by the paper's own results:

  it gated the CAMERA stream        -> C1 forces inference local, so camera
                                       frames terminate at the edge and never
                                       cross the uplink at all
  it drew camera frames reaching    -> what crosses is an alert and the
  the cloud                            evidence that justifies it
  it drew the gate ADMITTING        -> C4: the gate is a structural no-op on
                                       evidence traffic, by derivation
  it closed a feedback loop onto    -> that was the controller contribution,
  the bucket rate r(t)                 which this paper does not make
  it labelled the server with AoI   -> the paper's quantity is the dispatch
                                       gap of eq. (2), not age

Editing it would have left a diagram whose composition still argued the old
case. So this draws the new one, and arch_system.py is kept unedited as the
record of the withdrawn framing (as main_v05.tex is).

WHAT A READER MUST SEE WITHOUT THE CAPTION
  1. The inference is AT THE EDGE because it cannot be anywhere else -- and
     the per-frame budget is drawn on it, because that is the third wall.
  2. Camera frames STOP at the edge. The terminator is explicit, not implied
     by the absence of a line.
  3. Two things cross the uplink, and they are wildly different sizes: a
     128 B alert and up to 138 kB of evidence. The rules are weighted to
     match, so the asymmetry is visible before any label is read.
  4. The gate is DISENGAGED. It is drawn greyed, with the evidence path
     passing around it, and labelled with the proposition that makes it a
     no-op. A reader who remembers only one thing should remember that the
     box does nothing.
  5. The server VERIFIES BEFORE DISPATCHING. The decision instant is
     max(alert, verify), so the gap G is the paper's subject, and it is
     marked on the figure as a brace between the two arrivals.

DELIBERATE OMISSIONS
  - No measured numbers. They are in Tables I-IV, where they can be compared.
  - No indoor/WLAN branch. The WLAN appears in this paper only as one of
    C1's capacity constraints (Fig. 1), not as a deployment this paper
    evaluates.
  - No feedback path. There is no controller in this paper.

FORM: single column, 3.5 in. Axis units square (100 x 150 over 3.5 x 5.25 in)
so nothing is secretly stretched. Greyscale only, separated by fill, weight
and dash -- identical in print and immune to colourblindness. Every channel
is redundant with a text label.

LAYOUT CONTRACT, so edits do not silently collide:
  x  0 ..  6   rotated tier labels, nothing else
  x  8 .. 92   the flow
  x 93 .. 99   the gap brace and its label
  Arrowheads mark entry INTO a box; plain rules carry flow between boxes.

Usage: python figC0_architecture.py [out-dir]
"""
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt                                   # noqa: E402
from matplotlib.patches import FancyArrowPatch, Rectangle         # noqa: E402

INK = '#000000'
SOFT = '#4d4d4d'
HAIR = '#8a8a8a'
FILL = '#f4f4f4'
DEAD = '#bdbdbd'          # the disengaged gate: present, visibly inert
WHITE = '#ffffff'

plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Nimbus Roman', 'Times New Roman', 'DejaVu Serif'],
    'pdf.fonttype': 42,
    'ps.fonttype': 42,
})

W, H = 3.5, 5.25


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..', 'figures')
    outdir = os.path.normpath(outdir)
    os.makedirs(outdir, exist_ok=True)

    fig, ax = plt.subplots(figsize=(W, H))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 150)
    ax.axis('off')

    def box(x, y, w, h, *, fc=WHITE, lw=0.7, ec=INK, z=2, ls='-'):
        ax.add_patch(Rectangle((x, y), w, h, facecolor=fc, edgecolor=ec,
                               linewidth=lw, zorder=z, linestyle=ls))

    def txt(x, y, s, *, size=5.6, weight='normal', style='normal',
            color=INK, ha='center', va='center', z=5, rot=0):
        ax.text(x, y, s, fontsize=size, fontweight=weight, fontstyle=style,
                color=color, ha=ha, va=va, zorder=z, rotation=rot)

    def arrow(p, q, *, lw=0.7, ls='-', color=INK, z=4):
        ax.add_patch(FancyArrowPatch(
            p, q, arrowstyle='-|>,head_width=1.25,head_length=2.5',
            mutation_scale=1.0, linewidth=lw, linestyle=ls, color=color,
            zorder=z, shrinkA=0, shrinkB=0))

    def line(xs, ys, *, lw=0.7, ls='-', color=INK, z=3):
        ax.plot(xs, ys, color=color, lw=lw, linestyle=ls, zorder=z,
                solid_capstyle='butt')

    def tier(y, s):
        txt(3.0, y, s, size=5.4, color=SOFT, rot=90)

    # ============================================================== Tier 1
    tier(137, 'Tier 1')
    box(8, 131, 32, 13)
    txt(24, 140.3, 'Wearable', size=6.2)
    txt(24, 136.3, '512 B, 1 Hz, BLE', size=4.9, color=SOFT)

    box(50, 131, 42, 13)
    txt(71, 140.3, 'Cabin camera', size=6.2)
    txt(71, 136.3, '60 fps --- the rate PRV needs', size=4.9, color=SOFT)

    # ============================================================== Tier 2
    tier(93, 'Tier 2 --- edge device')
    box(8, 62, 84, 62, fc=FILL, lw=0.9)

    # ---- the inference, and the wall it sits under -----------------------
    arrow((72, 131), (72, 120.4), lw=1.6)
    box(46, 106, 42, 14, lw=1.0)
    txt(67, 116.0, 'local inference', size=6.1, weight='bold')
    txt(67, 111.8, 'budget 16.67 ms/frame;', size=4.9, color=SOFT)
    txt(67, 108.3, 'measured 22.73 | 94.27 ms', size=4.9, color=SOFT)

    # Camera frames terminate HERE: an explicit stop, not an absent line.
    # Drawn under the LEFT of the inference box so that it cannot be read as
    # a gate on the detection path, which leaves from the right at x = 78.
    line([50, 62], [103.4, 103.4], lw=1.5)
    line([50, 62], [102.2, 102.2], lw=1.5)
    txt(48.5, 102.8, 'frames stop here', size=4.9, style='italic',
        color=SOFT, ha='right')

    # ---- vitals bypass the whole mechanism -------------------------------
    line([19, 19], [131, 76.5], lw=0.7)
    txt(16.6, 104, 'vitals', size=4.9, style='italic', color=SOFT, rot=90)
    line([19, 30], [76.5, 76.5], lw=0.7)
    line([30, 30], [76.5, 65], lw=0.7)
    arrow((30, 65), (30, 62.6), lw=0.7)

    # ---- on detection: an alert, and the evidence that justifies it ------
    box(26, 86, 62, 13, lw=0.8, ls=(0, (2.4, 1.8)))
    txt(57, 94.8, 'escalation detected on the fused stream', size=5.5)
    txt(57, 89.8, 'alert 128 B  $+$  evidence, 512 B to 138 kB',
        size=5.0, color=SOFT)
    line([78, 78], [106, 99], lw=1.0)

    # the alert leaves immediately and thinly; the evidence is the heavy one
    line([40, 40], [86, 65], lw=0.7)
    arrow((40, 65), (40, 62.6), lw=0.7)
    txt(37.6, 75, 'alert', size=4.9, rot=90, color=SOFT)

    # ---- the gate: the evidence passes straight THROUGH an inert box -----
    # It is not bypassed in code -- the bytes really do enter the bucket.
    # It simply never engages, so the rule through it is unbroken.
    # The box is wide and the rule passes through its RIGHT margin, so the
    # label is never struck through by the path it fails to act on.
    box(46, 68, 42, 14, fc=WHITE, lw=0.8, ec=DEAD, ls=(0, (2.0, 1.6)))
    txt(48.5, 78.4, 'token bucket', size=5.3, color=DEAD, ha='left')
    txt(48.5, 74.6, r'$b=64$ KiB, $r=1$ Mb/s', size=4.7, color=DEAD,
        ha='left')
    # NOT "never engages": at E4 the burst exceeds b and the bucket DOES
    # act -- it just cannot help. Inert on four rungs, costly on the fifth.
    txt(48.5, 71.0, 'inert below 64 KiB (Prop 1)', size=4.7, color=DEAD,
        style='italic', ha='left')

    line([78, 78], [86, 65], lw=1.7)
    arrow((78, 65), (78, 62.6), lw=1.7)
    txt(76.0, 84.0, 'evidence', size=4.9, color=SOFT, ha='right')

    # ---- the shared queue: the last point of control ---------------------
    box(10, 50, 80, 12, lw=0.7)
    txt(50, 58.2, 'queue (100 KiB, drop-tail), UDP socket', size=5.7)
    txt(50, 53.2, 'past here nothing can be withdrawn', size=4.9,
        color=SOFT, style='italic')

    # ============================================================= backhaul
    tier(41, 'uplink')
    box(18, 33, 64, 12, lw=0.8)
    arrow((50, 50), (50, 45.4), lw=1.0)
    txt(50, 41.0, 'LTE uplink', size=6.0)
    txt(50, 36.2, 'vehicle in motion, multi-site, X2 handover', size=4.9,
        color=SOFT)

    # ============================================================== Tier 3
    tier(14, 'Tier 3')
    arrow((50, 33), (50, 28.4), lw=1.0)
    box(8, 3, 84, 25, lw=0.9)
    txt(50, 24.4, 'Server: verifies before dispatching', size=6.2,
        weight='bold')

    # the two arrivals, and the gap between them -- the paper's quantity
    txt(45, 18.6, 'alert arrives', size=5.0, ha='right', color=SOFT)
    line([47, 70], [18.6, 18.6], lw=0.7)
    txt(45, 12.4, 'evidence complete', size=5.0, ha='right', color=SOFT)
    line([47, 70], [12.4, 12.4], lw=1.7)

    # the brace, inside the box and clear of both rules
    line([70, 73], [18.6, 18.6], lw=0.6, color=SOFT)
    line([70, 73], [12.4, 12.4], lw=0.6, color=SOFT)
    line([73, 73], [12.4, 18.6], lw=0.6, color=SOFT)
    txt(75.0, 15.5, r'$G$', size=6.0, ha='left')

    txt(50, 6.6, r'$T_{\mathrm{dispatch}} = \max(T_{\mathrm{alert}},'
                 r'\, T_{\mathrm{verify}})$, against a 4 s budget',
        size=5.4)

    fig.subplots_adjust(left=0.004, right=0.996, top=0.998, bottom=0.002)
    for ext in ('pdf', 'png'):
        p = os.path.join(outdir, f'figC0_architecture.{ext}')
        fig.savefig(p, dpi=400 if ext == 'png' else None)
        print('wrote', p)
    plt.close(fig)


if __name__ == '__main__':
    main()
