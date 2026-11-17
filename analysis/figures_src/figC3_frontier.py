#!/usr/bin/env python3
"""F3 -- C3 drawn: the verification frontier is LINEAR in evidence bytes.

WHAT THIS FIGURE HAD TO UNLEARN
  An earlier version of C3 claimed a sublinear curve with a waveform->image
  MODALITY step. That was an artefact of the per-run-max estimator and is
  withdrawn (VERIFICATION_FRONTIER.md section 3). Drawing the figure is what
  exposed it: on log-log axes the points are a straight line of slope ~1, and
  no amount of annotation makes a straight line look like a knee.

  So the figure now asserts the true thing, which is also the more useful one:
  there is no free region and no boundary to design around. Every byte costs,
  proportionally. The only lever is total bytes -- and C4 shows you cannot
  schedule your way around it either.

THE FORM
  Four conditions must be told apart over a continuous x, so: multi-line,
  categorical colour, log-log. A slope-1 guide makes linearity readable
  directly -- parallel to the guide IS the claim.

  NO THRESHOLD LINE. This figure used to carry a horizontal "4 s eCall
  budget". It was wrong twice over and was removed on 2026-11-16 after an
  external review caught it. ETSI TS 122 101 cl. A.27.2 measures its 4 s
  from the moment the end-to-end connection with the PSAP is established,
  not from the triggering event; and the y axis here is the GAP, which
  itself starts at alert arrival. Drawing one clock's threshold across
  another clock's interval invites exactly the comparison it should not.
  The study-defined 4 s threshold now appears only against TOTAL readiness
  time, in the results table, where the clocks agree.

PRINT / GRAYSCALE
  Four validated hues (#2a78d6/#eb6834/#1baf7a/#6250d6: all six checks pass,
  worst adjacent dE 9.2 deutan, 27.6 normal). The validator WARNs that
  #1baf7a's contrast vs surface is 2.74 (<3:1); the required relief is visible
  labels, and all four series are direct-labelled, which also satisfies the
  "<=4 series are direct-labelled" rule. Each series additionally carries its
  own dash pattern and marker, so identity survives grayscale entirely.

DATA
  Computed from the two committed extracts via dispatch_times.pair_bursts, so
  this figure and the tables in VERIFICATION_FRONTIER.md and PHASE2_RESULT.md
  cannot drift apart. E2' comes from the Phase 2 corpus, the rest from Gate A;
  both at the free edge, 60 fps, matched seeds.
"""
import csv
import gzip
import math
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

# ===== STYLE =================================================================
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#d8d7d3"
FS = 7.0
SERIES = [  # condition, hue, dash, marker, display name
    ("CondHealthy",   "#2a78d6", (None, None), "o", "Healthy"),
    ("CondCongested", "#eb6834", (3.2, 1.4),   "s", "Congested"),
    ("CondTransient", "#1baf7a", (1.3, 1.3),   "^", "Transient"),
    ("CondOutage",    "#6250d6", (4.5, 1.4, 1.2, 1.4), "D", "Outage"),
]
RUNGS = [("e1", 512, "E1"), ("e2", 3584, "E2"), ("e2b", 14400, "E2$'$"),
         ("e3", 57344, "E3"), ("e4", 138000, "E4")]


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


GA = load(os.path.join(ROOT, "analysis/escalation_vec/escalation_latencies.csv.gz"))
P2 = load(os.path.join(ROOT, "analysis/phase2/escalation_latencies.csv.gz"))


# Chunks per complete burst, by rung. Readiness is undefined for an
# escalation that never received its whole burst, so the frontier is plotted
# among COMPLETE escalations. That makes every point optimistic -- the bursts
# that lost chunks were the ones the radio treated badly -- and the completion
# rate that belongs beside it is in the results table. Changed 2026-11-16;
# before that this plotted a median over a mixture in which incomplete bursts
# contributed an understated value.
EXPECTED = {"e1": 1, "e2": 3, "e2b": 11, "e3": 41, "e4": 99}


def gap(cond, arm):
    src = P2 if arm == "e2b" else GA
    exp = EXPECTED[arm]
    rows = [r for (c, m, _), rr in src.items() if c == cond and m == arm
            for r in rr if r[2] >= exp]
    return statistics.median(r[1] - r[0] for r in rows) if rows else float("nan")


# ===== FIGURE ================================================================
fig, ax = plt.subplots(figsize=(3.5, 2.85))
fig.patch.set_facecolor(SURFACE)
ax.set_facecolor(SURFACE)

FLOOR = 5e-4        # E1/CondHealthy is 0 and cannot sit on a log axis.
                    # Below the smallest REAL value (1e-3) so clamping never
                    # collides with a measurement.
xs = np.array([b for _, b, _ in RUNGS], dtype=float)

for cond, hue, dash, mk, name in SERIES:
    ys = np.array([gap(cond, a) for a, _, _ in RUNGS])
    # "<= 0" is not enough: a median of exactly zero can arrive as ~1e-17,
    # which plots far below the axis instead of at the floor.
    drawn = np.where(ys < FLOOR, FLOOR, ys)
    ln, = ax.plot(xs, drawn, color=hue, lw=1.6, marker=mk, ms=3.6,
                  markeredgecolor=SURFACE, markeredgewidth=0.6, zorder=3,
                  solid_capstyle="round")
    if dash[0] is not None:
        ln.set_dashes(list(dash))
    # open marker where the true value is 0, so the floor is never read as data
    for x, y in zip(xs, ys):
        if y < FLOOR:
            ax.plot([x], [FLOOR], marker=mk, ms=3.6, mfc=SURFACE,
                    mec=hue, mew=1.0, zorder=4)
    ax.annotate(name, xy=(xs[-1], drawn[-1]), xytext=(4, 0),
                textcoords="offset points", fontsize=FS - 0.8, color=hue,
                va="center", ha="left", zorder=5)

# slope-1 guide: linearity is the claim, so make it directly readable
gx = np.array([3584.0, 138000.0])
# offset below the data: anchored ON a series the guide hides under it,
# because those series ARE slope ~1 -- which is the claim, but invisible.
anchor = gap("CondCongested", "e2") * 0.13
ax.plot(gx, anchor * gx / gx[0], color=INK2, lw=0.8, ls=(0, (1, 2)), zorder=2)
ax.annotate("slope 1 = linear in bytes", xy=(138000, anchor * 138000 / gx[0]),
            xytext=(1, -7), textcoords="offset points", fontsize=FS - 1.1,
            color=INK2, ha="right", va="top", zorder=5)

ax.set_xscale("log")
ax.set_yscale("log")
ax.set_xlim(350, 900000)
ax.set_ylim(FLOOR * 0.7, 9)
ax.set_xticks([b for _, b, _ in RUNGS])
ax.set_xticklabels([f"{lab}\n{b/1000:.0f} kB" if b >= 10000 else
                    (f"{lab}\n{b/1000:.1f} kB" if b >= 1000 else f"{lab}\n{b} B")
                    for _, b, lab in RUNGS], fontsize=FS - 1.0, color=INK2)
ax.minorticks_off()
ax.set_yticks([FLOOR, 1e-2, 1e-1, 1, 4])
ax.set_yticklabels(["0*", "10 ms", "100 ms", "1 s", "4 s"],
                   fontsize=FS - 0.5, color=INK2)
ax.set_ylabel("dispatch gap  (median, log)", fontsize=FS, color=INK)
ax.set_xlabel("evidence payload  (log)", fontsize=FS, color=INK, labelpad=1)

ax.grid(True, which="major", color=GRID, lw=0.5, zorder=1)
ax.set_axisbelow(True)
for sp in ("top", "right"):
    ax.spines[sp].set_visible(False)
for sp in ("bottom", "left"):
    ax.spines[sp].set_color(GRID)
ax.tick_params(length=0)
ax.text(0.0, -0.265, "*open marker: gap is exactly 0, placed at the axis floor",
        transform=ax.transAxes, fontsize=FS - 1.6, color=INK2, va="top")

fig.tight_layout(pad=0.35)
for ext in ("pdf", "png"):
    fig.savefig(os.path.join(FIGDIR, f"figC3_frontier.{ext}"), dpi=400,
                facecolor=SURFACE)
print("wrote figC3_frontier.pdf/.png\n")

# ===== the numbers, so the caption cannot drift from the figure ==============
print(f"{'condition':15s}" + "".join(f"{lab:>10s}" for _, _, lab in RUNGS)
      + f"{'slope':>8s}{'R2':>7s}")
for cond, _, _, _, name in SERIES:
    ys = [gap(cond, a) for a, _, _ in RUNGS]
    # Fit on E2/E3/E4 only. E1 is excluded because its gap is ~0, and E2'
    # because it comes from the OTHER campaign -- it is plotted, since it is
    # the rung the design rule is about, but mixing corpora inside one
    # regression would make the slope unattributable. The paper quotes this
    # three-point fit, so the two cannot disagree.
    FIT = {"e2", "e3", "e4"}
    lx = [math.log(b) for (a, b, _), y in zip(RUNGS, ys) if y > 0 and a in FIT]
    ly = [math.log(y) for (a, _, _), y in zip(RUNGS, ys) if y > 0 and a in FIT]
    mx, my = sum(lx)/len(lx), sum(ly)/len(ly)
    sl = sum((x-mx)*(y-my) for x, y in zip(lx, ly))/sum((x-mx)**2 for x in lx)
    ic = my - sl*mx
    ss = sum((y-(sl*x+ic))**2 for x, y in zip(lx, ly))
    tt = sum((y-my)**2 for y in ly)
    print(f"{cond:15s}" + "".join(f"{y:10.4f}" for y in ys)
          + f"{sl:8.2f}{1-ss/tt:7.3f}")
