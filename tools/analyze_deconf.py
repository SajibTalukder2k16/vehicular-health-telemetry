#!/usr/bin/env python3
"""Marginal main effects of the RuralEdgeDeconf factorial, recomputed from source.

WHY THIS EXISTS. The de-confounding result (docs/CORRECTIONS_2026-10.md C7,
analysis/EFFECTS_SUMMARY.md) was reported without a script that regenerates it,
and when it was finally recomputed on 2026-11-04 not one of the six published
point estimates reproduced from the committed data -- two of them had the wrong
sign. The conclusion was unaffected, but a table nobody can regenerate is a
table nobody can check. This is that script.

DESIGN. [Config RuralEdgeDeconf] crosses camera link x OBD link x edge
processing time, 2 x 2 x 2, 30 seeds per cell, 240 runs, in the stressed rural
cell. The three factors were tied together by parallel iteration in Family A,
so "smartphone vs embedded edge" moved all three at once and the effect could
not be attributed.

PAIRING. `seed-set = ${repetition}`, so repetition N is the same seed draw in
every cell. The main effect of a factor is therefore computed as a per-seed
block contrast -- mean of that seed's four cells at the high level minus its
four at the low level -- and the interval is taken over the 30 block
differences. The original analysis pooled runs instead, which leaves the large
camera-link split inside the residual variance of the other two factors and
roughly doubles their intervals: OBD on timely camera goes from +/-4.0 pooled
to +/-1.4 paired. Both versions are printed, because the pooled one is what the
docs quoted and the difference is the point.

Usage: analyze_deconf.py [runs_detailed.csv]
"""
import csv
import math
import os
import statistics
import sys

# High level listed first in each pair: the effect is reported as HIGH - LOW,
# matching the published table's "BLE vs wired" and "slow vs fast" wording.
FACTORS = [
    ('camlink', 'BleLink', 'WiredLink', 'camera link BLE vs wired'),
    ('obdlink', 'BleLink', 'WiredLink', 'OBD link BLE vs wired'),
    ('proc', 'uniform(2ms,8ms)', 'uniform(0.5ms,2ms)', 'processing slow vs fast'),
]
METRICS = ['timely_vitals', 'timely_camera', 'delivery_e2e']

# t for 95% two-sided, by degrees of freedom; the project's other analyzers use
# the same table (tools/analyze_ablation.py). The published CIs used z=1.96,
# which is why they read ~4% narrower than these at n=30.
_T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
        8: 2.306, 9: 2.262, 10: 2.228, 12: 2.179, 15: 2.131, 20: 2.086,
        25: 2.060, 29: 2.045, 30: 2.042, 40: 2.021, 60: 2.000, 120: 1.980}


def t95(n):
    df = n - 1
    for k in sorted(_T95):
        if df <= k:
            return _T95[k]
    return 1.960


def mean_ci(xs):
    n = len(xs)
    if n == 0:
        return float('nan'), float('nan'), 0
    m = sum(xs) / n
    if n < 2:
        return m, float('nan'), n
    sd = statistics.stdev(xs)
    return m, t95(n) * sd / math.sqrt(n), n


def unquote(v):
    """The exporter wrote OMNeT++ iteration values as \\"BleLink\\" inside CSV."""
    return v.replace('\\', '').replace('"', '').strip()


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        here, '..', 'analysis', 'deconf', 'runs_detailed.csv')
    with open(path) as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        for k, *_ in FACTORS:
            r[k] = unquote(r[k])

    cells = {}
    for r in rows:
        cells.setdefault(tuple(r[k] for k, *_ in FACTORS), []).append(r)
    seeds = sorted({int(r['repetition']) for r in rows})

    print(f'RuralEdgeDeconf marginal main effects, recomputed from {path}')
    print(f'  {len(rows)} runs, {len(cells)} cells, '
          f'sizes {sorted({len(v) for v in cells.values()})}, '
          f'{len(seeds)} seeds ({min(seeds)}..{max(seeds)})')
    if len(cells) != 8 or {len(v) for v in cells.values()} != {30}:
        print('  WARNING: not the balanced 2x2x2x30 design the analysis assumes',
              file=sys.stderr)
    print()

    for metric in METRICS:
        print(f'=== {metric} (pp) ===')
        print(f'{"factor":<26} {"PAIRED (per-seed block)":>24} '
              f'{"POOLED (as published)":>22}')
        for key, hi, lo, label in FACTORS:
            blocks = []
            for s in seeds:
                a = [100 * float(r[metric]) for r in rows
                     if r[key] == hi and int(r['repetition']) == s]
                b = [100 * float(r[metric]) for r in rows
                     if r[key] == lo and int(r['repetition']) == s]
                if a and b:
                    blocks.append(sum(a) / len(a) - sum(b) / len(b))
            mp, cp, _n = mean_ci(blocks)

            a = [100 * float(r[metric]) for r in rows if r[key] == hi]
            b = [100 * float(r[metric]) for r in rows if r[key] == lo]
            ma, ca, _ = mean_ci(a)
            mb, cb, _ = mean_ci(b)
            pooled, cu = ma - mb, math.sqrt(ca * ca + cb * cb)

            sig = '' if abs(mp) <= cp else '  SIGNIFICANT'
            print(f'{label:<26} {f"{mp:+.2f} +/- {cp:.2f}":>24} '
                  f'{f"{pooled:+.2f} +/- {cu:.2f}":>22}{sig}')
        print()

    # The exchange rate the write-up quotes, recomputed so it cannot drift.
    def eff(metric):
        key, hi, lo, _ = FACTORS[0]
        a = [100 * float(r[metric]) for r in rows if r[key] == hi]
        b = [100 * float(r[metric]) for r in rows if r[key] == lo]
        return sum(a) / len(a) - sum(b) / len(b)

    v, c = eff('timely_vitals'), eff('timely_camera')
    print(f'Camera-link exchange rate: {v:+.2f} pp vitals per {c:+.2f} pp camera '
          f'= {abs(v / c):.3f} pp vitals per pp camera given up')
    return 0


if __name__ == '__main__':
    sys.exit(main())
