#!/usr/bin/env python3
"""Export the campaign's .sca corpus into two CSVs for analysis.

  runs_detailed.csv   one row per run: iteration variables + per-run KPIs
  cells_aggregated.csv one row per design cell: n, mean, std, 95% CI for the
                       main KPIs, plus pooled delay quantiles (p50/p95/p99)
                       computed from the summed e2eDelay histograms of all
                       seeds in the cell.

Usage: export_results.py <out-dir> <results-dir> [more results-dirs...]
"""
import csv
import glob
import math
import os
import re
import sys
from collections import defaultdict

# KPIs aggregated per design cell. delivery_e2e (generated-to-received) and
# delivery_uplink (what the radio did with what it was handed) are both carried
# because a lossy sensor link makes them diverge by >13 pp. Per-stream
# accounting keeps "arrived late" and "never arrived" separate.
AGG_KPIS = ('delivery_e2e', 'delivery_uplink', 'preUplinkLoss', 'e2eDelayMean',
            'late_vitals', 'undelivered_vitals', 'late_alarm', 'undelivered_alarm',
            'edgeDrops', 'linkDrops',
            'delivered_vitals', 'delivered_alarm', 'delivered_camera', 'delivered_obd',
            'timely_vitals', 'timely_alarm', 'timely_camera', 'timely_obd')

T95 = {2: 12.71, 3: 4.303, 4: 3.182, 5: 2.776, 10: 2.262, 20: 2.093, 30: 2.045}


def t95(n):
    if n <= 1:
        return float('nan')
    best = min((k for k in T95), key=lambda k: abs(k - n))
    return T95[best] if n < 40 else 1.96


SCALAR_RE = re.compile(r'^scalar (\S+) (\S+) (\S+)$')
FIELD_RE = re.compile(r'^field (\S+) (\S+)$')
STATISTIC_RE = re.compile(r'^statistic (\S+) (\S+)$')
BIN_RE = re.compile(r'^bin\t(\S+)\t(\S+)$')
ITERVARS_RE = re.compile(r'^attr iterationvars "?(.*?)"?$')
CONFIG_RE = re.compile(r'^attr configname (\S+)$')
REPETITION_RE = re.compile(r'^attr repetition (\S+)$')


def parse_sca(path):
    scalars, stats, bins = {}, {}, defaultdict(list)
    itervars, config, rep = '', '', ''
    cur = None
    with open(path) as f:
        for line in f:
            line = line.rstrip('\n')
            m = SCALAR_RE.match(line)
            if m:
                cur = None
                try:
                    scalars[(m.group(1), m.group(2))] = float(m.group(3))
                except ValueError:
                    pass
                continue
            m = STATISTIC_RE.match(line)
            if m:
                cur = (m.group(1), m.group(2))
                continue
            m = FIELD_RE.match(line)
            if m and cur:
                try:
                    stats[(cur[0], cur[1], m.group(1))] = float(m.group(2))
                except ValueError:
                    pass
                continue
            m = BIN_RE.match(line)
            if m and cur:
                try:
                    bins[cur].append((float(m.group(1)), float(m.group(2))))
                except ValueError:
                    pass
                continue
            m = ITERVARS_RE.match(line)
            if m:
                itervars = m.group(1)
                continue
            m = CONFIG_RE.match(line)
            if m:
                config = m.group(1)
                continue
            m = REPETITION_RE.match(line)
            if m:
                rep = m.group(1)
    return config, itervars, rep, scalars, stats, bins


def sum_scalar(scalars, name):
    return sum(v for (mod, n), v in scalars.items() if n == name)


def find_stat(stats, statname, field):
    for (mod, s, f), v in stats.items():
        if s == statname and f == field:
            return v
    return float('nan')


def pooled_quantiles(binlist, qs=(0.5, 0.95, 0.99)):
    """binlist: list of {edge: count} histograms (lower-edge, count)."""
    total = defaultdict(float)
    for bl in binlist:
        for edge, cnt in bl:
            total[edge] += cnt
    if not total:
        return [float('nan')] * len(qs)
    edges = sorted(total)
    n = sum(total.values())
    out = []
    for q in qs:
        target = q * n
        acc = 0.0
        val = edges[-1]
        for e in edges:
            acc += total[e]
            if acc >= target:
                val = e
                break
        out.append(val)
    return out


def main():
    outdir = sys.argv[1]
    dirs = sys.argv[2:]
    os.makedirs(outdir, exist_ok=True)
    files = []
    for d in dirs:
        files += sorted(glob.glob(os.path.join(d, '*.sca')))
    print(f"parsing {len(files)} sca files ...")

    rows = []
    cell_hists = defaultdict(list)
    var_names = set()
    for path in files:
        config, itervars, rep, scalars, stats, bins = parse_sca(path)
        if not config:
            continue
        ivd = {}
        for kv in itervars.split(', '):
            if '=' in kv:
                k, v = kv.split('=', 1)
                ivd[k.lstrip('$')] = v
        var_names |= set(ivd)
        sent = sum_scalar(scalars, 'packetsSentToCloud')
        rcvd = sum_scalar(scalars, 'totalPacketsReceived')
        gen = sum_scalar(scalars, 'packetsGenerated')
        row = {
            'config': config, 'repetition': rep, **ivd,
            'generated': gen,
            'sentToCloud': sent,
            'received': rcvd,
            # Two different questions, reported separately. delivery_uplink is
            # what the radio did with what it was handed; delivery_e2e is what
            # fraction of what the sensors produced reached the cloud. A lossy
            # sensor link (BLE) flatters delivery_uplink by shrinking its
            # denominator, so delivery_e2e is the one to quote for feasibility.
            'delivery_uplink': rcvd / sent if sent else float('nan'),
            'delivery_e2e': rcvd / gen if gen else float('nan'),
            'preUplinkLoss': (gen - sent) / gen if gen else float('nan'),
            'e2eDelayMean': find_stat(stats, 'e2eDelay:stats', 'mean'),
            'e2eDelayMax': find_stat(stats, 'e2eDelay:stats', 'max'),
            'e2eDelayCount': find_stat(stats, 'e2eDelay:stats', 'count'),
            'edgeDrops': sum(v for (m, n), v in scalars.items()
                             if n == 'packetsDropped' and '.rig.edge' in m),
            # Sensor-link drops. The rig's link submodules are named
            # bleWearable, camLink and obdLink (SensorRig.ned) -- camLink and
            # obdLink keep those names whichever ILink type is plugged in, so
            # matching on 'ble' catches only the wearable and silently omits
            # camera and OBD losses. Match the submodule names instead.
            'linkDrops': sum(v for (m, n), v in scalars.items()
                             if n == 'packetsDropped'
                             and any(s in m for s in ('.rig.bleWearable',
                                                      '.rig.camLink',
                                                      '.rig.obdLink'))),
        }
        srcmod = {'vitals': '.wearable', 'obd': '.obd', 'camera': '.camera', 'alarm': '.alarm'}
        for t in ('vitals', 'obd', 'camera', 'alarm'):
            r_t = sum_scalar(scalars, f'received_{t}')
            late = sum_scalar(scalars, f'deadlineMisses_{t}')
            g = sum(v for (m, n), v in scalars.items()
                    if n == 'packetsGenerated' and m.endswith(srcmod[t]))
            row[f'generated_{t}'] = g
            row[f'received_{t}'] = r_t
            # Full accounting of every generated packet, so the three failure
            # modes stay visible: arrived late, never arrived, arrived on time.
            # 'late' counts only packets that DID arrive, so quoting it alone
            # (as "misses per drive") hides the undelivered ones entirely.
            row[f'late_{t}'] = late
            row[f'undelivered_{t}'] = g - r_t
            row[f'delivered_{t}'] = r_t / g if g else float('nan')
            row[f'timely_{t}'] = (r_t - late) / g if g else float('nan')
            # share of the undelivered that is attributable to the sensor link
            # rather than the uplink (0 for wired rigs)
        rows.append(row)
        row['_ivd'] = ivd
        for (mod, statname), bl in bins.items():
            if statname == 'e2eDelay:histogram':
                row['_hist'] = bl

    # detailed CSV
    var_names = sorted(var_names)
    fields = (['config', 'repetition'] + var_names +
              [k for k in rows[0] if k not in ('config', 'repetition') and k not in var_names
               and not k.startswith('_')])
    with open(os.path.join(outdir, 'runs_detailed.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, restval='', extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)

    # aggregated CSV (histogram key built identically to the cell key)
    cells = defaultdict(list)
    for row in rows:
        cellkey = (row['config'], tuple(sorted((k, row.get(k, '')) for k in var_names)))
        cells[cellkey].append(row)
        if '_hist' in row:
            cell_hists[cellkey].append(row['_hist'])

    def mstd(vals):
        vals = [v for v in vals if v == v]
        n = len(vals)
        if n == 0:
            return float('nan'), float('nan'), float('nan'), 0
        m = sum(vals) / n
        s = math.sqrt(sum((v - m) ** 2 for v in vals) / (n - 1)) if n > 1 else 0.0
        return m, s, t95(n) * s / math.sqrt(n) if n > 1 else float('nan'), n

    aggfields = (['config'] + var_names + ['n'] +
                 sum([[f'{k}_mean', f'{k}_std', f'{k}_ci95'] for k in
                      AGG_KPIS], []) +
                 ['delay_p50', 'delay_p95', 'delay_p99'])
    with open(os.path.join(outdir, 'cells_aggregated.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(aggfields)
        for (config, ivt), cellrows in sorted(cells.items()):
            ivd = dict(ivt)
            out = [config] + [ivd.get(k, '') for k in var_names] + [len(cellrows)]
            for k in AGG_KPIS:
                m, s, ci, _ = mstd([r[k] for r in cellrows])
                out += [f'{m:.6g}', f'{s:.6g}', f'{ci:.6g}']
            hk = (config, ivt)
            out += [f'{q:.6g}' for q in pooled_quantiles(cell_hists.get(hk, []))]
            w.writerow(out)

    print(f"wrote {len(rows)} runs, {len(cells)} cells -> {outdir}/")


if __name__ == '__main__':
    main()
