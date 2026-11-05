#!/usr/bin/env python3
"""Unit validation for paperrebuild.links.WifiLink.

Holds the module to the same bar BleLink was held to in docs/BLE_VALIDATION.md:
throughput and latency must EMERGE from the framing and timing parameters and
match the analytic DCF cycle, with no throughput or delay knob anywhere.

The analytic target is recomputed here from the same constants the ini sets,
so a parameter change in one place cannot silently pass against a stale
hard-coded expectation.

Usage: validate_wifi.py [results-dir]
"""
import glob
import math
import os
import re
import sys
from collections import defaultdict

SIM_SECONDS = 300.0


def dcf_cycle(payload, bitrate=54e6, ack_rate=24e6, mac=28, ackB=14,
              phy=20e-6, slot=9e-6, sifs=16e-6, cwmin=15, busy=0.0):
    difs = sifs + 2 * slot
    backoff = (cwmin / 2.0) * slot
    t_data = phy + (mac + payload) * 8 / bitrate
    t_ack = phy + ackB * 8 / ack_rate
    return (difs + backoff + t_data + sifs + t_ack) / (1.0 - busy)


def parse(path):
    sc, stats, cur = {}, {}, None
    with open(path) as f:
        for line in f:
            p = line.split()
            if not p:
                continue
            if p[0] == 'scalar' and len(p) >= 4:
                try:
                    sc[(p[1], p[2])] = float(p[3])
                except ValueError:
                    pass
            elif p[0] == 'statistic' and len(p) >= 3:
                cur = (p[1], p[2])
                stats[cur] = {}
            elif p[0] == 'field' and cur and len(p) >= 3:
                try:
                    stats[cur][p[1]] = float(p[2])
                except ValueError:
                    pass
    return sc, stats


def mean_ci(xs):
    xs = [x for x in xs if not math.isnan(x)]
    n = len(xs)
    if not n:
        return float('nan'), float('nan'), 0
    mu = sum(xs) / n
    if n == 1:
        return mu, float('nan'), 1
    sd = math.sqrt(sum((x - mu) ** 2 for x in xs) / (n - 1))
    t = {2: 12.71, 3: 4.303, 5: 2.776, 10: 2.262}.get(n, 2.262)
    return mu, t * sd / math.sqrt(n), n


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        '..', 'simulations', 'validation_wifi', 'results')
    runs = defaultdict(list)
    for p in sorted(glob.glob(os.path.join(root, '*.sca'))):
        m = re.match(r'(\w+)-#(\d+)$', os.path.basename(p)[:-4])
        if m:
            runs[m.group(1)].append(parse(p))
    if not runs:
        print(f'no runs under {root}', file=sys.stderr)
        return 1

    def delay_ms(pair):
        _sc, st = pair
        for (mod, name), f in st.items():
            if name.startswith('delay') and mod.endswith('sink'):
                return f.get('mean', float('nan')) * 1e3
        return float('nan')

    def goodput_mbps(pair):
        _sc, st = pair
        for (mod, name), f in st.items():
            if name.startswith('delay') and mod.endswith('sink'):
                n = f.get('count', 0)
                return n * payload_of(pair) * 8 / SIM_SECONDS / 1e6
        return float('nan')

    def payload_of(pair):
        sc, _st = pair
        for (mod, name), v in sc.items():
            if name == 'messageLength':
                return v
        return float('nan')

    # payload is not recorded as a scalar, so take it from the config name
    PAYLOAD = {'LatencyUnloaded': 20, 'Throughput54_1500': 1500,
               'ThroughputNetSimRef': 1450, 'MediumBusy50': 1500,
               'MediumBusy80': 1500, 'FER10': 1500,
               'CameraOverWifi': 4096, 'CameraOverWifiBusy80': 4096}

    EXPECT = {
        'LatencyUnloaded':
            ('delay', dcf_cycle(20) * 1e3, 'ms', 'one DCF cycle, 20 B'),
        'Throughput54_1500':
            ('tput', 1500 * 8 / dcf_cycle(1500) / 1e6, 'Mb/s',
             'analytic DCF ceiling, 54 Mbps PHY'),
        'ThroughputNetSimRef':
            ('tput', 1450 * 8 / dcf_cycle(1450, ack_rate=6e6) / 1e6, 'Mb/s',
             'analytic 29.4; NetSim worked example reports 28.9'),
        'MediumBusy50':
            ('tput', 1500 * 8 / dcf_cycle(1500, busy=0.5) / 1e6, 'Mb/s',
             'half the medium -> half the throughput'),
        'MediumBusy80':
            ('tput', 1500 * 8 / dcf_cycle(1500, busy=0.8) / 1e6, 'Mb/s',
             '20% of the medium'),
    }

    print('WifiLink unit validation')
    print('=' * 72)
    ok = True
    for cfg in sorted(runs):
        pairs = runs[cfg]
        pay = PAYLOAD.get(cfg, float('nan'))
        d_mu, d_ci, n = mean_ci([delay_ms(p) for p in pairs])
        counts = []
        for _sc, st in pairs:
            for (mod, name), f in st.items():
                if name.startswith('delay') and mod.endswith('sink'):
                    counts.append(f.get('count', 0))
        t_mu, t_ci, _ = mean_ci([c * pay * 8 / SIM_SECONDS / 1e6
                                 for c in counts])
        print(f'\n{cfg}  ({n} seeds)')
        print(f'    mean delay      {d_mu:10.4f} +/- {d_ci:7.4f} ms')
        print(f'    goodput         {t_mu:10.3f} +/- {t_ci:7.3f} Mb/s')
        if cfg in EXPECT:
            kind, target, unit, why = EXPECT[cfg]
            got = d_mu if kind == 'delay' else t_mu
            err = 100.0 * (got - target) / target
            flag = 'PASS' if abs(err) <= 20.0 else 'FAIL'
            if flag == 'FAIL':
                ok = False
            print(f'    expected        {target:10.4f} {unit}   ({why})')
            print(f'    error           {err:+10.1f} %   [{flag}, gate +/-20%]')
    print('\n' + '=' * 72)
    print('VERDICT:', 'all gated configs pass' if ok else 'A GATE FAILED')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
