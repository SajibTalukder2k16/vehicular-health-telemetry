#!/usr/bin/env python3
"""The room-to-road contrast, on the MATCHED room configurations only.

Why this script exists. The paper is titled "From Room to Road" but reports
only road. The indoor material is real -- simulations/room -- but the original
`Room*` configs are not comparable with the vehicular runs: 0.1 s camera
interval against 0.5 s, uniform(1ms,5ms) edge processing against
uniform(0.5ms,2ms), no OBD stream, no BLE PDU error process. Quoting an
indoor delay against a vehicular one across that mismatch compares two
different workloads, which is docs/CORRECTIONS_2026-10.md C5.

`RoomMatched*` (added 2026-10-07) holds the sensor rig identical to
simulations/dc_case, so the only difference between the two settings is the
backhaul: 802.11n/ac in a 10 m room against LTE from a moving vehicle. Those
are the only room numbers this script will report, and the only ones the
paper may quote.

One deliberate exception, and it runs the safe way. OBD-II is a vehicle port;
a real indoor installation carries the wearable and the camera only, and the
unmatched `Room*` configs set `hasObd = false` accordingly. `RoomMatched*`
sets it true, because holding the offered workload identical is what makes
the comparison mean anything -- dropping a stream indoors would put back the
confound these configs exist to remove. The indoor numbers are therefore
measured while carrying ~1.5% of offered bytes a room would not generate, so
they understate the indoor setting rather than flatter it.

What the contrast is FOR. The room runs have `admissionPolicy = "none"` --
the room ini never sets it and EdgeApp defaults to none. So the room is not
another arm of the controller comparison; it is the setting in which the
problem the controller solves does not exist. That is the claim it can
support, and it is the one the title needs.

Metrics come from analyze_ablation.kpis, the same definition as every other
table in the paper, so the room row cannot drift from the road rows.

Usage: analyze_room_road.py [room-results-dir] [dc-results-dir]
"""
import glob
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze_ablation import kpis, mean_ci, parse   # noqa: E402

ROOM_RE = r'(RoomMatched\w+)-#(\d+)$'
DC_RE = r'(DcDrive\w+)-#(\d+)$'

# Statistic -> the `field mean` of its :stats block. parse() reads only
# `scalar` lines, and the delays are recorded as statistic blocks.
STATS_WANTED = ('e2eDelay:stats', 'e2eDelayVitals:stats',
                'e2eDelayCamera:stats')


def stats_means(path):
    """mean of each :stats block in STATS_WANTED, in seconds."""
    out = {}
    want = None
    with open(path) as f:
        for line in f:
            if line.startswith('statistic '):
                want = None
                for s in STATS_WANTED:
                    if line.rstrip('\n').endswith(' ' + s):
                        want = s
                        break
            elif want and line.startswith('field mean '):
                try:
                    out[want] = float(line.split()[2])
                except (IndexError, ValueError):
                    pass
                want = None
    return out


def collect(pattern, keyre):
    """(config -> seed -> row) over a results directory."""
    out = defaultdict(dict)
    for p in sorted(glob.glob(pattern)):
        m = re.match(keyre, os.path.basename(p)[:-4])
        if not m:
            continue
        sc = parse(p)
        row = kpis(sc)
        row.update(stats_means(p))
        # delivery over all four streams, on generated packets
        gen = sum(v for (mod, n), v in sc.items() if n == 'packetsGenerated')
        rcv = sum(v for (mod, n), v in sc.items()
                  if n in ('received_vitals', 'received_camera',
                           'received_obd', 'received_alarm'))
        row['delivery'] = 100.0 * rcv / gen if gen else float('nan')
        out[m.group(1)][int(m.group(2))] = row
    return out


def show(label, cells):
    for cfg in sorted(cells):
        rows = cells[cfg]
        n = len(rows)
        print(f'\n{label}  {cfg}   ({n} seeds)')
        for key, name, scale, unit in (
                ('timely_vitals', 'timely vitals', 1.0, '%'),
                ('timely_camera', 'timely camera', 1.0, '%'),
                ('delivery', 'delivery (all streams)', 1.0, '%'),
                ('e2eDelay:stats', 'mean e2e delay, all streams', 1e3, 'ms'),
                ('e2eDelayVitals:stats', 'mean e2e delay, vitals', 1e3, 'ms'),
                ('e2eDelayCamera:stats', 'mean e2e delay, camera', 1e3, 'ms')):
            vals = [r[key] * scale for r in rows.values() if key in r]
            if not vals:
                print(f'    {name:<30} --')
                continue
            mu, ci, k = mean_ci(vals)
            print(f'    {name:<30} {mu:8.2f} +/- {ci:6.2f} {unit}   (n={k})')
        # admission control active at all?
        bo = [r.get('backoffs', 0) or 0 for r in rows.values()]
        pr = [r.get('probes', 0) or 0 for r in rows.values()]
        print(f'    {"aimd backoffs / probes":<30} '
              f'{sum(bo):.0f} / {sum(pr):.0f} summed over seeds')


def main():
    root = os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..'))
    roomdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        root, 'simulations', 'room', 'results_matched')
    dcdir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        root, 'simulations', 'dc_case', 'results')

    room = collect(os.path.join(roomdir, '*.sca'), ROOM_RE)
    dc = collect(os.path.join(dcdir, '*.sca'), DC_RE)

    if not room:
        print(f'no RoomMatched* runs under {roomdir}', file=sys.stderr)
        return 1

    print('ROOM-TO-ROAD, matched sensor rig, no admission control in either')
    print('=' * 66)
    print('Room: 10 m room, 802.11n/ac backhaul, stationary.')
    print('Road: urban drive, LTE uplink, real tower geometry.')
    print('The rig is identical; the backhaul is the only difference.')
    show('ROOM ', room)
    show('ROAD ', dc)

    print('\n' + '=' * 66)
    print('CONTRAST (road minus room), per road config, on config means')
    for rcfg in sorted(room):
        rv = [r['timely_vitals'] for r in room[rcfg].values()]
        rc = [r['timely_camera'] for r in room[rcfg].values()]
        rmv, _, _ = mean_ci(rv)
        rmc, _, _ = mean_ci(rc)
        for dcfg in sorted(dc):
            dv, _, _ = mean_ci([r['timely_vitals']
                                for r in dc[dcfg].values()])
            dcm, _, _ = mean_ci([r['timely_camera']
                                 for r in dc[dcfg].values()])
            print(f'  {dcfg:<16} vs {rcfg:<18} '
                  f'vitals {dv - rmv:+7.2f} pp   camera {dcm - rmc:+7.2f} pp')
        break   # the two room bands agree; one block is enough to read

    print('\nNOTE: these are unpaired between settings by construction -- the '
          '\n      room and road campaigns are different networks, so a seed '
          '\n      index means nothing across them. Quote the two levels, not '
          '\n      a paired difference with an interval.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
