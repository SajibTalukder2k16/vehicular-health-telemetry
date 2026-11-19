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

  Trap 1: order must be fixed BEFORE completeness is filtered, or the test
  silently becomes "first COMPLETED escalation vs later completed ones". See
  split()'s docstring; seed 54 of the 120-seed corpus is a worked example --
  its first escalation delivers 97 of 99 chunks, so the old code promoted its
  second escalation to "first".

  Trap 2: the WLAN arm is the control and must come out flat. If it does not,
  the effect is not about grant acquisition and the mechanism is wrong.

    python3 -I tools/grant_warmup.py <corpus> <condition> [--arm e4]
"""
import argparse
import math
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze_room_ladder import EXPECTED, load_corpus     # noqa: E402
from compare_backhaul import mann_whitney                 # noqa: E402
from dispatch_times import pair_bursts                    # noqa: E402

TOL = 1e-2


def split(per, cond, arm):
    """-> (first gaps, later gaps, [(first, median later) per run])

    ORDER IS DETERMINED BEFORE COMPLETENESS IS FILTERED. An earlier version
    filtered to complete bursts and then took index 0, so a run whose first
    escalation was incomplete promoted its SECOND to "first" -- comparing the
    first COMPLETED escalation against later completed ones, which is a
    different and much weaker question. An external review found a real
    misclassification of this kind in seed 54.

    A run whose first escalation is incomplete therefore contributes nothing
    to `first` (an incomplete burst has no readiness instant and so no gap)
    while its later complete bursts still contribute to `later`.

    The third return value pairs, within each run that has both, the first
    gap against the median of its later gaps. First and later observations
    from one run share a trajectory, so the unpaired test overstates its
    sample size; the paired sign test on that list does not.
    """
    exp = EXPECTED[arm]
    first, later, pairs = [], [], []
    for (c, a, s), (al, ch) in per.items():
        if c != cond or a != arm:
            continue
        al_sorted = sorted(al)
        # index over EVERY escalation, complete or not
        rows = sorted(zip((cr for cr, _ in al_sorted),
                          pair_bursts(al_sorted, ch, TOL)))
        f, l = None, []
        for i, (_, r) in enumerate(rows):
            complete = exp is None or r[2] >= exp
            if not complete:
                continue
            gap = r[1] - r[0]
            if i == 0:
                f = gap
                first.append(gap)
            else:
                l.append(gap)
                later.append(gap)
        if f is not None and l:
            pairs.append((f, statistics.median(l)))
    return first, later, pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus")
    ap.add_argument("condition")
    ap.add_argument("--arm", default="e4")
    a = ap.parse_args()

    per = load_corpus(a.corpus)
    if not per:
        sys.exit(f"no parseable output in {a.corpus}")
    first, later, pairs = split(per, a.condition, a.arm)
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
    print(f"  unpaired  U = {u:.1f}  z = {z:.3f}  p = {p:.4g}  ->  "
          f"{'SIGNIFICANT' if p < 0.05 else 'not significant'} at 0.05")
    print("            (observations from one run are dependent, so this")
    print("             overstates the sample size -- see the paired test)")
    print(f"  ratio first/later = {ratio:.2f}x")
    if len(pairs) >= 2:
        nz = [(f, l) for f, l in pairs if abs(f - l) > 1e-12]
        n = len(nz)
        pos = sum(1 for f, l in nz if f > l)
        k = min(pos, n - pos)
        pp = min(1.0, 2.0 * sum(math.comb(n, i)
                                for i in range(k + 1)) / 2.0 ** n) if n else 1.0
        print(f"  paired, within run: {n} runs with both, {pos} slower first, "
              f"exact sign test p = {pp:.4g}  ->  "
              f"{'SIGNIFICANT' if pp < 0.05 else 'not significant'} at 0.05")
    else:
        print(f"  paired, within run: only {len(pairs)} run(s) have both")


if __name__ == "__main__":
    main()
