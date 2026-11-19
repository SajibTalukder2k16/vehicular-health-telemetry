#!/usr/bin/env python3
"""Is the WLAN/LTE indoor difference real, or is it 35 bursts of noise?

WHY THIS SCRIPT EXISTS
  The indoor comparison grid produces two differences that are easy to quote
  and easy to overstate:

    completion at E4   WLAN 35/35 (100 %)   vs   LTE 32/35 (91.4 %)
    median gap at E4   WLAN 0.0350 s        vs   LTE 0.0680 s

  Three lost bursts out of 35 is exactly the size of difference that a
  two-sided exact test refuses to call. This project has already published a
  wrong significance claim once -- two edge outliers were described as
  non-significant when one of them was not (p = 0.0066) -- so the tests go in
  the repository next to the numbers rather than being done once by hand.

WHAT IS TESTED, AND THE LIMITS OF IT
  * COMPLETION: Fisher's exact test, two-sided, on the 2x2 of
    complete/lost. Exact, no approximation, no scipy.
  * GAP: Mann-Whitney U on PER-SEED MEDIAN gaps, two-sided, normal
    approximation with a tie correction and a continuity correction. 29-30
    seeds per arm is comfortably inside where that approximation is sound.

  The gap test is UNPAIRED even though both corpora use seed sets 0-29. The
  seeds index different networks -- one an 802.11 room, the other an LTE
  corridor -- so the same seed does not produce a matched pair of anything,
  and pairing it would be a pretence of precision. Unpaired is the honest
  choice and the weaker one.

    python3 -I tools/compare_backhaul.py <corpusA> <condA> <corpusB> <condB>
                                         [--arm e4]
"""
import argparse
import math
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import completion                                      # noqa: E402
from analyze_room_ladder import EXPECTED, load_corpus   # noqa: E402
from dispatch_times import pair_bursts                  # noqa: E402

TOL = 1e-2


def fisher_exact(a, b, c, d):
    """Two-sided Fisher's exact test on [[a, b], [c, d]] -> p.

    Summing the hypergeometric probability of every table with the same
    margins that is no more probable than the observed one. That is the
    conventional two-sided definition and it needs no normal approximation,
    which matters here because one cell is zero.
    """
    def pr(x):
        return (math.comb(a + b, x) * math.comb(c + d, a + c - x)
                / math.comb(a + b + c + d, a + c))
    lo = max(0, a + c - (c + d))
    hi = min(a + b, a + c)
    obs = pr(a)
    return min(1.0, sum(pr(x) for x in range(lo, hi + 1)
                        if pr(x) <= obs * (1 + 1e-9)))


def mann_whitney(xs, ys):
    """Two-sided Mann-Whitney U -> (U, z, p), tie-corrected, with continuity."""
    n1, n2 = len(xs), len(ys)
    both = sorted([(v, 0) for v in xs] + [(v, 1) for v in ys])
    ranks = [0.0] * len(both)
    i = 0
    ties = 0
    while i < len(both):
        j = i
        while j + 1 < len(both) and both[j + 1][0] == both[i][0]:
            j += 1
        r = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[k] = r
        t = j - i + 1
        ties += t ** 3 - t
        i = j + 1
    r1 = sum(r for r, (_, g) in zip(ranks, both) if g == 0)
    u1 = r1 - n1 * (n1 + 1) / 2.0
    u = min(u1, n1 * n2 - u1)
    n = n1 + n2
    mu = n1 * n2 / 2.0
    var = n1 * n2 / 12.0 * ((n + 1) - ties / (n * (n - 1.0)))
    if var <= 0:
        return u, float("nan"), 1.0
    z = (abs(u - mu) - 0.5) / math.sqrt(var)
    # STABLE TAIL. 2*(1 - Phi(z)) built from erf() cancels catastrophically
    # once z is large: at z = 10.08 it returned exactly 0.0, which was then
    # quoted in a table as "2e-16" -- a number the script could not produce.
    # The two-sided tail is erfc(z/sqrt2) identically, and erfc is accurate
    # to ~1e-300. At z = 10.08 that is 6.47e-24. Raised by external review.
    p = math.erfc(z / math.sqrt(2.0))
    return u, z, min(1.0, p)


def seed_completion(per, cond, arm, exp):
    """-> [per-seed completion fraction], one value per run that has bursts.

    WHY THIS EXISTS. Fisher's exact test on pooled escalations assumes every
    escalation is an independent observation. They are not: escalations from
    one run share a mobility trace, a radio realisation and a background-load
    draw, so a run that is having a bad time contributes several correlated
    failures. Pooling therefore overstates the effective sample size and the
    pooled p-value is anti-conservative.

    Clustering at the run is the natural unit, since the seed is what is
    independent by construction. The per-seed fractions then go through the
    same unpaired rank test as the gap, which makes no independence claim
    about escalations within a run. Raised by external review.
    """
    out = []
    for (c, a, s), (al, ch) in per.items():
        if c != cond or a != arm or not ch:
            continue
        full = [t for t, v in ch.items() if len(v) >= exp]
        out.append(len(full) / len(ch))
    return out


def seed_median_gaps(per, cond, arm):
    exp = EXPECTED[arm]
    out = []
    for (c, a, s), (alarms, ch) in sorted(per.items()):
        if c != cond or a != arm:
            continue
        full = ch if exp is None else {t: v for t, v in ch.items()
                                       if len(v) >= exp}
        g = [r[1] - r[0] for r in pair_bursts(alarms, full, TOL) if r[2] > 0]
        if g:
            out.append(statistics.median(g))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus_a"); ap.add_argument("cond_a")
    ap.add_argument("corpus_b"); ap.add_argument("cond_b")
    ap.add_argument("--arm", default="e4")
    ap.add_argument("--horizon-a", type=float, default=None,
                    help="sim-time-limit of corpus A; default: the condition's "
                         "own entry in completion.HORIZON, else 300 s")
    ap.add_argument("--horizon-b", type=float, default=None,
                    help="likewise for corpus B")
    a = ap.parse_args()

    pa, pb = load_corpus(a.corpus_a), load_corpus(a.corpus_b)

    # ONE HORIZON FOR BOTH INPUTS WAS A BUG, and a silent one. The censoring
    # test is `creation + t_obs > horizon`, so forcing 300 s onto a condition
    # that ran to 680 s reclassifies real losses as censored and drops them
    # from the denominator. On CondOutage at E4 that turned 37/72 into 37/43
    # and Fisher's p from 0.000882 into 1.000 -- it would have erased the one
    # completion effect in the decomposition. Raised by external review.
    #
    # The four cellular conditions carry their own sim-time-limits in
    # completion.HORIZON (320/1369/1369/680 s); the indoor configurations run
    # 300 s and are not in that table. So the default is now: use the
    # condition's own entry when it has one, else 300 s. --horizon-a/-b
    # override per input, never jointly.
    INDOOR_DEFAULT = 300.0
    hz = {}
    for cond, override in ((a.cond_a, a.horizon_a), (a.cond_b, a.horizon_b)):
        if override is not None:
            completion.HORIZON[cond] = override
        elif cond not in completion.HORIZON:
            completion.HORIZON[cond] = INDOOR_DEFAULT
        hz[cond] = completion.HORIZON[cond]

    print(f"arm {a.arm}\n")
    print(f"  A = {a.cond_a}  ({a.corpus_a})  horizon {hz[a.cond_a]:g} s")
    print(f"  B = {a.cond_b}  ({a.corpus_b})  horizon {hz[a.cond_b]:g} s\n")

    ca, _, la, _ = completion.classify(pa, a.arm, a.cond_a, EXPECTED[a.arm])
    cb, _, lb, _ = completion.classify(pb, a.arm, a.cond_b, EXPECTED[a.arm])
    p = fisher_exact(ca, la, cb, lb)
    print("COMPLETION   Fisher's exact, two-sided")
    print(f"  A  {ca:3d} complete / {la:3d} lost   "
          f"{100*ca/(ca+la) if ca+la else float('nan'):.1f}%")
    print(f"  B  {cb:3d} complete / {lb:3d} lost   "
          f"{100*cb/(cb+lb) if cb+lb else float('nan'):.1f}%")
    print(f"  p = {p:.3g}   -> "
          f"{'SIGNIFICANT at 0.05' if p < 0.05 else 'NOT significant at 0.05'}")
    print("  (pools escalations; those within a run are correlated, so this")
    print("   p-value is anti-conservative -- see the clustered test below)")

    sa = seed_completion(pa, a.cond_a, a.arm, EXPECTED[a.arm])
    sb = seed_completion(pb, a.cond_b, a.arm, EXPECTED[a.arm])
    print("\nCOMPLETION, CLUSTERED BY RUN   Mann-Whitney U on per-seed "
          "completion fractions")
    print(f"  A  n={len(sa):3d} runs  mean fraction "
          f"{sum(sa)/len(sa) if sa else float('nan'):.3f}")
    print(f"  B  n={len(sb):3d} runs  mean fraction "
          f"{sum(sb)/len(sb) if sb else float('nan'):.3f}")
    if len(sa) >= 2 and len(sb) >= 2:
        _, _, pc = mann_whitney(sa, sb)
        print(f"  p = {pc:.4g}   -> "
              f"{'SIGNIFICANT at 0.05' if pc < 0.05 else 'NOT significant at 0.05'}")

    ga, gb = seed_median_gaps(pa, a.cond_a, a.arm), seed_median_gaps(pb, a.cond_b, a.arm)
    print("\nGAP          Mann-Whitney U on per-seed medians, two-sided, unpaired")
    print(f"  A  n={len(ga):3d}  median {statistics.median(ga):.4f} s")
    print(f"  B  n={len(gb):3d}  median {statistics.median(gb):.4f} s")
    if len(ga) >= 2 and len(gb) >= 2:
        u, z, pg = mann_whitney(ga, gb)
        print(f"  U = {u:.1f}  z = {z:.3f}  p = {pg:.3g}   -> "
              f"{'SIGNIFICANT at 0.05' if pg < 0.05 else 'NOT significant at 0.05'}")
        print(f"  ratio of medians B/A = "
              f"{statistics.median(gb)/statistics.median(ga):.2f}x")


if __name__ == "__main__":
    main()
