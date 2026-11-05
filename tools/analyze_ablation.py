#!/usr/bin/env python3
"""Cross-stream vs. self-signal AIMD: paired analysis of results_ablation.

Metric definitions are taken from tools/export_results.py verbatim --
timely_t = (received_t - deadlineMisses_t) / generated_t -- so the numbers here
are comparable with every other table in the study rather than a second,
subtly different definition.

The two arms share seeds and RNG stream separation, so the comparison is
PAIRED: the per-seed difference is the statistic, and its CI is narrower and
more honest than differencing two independent means.

Usage: analyze_ablation.py [results-dir]
"""
import glob
import math
import os
import re
import sys
from collections import defaultdict

SCALAR_RE = re.compile(r'^scalar (\S+) (\S+) (\S+)$')
SRCMOD = {'vitals': '.wearable', 'camera': '.camera',
          'obd': '.obd', 'alarm': '.alarm'}
# n -> two-sided 95% t quantile, as in export_results.py
T95 = {2: 12.71, 3: 4.303, 4: 3.182, 5: 2.776, 10: 2.262, 20: 2.093, 30: 2.045}
CONDS = ('CondHealthy', 'CondCongested', 'CondTransient', 'CondOutage')
ARMS = ('aimd', 'aimdSelf')


def t95(n):
    if n <= 1:
        return float('nan')
    if n >= 40:
        return 1.96
    return T95[min(T95, key=lambda k: abs(k - n))]


def parse(path):
    sc = {}
    with open(path) as f:
        for line in f:
            m = SCALAR_RE.match(line.rstrip('\n'))
            if m:
                try:
                    sc[(m.group(1), m.group(2))] = float(m.group(3))
                except ValueError:
                    pass
    return sc


def total(sc, name):
    return sum(v for (_m, n), v in sc.items() if n == name)


def one(sc, name):
    """A scalar recorded by exactly one module (the gateway app)."""
    for (_m, n), v in sc.items():
        if n == name:
            return v
    return float('nan')


def kpis(sc):
    out = {}
    for t in ('vitals', 'camera'):
        g = sum(v for (m, n), v in sc.items()
                if n == 'packetsGenerated' and m.endswith(SRCMOD[t]))
        r = total(sc, f'received_{t}')
        late = total(sc, f'deadlineMisses_{t}')
        out[f'timely_{t}'] = 100.0 * (r - late) / g if g else float('nan')
        out[f'gen_{t}'] = g
    for k, s in (('backoffs', 'aimdBackoffs'), ('probes', 'aimdProbes'),
                 ('meanRate', 'meanBucketRateBps'),
                 ('finalRate', 'finalBucketRateBps'),
                 ('maxSignalAge', 'maxObservedVitalsAge')):
        out[k] = one(sc, s)
    return out


def mean_ci(xs):
    xs = [x for x in xs if not math.isnan(x)]
    n = len(xs)
    if n == 0:
        return float('nan'), float('nan'), 0
    mu = sum(xs) / n
    if n == 1:
        return mu, float('nan'), 1
    sd = math.sqrt(sum((x - mu) ** 2 for x in xs) / (n - 1))
    return mu, t95(n) * sd / math.sqrt(n), n


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        '..', 'simulations', 'pilot', 'results_ablation')
    data = defaultdict(dict)        # (cond, arm) -> seed -> kpis
    for p in sorted(glob.glob(os.path.join(root, '*.sca'))):
        base = os.path.basename(p)[:-4]
        m = re.match(r'(Cond\w+)-(\w+)-s(\d+)$', base)
        if not m:
            continue
        cond, arm, seed = m.group(1), m.group(2), int(m.group(3))
        data[(cond, arm)][seed] = kpis(parse(p))

    print('WORKLOAD CHECK -- the arms must be offered identical traffic, or')
    print('the comparison is not paired (see simulations/pilot/omnetpp.ini).')
    print(f'{"condition":<15} {"stream":<8} {"aimd":>10} {"aimdSelf":>10}  {"max drift":>9}')
    for cond in CONDS:
        for t in ('vitals', 'camera'):
            a = [v[f'gen_{t}'] for v in data[(cond, 'aimd')].values()]
            b = [v[f'gen_{t}'] for v in data[(cond, 'aimdSelf')].values()]
            if not a or not b:
                continue
            drift = max(abs(x - y) for x, y in zip(sorted(a), sorted(b)))
            print(f'{cond:<15} {t:<8} {sum(a)/len(a):>10.1f} '
                  f'{sum(b)/len(b):>10.1f}  {drift:>9.0f}')

    print()
    print('TIMELY DELIVERY (%), mean +/- 95% CI over 10 held-out seeds')
    hdr = (f'{"condition":<15} {"arm":<9} {"vitals":>16} {"camera":>16} '
           f'{"backoff:probe":>14} {"mean rate kbps":>15}')
    print(hdr)
    for cond in CONDS:
        for arm in ARMS:
            d = data[(cond, arm)]
            if not d:
                continue
            v, vci, n = mean_ci([x['timely_vitals'] for x in d.values()])
            c, cci, _ = mean_ci([x['timely_camera'] for x in d.values()])
            bo, _, _ = mean_ci([x['backoffs'] for x in d.values()])
            pr, _, _ = mean_ci([x['probes'] for x in d.values()])
            mr, _, _ = mean_ci([x['meanRate'] for x in d.values()])
            ratio = f'{bo:.0f}:{pr:.0f}'
            print(f'{cond:<15} {arm:<9} {v:>9.1f} +/-{vci:>4.1f} '
                  f'{c:>9.1f} +/-{cci:>4.1f} {ratio:>14} {mr/1000:>15.1f}')

    print()
    print('PAIRED DIFFERENCE, aimdSelf - aimd (pp), mean +/- 95% CI')
    print('Negative means the self-signal arm is worse. Paired per seed.')
    print(f'{"condition":<15} {"d timely vitals":>18} {"d timely camera":>18}')
    for cond in CONDS:
        a, b = data[(cond, 'aimd')], data[(cond, 'aimdSelf')]
        seeds = sorted(set(a) & set(b))
        if not seeds:
            continue
        dv = [b[s]['timely_vitals'] - a[s]['timely_vitals'] for s in seeds]
        dc = [b[s]['timely_camera'] - a[s]['timely_camera'] for s in seeds]
        mv, cv, n = mean_ci(dv)
        mc, cc, _ = mean_ci(dc)
        print(f'{cond:<15} {mv:>11.2f} +/-{cv:>5.2f} {mc:>11.2f} +/-{cc:>5.2f}'
              f'   (n={n})')

    print()
    print('CONTROL-SIGNAL DIAGNOSTIC')
    print('maxSignalAge is the worst age of whichever stream drives the arm:')
    print('vitals for aimd, camera for aimdSelf. If the self arm shows a WORSE')
    print('age than the cross-stream arm, its backoffs made its own signal')
    print('worse -- the circularity, measured.')
    print(f'{"condition":<15} {"arm":<9} {"max signal age s":>17} '
          f'{"final rate kbps":>16}')
    for cond in CONDS:
        for arm in ARMS:
            d = data[(cond, arm)]
            if not d:
                continue
            ag, agci, _ = mean_ci([x['maxSignalAge'] for x in d.values()])
            fr, _, _ = mean_ci([x['finalRate'] for x in d.values()])
            print(f'{cond:<15} {arm:<9} {ag:>10.1f} +/-{agci:>4.1f} '
                  f'{fr/1000:>16.1f}')


if __name__ == '__main__':
    main()
