"""Data-loading helpers shared by the figure scripts.

Style is deliberately NOT shared: every figure script carries its own
style block so each can be restyled independently.
"""
import os
import re

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ANALYSIS = os.path.join(HERE, '..')                 # analysis/
ROOT = os.path.join(ANALYSIS, '..')                 # PaperRebuild/
FIGDIR = os.path.join(ANALYSIS, 'figures')
os.makedirs(FIGDIR, exist_ok=True)


def load_family_a():
    """Family A (Urban/Rural factorial) runs with numeric factor columns."""
    runs = pd.read_csv(os.path.join(ANALYSIS, 'runs_detailed.csv'))
    fam = runs[runs.config.isin(['Urban', 'Rural'])].copy()
    for c in ('isd', 'speed', 'bgues', 'payload'):
        fam[c] = pd.to_numeric(fam[c], errors='coerce')
    fam['camlink'] = fam['camlink'].str.strip('"\\\\')
    return fam


def load_vec(case, name, seeds=range(3)):
    """All (time, value) arrays for a named vector in a case study's subset."""
    out = []
    for r in seeds:
        df = pd.read_csv(os.path.join(ANALYSIS, 'vectors', f'{case}_r{r}.csv'))
        rows = df[(df.type == 'vector') & (df.name == name)]
        for _, rr in rows.iterrows():
            out.append((np.fromstring(rr.vectime, sep=' '),
                        np.fromstring(rr.vecvalue, sep=' ')))
    return out


def sim_time_limit(case_ini):
    """sim-time-limit (s) from a case study's omnetpp.ini."""
    txt = open(os.path.join(ROOT, case_ini)).read()
    m = re.search(r'^\s*sim-time-limit\s*=\s*([\d.]+)\s*s', txt, re.M)
    if not m:
        raise ValueError(f'no sim-time-limit in {case_ini}')
    return float(m.group(1))


def aoi_series(t, delay, horizon):
    """Age of Information staircase over the FULL observation window [0, horizon].

    AoI at time s is s minus the generation time of the freshest observation
    received by s: it grows linearly between updates and drops on each arrival
    carrying a newer observation.

    horizon is required and must be the configured sim-time-limit. Ending the
    series at the last received update -- which an earlier version of the figure
    script did -- silently truncates the final outage. On the rural corridor the
    last vitals update arrived at t=691 s of a 922 s drive in one seed, so
    truncation reported a 25 s peak where the true peak is 232 s, and it made
    the worst seed look like the mildest.
    """
    t = np.asarray(t, dtype=float)
    gen = t - np.asarray(delay, dtype=float)
    best = -np.inf
    pts = []                                   # (arrival time, AoI just after)
    for ti, gi in zip(t, gen):
        if gi > best:
            best = gi
            pts.append((ti, ti - gi))
    if not pts:                                # nothing ever arrived
        return np.array([0.0, horizon]), np.array([0.0, horizon])
    xs, ys = [0.0], [0.0]
    prev_t, prev_a = 0.0, 0.0
    for ti, ai in pts:
        xs.append(ti)
        ys.append(prev_a + (ti - prev_t))      # aged just before this arrival
        xs.append(ti)
        ys.append(ai)                          # reset by this arrival
        prev_t, prev_a = ti, ai
    if horizon > prev_t:                       # the final, unterminated outage
        xs.append(horizon)
        ys.append(prev_a + (horizon - prev_t))
    return np.array(xs), np.array(ys)


def aoi_stats(t, delay, horizon, threshold):
    """Peak / mean AoI and time above a freshness threshold over [0, horizon]."""
    xs, ys = aoi_series(t, delay, horizon)
    above = 0.0
    for i in range(len(xs) - 1):
        x0, x1, y0, y1 = xs[i], xs[i + 1], ys[i], ys[i + 1]
        if x1 <= x0:
            continue
        if y0 >= threshold and y1 >= threshold:
            above += x1 - x0
        elif y1 > threshold:                   # rising through the threshold
            above += (x1 - x0) * (y1 - threshold) / (y1 - y0)
        elif y0 > threshold:                   # falling through it
            above += (x1 - x0) * (y0 - threshold) / (y0 - y1)
    # time of the last arrival that refreshed the age (the trough before the
    # final outage); equals horizon only if an update landed at the cutoff
    troughs = [x for i, x in enumerate(xs) if i and ys[i] < ys[i - 1]]
    last_update = float(troughs[-1]) if troughs else 0.0
    return {'peak': float(ys.max()),
            'mean': float(np.trapezoid(ys, xs) / horizon),
            'time_above': float(above),
            'frac_above': float(above / horizon),
            'last_update': last_update}


def towers_from_ini(relpath):
    """eNodeB (x, y) positions from a towers_*.ini fragment."""
    txt = open(os.path.join(ROOT, relpath)).read()
    xs = [float(v) for v in re.findall(r'initialX = ([\d.]+)m', txt)]
    ys = [float(v) for v in re.findall(r'initialY = ([\d.]+)m', txt)]
    return np.array(list(zip(xs, ys)))


def trace_positions(relpath):
    """(t, x, y) arrays from a BonnMotion trace."""
    vals = open(os.path.join(ROOT, relpath)).readline().split()
    a = np.array(vals, dtype=float).reshape(-1, 3)
    return a[:, 0], a[:, 1], a[:, 2]


def save(fig, name, dpi=300):
    fig.savefig(os.path.join(FIGDIR, name + '.png'), dpi=dpi,
                bbox_inches='tight')
    fig.savefig(os.path.join(FIGDIR, name + '.pdf'), bbox_inches='tight')
    print('wrote', os.path.join(FIGDIR, name + '.{png,pdf}'))
