#!/usr/bin/env python3
"""F1 -- C1 drawn: PRV-grade sensing fails five of six capacity constraints.

THE FORM, AND WHY
  The constraints do not share a unit: four are bitrates (Mb/s) and two are
  per-frame compute costs (ms/frame). Plotting them on one axis in native units
  is the dual-axis mistake. So the quantity plotted is the DIMENSIONLESS ratio

      requirement / capacity

  for which 1.0 is the wall itself. The reader's job is "above or below a
  baseline", which makes this a DIVERGING form about that wall -- and plotting
  log10(ratio) puts the wall at a true zero baseline, so bars are legal here.
  (Bars on a raw log axis would not be: a log axis has no zero, so bar LENGTH
  would encode nothing.)

  Feasibility is carried by POSITION -- left of the wall is feasible, right is
  not -- which leaves the two hues free to carry the only identity in the
  chart, the sensing grade. Nothing is double-encoded.

PRINT / GRAYSCALE
  Two series, validated: #2a78d6 / #eb6834 pass all six checks in light mode
  (worst adjacent dE 24.7 protan, 33.6 normal). HR additionally carries a hatch
  so identity survives a grayscale print, and every bar is direct-labelled, so
  identity is never colour-alone.

SOURCES -- every constant below is derived or measured elsewhere, not chosen
  PRV-grade video     25.5 Mb/s   Cerina 2019 Tables 1+7, H.264 CRF 8, the
                                  conservative end of the usable threshold
                                  (PLAN_2026-11.md 5.2)
  HR-grade video      0.110 Mb/s  Nowara 2020 4.1, CRF 24, HR MAE 1.4 bpm
                                  (PLAN_2026-11.md 5.3)
  PRV frame rate      60 fps      Cerina 2019 recording format -> 16.67 ms/frame
  HR frame rate       20 fps      the HR floor (PLAN_2026-11.md 5.1) -> 50 ms
  BLE 4.2 DLE         0.737 Mb/s  measured, within 1.5% of Gomez 2012/Tosi 2017
  Cellular uplink     3 Mb/s      FCC LTE benchmark (10/3)
  802.11a/g 80% busy  6.18 Mb/s   measured, same module
  802.11a/g quiet     30.9 Mb/s   measured, -1.6% vs Jun 2003
  Edge PC-class       22.73 ms    Kim & Koo 2023, Beelink Mini PC
  Edge embedded       94.27 ms    Kim & Koo 2023, Jetson Nano

  The two compute figures are an EXTRAPOLATION and the caption must say so:
  Kim & Koo measure a blink-based drowsiness pipeline, not rPPG PRV
  extraction (PARAMETER_PROVENANCE.md A.7).
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

HERE = os.path.dirname(os.path.abspath(__file__))
FIGDIR = os.path.join(HERE, "..", "figures")
os.makedirs(FIGDIR, exist_ok=True)

# ===== STYLE =================================================================
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#d8d7d3"
S_PRV = "#2a78d6"      # categorical slot 1
S_HR = "#eb6834"       # categorical slot 2
FAIL_WASH = "#f2efe9"  # the infeasible half-plane, barely there
FS = 7.0

# ===== DATA (see SOURCES above) ==============================================
PRV_BPS, HR_BPS = 25.5, 0.110          # Mb/s
PRV_BUDGET_MS, HR_BUDGET_MS = 1000.0 / 60.0, 1000.0 / 20.0
EDGE_PC_MS, EDGE_EMB_MS = 22.73, 94.27
# Retrieved 2026-11-16 and verified against the full text: Liu, Hill, Jiang,
# Patel & McDuff, EfficientPhys, WACV 2023, pp. 5008-5017, Table 4 -- on-device
# per-frame latency on a Raspberry Pi 4B. This is a MEASURED rPPG pipeline,
# which is what this wall always needed; Kim & Koo's blink-detection figures
# above are retained because they are the two device classes the 960-run edge
# campaign actually swept, and the rPPG cost falls between them.
#   EfficientPhys-C/T2 40 | EfficientPhys-T1 300 | TS-CAN 63 (3 pre + 60)
#   Dual-GAN >275 (preprocessing alone) | POS 27 | CHROM 28 | ICA 31
# The two plotted below are the BEST case of each kind, so the wall is drawn
# at its most favourable: no method tested clears the PRV budget.
EDGE_RPPG_BEST_MS = 27.0        # POS, the fastest of the eight
EDGE_RPPG_NN_MS = 40.0          # EfficientPhys-C/T2, fastest learned method

LINKS = [                               # (label, capacity Mb/s)
    ("BLE 4.2 DLE", 0.737),
    ("Cellular uplink", 3.0),
    ("Wi-Fi, 80% busy", 6.18),
    ("Wi-Fi, quiet", 30.9),
]
COMPUTE = [                             # (label, per-frame cost ms)
    ("Edge, embedded", EDGE_EMB_MS),
    ("rPPG net, Pi 4B", EDGE_RPPG_NN_MS),
    ("rPPG signal, Pi 4B", EDGE_RPPG_BEST_MS),
    ("Edge, PC-class", EDGE_PC_MS),
]

rows = []   # (label, prv_ratio, hr_ratio)
for lbl, cap in LINKS:
    rows.append((lbl, PRV_BPS / cap, HR_BPS / cap))
for lbl, cost in COMPUTE:
    rows.append((lbl, cost / PRV_BUDGET_MS, cost / HR_BUDGET_MS))
rows.sort(key=lambda r: r[1], reverse=True)     # worst for PRV first

labels = [r[0] for r in rows]
prv = np.array([r[1] for r in rows])
hr = np.array([r[2] for r in rows])

# ===== FIGURE ================================================================
fig, ax = plt.subplots(figsize=(3.5, 2.75))
fig.patch.set_facecolor(SURFACE)
ax.set_facecolor(SURFACE)

y = np.arange(len(rows))[::-1]          # worst at the top
h = 0.34
XLO, XHI = np.log10(0.00055), np.log10(300)

ax.axvspan(0, XHI, color=FAIL_WASH, zorder=0, lw=0)

b1 = ax.barh(y + h / 2 + 0.02, np.log10(prv), height=h, color=S_PRV,
             edgecolor=SURFACE, linewidth=0.8, zorder=3)
b2 = ax.barh(y - h / 2 - 0.02, np.log10(hr), height=h, color=S_HR,
             edgecolor=SURFACE, linewidth=0.8, hatch="////", zorder=3)

ax.axvline(0, color=INK, lw=1.1, zorder=4)

# direct labels -- the required relief for the contrast WARN, and the point
def lab(bars, vals):
    for r, v in zip(bars, vals):
        x = np.log10(v)
        txt = f"{v:.1f}x" if v >= 10 else (f"{v:.2f}x" if v >= 0.01 else f"{v:.3f}x")
        ax.text(x + (0.07 if x >= 0 else -0.07), r.get_y() + r.get_height() / 2,
                txt, fontsize=FS - 1.0, color=INK2, va="center",
                ha="left" if x >= 0 else "right", zorder=5)

lab(b1, prv)
lab(b2, hr)

ticks = [0.003, 0.03, 0.3, 3, 30]
ax.set_xticks(np.log10(ticks))
ax.set_xticklabels([("%g" % t) for t in ticks], fontsize=FS - 0.5, color=INK2)
ax.set_xlim(XLO, XHI)
ax.set_ylim(-0.75, len(rows) - 0.25)
ax.set_yticks(y)
ax.set_yticklabels(labels, fontsize=FS, color=INK)
ax.set_xlabel("requirement $\\div$ capacity    (1 = the wall)",
              fontsize=FS, color=INK, labelpad=2)

ax.xaxis.grid(True, color=GRID, lw=0.5, zorder=1)
ax.set_axisbelow(True)
ax.yaxis.grid(False)
for sp in ("top", "right", "left"):
    ax.spines[sp].set_visible(False)
ax.spines["bottom"].set_color(GRID)
ax.tick_params(length=0)

# feasibility, named once at the top where there is whitespace
ytop = len(rows) - 0.45
ax.text(np.log10(0.006), ytop, "feasible", fontsize=FS - 1.0, color=INK2,
        ha="center", va="center", style="italic", zorder=5)
ax.text(np.log10(18), ytop, "infeasible", fontsize=FS - 1.0, color=INK2,
        ha="center", va="center", style="italic", zorder=5)

ax.legend(handles=[Patch(facecolor=S_PRV, edgecolor=SURFACE, label="PRV-grade"),
                   Patch(facecolor=S_HR, edgecolor=SURFACE, hatch="////",
                         label="HR-grade")],
          fontsize=FS - 0.5, loc="upper center", bbox_to_anchor=(0.5, -0.20),
          ncol=2, frameon=False, handlelength=1.6, handleheight=0.9,
          columnspacing=1.4, borderaxespad=0.0)

fig.tight_layout(pad=0.35)
for ext in ("pdf", "png"):
    fig.savefig(os.path.join(FIGDIR, f"figC1_three_walls.{ext}"), dpi=400,
                facecolor=SURFACE)
print("wrote figC1_three_walls.pdf/.png")

# ===== the numbers, printed so the caption cannot drift from the figure ======
print(f"\n{'constraint':26s} {'PRV':>9s} {'HR':>9s}")
for lbl, p, hh in rows:
    print(f"{lbl:26s} {p:8.3f}x {hh:8.3f}x")
print(f"\nPRV infeasible on {sum(1 for _, p, _ in rows if p > 1)} of {len(rows)};"
      f"  HR infeasible on {sum(1 for _, _, hh in rows if hh > 1)} of {len(rows)}")
