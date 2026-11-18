#!/usr/bin/env python3
"""Check each indoor extract against its raw corpus, cell by cell.

WHY THIS EXISTS
  The paper's Reproducibility section claims every table regenerates from
  committed extracts alone, and says the claim was checked directly for the
  gate sweep -- the analysis tool reads either the raw corpus or the extract
  and the two produce identical output. The indoor extracts are new, so they
  need the same check, by the same standard, before that sentence covers them.

  This matters more than it sounds. An extract is a lossy rewrite of a corpus
  that is then deleted. If it drops a cell, nothing afterwards can tell: the
  tables still compute, still look plausible, and are quietly wrong. This
  project has already shipped one silently-wrong table, and the tell was that
  a number looked too clean.

WHAT IS COMPARED
  Not file counts or row counts -- those can match while the values differ.
  The comparison is the published statistics themselves: per (condition, arm),
  the completion counts and the median alert, gap and dispatch, computed from
  the raw .vec corpus and from the .csv.gz, and required to agree to 1e-9.

    python3 -I tools/verify_indoor_extract.py <results_dir> <extract.csv.gz>
"""
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import completion                                            # noqa: E402
from analyze_room_ladder import ARM_ORDER, EXPECTED, load_corpus  # noqa: E402
from dispatch_times import pair_bursts                        # noqa: E402

TOL = 1e-2
EPS = 1e-9


def stats(per, horizon):
    """-> {(cond, arm): (complete, lost, med_alert, med_gap, med_dispatch)}"""
    conds = sorted({c for c, _, _ in per})
    for c in conds:
        completion.HORIZON[c] = horizon
    out = {}
    for c in conds:
        for arm in ARM_ORDER:
            exp = EXPECTED.get(arm)
            al, ga, di = [], [], []
            seen = False
            for (cc, aa, _), (alarms, ch) in per.items():
                if cc != c or aa != arm:
                    continue
                seen = True
                full = ch if exp is None else {
                    t: v for t, v in ch.items() if len(v) >= exp}
                for r in pair_bursts(alarms, full, TOL):
                    al.append(r[0])
                    if r[2] > 0 or exp is None:
                        ga.append(r[1] - r[0])
                        di.append(r[1])
            if not seen:
                continue
            comp, _, lost, _ = completion.classify(per, arm, c, exp)
            med = lambda xs: statistics.median(xs) if xs else float("nan")  # noqa: E731
            out[(c, arm)] = (comp, lost, med(al), med(ga), med(di))
    return out


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    raw_dir, extract = sys.argv[1], sys.argv[2]
    a = stats(load_corpus(raw_dir), 300.0)
    b = stats(load_corpus(extract), 300.0)

    if set(a) != set(b):
        only_a, only_b = sorted(set(a) - set(b)), sorted(set(b) - set(a))
        print(f"FAIL: cell sets differ.\n  only in corpus:  {only_a}"
              f"\n  only in extract: {only_b}")
        sys.exit(1)

    names = ["complete", "lost", "alert", "gap", "dispatch"]
    bad = 0
    for k in sorted(a):
        for name, x, y in zip(names, a[k], b[k]):
            same = (x != x and y != y) or abs(x - y) <= EPS
            if not same:
                bad += 1
                print(f"FAIL {k[0]}/{k[1]} {name}: corpus {x!r} "
                      f"extract {y!r}")
    print(f"{len(a)} cells x {len(names)} statistics compared")
    if bad:
        print(f"MISMATCHES: {bad}")
        sys.exit(1)
    print(f"OK: {raw_dir} and {extract} agree to {EPS:g}")


if __name__ == "__main__":
    main()
