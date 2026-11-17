#!/usr/bin/env python3
"""F2 -- C2' drawn: the evidence does not delay the ALERT, it delays the DECISION.

THE CLAIM, AND WHY IT NEEDS A FIGURE
  C2 said the verification burst delays the alert. It does not -- 0 of 16 cells,
  and the sign reverses in 4 (GATE_A_RESULT.md). C2' relocates the conflict: the
  server verifies before dispatching, so what the evidence delays is the
  DECISION. Both halves are visible in one picture: over the same evidence
  ladder, the alert line is flat or FALLING while the dispatch gap climbs by one
  to two orders of magnitude.

  In CondOutage the alert actively gets faster -- 1.0071 s at no evidence down
  to 0.1376 s at E3, 0.3704 s at E4 -- while the gap climbs to 0.4020 s.

  THE GAP SERIES IS CONDITIONAL ON COMPLETION (changed 2026-11-16). Readiness
  is undefined for an escalation that never received its whole burst, so the
  gap is a median among complete escalations. It is therefore optimistic: the
  bursts that lost chunks were the ones the radio treated badly. The companion
  number -- what fraction completed at all -- is in the results table, and the
  two belong together. The alert series is NOT conditioned; see stats().

THE FORM
  Two measures, both in SECONDS, so they may share one axis honestly -- this is
  not the dual-axis mistake. Eight series on one panel would be too many, so:
  2x2 small multiples, one per link condition, two series each. The reader's job
  is "these two move in opposite directions", which is a direct visual
  comparison within each panel.

  Log y, because the gap spans 0 -> 1.87 s and a linear axis would flatten
  everything below E3 into the baseline, hiding exactly the half of the claim
  that says verification is free at the low rungs.

PRINT / GRAYSCALE
  Two series only: #2a78d6 / #eb6834, validated (all six checks pass, worst
  adjacent dE 24.7 protan / 33.6 normal). Separated additionally by dash and
  marker, so identity survives grayscale. Legend once, on the figure.

DATA
  analysis/escalation_vec/ (Gate A, policy=none, 600 runs) via
  dispatch_times.pair_bursts, so this figure cannot drift from
  VERIFICATION_FRONTIER.md section 2.
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

# ===== STYLE =================================================================
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#d8d7d3"
C_ALERT = "#2a78d6"
C_GAP = "#eb6834"
FS = 7.0
FLOOR = 5e-4        # the gap is exactly 0 at `ref`; log axes have no zero

RUNGS = [("ref", "none"), ("e1", "E1"), ("e2", "E2"), ("e3", "E3"), ("e4", "E4")]
PANELS = [("CondHealthy", "Healthy"), ("CondCongested", "Congested"),
          ("CondTransient", "Transient"), ("CondOutage", "Outage")]


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


# Chunks per complete burst, by rung. The gap is undefined for an escalation
# whose evidence never completed, so the gap series is conditional on
# completion -- and the ALERT series deliberately is not, because an alert's
# arrival does not depend on its evidence completing and conditioning it would
# import survivorship bias into the one claim that must not carry it.
EXPECTED = {"ref": 0, "e1": 1, "e2": 3, "e3": 41, "e4": 99}


def stats(cond, arm):
    """-> (median alert over ALL escalations, median gap over COMPLETE ones)"""
    alerts, gaps = [], []
    exp = EXPECTED[arm]
    for (c, m, _), rr in GA.items():
        if c != cond or m != arm:
            continue
        for r in rr:
            alerts.append(r[0])
            if r[2] >= exp:
                gaps.append(r[1] - r[0])
    if not alerts:
        return float("nan"), float("nan")
    return (statistics.median(alerts),
            statistics.median(gaps) if gaps else float("nan"))


# ===== FIGURE ================================================================
fig, axes = plt.subplots(2, 2, figsize=(3.5, 3.3), sharex=True, sharey=True)
fig.patch.set_facecolor(SURFACE)
x = np.arange(len(RUNGS))

for ax, (cond, name) in zip(axes.flat, PANELS):
    ax.set_facecolor(SURFACE)
    alert = np.array([stats(cond, a)[0] for a, _ in RUNGS])
    gap = np.array([stats(cond, a)[1] for a, _ in RUNGS])
    gap_d = np.where(gap < FLOOR, FLOOR, gap)

    ax.plot(x, alert, color=C_ALERT, lw=1.5, marker="o", ms=2.9,
            markeredgecolor=SURFACE, markeredgewidth=0.5, zorder=3)
    ln, = ax.plot(x, gap_d, color=C_GAP, lw=1.5, marker="s", ms=2.9,
                  markeredgecolor=SURFACE, markeredgewidth=0.5, zorder=3)
    ln.set_dashes([3.0, 1.3])
    # open marker where the gap is exactly zero, so the floor is not read as data
    for xi, g in zip(x, gap):
        if g < FLOOR:
            ax.plot([xi], [FLOOR], marker="s", ms=2.9, mfc=SURFACE,
                    mec=C_GAP, mew=0.9, zorder=4)

    ax.set_yscale("log")
    ax.set_ylim(FLOOR * 0.65, 6)
    ax.set_xlim(-0.35, len(RUNGS) - 0.65)
    ax.set_xticks(x)
    ax.set_xticklabels([lab for _, lab in RUNGS], fontsize=FS - 1.3, color=INK2)
    ax.set_yticks([FLOOR, 1e-2, 1e-1, 1])
    ax.set_yticklabels(["0*", "10 ms", "100 ms", "1 s"], fontsize=FS - 1.3,
                       color=INK2)
    ax.minorticks_off()
    ax.grid(True, which="major", color=GRID, lw=0.45, zorder=1)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("bottom", "left"):
        ax.spines[sp].set_color(GRID)
    ax.tick_params(length=0, pad=1.5)
    ax.set_title(name, fontsize=FS - 0.3, color=INK, pad=2.0)

# direct labels, placed once in the panel with the most room
a0 = axes.flat[0]
a0.annotate("dispatch gap", xy=(4, 0.233), xytext=(-1, 5),
            textcoords="offset points", fontsize=FS - 1.3, color=C_GAP,
            ha="right", va="bottom", zorder=5)
a0.annotate("alert delay", xy=(2, 0.016), xytext=(0, -5),
            textcoords="offset points", fontsize=FS - 1.3, color=C_ALERT,
            ha="center", va="top", zorder=5)

# legend: required for >=2 series even though both are direct-labelled above
from matplotlib.lines import Line2D
_al = Line2D([], [], color=C_ALERT, lw=1.5, marker="o", ms=2.9, label="alert delay")
_gp = Line2D([], [], color=C_GAP, lw=1.5, ls=(0, (3.0, 1.3)), marker="s", ms=2.9,
             label="dispatch gap")
fig.legend(handles=[_al, _gp], fontsize=FS - 1.0, loc="lower center",
           bbox_to_anchor=(0.56, -0.012), ncol=2, frameon=False,
           handlelength=2.0, columnspacing=1.5)

fig.supxlabel("evidence rung", fontsize=FS, color=INK, y=0.125)
fig.supylabel("median delay (log)", fontsize=FS, color=INK, x=0.015)
fig.text(0.0, 0.052, "*open marker: gap is\n exactly 0, at the floor",
         fontsize=FS - 2.2, color=INK2, va="bottom", linespacing=1.1)
fig.tight_layout(pad=0.3, rect=(0.02, 0.10, 1.0, 1.0))
for ext in ("pdf", "png"):
    fig.savefig(os.path.join(FIGDIR, f"figC2_alert_vs_decision.{ext}"), dpi=400,
                facecolor=SURFACE)
print("wrote figC2_alert_vs_decision.pdf/.png\n")

# ===== the numbers, so the caption cannot drift from the figure ==============
print(f"{'condition':15s} {'measure':8s}" + "".join(f"{lab:>9s}" for _, lab in RUNGS))
for cond, name in PANELS:
    al = [stats(cond, a)[0] for a, _ in RUNGS]
    gp = [stats(cond, a)[1] for a, _ in RUNGS]
    print(f"{cond:15s} {'alert':8s}" + "".join(f"{v:9.4f}" for v in al))
    print(f"{'':15s} {'gap':8s}" + "".join(f"{v:9.4f}" for v in gp))
    print(f"{'':15s} {'-> alert':8s} {al[-1]/al[0]:8.2f}x over the ladder, "
          f"gap {gp[0]:.4f} -> {gp[-1]:.4f}")
