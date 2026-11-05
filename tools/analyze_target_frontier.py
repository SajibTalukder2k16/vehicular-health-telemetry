#!/usr/bin/env python3
"""Does the CROSS-STREAM freshness signal beat the own-stream one at matched
vitals, or do the two arms just sit at different points on one frontier?

docs/ABLATION_CROSS_STREAM.md compares `aimd` and `aimdSelf` at a single shared
freshnessTarget. At 10 seeds that comparison resolves -- aimdSelf gains vitals
and loses camera -- but it cannot say which signal is BETTER, because aimdSelf
throttles harder at the same target and is therefore buying vitals with camera.
Any policy tuned more conservatively would do that with either signal.

That is the same error the static baseline made before
docs/CORRIDOR_REGIME.md's oracle audit: one configuration of the alternative
standing in for the alternative. The fix is the same, so the method here is
deliberately the method there -- build each arm its own Pareto frontier over
swept freshnessTarget, then compare camera at MATCHED VITALS.

  TEST A -- MEAN FRONTIERS. For each of one arm's operating points, what camera
    does the other arm's frontier deliver at that same vitals? Averaged over
    the points that fall inside the other arm's reachable vitals range. Run in
    both directions, because "A beats B where B can reach" and "B beats A where
    A can reach" are different questions and either can be the informative one.

  TEST B -- PER-SEED PAIRED. The same comparison with both frontiers rebuilt
    inside each seed and paired, which is what yields an interval. Deliberately
    noisier and deliberately fairer: each arm banks its own seed-level noise.

Interpretation, stated up front so it is not decided after seeing the numbers:
a frontier gap that is small relative to its interval, or that changes sign
between the two directions, means the signal source is a free design choice and
the contribution is elsewhere. A consistent one-directional gap means the
signal choice is itself load-bearing.

Reads the 5 s column from the headline campaign (results_seeds10) and the
2/3/7/10 s columns from results_targets, so each arm gets five frontier points.

Usage: analyze_target_frontier.py [targets-dir] [seeds10-dir]
"""
import glob
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze_ablation import kpis, mean_ci, parse          # noqa: E402
from analyze_static_oracle import PCTILE, camera_at, frontier   # noqa: E402

ARMS = ('aimd', 'aimdSelf')
BASE_TARGET = 5          # the column that lives in results_seeds10


def usable(k):
    """Reject a run whose KPIs are not finite.

    kpis() returns NaN when a stream's generated count is zero, which is what a
    run still being written -- or one killed mid-write -- looks like. Such a
    cell must never reach the frontier silently: it would drag a mean to NaN at
    best and distort a frontier at worst. This is the hazard
    tools/validate_runs.py exists for, applied at read time so a partially
    complete campaign can be inspected safely while it runs.
    """
    return (k['timely_vitals'] == k['timely_vitals']
            and k['timely_camera'] == k['timely_camera'])


def collect(targets_dir, seeds10_dir):
    """(corridor, arm, target) -> seed -> kpis"""
    out = defaultdict(dict)
    skipped = 0
    for p in sorted(glob.glob(os.path.join(targets_dir, '*.sca'))):
        m = re.match(r'(c\d+)-(aimd|aimdSelf)-t(\d+)-s(\d+)$',
                     os.path.basename(p)[:-4])
        if m:
            k = kpis(parse(p))
            if not usable(k):
                skipped += 1
                continue
            out[(m.group(1), m.group(2), int(m.group(3)))][int(m.group(4))] = k
    for p in sorted(glob.glob(os.path.join(seeds10_dir, '*.sca'))):
        m = re.match(r'(c\d+)-(aimd|aimdSelf)-s(\d+)$',
                     os.path.basename(p)[:-4])
        if m:
            k = kpis(parse(p))
            if not usable(k):
                skipped += 1
                continue
            out[(m.group(1), m.group(2), BASE_TARGET)][int(m.group(3))] = k
    if skipped:
        print(f'NOTE: skipped {skipped} incomplete run(s) -- campaign still '
              f'in flight, or re-run them before quoting these numbers.',
              file=sys.stderr)
    return out


def mean_point(cell):
    v = sum(x['timely_vitals'] for x in cell.values()) / len(cell)
    c = sum(x['timely_camera'] for x in cell.values()) / len(cell)
    return v, c


GRID = 21


def compare_frontiers(cross_pts, self_pts, ngrid=GRID):
    """Vertical gap between the two arms' Pareto frontiers, cross minus self.

    Evaluated on a uniform grid of vitals across the range BOTH frontiers span,
    so the two arms are compared envelope to envelope. Returns
    (deltas, lo, hi) or None when the frontiers do not overlap in vitals.

    This replaces an earlier, broken statistic that scored each of one arm's
    RAW operating points against the other arm's ENVELOPE. That is biased
    towards whichever arm supplies the envelope, in whichever direction it is
    run: the scored arm is charged for its own badly-tuned configurations --
    both arms collapse to ~5% camera at a 2 s target -- while the reference arm
    is always credited with its best envelope. Run symmetrically it made BOTH
    directions come out positive on all seven corridors, which looks exactly
    like genuinely crossing frontiers and is not. Comparing like with like is
    the whole point of a frontier comparison.
    """
    fc, fs = frontier(cross_pts), frontier(self_pts)
    if not fc or not fs:
        return None
    lo = max(fc[0][0], fs[0][0])
    hi = min(fc[-1][0], fs[-1][0])
    if hi - lo < 1e-9:
        return None
    deltas = []
    for i in range(ngrid):
        v = lo + (hi - lo) * i / (ngrid - 1)
        cc, _ = camera_at(cross_pts, v)
        cs, _ = camera_at(self_pts, v)
        if cc != cc or cs != cs:
            continue
        deltas.append(cc - cs)
    if not deltas:
        return None
    return deltas, lo, hi


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    tdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        here, '..', 'simulations', 'corridorpop', 'results_targets')
    sdir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        here, '..', 'simulations', 'corridorpop', 'results_seeds10')

    data = collect(tdir, sdir)
    if not data:
        print(f'no runs matched in {tdir} / {sdir}', file=sys.stderr)
        return 1
    corridors = sorted({c for (c, _a, _t) in data})
    targets = sorted({t for (_c, _a, t) in data})

    print('Cross-stream vs own-stream freshness signal, FRONTIER comparison')
    print(f'freshnessTarget swept {targets} s; '
          f'{len(corridors)} corridors')
    print(f'  targets: {tdir}')
    print(f'  {BASE_TARGET}s col: {sdir}')
    print()
    print('Operating points, timely vitals / timely camera %, mean of seeds')
    head = f'{"corr":<5} {"arm":<9} ' + ' '.join(f'{f"{t}s":>13}' for t in targets)
    print(head)
    pts = {}
    for c in corridors:
        for arm in ARMS:
            row = []
            for t in targets:
                cell = data.get((c, arm, t))
                row.append(mean_point(cell) if cell else None)
            pts[(c, arm)] = [p for p in row if p]
            line = f'{c:<5} {arm:<9} ' + ' '.join(
                (f'{f"{p[0]:.1f}/{p[1]:.1f}":>13}' if p else f'{"-":>13}')
                for p in row)
            print(line)
        print()

    print('REACHABLE RANGES -- what each arm can be tuned to at all.')
    print('The frontier comparison below is only meaningful where both arms')
    print('can operate, so the width of that overlap is reported first.')
    print(f'{"corr":<5} {"cross vitals":>14} {"best cam":>9} '
          f'{"self vitals":>14} {"best cam":>9} {"overlap":>8} {"d best":>7}')
    best_d = []
    for c in corridors:
        cp, sp = pts.get((c, 'aimd'), []), pts.get((c, 'aimdSelf'), [])
        fc, fs = frontier(cp), frontier(sp)
        if not fc or not fs:
            continue
        ov = min(fc[-1][0], fs[-1][0]) - max(fc[0][0], fs[0][0])
        bc, bs = max(p[1] for p in fc), max(p[1] for p in fs)
        best_d.append(bc - bs)
        print(f'{c:<5} {f"{fc[0][0]:.1f}-{fc[-1][0]:.1f}":>14} '
              f'{bc:>9.1f} '
              f'{f"{fs[0][0]:.1f}-{fs[-1][0]:.1f}":>14} '
              f'{bs:>9.1f} {ov:>8.1f} {bc - bs:>+7.1f}')
    if best_d:
        mu, ci, n = mean_ci(best_d)
        print(f'  BEST ACHIEVABLE CAMERA, cross minus self, over {n} '
              f'corridors: {mu:+.1f} +/- {ci:.1f} pp')
        print('  This is the robust statistic here: it needs no overlap and no')
        print('  interpolation, only each arm tuned to its own best point.')
    print()
    print('TEST A -- MEAN FRONTIERS, envelope vs envelope')
    print('  Vertical gap (cross minus self) on a 21-point grid of vitals')
    print('  across the range BOTH frontiers span. Positive => the')
    print('  cross-stream frontier sits above the own-stream one.')
    print('  "worst" is the least favourable grid point: if it is negative')
    print('  while the mean is positive, the frontiers CROSS inside the')
    print('  overlap and no unqualified dominance claim is available.')
    print(f'{"corr":<5} {"pct":>5} {"vitals overlap":>16} {"mean d cam":>11} '
          f'{"worst":>8} {"best":>8}')
    a_mean = []
    for c in corridors:
        cp, sp = pts.get((c, 'aimd'), []), pts.get((c, 'aimdSelf'), [])
        res = compare_frontiers(cp, sp)
        if not res:
            print(f'{c:<5} {PCTILE.get(c, "?"):>5} {"no overlap":>16}')
            continue
        d, lo, hi = res
        m = sum(d) / len(d)
        a_mean.append(m)
        print(f'{c:<5} {PCTILE.get(c, "?"):>5} '
              f'{f"{lo:.1f}-{hi:.1f}":>16} {m:>+11.1f} '
              f'{min(d):>+8.1f} {max(d):>+8.1f}')
    if a_mean:
        mu, ci, n = mean_ci(a_mean)
        print(f'  mean over {n} corridors: {mu:+.1f} +/- {ci:.1f} pp')

    print()
    print('TEST B -- PER-SEED PAIRED FRONTIERS (both rebuilt within each seed)')
    print(f'{"corr":<5} {"seeds":>5} {"mean d cam (95% CI)":>24} '
          f'{"n<0":>5}')
    b_means = []
    for c in corridors:
        # Only seeds for which BOTH arms have every swept target, so each
        # seed's two frontiers are built from the same grid.
        cells = [data.get((c, arm, t), {}) for arm in ARMS for t in targets]
        seeds = sorted(set.intersection(*(set(x) for x in cells))) \
            if all(cells) else []
        per_seed = []
        for s in seeds:
            sp = [(data[(c, 'aimdSelf', t)][s]['timely_vitals'],
                   data[(c, 'aimdSelf', t)][s]['timely_camera'])
                  for t in targets if s in data[(c, 'aimdSelf', t)]]
            cp = [(data[(c, 'aimd', t)][s]['timely_vitals'],
                   data[(c, 'aimd', t)][s]['timely_camera'])
                  for t in targets if s in data[(c, 'aimd', t)]]
            res = compare_frontiers(cp, sp)
            if not res:
                continue
            d, _lo, _hi = res
            per_seed.append(sum(d) / len(d))
        if not per_seed:
            print(f'{c:<5} {len(seeds):>5} {"no overlap":>24}')
            continue
        mu, ci, n = mean_ci(per_seed)
        b_means.append(mu)
        neg = sum(1 for x in per_seed if x < 0)
        print(f'{c:<5} {len(seeds):>5} {f"{mu:+.1f} +/- {ci:.1f}":>24} '
              f'{neg:>5}')
    if b_means:
        mu, ci, n = mean_ci(b_means)
        print(f'  mean of per-corridor means over {n} corridors: '
              f'{mu:+.1f} +/- {ci:.1f} pp')
        print('  n<0 counts seeds where the own-stream frontier came out on')
        print('  top, i.e. how often the result reverses seed to seed.')

    print()
    print('Positive => at matched vitals the cross-stream frontier delivers')
    print('more timely camera, so the SIGNAL CHOICE is itself load-bearing and')
    print('not merely a tuning difference. A mean small against its interval,')
    print('or a negative "worst" column in TEST A, means the arms share one')
    print('frontier and the signal source is a free design choice.')
    return 0


if __name__ == '__main__':
    sys.exit(main() or 0)
