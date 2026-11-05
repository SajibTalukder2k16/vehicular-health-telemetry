#!/usr/bin/env python3
"""Age-of-Information metrics for the Family B case studies.

Reports, per config and per vector-recorded seed, the metrics that describe a
freshness failure properly: peak AoI, mean AoI, and time spent above the
clinical freshness budget -- all computed over the FULL configured observation
window, not up to the last received update.

Run: python3 aoi_metrics.py [config ...]
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                'figures_src'))
from _shared import aoi_stats, load_vec, sim_time_limit  # noqa: E402

BUDGET_S = 10.0            # vitals freshness budget (see docs/CALIBRATION.md)
SEEDS = (0, 1, 2)
CONFIGS = ('DcDriveAtt', 'DcDriveTmo', 'DcDriveVzw', 'DcDriveLegacy8',
           'VaDriveAtt', 'VaDriveTmo', 'VaDriveVzw', 'VaDriveLegacy8')


def case_ini(config):
    return ('simulations/dc_case/omnetpp.ini' if config.startswith('Dc')
            else 'simulations/va_case/omnetpp.ini')


def main():
    configs = sys.argv[1:] or list(CONFIGS)
    print(f'AoI over the full observation window, budget {BUDGET_S:.0f} s\n')
    print(f"{'config':<17}{'T':>6}{'seed':>5}{'last upd':>10}"
          f"{'peak':>9}{'mean':>8}{'t>budget':>10}{'% drive':>9}")
    summary = {}
    for cfg in configs:
        T = sim_time_limit(case_ini(cfg))
        peaks, means, fracs = [], [], []
        for s in SEEDS:
            try:
                t, d = load_vec(cfg, 'e2eDelayVitals:vector', seeds=[s])[0]
            except (FileNotFoundError, IndexError):
                print(f'{cfg:<17}{T:>6.0f}{s:>5}   (no vector data)')
                continue
            st = aoi_stats(t, d, T, BUDGET_S)
            peaks.append(st['peak'])
            means.append(st['mean'])
            fracs.append(st['frac_above'])
            print(f"{cfg:<17}{T:>6.0f}{s:>5}{st['last_update']:>10.0f}"
                  f"{st['peak']:>8.1f}s{st['mean']:>7.1f}s"
                  f"{st['time_above']:>9.0f}s{st['frac_above'] * 100:>8.1f}%")
        if peaks:
            summary[cfg] = (np.mean(peaks), max(peaks), np.mean(means),
                            np.mean(fracs) * 100)
    print(f"\n{'config':<17}{'peak mean':>11}{'peak worst':>12}"
          f"{'mean AoI':>10}{'% drive stale':>15}")
    for cfg, (pm, pw, mm, fa) in summary.items():
        print(f'{cfg:<17}{pm:>10.1f}s{pw:>11.1f}s{mm:>9.1f}s{fa:>14.1f}%')
    print('\nNote: peaks are over 3 vector-recorded seeds only; the scalar '
          'corpus\nhas 30 seeds per config but does not carry the per-packet '
          'timing\nneeded for AoI. Treat these as illustrative, not as a '
          'distribution.')


if __name__ == '__main__':
    main()
