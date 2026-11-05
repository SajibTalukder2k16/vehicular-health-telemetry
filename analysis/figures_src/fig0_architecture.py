#!/usr/bin/env python3
"""Fig. 0 — Three-tier architecture diagram.
Run: python3 fig0_architecture.py
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

from _shared import save

# ===== STYLE — edit freely ==================================================
INK = 'black'         # text / arrows / box borders
LIGHT = '#e8e8e8'      # highlight fill (edge device elements) -- neutral gray
FONT_FAMILY = ['Liberation Serif', 'Times New Roman', 'Times', 'DejaVu Serif']
FS_BOX, FS_SUB, FS_TIER, FS_ARROW = 8.2, 6.8, 8, 6.8
plt.rcParams.update({
    'font.family': 'serif', 'font.serif': FONT_FAMILY,
    'pdf.fonttype': 42, 'ps.fonttype': 42,
})
# ============================================================================

fig, ax = plt.subplots(figsize=(7.2, 2.9))
ax.set_xlim(0, 10.4)
ax.set_ylim(0, 3.6)
ax.axis('off')


def box(x, y, w, h, label, sub='', fc='white', lw=1.0, fs=FS_BOX,
        fs_sub=FS_SUB):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='square,pad=0.02',
                                fc=fc, ec=INK, lw=lw))
    ax.text(x + w/2, y + h/2 + (0.15 if sub else 0), label, ha='center',
            va='center', fontsize=fs, color=INK, fontweight='bold')
    if sub:
        ax.text(x + w/2, y + h/2 - 0.21, sub, ha='center', va='center',
                fontsize=fs_sub, color=INK)


def arrow(x1, y1, x2, y2, label='', ly=0.16, lx=0.0, fs=FS_ARROW):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle='-|>',
                                 mutation_scale=11, color=INK, lw=1.0))
    if label:
        ax.text((x1+x2)/2 + lx, (y1+y2)/2 + ly, label, ha='center',
                fontsize=fs, color=INK)


# Tier 1: three sensor streams, evenly spaced
box(0.2, 2.55, 1.95, 0.62, 'Wearable vitals', '512 B, exp(1 s)')
box(0.2, 1.35, 1.95, 0.62, 'OBD-II', '256 B, exp(2 s)')
box(0.2, 0.15, 1.95, 0.62, 'Cabin camera', '4/60 KiB, 2 Hz')

# Tier 2: edge aggregation/queue, plus the edge's own anomaly-detection
# logic, which is the source of the alarm stream (not a Tier-1 device)
box(3.55, 1.05, 2.15, 1.45, 'In-vehicle edge',
    'Finite queue +\nprocessing + UDP app', fc=LIGHT, lw=1.2)
# short internal arrow (filled dot = internally generated, not a Tier-1
# input) representing the edge's own anomaly detection triggering an alarm
ax.plot(4.625, 3.05, marker='o', markersize=4, color=INK)
arrow(4.625, 3.0, 4.625, 2.52)
ax.text(5.15, 2.78, 'Edge-detected\nalarm (128 B)', ha='left', va='center',
        fontsize=FS_ARROW, color=INK)

box(6.55, 1.05, 1.45, 1.45, 'LTE RAN', 'Multi-site,\nX2 handover')
box(8.85, 1.05, 1.4, 1.45, 'Cloud server', 'E2E delay,\ndeadlines, AoI',
    fs=7.8)

arrow(2.15, 2.86, 3.55, 2.2, 'BLE')
arrow(2.15, 1.66, 3.55, 1.7, 'Wired / BLE', ly=0.20)
arrow(2.15, 0.46, 3.55, 1.3, 'Wired / BLE', ly=-0.34)
arrow(5.7, 1.77, 6.55, 1.77, 'LTE\nuplink', ly=0.42)
arrow(8.0, 1.77, 8.85, 1.77, 'Wired', ly=0.28)

ax.text(1.17, 3.32, 'Tier 1 -- sensors', fontsize=FS_TIER, color=INK,
        ha='center')
ax.text(4.6, 3.32, 'Tier 2 -- edge device', fontsize=FS_TIER, color=INK,
        ha='center')
ax.text(9.55, 3.32, 'Tier 3 -- application', fontsize=FS_TIER, color=INK,
        ha='center')

save(fig, 'fig0_architecture')
