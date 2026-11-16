#!/usr/bin/env python3
"""Per-escalation time-to-dispatch, from the pilot's .vec files.

The server cannot dispatch emergency services until it has BOTH the alert and
enough evidence to verify it, so the decision-relevant latency is

    dispatch_delay = max(alert_delay, max over the burst's chunk delays)

measured per escalation. This is the quantity C2' and C3 are about
(docs/VERIFICATION_FRONTIER.md).

Requires a corpus run with per-escalation vector recording enabled -- see the
ordering warning in simulations/pilot/omnetpp.ini. The 2026-11-08 and
2026-11-09 corpora have `**.vector-recording = false` and their .vec files hold
zero samples; on those, only the per-run `e2eDelayEvidence:max` scalar is
available, which overstates the typical escalation badly (it is a maximum over
~5 escalations). Use results_escalation_vec/ or later.

THE TWO SIGNALS ARE ON DIFFERENT CLOCKS -- THIS IS THE CENTRAL SUBTLETY
-----------------------------------------------------------------------
The server computes one delay for every packet, `simTime() -
payload->getSensorCreationTime()` (HealthServerApp.cc), but the two classes
carry different creation stamps:

  * an ALERT carries the rig's SENSOR creation time, so `e2eDelayAlarm`
    INCLUDES the edge's processing and queueing delay;
  * an EVIDENCE chunk is a SensorData constructed at the edge inside
    EdgeApp::escalate(), so its stamp is the DETECTION instant and
    `e2eDelayEvidence` EXCLUDES everything upstream of the edge.

Their difference is the per-frame edge latency, measured here:

    offset = chunk_creation - alert_creation   (>= 0 by construction)

    edge setting                       min      median         max
    uniform(0.5ms, 2ms)           0.000502    0.001194    0.002440
    22.73 ms @ 30 fps             0.022730    0.030898    0.066293
    22.73 ms @ 60 fps             0.032327    0.048418    0.087952
    94.27 ms @ 60 fps             0.174657    0.233411    0.450942

So a naive `max(alert_delay, max chunk_delay)` charges the edge cost to the
alert and credits it to the evidence. At the unsourced 1.28 ms edge that is a
<=1.3 ms error and invisible; at a sourced 94.27 ms edge it is a 230 ms error
that drives the dispatch GAP to exactly 0.0000 and reads as "a slower edge
makes verification free". It does not. Dispatch is referred to the SENSOR
instant -- when the physiological event was observed, which is what an
emergency latency is measured from -- so the offset must be added back:

    dispatch_delay = max(alert_delay, offset + max over the burst's chunk delays)

PAIRING IS A SIGNED WINDOW, NOT AN ABSOLUTE TOLERANCE
-----------------------------------------------------
Evidence is created at or after its alert, never before, so the burst is the
nearest creation key in [creation - EPS, creation + tol]. Using |delta| is
unsafe here: the measured minimum inter-escalation spacing is 1.1692 s, below
the tol a saturated edge needs, so a symmetric window can pair an alert to its
NEIGHBOUR's burst. A signed window cannot, because a neighbour's burst lies in
the past.

The window must still exceed the largest real offset, or escalations go
unpaired -- and an unpaired escalation silently falls back to the alert delay,
making dispatch look identical to the alert and erasing the entire effect. That
bug produced a wrong table once; hence --report-pairing, which must be read
BEFORE the table, every time. Defaults: 10 ms is right for the unsourced edge;
the M4 edge-cost corpora need --tol 1.0 -- above the 0.451 s maximum offset and
below the 1.169 s minimum spacing.

    python3 tools/dispatch_times.py <results_dir> [--tol SECONDS]
                                    [--budget SECONDS] [--report-pairing]
"""
import argparse
import glob
import math
import os
import re
import statistics

CONDS = ["CondHealthy", "CondCongested", "CondTransient", "CondOutage"]
# Arms are DISCOVERED, not fixed: the Gate A pilot uses ref/e1..e4 at policy
# none, while Phase 2 adds e2b (14,400 B, the W>=120s waveform rung) and the
# deferral arms e3/e4 at policy pace and e4dp at dropPace. A hardcoded list
# silently drops whatever it does not know about.
ARM_ORDER = ["ref", "e1", "e2", "e2b", "e3", "e4", "e4dp",
             # M4 edge-cost sensitivity (tools/edge_sensitivity.sh)
             "e2bB30", "e2bPC30", "e2bPC", "e2bEMB",
             "e4B30", "e4PC30", "e4PC", "e4EMB"]
RUNG = {"ref": "none", "e1": "512B", "e2": "3.5KiB", "e2b": "14.4kB",
        "e3": "56KiB", "e4": "138kB", "e4dp": "138kB/dp",
        "e2bB30": "14.4k/b30", "e2bPC30": "14.4k/pc30",
        "e2bPC": "14.4k/pc60", "e2bEMB": "14.4k/em60",
        "e4B30": "138k/b30", "e4PC30": "138k/pc30",
        "e4PC": "138k/pc60", "e4EMB": "138k/em60"}
DEFAULT_TOL = 1e-2

# THE DEFAULT WINDOW IS NOT SAFE FOR THE EDGE-COST ARMS.
# The alert/evidence creation offset IS the edge latency, so at a sourced edge
# cost it is 23-88 ms rather than 1.28 ms -- and where the edge saturates it is
# dominated by QUEUEING, measured up to 0.451 s at 94.27 ms. Those corpora need
# --tol 1.0: above that maximum, and below the 1.169 s minimum inter-escalation
# spacing, which a wider window would let it cross. Read --report-pairing
# every time, before the table.


def order_arms(found):
    known = [a for a in ARM_ORDER if a in found]
    return known + sorted(a for a in found if a not in ARM_ORDER)


def parse_vec(path):
    """-> (alarms, chunks): [(creation, delay)], {creation: [delay, ...]}"""
    vid_alarm = vid_ev = None
    alarms, chunks = [], {}
    with open(path) as f:
        for line in f:
            if line.startswith("vector "):
                p = line.split()
                if len(p) >= 4 and p[3].startswith("e2eDelayAlarm:"):
                    vid_alarm = p[1]
                elif len(p) >= 4 and p[3].startswith("e2eDelayEvidence:"):
                    vid_ev = p[1]
                continue
            if not line[:1].isdigit():
                continue
            p = line.split()
            if len(p) != 4:
                continue
            if p[0] == vid_alarm:
                t, v = float(p[2]), float(p[3])
                alarms.append((t - v, v))
            elif p[0] == vid_ev:
                t, v = float(p[2]), float(p[3])
                chunks.setdefault(round(t - v, 6), []).append(v)
    return alarms, chunks


# The two stamps coincide exactly when the edge delay rounds to zero, so the
# signed window has to admit a hair of negative slack.
EPS = 1e-9


def pair_bursts(alarms, chunks, tol):
    """-> [(alert_delay, dispatch_delay, n_chunks, offset_or_None)]

    ONE implementation, used by both the corpus and the .csv.gz path: these
    were duplicated, and duplicated pairing logic is exactly how the two could
    drift into disagreeing about the headline number.

    `offset` is signed and non-negative by construction, and is ADDED to the
    burst's chunk delays before the max, which puts dispatch on the sensor
    clock. See the module docstring -- omitting it is a real bug, not a rounding
    choice.
    """
    keys = sorted(chunks)
    out = []
    for creation, adelay in alarms:
        # earliest burst at or after this alert; a neighbour's burst is in the
        # past and therefore cannot be selected
        best = None
        for k in keys:
            if k - creation >= -EPS:
                if k - creation <= tol:
                    best = k
                break
        if best is None:
            out.append((adelay, adelay, 0, None))
            continue
        off = best - creation
        out.append((adelay, max(adelay, off + max(chunks[best])),
                    len(chunks[best]), off))
    return out


def escalations(path, tol):
    alarms, chunks = parse_vec(path)
    return pair_bursts(alarms, chunks, tol)


def q(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))] if xs else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results_dir")
    ap.add_argument("--tol", type=float, default=DEFAULT_TOL)
    ap.add_argument("--budget", type=float, default=4.0,
                    help="dispatch budget in s; default 4.0 = eCall MSD-to-PSAP, "
                         "ETSI TS 122 101 cl. A.27.2")
    ap.add_argument("--report-pairing", action="store_true")
    a = ap.parse_args()

    data = {}
    if a.results_dir.endswith(".csv.gz"):
        # the committed extract (tools/extract_vec.py), so the table is
        # reproducible from the repository without the 956 MB corpus
        import csv as _csv
        import gzip as _gzip
        per = {}
        with _gzip.open(a.results_dir, "rt", newline="") as fh:
            for r in _csv.DictReader(fh):
                key = (r["condition"], r["arm"], r["seed"])
                al, ch = per.setdefault(key, ([], {}))
                if r["kind"] == "alarm":
                    al.append((float(r["creation"]), float(r["delay"])))
                else:
                    ch.setdefault(round(float(r["creation"]), 6), []).append(float(r["delay"]))
        found = {m for (_, m, _) in per}
        arms = order_arms(found)
        for cond in CONDS:
            for arm in arms:
                rows = []
                for (c, m, s), (al, ch) in sorted(per.items()):
                    if c != cond or m != arm:
                        continue
                    rows += pair_bursts(al, ch, a.tol)
                data[(cond, arm)] = rows
    else:
        found = set()
        for p in glob.glob(os.path.join(a.results_dir, "*.vec")):
            m = re.match(r"^[A-Za-z0-9_]+-(.+)-s\d+\.vec$", os.path.basename(p))
            if m:
                found.add(m.group(1))
        arms = order_arms(found)
        for cond in CONDS:
            for arm in arms:
                rows = []
                for p in sorted(glob.glob(os.path.join(a.results_dir,
                                                       f"{cond}-{arm}-s*.vec"))):
                    rows += escalations(p, a.tol)
                data[(cond, arm)] = rows

    if a.report_pairing:
        print("PAIRING DIAGNOSTIC -- unpaired escalations silently collapse "
              "dispatch onto the alert\n")
        print(f"{'condition':15s} {'arm':4s} {'esc':>5s} {'paired':>7s} "
              f"{'median offset':>14s}  {'max offset':>11s}  {'chunks/burst':>12s}")
        for cond in CONDS:
            for arm in arms:
                if arm == "ref":
                    continue
                rows = data[(cond, arm)]
                if not rows:
                    continue
                d = [r[3] for r in rows if r[3] is not None]
                nch = [r[2] for r in rows if r[2]]
                print(f"{cond:15s} {arm:4s} {len(rows):5d} "
                      f"{str(sum(1 for r in rows if r[2]))+'/'+str(len(rows)):>7s} "
                      f"{(statistics.median(d) if d else float('nan')):14.6f}  "
                      f"{(max(d) if d else float('nan')):11.6f}  "
                      f"{(statistics.median(nch) if nch else 0):12.0f}")
        print()

    print(f"corpus: {a.results_dir}   tol={a.tol}s   budget={a.budget}s\n")
    h = (f"{'condition':15s} {'arm':4s} {'rung':7s} {'esc':>4s} {'alert_med':>9s} "
         f"{'disp_med':>9s} {'disp_p90':>9s} {'disp_max':>9s} {'over':>6s} "
         f"{'gap_med':>8s}")
    print(h)
    print("-" * len(h))
    for cond in CONDS:
        for arm in arms:
            rows = data[(cond, arm)]
            if not rows:
                continue
            al = [r[0] for r in rows]
            dp = [r[1] for r in rows]
            gp = [r[1] - r[0] for r in rows]
            over = sum(1 for x in dp if x > a.budget) / len(dp) * 100
            print(f"{cond:15s} {arm:4s} {RUNG.get(arm, arm):7s} {len(rows):4d} "
                  f"{statistics.median(al):9.4f} {statistics.median(dp):9.4f} "
                  f"{q(dp, 0.90):9.4f} {max(dp):9.4f} {over:5.1f}% "
                  f"{statistics.median(gp):8.4f}")
        print()


if __name__ == "__main__":
    main()
