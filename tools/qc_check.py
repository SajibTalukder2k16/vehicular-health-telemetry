#!/usr/bin/env python3
"""Quality-control harness for PaperRebuild result sets.

Implements the standing QC rules derived from the old model's failure modes
(see docs/OLD_MODEL_DEFICIENCIES.md #5). A run set FAILS if:

  R1  any recorded metric is constant across seeds within a config
      (catches placeholder values like the old bufferOccupancy=0.5)
  R2  any delay statistic exceeds the run's simulation time
      (catches runaway-queue timestamps like the old 115,000 s "115 s")
  R3  two different factor levels produce bit-identical results
      (catches unimplemented factors like the old 2.4 vs 5 GHz)
  R4  packet accounting does not close:
      generated >= forwarded >= sent-to-cloud >= received at server

Usage: qc_check.py <results-dir> [more-dirs...]
Exit code 0 = all checks pass, 1 = failures found.
"""
import glob
import os
import re
import sys
from collections import defaultdict

SCALAR_RE = re.compile(r'^scalar (\S+) (\S+) (\S+)$')
FIELD_RE = re.compile(r'^field (\S+) (\S+)$')
STATISTIC_RE = re.compile(r'^statistic (\S+) (\S+)$')
ATTR_RE = re.compile(r'^attr (\S+) (.*)$')
CONFIG_RE = re.compile(r'^(.*?)-\d+-20\d{6}')

# R1 targets continuous metrics: a constant integer counter can be honest
# physics (e.g. a saturated deterministic link), but a constant continuous
# statistic (mean occupancy, mean delay) is the placeholder signature.
COUNTER_RE = re.compile(
    r'^(packets|bytes|received_|totalPackets|packetSent|packetDropped|'
    r'deadlineMisses|throughputBps)')

# R1/R3 audit only experiment KPI modules (rig, apps, cellular phy KPIs);
# protocol-stack internals (X2 setup, SCTP, PPP queues) are legitimately
# deterministic across seeds and are not placeholder suspects.
KPI_MODULE_RE = re.compile(r'(\.rig\.|\.app\[|cellularNic\.phy$|\.sink|\.link|\.src)')

# a dedicated wired point-to-point link (WiredLink) has deterministic
# serialization delay by construction: constant linkDelay on the wired
# camera/OBD links is honest physics, not a placeholder
def constant_ok(module, stat, config=''):
    if stat.startswith('linkDelay') and ('camLink' in module or 'obdLink' in module):
        return True
    # queueBytes samples only two values (len on enqueue, 0 on dequeue): with
    # fixed-size frames that never overlap, its sample mean is structurally
    # payload/2 regardless of RNG. Time-weighted queue stats still vary.
    if stat.startswith('queueBytes') and '.rig.' in module:
        return True
    # A static token-bucket arm (`dropPace` at a fixed cap, config `*-staticN`)
    # admits a deterministic number of camera frames: the camera source is
    # periodic with a fixed frame size, and admission happens upstream of the
    # radio, so neither the channel RNG nor the seed can change the decision.
    # cameraAdmitted is therefore identically 536 frames in every seed -- and
    # identical on c08 and c14, corridors at opposite ends of the coverage
    # sample. That is the static arm being radio-blind by construction, which
    # is the effect this study measures, not a placeholder.
    #
    # Deliberately scoped to the static arms. On `aimd`/`aimdSelf` the same
    # metrics are measurements of the controller and R1 still audits them --
    # which is why c12-aimdSelf converging to exactly 80 kb/s in all 10 seeds
    # is still reported rather than hidden.
    if STATIC_ARM_RE.search(config) and stat.startswith('cameraAdmitted'):
        return True
    # finalBucketRateBps is only a MEASUREMENT where an adaptive policy is
    # running, i.e. the `-aimd`/`-aimdSelf` arms. Everywhere else -- the static
    # caps, and all of Family A, whose campaigns predate the token-bucket
    # controller entirely -- it is a configured default echoed back, and being
    # constant across seeds says nothing. Exempt there, live on the adaptive
    # arms, where it still reports (see the note below).
    if stat == 'finalBucketRateBps' and not ADAPTIVE_ARM_RE.search(config):
        return True
    return False


# Config keys written by tools/corridor_*.sh.
STATIC_ARM_RE = re.compile(r'-static\d+$')
ADAPTIVE_ARM_RE = re.compile(r'-aimd(Self)?$')

# R1 still fires on finalBucketRateBps for the adaptive arms, and that is
# deliberate -- the findings are informative rather than defects. The
# controller's terminal rate is bimodal and seed-independent: exactly the
# 1 Mb/s ceiling on c08/c09/c11 and exactly the 80 kb/s probe floor on
# c12/c14, in all 10 seeds. c12's cross-stream arm sits on the floor only
# under background load, which is one of the cleaner illustrations that the
# load bites. Reported, explained, not suppressed.


def parse_sca(path):
    """Return (configname, runname, simtime_limit, {(module,name): value}, {(module,stat,field): value})."""
    scalars = {}
    stat_fields = {}
    configname = runname = None
    simtime = None
    cur_stat = None
    with open(path) as f:
        for line in f:
            line = line.rstrip('\n')
            m = SCALAR_RE.match(line)
            if m:
                cur_stat = None
                try:
                    scalars[(m.group(1), m.group(2))] = float(m.group(3))
                except ValueError:
                    pass
                continue
            m = STATISTIC_RE.match(line)
            if m:
                cur_stat = (m.group(1), m.group(2))
                continue
            m = FIELD_RE.match(line)
            if m and cur_stat:
                try:
                    stat_fields[(cur_stat[0], cur_stat[1], m.group(1))] = float(m.group(2))
                except ValueError:
                    pass
                continue
            m = ATTR_RE.match(line)
            if m:
                if m.group(1) == 'configname':
                    configname = m.group(2)
                elif m.group(1) == 'runnumber':
                    pass
            if line.startswith('run '):
                runname = line.split()[1]
            if line.startswith('config sim-time-limit'):
                val = line.split(None, 2)[2].strip('"')
                mt = re.match(r'([\d.eE+-]+)\s*s', val)
                if mt:
                    simtime = float(mt.group(1))
    return configname, runname, simtime, scalars, stat_fields


# A replication suffix the campaign runners write instead of OMNeT++'s `-#N`:
# tools/corridor_*.sh name cells `<corridor>-<arm>-s<NN>.sca` because they
# override every factor on the command line rather than through iteration
# variables.
SEED_SUFFIX_RE = re.compile(r'-s\d+$')


def config_key(path, configname):
    """Config + iteration variables (from filename), without the replication.

    Both naming schemes must collapse to the same key, or R1 and R3 silently
    stop testing: they need several runs per config, and a key that still
    carries the replication index puts every run in a config of its own.

    That is exactly what happened. Until 2026-11-04 this stripped only
    OMNeT++'s `-#N`, so the 490-run corridor campaigns -- named `-s<NN>` by
    their runners -- audited as "490 runs in 490 configs" and reported
    QC PASSED while R1 and R3 were no-ops. See docs/CORRECTIONS_2026-10.md C15.
    """
    # Drop the extension first: OMNeT++'s `-#N.sca` loses it to the rsplit,
    # but `-s<NN>.sca` does not, and a trailing `.sca` stops the suffix match.
    base = os.path.splitext(os.path.basename(path))[0].rsplit('-#', 1)[0]
    return SEED_SUFFIX_RE.sub('', base)


def main(dirs):
    files = []
    for d in dirs:
        files += glob.glob(os.path.join(d, '*.sca'))
    if not files:
        print("QC: no .sca files found")
        return 1

    by_config = defaultdict(list)
    failures = []

    for path in files:
        configname, runname, simtime, scalars, stats = parse_sca(path)
        key = config_key(path, configname)
        by_config[key].append((path, simtime, scalars, stats))

        # R2: delays must not exceed sim time
        if simtime:
            for (mod, stat, field), v in stats.items():
                if 'elay' in stat and field == 'max' and v > simtime:
                    failures.append(f"R2 {os.path.basename(path)}: {mod}.{stat} max={v:.1f}s > simtime {simtime:.0f}s")

        # R4: accounting closes (only when all counters present)
        gen = sum(v for (m, n), v in scalars.items() if n == 'packetsGenerated')
        fwd = sum(v for (m, n), v in scalars.items() if n == 'packetsForwarded')
        sent = sum(v for (m, n), v in scalars.items() if n == 'packetsSentToCloud')
        rcvd = sum(v for (m, n), v in scalars.items() if n == 'totalPacketsReceived')
        if gen and not (gen >= fwd >= sent >= rcvd):
            failures.append(f"R4 {os.path.basename(path)}: accounting gen={gen:.0f} fwd={fwd:.0f} sent={sent:.0f} rcvd={rcvd:.0f}")

    # R1: constant across seeds within a config
    for key, runs in by_config.items():
        if len(runs) < 3:
            continue
        allkeys = set()
        for _, _, scalars, _ in runs:
            allkeys |= set(scalars)
        for sk in allkeys:
            name = sk[1]
            if COUNTER_RE.match(name) or not KPI_MODULE_RE.search(sk[0]):
                continue
            # `key` is the config, so a constant that is a deterministic
            # consequence of that config can be exempted per-arm.
            if constant_ok(sk[0], name, key):
                continue
            vals = [scalars.get(sk) for _, _, scalars, _ in runs if sk in scalars]
            if len(vals) >= 3 and len(set(vals)) == 1 and vals[0] not in (0.0,):
                failures.append(f"R1 {key}: {sk[0]}.{name} constant {vals[0]} across {len(vals)} seeds")
        statkeys = set()
        for _, _, _, stats in runs:
            statkeys |= {k for k in stats if k[2] == 'mean' and KPI_MODULE_RE.search(k[0])}
        for sk in statkeys:
            if constant_ok(sk[0], sk[1], key):
                continue
            vals = [stats.get(sk) for _, _, _, stats in runs if sk in stats]
            vals = [v for v in vals if v is not None and v == v]  # drop NaN
            if len(vals) >= 3 and len(set(vals)) == 1 and vals[0] != 0.0:
                failures.append(f"R1 {key}: {sk[0]}.{sk[1]} mean constant {vals[0]} across {len(vals)} seeds")

    # R3: different factor levels bit-identical (compare per-config mean vectors)
    signature = {}
    for key, runs in by_config.items():
        sig = []
        for _, _, scalars, _ in sorted(runs, key=lambda r: r[0]):
            sig += [v for k, v in sorted(scalars.items()) if k[1] in
                    ('totalPacketsReceived', 'packetsSentToCloud')]
        signature[key] = tuple(sig)
    # The *Legacy8 configs deliberately reproduce the superseded pooled/
    # 8-densest tower selection that DcDrive and VaDrive used, so they are
    # expected to match those bit for bit -- that equality is the evidence
    # that the site-selection sensitivity arm reproduces the published
    # numbers (docs/CORRECTIONS_2026-10.md, C1). Any other pair matching is
    # still a genuine R3 failure.
    def expected_twins(a, b):
        pair = {a.replace('Legacy8', ''), b.replace('Legacy8', '')}
        return len(pair) == 1 and ('Legacy8' in a) != ('Legacy8' in b)

    seen = {}
    for key, sig in signature.items():
        if sig and sig in seen and not expected_twins(seen[sig], key):
            failures.append(f"R3 configs '{seen[sig]}' and '{key}' produced bit-identical results")
        seen[sig] = key

    print(f"QC: {len(files)} runs in {len(by_config)} configs")
    if failures:
        print(f"QC FAILED ({len(failures)} findings):")
        # Count by rule BEFORE truncating. The listing is capped, and a cap
        # that hides which rules fired is worse than no listing: it was
        # possible to read 50 benign R1 lines and not notice an R3 below them.
        counts = {}
        for f_ in failures:
            counts[f_.split()[0]] = counts.get(f_.split()[0], 0) + 1
        print("  by rule: " + ", ".join(f"{r} x{counts[r]}"
                                       for r in sorted(counts)))
        for f_ in failures[:50]:
            print("  " + f_)
        if len(failures) > 50:
            print(f"  ... {len(failures) - 50} further findings not listed; "
                  f"see the by-rule counts above")
        return 1
    print("QC PASSED: no degenerate constants, no impossible delays, "
          "no identical factor levels, accounting closes")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:] or ['.']))
