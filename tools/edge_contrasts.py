#!/usr/bin/env python3
"""M4 edge-cost sensitivity: matched contrasts, with an exact sign test.

Scores the prediction recorded in tools/edge_sensitivity.sh BEFORE the run:
the shift should be first-order ADDITIVE on absolute delays and the dispatch
GAP should be close to INVARIANT.

MATCHING IS THE WHOLE POINT, AND IT IS EASY TO GET WRONG
--------------------------------------------------------
Each edge arm must be compared with a baseline at the SAME frame rate, because
the camera stream is uplink background load as well as edge load: a 30 fps arm
and a 60 fps arm differ in the radio even with an identical edge. So:

    30 fps  e2bPC30 vs e2bB30   |  e4PC30 vs e4B30     (both in results_edge)
    60 fps  e2bPC, e2bEMB vs e2b in analysis/phase2         (free edge, 60 fps)
            e4PC,  e4EMB  vs e4  in analysis/escalation_vec (free edge, 60 fps)

Comparing e2bEMB (60 fps) against e2bB30 (30 fps) -- the two arms that sit
adjacent in the dispatch table -- is the trap, and it reads as a slower edge
IMPROVING the budget-miss rate.

The statistic is the per-seed median, paired across arms on the seed, and the
test is the exact two-sided sign test the rest of the project uses. Seeds in
which either arm saw no escalation are dropped, not zero-filled.

    python3 tools/edge_contrasts.py
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
EDGE_TOL = 1.0   # > 0.451 s max offset, < 1.169 s min inter-escalation spacing
FREE_TOL = 1e-2  # the unsourced edge: offset ~1.28 ms


def load_corpus(d, tol):
    """-> {(cond, arm, seed): [(alert, dispatch, nchunks, offset), ...]}"""
    out = {}
    for p in sorted(glob.glob(os.path.join(d, "*.vec"))):
        m = re.match(r"^([A-Za-z0-9_]+)-(.+)-s(\d+)\.vec$", os.path.basename(p))
        if not m:
            continue
        al, ch = parse_vec(p)
        out[(m.group(1), m.group(2), int(m.group(3)))] = pair_bursts(al, ch, tol)
    return out


def load_extract(path, tol):
    per = {}
    with gzip.open(path, "rt", newline="") as fh:
        for r in csv.DictReader(fh):
            key = (r["condition"], r["arm"], int(r["seed"]))
            al, ch = per.setdefault(key, ([], {}))
            if r["kind"] == "alarm":
                al.append((float(r["creation"]), float(r["delay"])))
            else:
                ch.setdefault(round(float(r["creation"]), 6), []).append(
                    float(r["delay"]))
    return {k: pair_bursts(al, ch, tol) for k, (al, ch) in per.items()}


def sign_test(pairs):
    """Exact two-sided sign test on (a, b) pairs; ties dropped."""
    pos = sum(1 for a, b in pairs if b > a)
    neg = sum(1 for a, b in pairs if b < a)
    n = pos + neg
    if n == 0:
        return n, pos, neg, 1.0
    k = min(pos, neg)
    p = 2.0 * sum(math.comb(n, i) for i in range(k + 1)) / (2.0 ** n)
    return n, pos, neg, min(1.0, p)


def per_seed(data, cond, arm, idx):
    """-> {seed: median of field idx over that seed's escalations}"""
    out = {}
    for (c, m, s), rows in data.items():
        if c == cond and m == arm and rows:
            out[s] = statistics.median(r[idx] for r in rows)
    return out


def gap_per_seed(data, cond, arm):
    out = {}
    for (c, m, s), rows in data.items():
        if c == cond and m == arm and rows:
            out[s] = statistics.median(r[1] - r[0] for r in rows)
    return out


def contrast(label, base, test, getter, bd, td):
    print(f"\n{label}")
    print(f"  {'condition':15s} {'n':>3s} {'base':>9s} {'test':>9s} "
          f"{'delta':>9s} {'ratio':>7s} {'+/-':>9s} {'p':>8s}")
    for cond in CONDS:
        b = getter(bd, cond, base)
        t = getter(td, cond, test)
        seeds = sorted(set(b) & set(t))
        pairs = [(b[s], t[s]) for s in seeds]
        if not pairs:
            continue
        n, pos, neg, p = sign_test(pairs)
        mb = statistics.median(x for x, _ in pairs)
        mt = statistics.median(y for _, y in pairs)
        star = "*" if p < 0.05 else " "
        print(f"  {cond:15s} {len(pairs):3d} {mb:9.4f} {mt:9.4f} "
              f"{mt - mb:9.4f} {(mt / mb if mb else float('nan')):7.2f} "
              f"{str(pos) + '/' + str(neg):>9s} {p:8.4f}{star}")


def load_edge():
    """The 960-run edge corpus, from the committed extract when present.

    Until 2026-11-16 this read ONLY simulations/pilot/results_edge, the raw
    1.5 GB corpus, which is gitignored and not redistributed -- so section
    VI-C's tables could not be regenerated outside this machine. Worse, the
    failure was SILENT: with the corpus absent, every contrast found no
    matching seeds and printed an empty table under a correct-looking
    heading. A reproduction script that prints nothing is worse than one
    that stops, so this raises instead.
    """
    ext = os.path.join(ROOT, "analysis/edge", "escalation_latencies.csv.gz")
    if os.path.exists(ext):
        return load_extract(ext, EDGE_TOL)
    raw = os.path.join(ROOT, "simulations/pilot/results_edge")
    if os.path.isdir(raw) and glob.glob(os.path.join(raw, "*.vec")):
        return load_corpus(raw, EDGE_TOL)
    raise SystemExit(
        f"edge_contrasts: no data.\n"
        f"  looked for the extract at {ext}\n"
        f"  and the raw corpus at    {raw}\n"
        f"The extract ships with the repository; if it is missing, "
        f"regenerate the corpus with tools/edge_sensitivity.sh.")


def main():
    edge = load_edge()
    ph2 = load_extract(os.path.join(ROOT, "analysis/phase2",
                                    "escalation_latencies.csv.gz"), FREE_TOL)
    gatea = load_extract(os.path.join(ROOT, "analysis/escalation_vec",
                                      "escalation_latencies.csv.gz"), FREE_TOL)

    print("=" * 78)
    print("A. IS THE ALERT SHIFT ADDITIVE?  (alert delay, per-seed median)")
    print("   predicted +21 ms at PC-class, +93 ms at embedded")
    print("=" * 78)
    contrast("A1  30 fps, waveform rung:  free edge -> PC-class (nominal +22.73 ms)",
             "e2bB30", "e2bPC30", per_seed_alert := (lambda d, c, m: per_seed(d, c, m, 0)),
             edge, edge)
    contrast("A2  30 fps, image rung:     free edge -> PC-class (nominal +22.73 ms)",
             "e4B30", "e4PC30", per_seed_alert, edge, edge)
    contrast("A3  60 fps, waveform rung:  free edge -> PC-class (nominal +22.73 ms)",
             "e2b", "e2bPC", per_seed_alert, ph2, edge)
    contrast("A4  60 fps, waveform rung:  free edge -> embedded (nominal +94.27 ms)",
             "e2b", "e2bEMB", per_seed_alert, ph2, edge)
    contrast("A5  60 fps, image rung:     free edge -> PC-class (nominal +22.73 ms)",
             "e4", "e4PC", per_seed_alert, gatea, edge)
    contrast("A6  60 fps, image rung:     free edge -> embedded (nominal +94.27 ms)",
             "e4", "e4EMB", per_seed_alert, gatea, edge)

    print("\n" + "=" * 78)
    print("B. IS THE DISPATCH GAP INVARIANT?  (per-seed median gap)")
    print("   predicted: invariant, because alert and evidence shift together")
    print("=" * 78)
    contrast("B1  30 fps, waveform rung:  free edge -> PC-class",
             "e2bB30", "e2bPC30", gap_per_seed, edge, edge)
    contrast("B2  30 fps, image rung:     free edge -> PC-class",
             "e4B30", "e4PC30", gap_per_seed, edge, edge)
    contrast("B3  60 fps, waveform rung:  free edge -> PC-class",
             "e2b", "e2bPC", gap_per_seed, ph2, edge)
    contrast("B4  60 fps, waveform rung:  free edge -> embedded",
             "e2b", "e2bEMB", gap_per_seed, ph2, edge)
    contrast("B5  60 fps, image rung:     free edge -> PC-class",
             "e4", "e4PC", gap_per_seed, gatea, edge)
    contrast("B6  60 fps, image rung:     free edge -> embedded",
             "e4", "e4EMB", gap_per_seed, gatea, edge)

    print("\n" + "=" * 78)
    print("C. DOES 'VERIFY FROM THE WAVEFORM, NOT THE IMAGE' SURVIVE THE")
    print("   EDGE COST?  (E2' 14.4 kB -> E4 138 kB, within one edge setting)")
    print("=" * 78)
    contrast("C1  free edge, 60 fps   (the published Phase 2 / Gate A pair)",
             "e2b", "e4", gap_per_seed, ph2, gatea)
    contrast("C2  free edge, 30 fps", "e2bB30", "e4B30", gap_per_seed, edge, edge)
    contrast("C3  PC-class, 30 fps", "e2bPC30", "e4PC30", gap_per_seed, edge, edge)
    contrast("C4  PC-class, 60 fps", "e2bPC", "e4PC", gap_per_seed, edge, edge)
    contrast("C5  embedded, 60 fps", "e2bEMB", "e4EMB", gap_per_seed, edge, edge)


if __name__ == "__main__":
    main()
