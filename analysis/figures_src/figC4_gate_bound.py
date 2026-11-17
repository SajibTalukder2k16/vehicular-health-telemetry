#!/usr/bin/env python3
"""F4 -- C4 drawn: every gate configuration lands inside the derived triangle.

THE CLAIM, AND WHY THIS FORM
  GATE_DERIVATION.md proves two things about pacing the verification payload:

      Prop 2   penalty >= 0      (work conservation: releasing bytes later
                                  cannot make them depart earlier)
      Prop 3   penalty <= (B-b)/r (the last byte is admitted at that time)

  Together they confine every configuration to the triangle between y = 0 and
  y = x, where x is each cell's OWN derived bound. So the figure plots measured
  penalty against derived bound: one panel, all 48 cells, and the claim is
  simply "nothing escapes the triangle".

  A grouped bar chart over (bucket, rate) would show the same numbers and none
  of the argument. Here the derivation is drawn as geometry, and a single point
  above the diagonal or below the axis would refute it visibly.

  x = 0 is the POSITIVE CONTROL: b = 256 KiB exceeds the E4 burst, so Prop 1
  says the gate cannot engage and the bound is identically zero. Those twelve
  cells must sit exactly at the origin, and do -- with completion identical to
  the no-gate baseline, which is the stronger check.

  WHAT THIS FIGURE DOES NOT SHOW (added 2026-11-17, second review). The
  penalties plotted are CELL MEDIANS conditioned on completion. Individual
  paired escalations move in both directions -- 22.6 % complete sooner under
  the inherited gate -- so the triangle is a statement about medians, not a
  universal bound. It also says nothing about the completeness cost: where the
  gate engages it reduces the fraction of escalations that complete at all,
  which is in the results table and not here.

PRINT / GRAYSCALE
  Four validated hues (#2a78d6/#eb6834/#1baf7a/#6250d6; all six checks pass,
  worst adjacent dE 9.2 deutan, 27.6 normal). The validator WARNs that
  #1baf7a's contrast vs surface is 2.74; the required relief is visible labels,
  and the legend plus distinct marker SHAPES carry identity without colour.

DATA
  analysis/gate/escalation_latencies.csv.gz (2,160 runs) via
  dispatch_times.pair_bursts, paired on seed against the corpus's own
  policy=none baseline -- so this figure cannot drift from
  GATE_SWEEP_RESULT.md section 2.
"""
import csv
import gzip
import os
import statistics
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
FIGDIR = os.path.join(HERE, "..", "figures")
os.makedirs(FIGDIR, exist_ok=True)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from dispatch_times import pair_bursts  # noqa: E402

SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#d8d7d3"
FS = 7.0
EV = 138000.0
PACE = {"p16k1": (16384, 1e6/8), "p16k4": (16384, 4e6/8), "p16k16": (16384, 16e6/8),
        "p64k1": (65536, 1e6/8), "p64k4": (65536, 4e6/8), "p64k16": (65536, 16e6/8),
        "p128k1": (131072, 1e6/8), "p128k4": (131072, 4e6/8),
        "p128k16": (131072, 16e6/8), "p256k1": (262144, 1e6/8),
        "p256k4": (262144, 4e6/8), "p256k16": (262144, 16e6/8)}
SERIES = [("CondHealthy", "#2a78d6", "o", "Healthy"),
          ("CondCongested", "#eb6834", "s", "Congested"),
          ("CondTransient", "#1baf7a", "^", "Transient"),
          ("CondOutage", "#6250d6", "D", "Outage")]


def load(path, tol=1e-2):
    per = {}
    with gzip.open(path, "rt", newline="") as fh:
        for r in csv.DictReader(fh):
            k = (r["condition"], r["arm"], r["seed"])
            al, ch = per.setdefault(k, ([], {}))
            if r["kind"] == "alarm":
                al.append((float(r["creation"]), float(r["delay"])))
            else:
                ch.setdefault(round(float(r["creation"]), 6), []).append(
                    float(r["delay"]))
    return {k: pair_bursts(a, c, tol) for k, (a, c) in per.items()}


G = load(os.path.join(ROOT, "analysis/gate/escalation_latencies.csv.gz"))


# Chunks in a complete E4 burst. The gap is undefined for an escalation whose
# evidence never completed, so the penalty plotted here is conditioned on
# completion and must match Table "sweep" exactly. An earlier version of this
# script plotted the UNCONDITIONAL median while the table had moved to the
# conditional one; the figure and the table then disagreed (0.8082 vs 0.8110 at
# the maximum), which an external reviewer caught. Changing the caption alone
# did not fix it -- the computation had to change too.
EXPECTED_E4 = 99


def gap_by_seed(cond, arm):
    out = {}
    for (c, m, s), rr in G.items():
        if c != cond or m != arm:
            continue
        g = [r[1] - r[0] for r in rr if r[2] >= EXPECTED_E4]
        if g:
            out[s] = statistics.median(g)
    return out


fig, ax = plt.subplots(figsize=(3.5, 2.9))
fig.patch.set_facecolor(SURFACE)
ax.set_facecolor(SURFACE)

LIM = 1.04
# The half-planes the DERIVATION excludes. "Forbidden" overstates it: these
# are regions a fluid model of the bucket rules out for a cell median, not
# regions physically unreachable -- individual escalations do land below
# zero (section V-D). Labelled as predictions, which is what they are.
ax.fill_between([0, LIM], [0, LIM], [LIM, LIM], color="#f2efe9", zorder=0, lw=0)
ax.plot([0, LIM], [0, LIM], color=INK, lw=1.0, zorder=2)
ax.axhline(0, color=INK, lw=1.0, zorder=2)
ax.annotate("penalty = the bound $(B-b)/r$", xy=(0.995, 0.995), xytext=(-2, 3),
            textcoords="offset points", fontsize=FS - 1.2, color=INK,
            rotation=45, rotation_mode="anchor", ha="right", va="bottom")
ax.text(0.56, 0.93, "Prop 3 predicts no cell here:\npenalty exceeds its bound",
        fontsize=FS - 1.2, color=INK2, ha="center", va="center",
        style="italic", linespacing=1.2)
ax.text(1.02, -0.055, "Prop 2 predicts no cell here: median penalty below zero",
        fontsize=FS - 1.2, color=INK2, ha="right", va="center", style="italic")

rows = []
for cond, hue, mk, name in SERIES:
    base = gap_by_seed(cond, "none")
    xs, ys = [], []
    for arm, (b, r) in PACE.items():
        test = gap_by_seed(cond, arm)
        seeds = sorted(set(base) & set(test))
        if not seeds:
            continue
        pen = statistics.median(test[s] - base[s] for s in seeds)
        bnd = max(0.0, (EV - b) / r)
        xs.append(bnd)
        ys.append(pen)
        rows.append((cond, arm, b, r, bnd, pen))
    ax.scatter(xs, ys, s=15, marker=mk, facecolor=hue, edgecolor=SURFACE,
               linewidth=0.5, zorder=4, label=name)

# the two cells a reader should be able to find
inh = [(x, y) for c, a, b, r, x, y in rows if a == "p64k1" and c == "CondHealthy"]
if inh:
    ax.annotate("inherited gate\n64 KiB, 1 Mbps", xy=inh[0], xytext=(13, -2),
                textcoords="offset points", fontsize=FS - 1.3, color=INK2,
                ha="left", va="top", linespacing=1.15,
                arrowprops=dict(arrowstyle="-", lw=0.6, color=INK2))
# The positive control is NOT annotated on the figure: the twelve cells with
# b = 256 KiB > B have a bound of exactly 0 and sit on the origin, where any
# label collides with the 16 KiB column. The caption names them instead:
#   "The twelve cells at the origin are the positive control: b > B, so
#    Proposition 1 makes the gate a no-op and both coordinates are exactly 0."

ax.set_xlim(-0.035, LIM)
ax.set_ylim(-0.085, LIM)
ax.set_xlabel("derived bound on the penalty, $(B-b)/r$   (s)", fontsize=FS,
              color=INK, labelpad=1.5)
ax.set_ylabel("measured penalty   (s)", fontsize=FS, color=INK)
ax.tick_params(labelsize=FS - 0.5, colors=INK2, length=0)
ax.grid(True, color=GRID, lw=0.45, zorder=1)
ax.set_axisbelow(True)
for sp in ("top", "right"):
    ax.spines[sp].set_visible(False)
for sp in ("bottom", "left"):
    ax.spines[sp].set_color(GRID)
ax.legend(fontsize=FS - 1.0, loc="upper left", frameon=False, ncol=1,
          handletextpad=0.25, labelspacing=0.32, borderaxespad=0.4,
          scatterpoints=1)

fig.tight_layout(pad=0.35)
for ext in ("pdf", "png"):
    fig.savefig(os.path.join(FIGDIR, f"figC4_gate_bound.{ext}"), dpi=400,
                facecolor=SURFACE)
print("wrote figC4_gate_bound.pdf/.png\n")

viol_hi = [r for r in rows if r[5] > r[4] + 1e-9]
viol_lo = [r for r in rows if r[5] < -1e-9]
ctrl = [r for r in rows if r[2] > EV and abs(r[5]) > 1e-9]
print(f"cells plotted: {len(rows)}")
print(f"  above the bound (refutes Prop 3): {len(viol_hi)}")
print(f"  below zero      (refutes Prop 2): {len(viol_lo)}")
print(f"  control non-zero (refutes Prop 1): {len(ctrl)}")
print(f"  max penalty {max(r[5] for r in rows):.4f} s at "
      f"{max(rows, key=lambda r: r[5])[1]}/{max(rows, key=lambda r: r[5])[0]}")
