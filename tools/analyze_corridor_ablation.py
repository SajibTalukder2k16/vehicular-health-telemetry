#!/usr/bin/env python3
"""Cross-stream vs. self-signal AIMD on the measured contention-limited
corridors c08-c14 (docs/CORRIDOR_REGIME.md).

docs/ABLATION_CROSS_STREAM.md establishes the self-signal collapse on synthetic
conditions and states as a limitation that real-corridor contention is milder,
so the claim should not be generalised without this. Same metric definitions
and the same pairing as the synthetic ablation.

Accepts both seed-naming schemes: the original 3-seed archive's `-<run>` and
the 10-seed campaign's `-s<NN>` (tools/corridor_seeds10.sh). At 3 seeds the
per-corridor CIs are too wide to quote (t=4.303) and only the pooled row is
usable; at 10 they are worth reading directly.

Usage: analyze_corridor_ablation.py [results-dir]
"""
import glob
import math
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze_ablation import kpis, mean_ci, parse   # noqa: E402

# approximate national percentile of each corridor (docs/CORRIDOR_REGIME.md)
PCTILE = {'c08': '57th', 'c09': '64th', 'c10': '71st', 'c11': '78th',
          'c12': '85th', 'c13': '93rd', 'c14': '97th'}
# Measured sample percentiles of max_m in analysis/corridors/tmo_corridors.csv,
# not the NN/14*100 rank formula: that formula drifts (c11 79 vs 78.3, c12 86
# vs 85.3) and labels c14 '100th' when it is the 97th of 300. c14 is also AT
# the sampler's structural ceiling (max_m == 10000.0 exactly, the corridor
# half-length), so its difficulty is a LOWER BOUND. Do not describe it as the
# worst of the national distribution. See docs/CORRIDOR_POPULATION.md.


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        '..', 'simulations', 'corridorpop', 'results_ctl')
    data = defaultdict(dict)
    for p in sorted(glob.glob(os.path.join(root, '*.sca'))):
        m = re.match(r'(c\d+)-(aimd|aimdSelf)-s?(\d+)$',
                     os.path.basename(p)[:-4])
        if m:
            data[(m.group(1), m.group(2))][int(m.group(3))] = kpis(parse(p))

    corridors = sorted({c for (c, _a) in data})
    if not corridors:
        print(f'no runs matched in {root}', file=sys.stderr)
        return 1
    nseed = min(len(set(data[(c, 'aimd')]) & set(data[(c, 'aimdSelf')]))
                for c in corridors)
    print('Cross-stream (aimd) vs self-signal (aimdSelf) on measured corridors')
    print(f'timely delivery %, {nseed} paired seeds; backoff:probe from the gateway')
    print(f'  {root}')
    print()
    print(f'{"corr":<5} {"pct":>5} {"aimd v/c":>14} {"aimdSelf v/c":>14} '
          f'{"d vitals":>16} {"d camera":>16} {"self b:p":>12}')

    allv, allc = [], []
    for c in corridors:
        a, b = data[(c, 'aimd')], data[(c, 'aimdSelf')]
        runs = sorted(set(a) & set(b))
        if not runs:
            continue
        av = sum(a[r]['timely_vitals'] for r in runs) / len(runs)
        ac = sum(a[r]['timely_camera'] for r in runs) / len(runs)
        bv = sum(b[r]['timely_vitals'] for r in runs) / len(runs)
        bc = sum(b[r]['timely_camera'] for r in runs) / len(runs)
        dv = [b[r]['timely_vitals'] - a[r]['timely_vitals'] for r in runs]
        dc = [b[r]['timely_camera'] - a[r]['timely_camera'] for r in runs]
        allv += dv
        allc += dc
        bo = sum(b[r]['backoffs'] for r in runs) / len(runs)
        pr = sum(b[r]['probes'] for r in runs) / len(runs)
        mdv, cdv, _ = mean_ci(dv)
        mdc, cdc, _ = mean_ci(dc)
        print(f'{c:<5} {PCTILE.get(c, "?"):>5} {f"{av:.1f} / {ac:.1f}":>14} '
              f'{f"{bv:.1f} / {bc:.1f}":>14} '
              f'{f"{mdv:+.1f} +/- {cdv:.1f}":>16} '
              f'{f"{mdc:+.1f} +/- {cdc:.1f}":>16} '
              f'{f"{bo:.0f}:{pr:.0f}":>12}')

    print()
    mv, cv, n = mean_ci(allv)
    mc, cc, _ = mean_ci(allc)
    print(f'POOLED paired difference over {n} run pairs (aimdSelf - aimd, pp):')
    print(f'  timely vitals {mv:+.2f} +/- {cv:.2f}')
    print(f'  timely camera {mc:+.2f} +/- {cc:.2f}')
    print()
    print('Pooling across corridors treats run pairs as independent draws and')
    print('so overstates precision, because corridors differ systematically.')
    print('Read the per-corridor rows where the seed count supports them and')
    print('treat the pooled row as a summary, not an inference.')
    return 0


if __name__ == '__main__':
    sys.exit(main() or 0)
