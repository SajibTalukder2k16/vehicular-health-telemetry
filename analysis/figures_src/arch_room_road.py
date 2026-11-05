#!/usr/bin/env python3
"""Architecture figure for both settings: room and road, one shared rig.

Why a fork rather than two panels. The claim the figure has to carry is that
the sensor rig and the edge device are IDENTICAL in the two settings -- that
is what simulations/room/omnetpp.ini's RoomMatched* configs were built for,
and it is the only reason the two settings may be quoted against each other
at all. Two side-by-side panels would draw the shared part twice and bury
exactly that point. So Tier 1 and Tier 2 are drawn once, the path forks at the
backhaul, and the two branches rejoin at the same Tier-3 server.

What this figure adds over the old fig0_architecture:

  1. The room path exists at all. fig0 drew LTE only.
  2. The admission gate is marked inside the edge device, where it sits --
     upstream of the socket, because once a frame is handed to UDP it is
     committed to the RLC/PDCP queues.
  3. The freshness feedback loop is drawn. fig0 had no return path, so it
     depicted a pipeline rather than a controller.

Every measured number on the figure is computed here from the .sca corpus
through analyze_ablation.kpis -- the same definition as every table in the
paper -- so the annotations cannot drift from the text. Nothing is typed in.

Colour: orange marks the controller and its feedback, matching
fig6_oracle_frontier.py where orange is the controller throughout. Identity
never rests on hue alone -- the gate is also labelled and the feedback path is
also dashed -- so the figure survives grayscale printing, which a journal PDF
has to.

Usage: python arch_room_road.py [out-dir]
"""
import glob
import os
import re
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt                              # noqa: E402
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from analyze_ablation import kpis, parse                     # noqa: E402

INK = '#0b0b0b'
INK_SOFT = '#52514e'
LIGHT = '#eeeeee'
SURFACE = '#ffffff'
CTRL = '#eb6834'          # the controller, as in fig6/fig7

plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['DejaVu Serif'],
    'pdf.fonttype': 42,
    'ps.fonttype': 42,
})
FS_BOX, FS_SUB, FS_TIER, FS_ARROW, FS_NOTE = 7.4, 6.0, 7.2, 6.0, 6.0


# ---------------------------------------------------------------------------
# measured numbers, from the corpus
# ---------------------------------------------------------------------------
def span(vals, dp=1, ceiling=None):
    """'lo-hi' over config means, collapsed when they agree AT THE PRINTED
    PRECISION. Comparing the raw floats instead prints '9-9', which is how
    this first came out.

    `ceiling` guards against a rounding that reads as a stronger claim than
    the data supports: the matched room's timely-vitals mean is 99.988 -- one
    seed in thirty has a late vitals packet -- and printing '100.0' on a
    figure asserts that none does. When a value is below the ceiling but
    rounds onto it, the precision is raised until it does not.
    """
    def fmt(d):
        lo, hi = f'{min(vals):.{d}f}', f'{max(vals):.{d}f}'
        return lo if lo == hi else f'{lo}-{hi}'

    if ceiling is not None and min(vals) < ceiling:
        while dp < 4 and f'{min(vals):.{dp}f}' == f'{ceiling:.{dp}f}':
            dp += 1
    return fmt(dp)


def span_time(vals):
    """Delay range, in ms or s, whichever keeps it readable. The rural
    aggregate runs to tens of seconds, so a fixed ms unit is unhelpful."""
    if max(vals) >= 1000.0:
        return span([v / 1000.0 for v in vals], dp=1), 's'
    return span(vals, dp=1), 'ms'


def mean_of(rows, key):
    vals = [r[key] for r in rows if key in r]
    return sum(vals) / len(vals) if vals else float('nan')


def stats_mean(path, stat):
    want = False
    with open(path) as f:
        for line in f:
            if line.startswith('statistic '):
                want = line.rstrip('\n').endswith(' ' + stat)
            elif want and line.startswith('field mean '):
                return float(line.split()[2])
    return float('nan')


def regime(pattern, keyre, delay_stat='e2eDelay:stats'):
    """config -> {timely_vitals, timely_camera, delay_ms} over its seeds."""
    cells = {}
    for p in sorted(glob.glob(pattern)):
        m = re.match(keyre, os.path.basename(p)[:-4])
        if not m:
            continue
        row = kpis(parse(p))
        row['delay_ms'] = stats_mean(p, delay_stat) * 1e3
        cells.setdefault(m.group(1), []).append(row)
    return {c: {k: mean_of(rows, k)
                for k in ('timely_vitals', 'timely_camera', 'delay_ms')}
            for c, rows in cells.items()}


def measured():
    sims = os.path.join(ROOT, 'simulations')
    room = regime(os.path.join(sims, 'room', 'results_matched', '*.sca'),
                  r'(RoomMatched\w+)-#(\d+)$')
    urban = regime(os.path.join(sims, 'dc_case', 'results', '*.sca'),
                   r'(DcDrive\w+)-#(\d+)$')
    rural = regime(os.path.join(sims, 'corridorpop', 'results_seeds10',
                                '*.sca'),
                   r'(c\d+)-aimd-s(\d+)$')
    out = {}
    for name, cells in (('room', room), ('urban', urban), ('rural', rural)):
        if not cells:
            out[name] = None
            continue
        d, unit = span_time([c['delay_ms'] for c in cells.values()])
        out[name] = {
            'v': span([c['timely_vitals'] for c in cells.values()], dp=1,
                      ceiling=100.0),
            'c': span([c['timely_camera'] for c in cells.values()], dp=1,
                      ceiling=100.0),
            'd': d, 'dunit': unit,
            'n': len(cells),
        }
    return out


# ---------------------------------------------------------------------------
# drawing
# ---------------------------------------------------------------------------
def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        ROOT, 'manuscript', 'figures')
    os.makedirs(outdir, exist_ok=True)
    m = measured()
    for k in ('room', 'urban', 'rural'):
        if m[k] is None:
            print(f'warning: no runs found for the {k} regime; '
                  f'its annotation will be left blank', file=sys.stderr)

    fig, ax = plt.subplots(figsize=(7.16, 3.45))
    ax.set_xlim(0, 12.0)
    ax.set_ylim(0, 4.60)
    ax.axis('off')
    ax.set_position([0, 0, 1, 1])

    def box(x, y, w, h, label, sub='', fc=SURFACE, lw=0.9, fs=FS_BOX,
            ec=INK):
        ax.add_patch(FancyBboxPatch((x, y), w, h,
                                    boxstyle='square,pad=0.02',
                                    fc=fc, ec=ec, lw=lw, zorder=3))
        nsub = sub.count('\n') + 1 if sub else 0
        dy = 0.15 + 0.05 * (nsub - 1) if sub else 0.0
        ax.text(x + w / 2, y + h / 2 + dy, label, ha='center', va='center',
                fontsize=fs, color=INK, fontweight='bold', zorder=4)
        if sub:
            ax.text(x + w / 2, y + h / 2 - 0.20 - 0.05 * (nsub - 1), sub,
                    ha='center', va='center', fontsize=FS_SUB, color=INK,
                    zorder=4, linespacing=1.25)

    def arrow(x1, y1, x2, y2, label='', ly=0.17, lx=0.0, color=INK,
              style='-', lw=0.9, ha='center'):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle='-|>',
                                     mutation_scale=9, color=color, lw=lw,
                                     linestyle=style, zorder=2,
                                     shrinkA=0, shrinkB=0))
        if label:
            ax.text((x1 + x2) / 2 + lx, (y1 + y2) / 2 + ly, label, ha=ha,
                    va='center', fontsize=FS_ARROW, color=color, zorder=4,
                    linespacing=1.2)

    # ---- Tier 1: the sensor rig, identical in both settings ---------------
    box(0.10, 3.30, 1.95, 0.60, 'Wearable vitals', '512 B, exp(1 s)')
    # OBD-II is a vehicle port. A room deployment has the wearable and the
    # camera only; the matched indoor runs carry the OBD stream anyway, to
    # hold the rig constant, which makes the indoor result conservative.
    # The note goes BELOW the box: a second sub-line clips through the frame.
    box(0.10, 2.22, 1.95, 0.60, 'OBD-II context', '256 B, exp(2 s)')
    ax.text(1.07, 2.10, 'vehicle only — see caption', ha='center',
            va='top', fontsize=FS_NOTE, color=INK_SOFT, zorder=4,
            style='italic')
    box(0.10, 1.14, 1.95, 0.60, 'Cabin camera', '4 KiB, 2 Hz')

    # ---- Tier 2: the edge device, identical in both settings --------------
    # No label on the container box: box() centres its label, which lands
    # behind the admission gate. The title is placed explicitly instead.
    box(3.05, 1.55, 2.20, 1.90, '', fc=LIGHT, lw=1.1)
    ax.text(4.15, 3.18, 'Edge device', ha='center', va='center',
            fontsize=FS_BOX, fontweight='bold', color=INK, zorder=4)
    ax.text(4.15, 1.95, 'finite queue +\nprocessing + UDP',
            ha='center', va='center', fontsize=FS_SUB, color=INK,
            zorder=4, linespacing=1.25)
    # the admission gate, where it actually sits: upstream of the socket
    box(3.22, 2.46, 1.86, 0.46, 'camera admission gate', fc=SURFACE,
        ec=CTRL, lw=1.2, fs=FS_SUB)

    arrow(2.05, 3.60, 3.05, 3.05, 'BLE', ly=0.20)
    arrow(2.05, 2.52, 3.05, 2.55, 'wired / BLE', ly=0.19)
    arrow(2.05, 1.44, 3.05, 2.05, 'wired / BLE / WLAN', ly=-0.24)

    # the alarm is generated at the edge, not by a Tier-1 device
    ax.plot(4.15, 3.98, marker='o', markersize=3.2, color=INK, zorder=4)
    arrow(4.15, 3.96, 4.15, 3.47)
    ax.text(4.42, 3.80, 'edge-detected\nalarm (128 B)', ha='left',
            va='center', fontsize=FS_ARROW, color=INK, linespacing=1.2)

    # ---- the fork: the backhaul is the ONLY thing that differs ------------
    ax.plot([5.62, 5.62], [1.72, 3.30], '-', color=INK_SOFT, lw=0.8,
            zorder=1)
    arrow(5.25, 2.50, 5.62, 2.50, lw=0.9)
    arrow(5.62, 3.28, 6.32, 3.28, lw=0.9)
    arrow(5.62, 1.74, 6.32, 1.74, lw=0.9)

    box(6.32, 2.95, 2.05, 0.66, 'ROOM: 802.11n/ac',
        '10 m room, stationary')
    box(6.32, 1.35, 2.05, 0.78, 'ROAD: LTE RAN',
        'multi-site, X2 handover,\nvehicle in motion')

    # ---- Tier 3 --------------------------------------------------------
    box(9.72, 2.14, 2.10, 0.74, 'Application server',
        'delay, deadlines, AoI')
    arrow(8.37, 3.28, 9.72, 2.72, lw=0.9)
    arrow(8.37, 1.74, 9.72, 2.30, lw=0.9)

    # ---- the control loop, which the old figure did not show --------------
    fb = 1.08                       # the return path's horizontal run
    for a, b in (((10.77, 2.14), (10.77, fb)), ((10.77, fb), (4.15, fb))):
        ax.add_patch(FancyArrowPatch(
            a, b, arrowstyle='-', color=CTRL, lw=1.0,
            linestyle=(0, (3, 2)), zorder=2, shrinkA=0, shrinkB=0))
    ax.add_patch(FancyArrowPatch(
        (4.15, fb), (4.15, 1.53), arrowstyle='-|>', mutation_scale=9,
        color=CTRL, lw=1.0, linestyle=(0, (3, 2)), zorder=2,
        shrinkA=0, shrinkB=0))
    ax.text(7.46, fb + 0.08, 'receiver-confirmed delivery freshness, every '
            '200 ms', ha='center', va='bottom', fontsize=FS_ARROW,
            color=CTRL, zorder=4)

    # ---- measured outcome per regime, in one strip, read left to right ----
    # The three blocks ARE the title's argument: same rig, same edge, and the
    # problem the gate exists to solve appears only in the third.
    # The rule starts clear of the heading; spanning the full width drew it
    # straight through the words.
    ax.plot([3.05, 11.82], [0.80, 0.80], '-', color='#cccccc', lw=0.6,
            zorder=1)

    def note(x, head, d):
        if d is None:
            txt = f'{head}\n(no runs found)'
        else:
            txt = (f'{head}\n'
                   f'timely vitals {d["v"]} %\n'
                   f'timely camera {d["c"]} %\n'
                   f'mean delay {d["d"]} {d["dunit"]}')
        ax.text(x, 0.66, txt, ha='left', va='top', fontsize=FS_NOTE,
                color=INK_SOFT, zorder=4, linespacing=1.38)

    ax.text(0.10, 0.74, 'measured, same rig throughout:', ha='left',
            va='bottom', fontsize=FS_NOTE, color=INK, zorder=4)
    note(0.10, 'room, no admission control', m['room'])
    note(4.15, 'urban road, no admission control', m['urban'])
    note(8.20, 'rural corridors, controller active', m['rural'])

    ax.text(1.07, 4.32, 'Tier 1 — sensors', fontsize=FS_TIER,
            color=INK, ha='center')
    ax.text(4.15, 4.32, 'Tier 2 — edge', fontsize=FS_TIER,
            color=INK, ha='center')
    ax.text(7.34, 4.32, 'backhaul — the only difference',
            fontsize=FS_TIER, color=INK, ha='center')
    ax.text(10.77, 4.32, 'Tier 3 — application', fontsize=FS_TIER,
            color=INK, ha='center')

    for ext in ('pdf', 'png'):
        path = os.path.join(outdir, f'arch_room_road.{ext}')
        fig.savefig(path, dpi=400, bbox_inches='tight', facecolor=SURFACE)
        print('wrote', path)

    print('\nannotations drawn (recomputed from the corpus):')
    for k in ('room', 'urban', 'rural'):
        print(f'  {k:<6} {m[k]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
