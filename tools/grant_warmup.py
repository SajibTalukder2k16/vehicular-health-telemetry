#!/usr/bin/env python3
"""Is a run's FIRST escalation slower than the ones after it?

THE QUESTION
  On indoor LTE the pooled median gap (0.0680 s) and the median of per-seed
  medians (0.1320 s) differ twofold, while on the indoor WLAN they agree to
  four decimals. The divergence has a candidate cause: a run's first
  escalation pays for acquiring an uplink grant, later ones reuse an active
  one. Pooling then over-weights the warm bursts and the per-seed median
  over-weights the cold ones.

  At 30 seeds this was 2.10x at p = 0.262 -- suggestive, unresolvable, and
  recorded as an open question rather than claimed. This tool is the test, so
  that it can be re-run at any seed count instead of being redone by hand.

WHAT IS COMPARED, AND THE TWO TRAPS
  Escalations are ordered by their CREATION time within a run, and index 0 is
  the run's first. Only COMPLETE bursts count: an incomplete burst has no
  readiness instant, so its "gap" is a maximum over whichever chunks happened
  to arrive and is not a readiness time at all.

  Trap 1: a run contributing only one escalation contributes only a cold one.
  That is why the pooled and per-seed summaries disagree in the first place,
  so the test must not be built on either -- it compares first against later
  directly, which is why runs with a single escalation contribute to the
  `first` group alone and bias nothing.

  Trap 2: the WLAN arm is the control and must come out flat. If it does not,
  the effect is not about grant acquisition and the mechanism is wrong.

    python3 -I tools/grant_warmup.py <corpus> <condition> [--arm e4]
"""
import argparse
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze_room_ladder import EXPECTED, load_corpus     # noqa: E402
from compare_backhaul import mann_whitney                 # noqa: E402
from dispatch_times import pair_bursts                    # noqa: E402

TOL = 1e-2


def split(per, cond, arm):
    """-> (first-escalation gaps, later-escalation gaps)"""
    exp = EXPECTED[arm]
    first, later = [], []
    for (c, a, s), (al, ch) in per.items():
        if c != cond or a != arm:
            continue
        full = ch if exp is None else {t: v for t, v in ch.items()
                                       if len(v) >= exp}
        al_sorted = sorted(al)
        rows = [(cr, r) for (cr, _), r in
                zip(al_sorted, pair_bursts(al_sorted, full, TOL)) if r[2] > 0]
        rows.sort()
        for i, (_, r) in enumerate(rows):
            (first if i == 0 else later).append(r[1] - r[0])
    return first, later


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus")
    ap.add_argument("condition")
    ap.add_argument("--arm", default="e4")
    a = ap.parse_args()

    per = load_corpus(a.corpus)
    if not per:
        sys.exit(f"no parseable output in {a.corpus}")
    first, later = split(per, a.condition, a.arm)
    if not first:
        sys.exit(f"no complete bursts for {a.condition}/{a.arm}")

    print(f"{a.condition} at {a.arm}: first escalation of a run vs the rest")
    print(f"  first  n={len(first):4d}  median {statistics.median(first):.4f} s")
    if not later:
        print("  later  n=   0  -- no run produced a second complete burst")
        return
    print(f"  later  n={len(later):4d}  median {statistics.median(later):.4f} s")
    u, z, p = mann_whitney(first, later)
    ratio = statistics.median(first) / statistics.median(later)
    print(f"  U = {u:.1f}  z = {z:.3f}  p = {p:.4g}  ->  "
          f"{'SIGNIFICANT at 0.05' if p < 0.05 else 'NOT significant at 0.05'}")
    print(f"  ratio first/later = {ratio:.2f}x")


if __name__ == "__main__":
    main()
