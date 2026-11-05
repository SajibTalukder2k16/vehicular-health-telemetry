#!/usr/bin/env python3
"""Freshness-target sweep for aimdSelf: is the ablation's failure a tuning
artifact?

Reports BOTH streams per target, because the claim under test is not "the self
signal always loses camera" -- at a loose enough target it delivers camera by
never backing off at all -- but that no target reaches the joint point the
cross-stream arm reaches. Printed alongside the cross-stream arm's operating
point on the same conditions for exactly that comparison.

The cross-stream comparison row comes from results_sens_aimd/*-base-*, which
is aimd at the identical baseline parameters on the SAME dev seeds (100-102),
not from the held-out head-to-head runs. Comparing a dev-seed sweep against a
held-out-seed operating point would confound the signal source with the seed
set. Those runs predate the bucketRate statistic, so their mean rate is blank.

Usage: analyze_ablation_sweep.py [sweep-dir] [aimd-dev-dir]
"""
import glob
import math
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze_ablation import kpis, mean_ci, parse   # noqa: E402  same definitions

CONDS = ('CondCongested', 'CondTransient')


def collect(pattern, keyre):
    out = defaultdict(dict)
    for p in sorted(glob.glob(pattern)):
        m = re.match(keyre, os.path.basename(p)[:-4])
        if m:
            out[(m.group(1), m.group(2))][int(m.group(3))] = kpis(parse(p))
    return out


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    sweep = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        here, '..', 'simulations', 'pilot', 'results_ablation_sweep')
    abl = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        here, '..', 'simulations', 'pilot', 'results_sens_aimd')

    sw = collect(os.path.join(sweep, '*.sca'), r'(Cond\w+)-tgt(\d+)-s(\d+)$')
    ab = collect(os.path.join(abl, '*.sca'), r'(Cond\w+)-(base)-s(\d+)$')

    print('aimdSelf freshness-target sweep, dev seeds 100-102')
    print('timely delivery (%), mean +/- 95% CI; rate is the mean adapted rate')
    print()
    for cond in CONDS:
        tgts = sorted((int(t) for (c, t) in sw if c == cond))
        if not tgts:
            continue
        print(f'--- {cond} ---')
        print(f'{"target s":>9} {"vitals":>15} {"camera":>15} '
              f'{"backoff:probe":>14} {"rate kbps":>10}')
        for t in tgts:
            d = sw[(cond, str(t))]
            v, vci, _ = mean_ci([x['timely_vitals'] for x in d.values()])
            c, cci, _ = mean_ci([x['timely_camera'] for x in d.values()])
            bo, _, _ = mean_ci([x['backoffs'] for x in d.values()])
            pr, _, _ = mean_ci([x['probes'] for x in d.values()])
            mr, _, _ = mean_ci([x['meanRate'] for x in d.values()])
            print(f'{t:>9} {v:>8.1f} +/-{vci:>4.1f} {c:>8.1f} +/-{cci:>4.1f} '
                  f'{f"{bo:.0f}:{pr:.0f}":>14} {mr/1000:>10.1f}')
        # the point to beat: aimd at the same baseline on the same dev seeds
        d = ab[(cond, 'base')]
        if d:
            v, vci, _ = mean_ci([x['timely_vitals'] for x in d.values()])
            c, cci, _ = mean_ci([x['timely_camera'] for x in d.values()])
            mr, _, _ = mean_ci([x['meanRate'] for x in d.values()])
            rate = '-' if math.isnan(mr) else f'{mr/1000:.1f}'
            print(f'{"aimd 5":>9} {v:>8.1f} +/-{vci:>4.1f} {c:>8.1f} '
                  f'+/-{cci:>4.1f} {"(cross-stream)":>14} {rate:>10}')
        print()

    print('Reading: a target that protects vitals starves camera, and a target')
    print('that delivers camera has stopped controlling. The cross-stream arm')
    print('is dominated by neither tail if no swept row beats it on BOTH')
    print('columns at once.')


if __name__ == '__main__':
    main()
