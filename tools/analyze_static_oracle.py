#!/usr/bin/env python3
"""Does the controller survive an ORACLE static baseline, per corridor?

docs/CORRIDOR_REGIME.md's headline (+24 to +48 pp camera) compares the
controller against ONE static rate, 400 kbps, on seven corridors spanning 4 to
10 km of site spacing. This re-compares it against the best static cap FOR EACH
CORRIDOR, chosen on the same seeds used to evaluate -- an oracle no deployment
could implement, and therefore an upper bound on any fixed configuration.

Four tests, none needing an arbitrary "tuned cap" selection rule:

  1. PARETO. Is the controller's point dominated by any single static cap on
     that corridor -- more timely vitals AND more timely camera at once? If
     yes on a corridor, a fixed rate beats the controller there outright.

  2. MATCHED VITALS. Among caps delivering at least as much timely vitals as
     the controller, which delivers the most camera? Snaps up to the next
     qualifying cap, which credits the controller too much; kept only because
     it needs no interpolation.

  3. INTERPOLATED FRONTIER, on the per-corridor MEAN points. The camera a
     static policy could reach at exactly the controller's mean vitals.

  4. PER-SEED PAIRED FRONTIER. Test 3 differences two sets of means and so has
     no per-corridor interval worth quoting. This instead builds the static
     frontier separately within EACH seed and compares it to that same seed's
     controller run, giving one paired observation per seed and therefore a
     real per-corridor CI.

     Test 4 is a STRONGER oracle than test 3, deliberately. Picking the best
     cap within each seed lets the static arm bank seed-level noise in its own
     favour -- it is choosing a cap with knowledge of the very run it is scored
     on. If the controller still wins here, the margin is not an artifact of
     either the cap grid or the seed draw.

Metric definitions are shared with tools/analyze_ablation.py.

Accepts both seed-naming schemes: the original 3-seed archive's `-<run>` and
the 10-seed campaign's `-s<NN>` (tools/corridor_seeds10.sh).

Usage: analyze_static_oracle.py [static-dir] [ctl-dir]
"""
import glob
import math
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze_ablation import kpis, mean_ci, parse   # noqa: E402

PCTILE = {'c08': '57th', 'c09': '64th', 'c10': '71st', 'c11': '78th',
          'c12': '85th', 'c13': '93rd', 'c14': '97th'}
# Measured sample percentiles of max_m in analysis/corridors/tmo_corridors.csv,
# not the NN/14*100 rank formula: that formula drifts (c11 79 vs 78.3, c12 86
# vs 85.3) and labels c14 '100th' when it is the 97th of 300. c14 is also AT
# the sampler's structural ceiling (max_m == 10000.0 exactly, the corridor
# half-length), so its difficulty is a LOWER BOUND. Do not describe it as the
# worst of the national distribution. See docs/CORRIDOR_POPULATION.md.
CAPS = (200, 400, 600, 800, 1000)
EPS = 1e-9


def collect(pattern, keyre):
    out = defaultdict(dict)
    for p in sorted(glob.glob(pattern)):
        m = re.match(keyre, os.path.basename(p)[:-4])
        if m:
            out[(m.group(1), m.group(2))][int(m.group(3))] = kpis(parse(p))
    return out


def point(d):
    """mean timely vitals / camera over the seeds in one cell."""
    if not d:
        return None
    v = sum(x['timely_vitals'] for x in d.values()) / len(d)
    c = sum(x['timely_camera'] for x in d.values()) / len(d)
    return v, c


def frontier(pts):
    """Upper Pareto frontier of (vitals, camera) points, sorted by vitals.

    A point survives if nothing else reaches at least its vitals with strictly
    more camera.
    """
    front = [p for p in pts
             if not any(q[0] >= p[0] and q[1] > p[1] for q in pts)]
    return sorted(front, key=lambda p: p[0])


def camera_at(pts, av):
    """Camera a static policy could reach at exactly vitals `av`.

    Returns (camera, note). camera is NaN when the controller's vitals exceeds
    every static point, i.e. no fixed rate reaches its operating region at all.
    """
    front = frontier(pts)
    if not front:
        return float('nan'), ' (no static points)'
    lo = [p for p in front if p[0] <= av]
    hi = [p for p in front if p[0] >= av]
    if not lo:
        # aimd's vitals sits below the whole frontier, so the best camera at
        # any vitals >= av is simply the frontier's best camera.
        return max(p[1] for p in front), ' (extrapolated: best camera on frontier)'
    if not hi:
        return float('nan'), ' (aimd vitals exceeds every static point)'
    p0 = max(lo, key=lambda p: p[0])
    p1 = min(hi, key=lambda p: p[0])
    if abs(p1[0] - p0[0]) < EPS:
        return max(p0[1], p1[1]), ''
    t = (av - p0[0]) / (p1[0] - p0[0])
    return p0[1] + t * (p1[1] - p0[1]), ''


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    sdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        here, '..', 'simulations', 'corridorpop', 'results_static')
    cdir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        here, '..', 'simulations', 'corridorpop', 'results_ctl')

    # `-s?(\d+)` accepts both the 3-seed archive's `-3` and the 10-seed
    # campaign's `-s03`. The `(aimd)` group is literal and followed by `-`, so
    # it cannot swallow `aimdSelf`.
    st = collect(os.path.join(sdir, '*.sca'), r'(c\d+)-static(\d+)-s?(\d+)$')
    ct = collect(os.path.join(cdir, '*.sca'), r'(c\d+)-(aimd)-s?(\d+)$')
    corridors = sorted({c for (c, _k) in ct})
    if not corridors:
        print(f'no controller runs matched in {cdir}', file=sys.stderr)
        return 1

    nseed = min(len(ct[(c, 'aimd')]) for c in corridors)
    print('Static frontier per corridor vs the controller')
    print(f'timely vitals / timely camera %, mean of {nseed} seeds')
    print(f'  static: {sdir}')
    print(f'  ctl:    {cdir}')
    print()
    head = f'{"corr":<5} {"pct":>5} ' + ' '.join(f'{f"{k}k":>13}' for k in CAPS)
    print(head + f' {"aimd":>13}')

    rows = {}
    for c in corridors:
        cells = {k: point(st[(c, str(k))]) for k in CAPS}
        a = point(ct[(c, 'aimd')])
        rows[c] = (cells, a)
        line = f'{c:<5} {PCTILE.get(c, "?"):>5} '
        line += ' '.join(
            (f'{f"{p[0]:.1f}/{p[1]:.1f}":>13}' if p else f'{"-":>13}')
            for p in (cells[k] for k in CAPS))
        line += f' {f"{a[0]:.1f}/{a[1]:.1f}":>13}' if a else f' {"-":>13}'
        print(line)

    print()
    print('TEST 1 -- PARETO: is the controller dominated by any single cap?')
    print(f'{"corr":<5} {"dominated by":>14}  {"margin":>22}')
    dom_any = False
    for c in corridors:
        cells, a = rows[c]
        if not a:
            continue
        hits = [(k, p) for k, p in cells.items()
                if p and p[0] > a[0] + EPS and p[1] > a[1] + EPS]
        if hits:
            dom_any = True
            k, p = max(hits, key=lambda kp: kp[1][1])
            print(f'{c:<5} {f"{k}k":>14}  '
                  f'{f"+{p[0]-a[0]:.1f} vitals +{p[1]-a[1]:.1f} camera":>22}')
        else:
            print(f'{c:<5} {"none":>14}  {"":>22}')
    print('  => ' + ('SOME corridors are dominated by a fixed rate'
                     if dom_any else
                     'the controller is on the Pareto frontier everywhere'))

    print()
    print('TEST 2 -- MATCHED VITALS: best static camera at vitals >= aimd')
    print(f'{"corr":<5} {"aimd v/c":>13} {"best static":>13} {"at cap":>7} '
          f'{"d camera":>9}')
    deltas = []
    for c in corridors:
        cells, a = rows[c]
        if not a:
            continue
        elig = [(k, p) for k, p in cells.items() if p and p[0] >= a[0] - EPS]
        if not elig:
            print(f'{c:<5} {f"{a[0]:.1f}/{a[1]:.1f}":>13} '
                  f'{"none reach it":>13} {"-":>7} {"-":>9}')
            continue
        k, p = max(elig, key=lambda kp: kp[1][1])
        d = a[1] - p[1]
        deltas.append(d)
        print(f'{c:<5} {f"{a[0]:.1f}/{a[1]:.1f}":>13} '
              f'{f"{p[0]:.1f}/{p[1]:.1f}":>13} {f"{k}k":>7} {d:>+9.1f}')
    if deltas:
        mu, ci, n = mean_ci(deltas)
        print(f'  mean extra camera at matched-or-better vitals: '
              f'{mu:+.1f} +/- {ci:.1f} pp over {n} corridors')
    print()
    print('TEST 3 -- INTERPOLATED FRONTIER on the per-corridor MEAN points:')
    print('camera a static policy could get at EXACTLY the controller\'s mean')
    print('vitals. Fairer than test 2, which snaps up to the next qualifying')
    print('cap and so credits the controller too much.')
    print(f'{"corr":<5} {"aimd v/c":>13} {"frontier cam":>13} {"d camera":>9}')
    idel = []
    for c in corridors:
        cells, a = rows[c]
        if not a:
            continue
        pts = [p for p in cells.values() if p]
        cam, note = camera_at(pts, a[0])
        if cam != cam:
            print(f'{c:<5} {f"{a[0]:.1f}/{a[1]:.1f}":>13} '
                  f'{"unreachable":>13} {"-":>9}{note}')
            continue
        d = a[1] - cam
        idel.append(d)
        print(f'{c:<5} {f"{a[0]:.1f}/{a[1]:.1f}":>13} {cam:>13.1f} '
              f'{d:>+9.1f}{note}')
    if idel:
        mu, ci, n = mean_ci(idel)
        print(f'  mean extra camera at the controller\'s own vitals level: '
              f'{mu:+.1f} +/- {ci:.1f} pp over {n} corridors')
        print('  (interval is ACROSS CORRIDORS -- it describes spread between')
        print('   corridors, not sampling error within one. See test 4.)')

    print()
    print('TEST 4 -- PER-SEED PAIRED FRONTIER: the static frontier rebuilt')
    print('inside each seed and compared to that seed\'s own controller run.')
    print('A stronger oracle than test 3 -- the static arm picks its cap with')
    print('knowledge of the run it is scored on -- and the only version with')
    print('a per-corridor interval.')
    print(f'{"corr":<5} {"seeds":>5} {"d camera (95% CI)":>22} '
          f'{"unreachable":>11}')
    per_seed_means = []
    pooled = []
    for c in corridors:
        seeds = sorted(ct[(c, 'aimd')])
        ds, unreach = [], 0
        for s in seeds:
            a = ct[(c, 'aimd')][s]
            pts = [(st[(c, str(k))][s]['timely_vitals'],
                    st[(c, str(k))][s]['timely_camera'])
                   for k in CAPS
                   if (c, str(k)) in st and s in st[(c, str(k))]]
            if not pts:
                continue
            cam, _note = camera_at(pts, a['timely_vitals'])
            if cam != cam:
                # No fixed rate reaches this seed's vitals. Counted and
                # excluded rather than scored as a win: the delta is undefined,
                # and treating it as a large positive number would let the
                # strongest cells inflate the mean.
                unreach += 1
                continue
            ds.append(a['timely_camera'] - cam)
        if not ds:
            print(f'{c:<5} {len(seeds):>5} {"all unreachable":>22} '
                  f'{unreach:>11}')
            continue
        mu, ci, n = mean_ci(ds)
        per_seed_means.append(mu)
        pooled += ds
        print(f'{c:<5} {len(seeds):>5} {f"{mu:+.1f} +/- {ci:.1f}":>22} '
              f'{unreach:>11}')
    if pooled:
        mu, ci, n = mean_ci(pooled)
        print(f'  pooled over {n} seed-corridor pairs: {mu:+.1f} +/- {ci:.1f} pp')
        mu2, ci2, n2 = mean_ci(per_seed_means)
        print(f'  mean of per-corridor means over {n2} corridors: '
              f'{mu2:+.1f} +/- {ci2:.1f} pp')
        print('  The second is the one to quote. Pooling treats seed-corridor')
        print('  pairs as independent draws, which understates the interval')
        print('  because corridors differ systematically; the corridor-level')
        print('  mean is the population statistic the study is about.')

    print()
    print('TESTS 3 and 4 are the defensible headline. The original +24 to')
    print('+48 pp was measured against a single 400 kbps cap and is not')
    print('comparable; it should not be quoted.')
    return 0


if __name__ == '__main__':
    sys.exit(main() or 0)
