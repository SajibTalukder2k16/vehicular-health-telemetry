#!/usr/bin/env python3
"""C4 confirmation sweep: does ANY gate configuration help the dispatch decision?

Scores the five predictions recorded in tools/gate_sweep.sh before the run, and
the three propositions of docs/GATE_DERIVATION.md. The corpus carries its own
policy=none baseline so every contrast is WITHIN one corpus at matched seeds --
see decision 17 and the camera-rate error that motivated it.

    python3 tools/gate_contrasts.py [results_dir | extract_dir]

TWO INPUT PATHS, AND WHY THE EXTRACT ONE EXISTS
  Until 2026-11-16 this tool read ONLY the raw 3.4 GB results_gate/ corpus,
  which is gitignored and not redistributed. That made Table V and the
  staleness results the one part of the paper a reader could not regenerate,
  while the paper claimed otherwise -- an overstatement found by checking the
  claim rather than the numbers.

  It now defaults to the committed extract in analysis/gate/ when that is
  present, and falls back to the raw corpus. The extract path parses
  escalation_latencies.csv.gz (the two escalation vectors) and pilot_all.csv.gz
  (the per-run scalars), both verified value-by-value against the corpus.

  The two paths are checked to print byte-identical output; see
  docs/GATE_SWEEP_RESULT.md section 7. If you change one, re-run that check.
"""
import csv
import glob
import gzip
import math
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dispatch_times import pair_bursts, parse_vec  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONDS = ["CondHealthy", "CondCongested", "CondTransient", "CondOutage"]
TOL = 1e-2            # free edge: offset ~1.28 ms
EV = 138000.0         # E4, the swept rung

# label -> (bucket bytes, fill rate bytes/s)
PACE = {
    "p16k1": (16384, 1e6/8),   "p16k4": (16384, 4e6/8),   "p16k16": (16384, 16e6/8),
    "p64k1": (65536, 1e6/8),   "p64k4": (65536, 4e6/8),   "p64k16": (65536, 16e6/8),
    "p128k1": (131072, 1e6/8), "p128k4": (131072, 4e6/8), "p128k16": (131072, 16e6/8),
    "p256k1": (262144, 1e6/8), "p256k4": (262144, 4e6/8), "p256k16": (262144, 16e6/8),
}
AGE = {"dp05": 0.5, "dp1": 1.0, "dp2": 2.0, "dp4": 4.0, "dp8": 8.0}


def bound(label):
    b, r = PACE[label]
    return max(0.0, (EV - b) / r)


def sign_test(pairs):
    pos = sum(1 for a, b in pairs if b > a)
    neg = sum(1 for a, b in pairs if b < a)
    n = pos + neg
    if n == 0:
        return n, pos, neg, 1.0
    k = min(pos, neg)
    return n, pos, neg, min(1.0, 2.0 * sum(math.comb(n, i)
                                           for i in range(k + 1)) / 2.0 ** n)


def load(d):
    """-> {(cond, arm, seed): rows}, and the per-run scalars we need."""
    esc, sca = {}, {}
    for p in sorted(glob.glob(os.path.join(d, "*.vec"))):
        m = re.match(r"^([A-Za-z0-9_]+)-([A-Za-z0-9_]+)-s(\d+)\.vec$",
                     os.path.basename(p))
        if not m:
            continue
        al, ch = parse_vec(p)
        esc[(m.group(1), m.group(2), int(m.group(3)))] = pair_bursts(al, ch, TOL)
    for p in sorted(glob.glob(os.path.join(d, "*.sca"))):
        m = re.match(r"^([A-Za-z0-9_]+)-([A-Za-z0-9_]+)-s(\d+)\.sca$",
                     os.path.basename(p))
        if not m:
            continue
        want = {"evidenceChunksEmitted", "received_evidence",
                "evidenceChunksStaleDropped", "evidenceChunksLost"}
        d2 = {}
        with open(p) as fh:
            for line in fh:
                if line.startswith("scalar "):
                    f = line.split()
                    if len(f) >= 4 and f[2] in want:
                        d2[f[2]] = float(f[3])
        sca[(m.group(1), m.group(2), int(m.group(3)))] = d2
    return esc, sca


def gap_by_seed(esc, cond, arm):
    return {s: statistics.median(r[1] - r[0] for r in rows)
            for (c, m, s), rows in esc.items()
            if c == cond and m == arm and rows}


def disp_by_seed(esc, cond, arm):
    return {s: statistics.median(r[1] for r in rows)
            for (c, m, s), rows in esc.items()
            if c == cond and m == arm and rows}


def frac_by_seed(sca, cond, arm):
    out = {}
    for (c, m, s), d in sca.items():
        if c == cond and m == arm and d.get("evidenceChunksEmitted", 0) > 0:
            out[s] = d.get("received_evidence", 0) / d["evidenceChunksEmitted"]
    return out


SCALARS = {"evidenceChunksEmitted", "received_evidence",
           "evidenceChunksStaleDropped", "evidenceChunksLost"}


def load_extract(d):
    """Same two products as load(), from the committed .csv.gz extract.

    Must agree with load() exactly: the extract is a lossless projection of
    the corpus, verified value-by-value by tools/verify_extract.py.
    """
    per = {}
    with gzip.open(os.path.join(d, "escalation_latencies.csv.gz"),
                   "rt", newline="") as fh:
        rd = csv.reader(fh)
        h = {n: i for i, n in enumerate(next(rd))}
        ic, ia, isd = h["condition"], h["arm"], h["seed"]
        ik, idl, icr = h["kind"], h["delay"], h["creation"]
        for row in rd:
            k = (row[ic], row[ia], int(row[isd]))
            al, ch = per.setdefault(k, ([], {}))
            if row[ik] == "alarm":
                al.append((float(row[icr]), float(row[idl])))
            else:
                ch.setdefault(round(float(row[icr]), 6), []).append(
                    float(row[idl]))
    esc = {k: pair_bursts(a, c, TOL) for k, (a, c) in per.items()}

    # gate_scalars.csv.gz is pilot_all.csv.gz projected onto the four scalars
    # used below: 27 KB instead of 54.7 MB, which is what makes the artifact
    # repository clonable. Identical columns, so one reader serves both.
    sca = {}
    scalars = os.path.join(d, "gate_scalars.csv.gz")
    if not os.path.exists(scalars):
        scalars = os.path.join(d, "pilot_all.csv.gz")
    with gzip.open(scalars, "rt", newline="") as fh:
        rd = csv.reader(fh)
        h = {n: i for i, n in enumerate(next(rd))}
        ic, ia, isd = h["condition"], h["arm"], h["seed"]
        inm, ifl, iv = h["name"], h["field"], h["value"]
        for row in rd:
            # field != "" is a histogram/statistic component, not the scalar
            if row[inm] in SCALARS and not row[ifl]:
                k = (row[ic], row[ia], int(row[isd]))
                # last occurrence wins, matching load()'s .sca parse
                sca.setdefault(k, {})[row[inm]] = float(row[iv])
    return esc, sca


def resolve(argv):
    """-> (path, loader). Prefer the committed extract; fall back to raw."""
    if len(argv) > 1:
        d = argv[1]
    else:
        ext = os.path.join(ROOT, "analysis/gate")
        raw = os.path.join(ROOT, "simulations/pilot/results_gate")
        d = ext if os.path.exists(
            os.path.join(ext, "escalation_latencies.csv.gz")) else raw
    if os.path.exists(os.path.join(d, "escalation_latencies.csv.gz")):
        return d, load_extract
    return d, load


def main():
    d, loader = resolve(sys.argv)
    esc, sca = loader(d)
    arms = sorted({m for (_, m, _) in esc})
    print(f"corpus: {d}\narms found: {' '.join(arms)}\n")

    # ---------------------------------------------------------------- P1 / P2
    print("=" * 78)
    print("PREDICTION 1 (POSITIVE CONTROL) and 2 (NO NEGATIVE PENALTY)")
    print("  penalty = gap(pace) - gap(none), per-seed median, paired on seed")
    print("  b=256KiB > B=138,000 B  =>  Prop 1 says penalty is EXACTLY 0")
    print("  Prop 2 forbids a significant NEGATIVE penalty at any (b, r)")
    print("=" * 78)
    hdr = (f"{'arm':9s} {'b':>8s} {'r Mbps':>7s} {'bound':>7s} | "
           + " ".join(f"{c[4:]:>11s}" for c in CONDS))
    print(hdr)
    print("-" * len(hdr))
    viol_neg, viol_ctrl, viol_bound = [], [], []
    for arm in [a for a in PACE if a in arms]:
        b, r = PACE[arm]
        cells = []
        for cond in CONDS:
            base, test = gap_by_seed(esc, cond, "none"), gap_by_seed(esc, cond, arm)
            seeds = sorted(set(base) & set(test))
            if not seeds:
                cells.append("        n/a")
                continue
            pairs = [(base[s], test[s]) for s in seeds]
            pen = statistics.median(y - x for x, y in pairs)
            n, pos, neg, p = sign_test(pairs)
            star = "*" if p < 0.05 else " "
            cells.append(f"{pen:+8.4f}{star}  ")
            if pen < 0 and p < 0.05:
                viol_neg.append((arm, cond, pen, p))
            if b > EV and abs(pen) > 1e-9:
                viol_ctrl.append((arm, cond, pen))
            if pen > bound(arm) + 1e-9:
                viol_bound.append((arm, cond, pen, bound(arm)))
        print(f"{arm:9s} {b:8d} {r*8/1e6:7.0f} {bound(arm):7.4f} | " + " ".join(cells))

    print("\n  VERDICTS")
    print(f"  P1 control (b=256KiB penalty exactly 0): "
          f"{'PASS' if not viol_ctrl else 'FAIL -- ' + str(viol_ctrl[:4])}")
    print(f"  P2 no significant negative penalty:      "
          f"{'PASS' if not viol_neg else 'FAIL -- ' + str(viol_neg[:4])}")
    print(f"  P3 penalty <= (B-b)/r in every cell:     "
          f"{'PASS' if not viol_bound else 'FAIL -- ' + str(viol_bound[:4])}")

    # -------------------------------------------------------------------- P3/P4
    print("\n" + "=" * 78)
    print("PREDICTION 3 (MONOTONE in b and r) and 4 (FRACTION OF BOUND falls")
    print("  with condition severity) -- realised penalty as % of (B-b)/r")
    print("=" * 78)
    print(hdr)
    print("-" * len(hdr))
    for arm in [a for a in PACE if a in arms]:
        b, r = PACE[arm]
        if b > EV:
            continue
        cells = []
        for cond in CONDS:
            base, test = gap_by_seed(esc, cond, "none"), gap_by_seed(esc, cond, arm)
            seeds = sorted(set(base) & set(test))
            pen = (statistics.median(test[s] - base[s] for s in seeds)
                   if seeds else float("nan"))
            cells.append(f"{pen / bound(arm) * 100:9.0f}%  ")
        print(f"{arm:9s} {b:8d} {r*8/1e6:7.0f} {bound(arm):7.4f} | " + " ".join(cells))

    # ---------------------------------------------------------------------- P5
    print("\n" + "=" * 78)
    print("PREDICTION 5: pacing never improves COMPLETENESS at any (b, r)")
    print("  delivered fraction = received_evidence / evidenceChunksEmitted")
    print("=" * 78)
    print(hdr)
    print("-" * len(hdr))
    gained = []
    for arm in [a for a in PACE if a in arms]:
        b, r = PACE[arm]
        cells = []
        for cond in CONDS:
            base, test = frac_by_seed(sca, cond, "none"), frac_by_seed(sca, cond, arm)
            seeds = sorted(set(base) & set(test))
            if not seeds:
                cells.append("        n/a")
                continue
            pairs = [(base[s], test[s]) for s in seeds]
            dl = statistics.median(y - x for x, y in pairs)
            n, pos, neg, p = sign_test(pairs)
            star = "*" if p < 0.05 else " "
            cells.append(f"{dl*100:+8.2f}{star}  ")
            if dl > 0 and p < 0.05:
                gained.append((arm, cond, dl, p))
        print(f"{arm:9s} {b:8d} {r*8/1e6:7.0f} {bound(arm):7.4f} | " + " ".join(cells))
    print(f"\n  P5 no significant completeness GAIN from pacing: "
          f"{'PASS' if not gained else 'FAIL -- ' + str(gained[:4])}")

    # ------------------------------------------------------------- the maxAge axis
    print("\n" + "=" * 78)
    print("C4.2 ON THE WHOLE AXIS: does any cameraMaxAge make dispatch latency")
    print("  a safe score?  PREDICTION: latency improves monotonically as maxAge")
    print("  falls while completeness degrades monotonically -- they never agree.")
    print("=" * 78)
    for cond in CONDS:
        print(f"\n  {cond}")
        print(f"    {'maxAge':>7s} {'disp_med':>9s} {'gap_med':>9s} "
              f"{'delivered':>10s} {'stale_drop':>11s}")
        base_d = disp_by_seed(esc, cond, "none")
        base_f = frac_by_seed(sca, cond, "none")
        print(f"    {'none':>7s} "
              f"{statistics.median(base_d.values()):9.4f} "
              f"{statistics.median(gap_by_seed(esc, cond, 'none').values()):9.4f} "
              f"{statistics.median(base_f.values())*100:9.1f}% {0:11.0f}")
        for arm in sorted((a for a in AGE if a in arms), key=lambda a: AGE[a]):
            dd, ff = disp_by_seed(esc, cond, arm), frac_by_seed(sca, cond, arm)
            gg = gap_by_seed(esc, cond, arm)
            sd = [v.get("evidenceChunksStaleDropped", 0)
                  for (c, m, _), v in sca.items() if c == cond and m == arm]
            if not dd:
                continue
            print(f"    {AGE[arm]:7.1f} {statistics.median(dd.values()):9.4f} "
                  f"{statistics.median(gg.values()):9.4f} "
                  f"{statistics.median(ff.values())*100:9.1f}% "
                  f"{statistics.median(sd) if sd else 0:11.0f}")


if __name__ == "__main__":
    main()
