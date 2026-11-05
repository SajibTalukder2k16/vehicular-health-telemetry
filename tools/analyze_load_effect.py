#!/usr/bin/env python3
"""Does the static-vs-adaptive headline survive real background load?

Compares the same oracle tests across the two background-load levels:

  unloaded  results_seeds10/  -- one active UE in an otherwise idle cell.
                                 This carries the published headline. It is
                                 unloaded not by design but because the
                                 background generator never started; see
                                 docs/CORRECTIONS_2026-10.md C13.
  loaded    results_loaded/   -- bgues=20 with the generator actually
                                 transmitting, ~2.5 Mbps/cell of competing
                                 uplink.

The cells are matched one-for-one, so the comparison is paired by corridor.

Two things this reports that reading the two analyze_static_oracle.py outputs
side by side does not:

  1. A PAIRED change. Corridors differ far more from each other than either
     load level differs from the other, so an unpaired comparison of
     "+34.8 +/- 13.9 vs +31.4 +/- 14.3" is dominated by between-corridor spread
     and can hide a consistent within-corridor shift (or invent one).

  2. Honest handling of corridors the oracle cannot score. When the
     controller's vitals exceed every static point in a seed, that seed has no
     frontier value and is excluded rather than counted as a win. Under load
     this gets worse -- c14 loses 9 of 10 seeds -- so a corridor mean can rest
     on a single seed. Such corridors are reported but excluded from the
     headline, because a one-seed mean has no interval and must not be averaged
     in as though it did.

Usage: analyze_load_effect.py [unloaded-dir] [loaded-dir]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze_ablation import mean_ci                      # noqa: E402
from analyze_static_oracle import CAPS, PCTILE, camera_at, collect  # noqa: E402

MIN_SEEDS = 2   # a mean with no interval is not a measurement


def arms(d):
    st = collect(os.path.join(d, '*.sca'), r'(c\d+)-static(\d+)-s?(\d+)$')
    ct = collect(os.path.join(d, '*.sca'), r'(c\d+)-(aimd)-s?(\d+)$')
    return st, ct


def per_seed_margins(st, ct, c):
    """TEST 4: static frontier rebuilt inside each seed, vs that seed's aimd.

    Returns {seed: margin} keyed by seed, not a bare list, so the two load
    levels can be intersected on the seeds that are scorable under BOTH. That
    matters: which seeds are scorable differs by load, and comparing a corridor
    mean over 7 unloaded seeds against 9 loaded ones is not a paired test. On
    c08 the unmatched comparison gave +32.6 pp and the matched one +22.3 +/-
    35.0, i.e. not significant -- the difference between a finding and an
    artifact.
    """
    out, unreachable = {}, 0
    for s in sorted(ct.get((c, 'aimd'), {})):
        a = ct[(c, 'aimd')][s]
        pts = [(st[(c, str(k))][s]['timely_vitals'],
                st[(c, str(k))][s]['timely_camera'])
               for k in CAPS if s in st[(c, str(k))]]
        if not pts:
            continue
        cam, _note = camera_at(pts, a['timely_vitals'])
        if cam != cam:
            unreachable += 1
            continue
        out[s] = a['timely_camera'] - cam
    return out, unreachable


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    base = os.path.join(here, '..', 'simulations', 'corridorpop')
    udir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(base, 'results_seeds10')
    ldir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(base, 'results_loaded')

    data = {'unloaded': arms(udir), 'loaded': arms(ldir)}
    corrs = sorted({c for (c, k) in data['loaded'][1]}
                   & {c for (c, k) in data['unloaded'][1]})
    if not corrs:
        print('no corridors common to both directories', file=sys.stderr)
        return 1

    print('Does the headline survive background load?')
    print(f'  unloaded: {udir}')
    print(f'  loaded:   {ldir}')
    print()

    print('Absolute operating point of the controller (timely vitals / camera %)')
    print(f'{"corr":<5} {"pct":>5} {"unloaded":>14} {"loaded":>14} '
          f'{"d vitals":>9} {"d camera":>9}')
    for c in corrs:
        au = data['unloaded'][1][(c, 'aimd')]
        al = data['loaded'][1][(c, 'aimd')]
        vu = sum(x['timely_vitals'] for x in au.values()) / len(au)
        cu = sum(x['timely_camera'] for x in au.values()) / len(au)
        vl = sum(x['timely_vitals'] for x in al.values()) / len(al)
        cl = sum(x['timely_camera'] for x in al.values()) / len(al)
        print(f'{c:<5} {PCTILE.get(c, "?"):>5} {f"{vu:.1f}/{cu:.1f}":>14} '
              f'{f"{vl:.1f}/{cl:.1f}":>14} {vl-vu:>+9.1f} {cl-cu:>+9.1f}')

    print()
    print('TEST 4 margin over the per-seed oracle, by load')
    print(f'{"corr":<5} {"unloaded":>17} {"loaded":>17} {"change":>8}  '
          f'{"seeds u/l":>9}  {"unreach u/l":>11}')
    marg, used_both = {}, []
    for c in corrs:
        row = {}
        for lab in ('unloaded', 'loaded'):
            st, ct = data[lab]
            row[lab] = per_seed_margins(st, ct, c)
        marg[c] = row
        (du, uu), (dl, ul) = row['unloaded'], row['loaded']
        mu, ciu, nu = mean_ci(list(du.values()))
        ml, cil, nl = mean_ci(list(dl.values()))
        ok = nu >= MIN_SEEDS and nl >= MIN_SEEDS
        if ok:
            used_both.append(c)
        chg = f'{ml-mu:+.1f}' if ok else '--'
        fu = f'{mu:.1f} +/- {ciu:.1f}' if nu >= MIN_SEEDS else f'{mu:.1f} (n={nu})'
        fl = f'{ml:.1f} +/- {cil:.1f}' if nl >= MIN_SEEDS else f'{ml:.1f} (n={nl})'
        flag = '' if ok else '   <-- too few scorable seeds, excluded'
        print(f'{c:<5} {fu:>17} {fl:>17} {chg:>8}  {f"{nu}/{nl}":>9}  '
              f'{f"{uu}/{ul}":>11}{flag}')

    print()
    for lab in ('unloaded', 'loaded'):
        per = [mean_ci(list(marg[c][lab][0].values()))[0] for c in used_both]
        m, ci, n = mean_ci(per)
        print(f'  {lab:<8} headline: {m:+.1f} +/- {ci:.1f} pp '
              f'over {n} corridors {used_both}')

    # The defensible statistic: restrict each corridor to the seeds scorable
    # under BOTH loads and difference within the seed, so the controller and
    # the oracle are compared on the same draws on both sides.
    print()
    print('MATCHED-SEED paired change due to load')
    print('  (same seeds both sides, differenced within seed -- the statistic')
    print('   to quote; the unmatched version above compares different seed')
    print('   subsets and inflates per-corridor swings)')
    print(f'{"corr":<5} {"unloaded":>17} {"loaded":>17} {"change":>17} {"n":>3}')
    pc = []
    for c in corrs:
        du = marg[c]['unloaded'][0]
        dl = marg[c]['loaded'][0]
        common = sorted(set(du) & set(dl))
        if len(common) < MIN_SEEDS:
            print(f'{c:<5} only {len(common)} seed(s) scorable under both '
                  f'-- cannot pair')
            continue
        mu, ciu, _ = mean_ci([du[s] for s in common])
        ml, cil, _ = mean_ci([dl[s] for s in common])
        mp, cip, n = mean_ci([dl[s] - du[s] for s in common])
        pc.append((c, mp, cip))
        print(f'{c:<5} {f"{mu:.1f} +/- {ciu:.1f}":>17} '
              f'{f"{ml:.1f} +/- {cil:.1f}":>17} '
              f'{f"{mp:+.1f} +/- {cip:.1f}":>17} {n:>3}')

    if not pc:
        print('\nno corridor has enough matched seeds to compare loads')
        return 1

    m, ci, n = mean_ci([d for _c, d, _ci in pc])
    print()
    print(f'Over {n} corridors with matched seeds: {m:+.1f} +/- {ci:.1f} pp')
    print('  per corridor: ' + ', '.join(f'{c} {d:+.1f}' for c, d, _ in pc))
    sig = [(c, d) for c, d, cip in pc if abs(d) > cip]
    print('  individually significant: '
          + (', '.join(f'{c} {d:+.1f}' for c, d in sig) if sig else 'none'))
    if m - ci < 0 < m + ci:
        print('  => interval spans zero: load does not measurably change the')
        print('     margin. The headline is NOT an artifact of an idle cell,')
        print('     and no load-dependence direction can be claimed.')
    elif m + ci < 0:
        print('  => the margin NARROWS under load, significantly.')
    else:
        print('  => the margin WIDENS under load, significantly.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
