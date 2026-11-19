#!/usr/bin/env python3
"""Do the first 30 seeds of a 120-seed corpus reproduce the published cell?

WHY THIS MUST RUN FIRST
  `--seed-set=s` is the same draw whatever else the campaign contains, so
  seeds 0-29 of a 120-seed run are the SAME RUNS as the published 30-seed
  corpus. They must therefore give identical statistics. If they do not,
  something other than the seed count changed -- a default, an override, an
  ini edit -- and no 120-seed number from that corpus is interpretable.

  This is the check that would have caught the camera-payload mismatch of
  docs/INDOOR_BACKHAUL_RESULT.md section 8b at the time rather than at review.

  It is deliberately a comparison against the PUBLISHED numbers, typed in
  below from the result documents, not against a recomputation of the old
  corpus. A recomputation shares any bug the analysis has; the published
  figures are what the paper actually claims.

    python3 -I tools/verify_power120.py <results_dir> <cell>

  where <cell> is one of the keys in EXPECTED.
"""
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import completion                                            # noqa: E402
from analyze_room_ladder import EXPECTED as CHUNKS, load_corpus  # noqa: E402
from dispatch_times import pair_bursts                        # noqa: E402

TOL = 1e-2

# (condition, horizon, expected complete, expected lost, pooled gap median,
#  per-seed gap median) at E4, as published.
EXPECTED = {
    "indoor_lte":  ("CondIndoorLte",   300.0, 32,  3, 0.0680, 0.1320),
    "indoor_lte_4k": ("CondIndoorLte", 300.0, 31,  4, 0.0680, None),
    "room5g":      ("RoomMatched5GHz", 300.0, 35,  0, 0.0350, 0.0349),
    "healthy":     ("CondHealthy",     320.0, 31,  6, 0.1920, 0.2035),
    "outage":      ("CondOutage",      680.0, 37, 35, 0.4020, 0.4455),
}


def at_e4(per, cond, horizon, seed_max):
    completion.HORIZON[cond] = horizon
    sub = {k: v for k, v in per.items()
           if k[0] == cond and k[1] == "e4" and int(k[2]) <= seed_max}
    comp, cens, lost, _ = completion.classify(sub, "e4", cond, CHUNKS["e4"])
    pooled, per_seed = [], []
    for (c, a, s), (al, ch) in sub.items():
        full = {t: v for t, v in ch.items() if len(v) >= CHUNKS["e4"]}
        g = [r[1] - r[0] for r in pair_bursts(al, full, TOL) if r[2] > 0]
        pooled += g
        if g:
            per_seed.append(statistics.median(g))
    return (comp, lost,
            statistics.median(pooled) if pooled else float("nan"),
            statistics.median(per_seed) if per_seed else float("nan"),
            len(sub))


def main():
    if len(sys.argv) != 3 or sys.argv[2] not in EXPECTED:
        sys.exit(__doc__ + "\ncells: " + ", ".join(EXPECTED))
    d, key = sys.argv[1], sys.argv[2]
    cond, hz, ec, el, eg, es = EXPECTED[key]
    per = load_corpus(d)
    if not per:
        sys.exit(f"no parseable output in {d}")

    comp, lost, gp, gs, nruns = at_e4(per, cond, hz, 29)
    allc, alll, agp, ags, anr = at_e4(per, cond, hz, 10**9)

    print(f"{key}: {cond} at E4, horizon {hz:g} s")
    print(f"  seeds 0-29  : {nruns} runs, {comp} complete / {lost} lost, "
          f"pooled {gp:.4f}, per-seed {gs:.4f}")
    print(f"  published   : {ec} complete / {el} lost, pooled {eg:.4f}, "
          f"per-seed {'n/a' if es is None else format(es, '.4f')}")
    print(f"  all seeds   : {anr} runs, {allc} complete / {alll} lost, "
          f"pooled {agp:.4f}, per-seed {ags:.4f}")

    # The published figures are rounded to four decimals, so comparing the
    # full float against them at 1e-9 fails on the rounding and not on the
    # data -- it did, on a corpus that was in fact correct. Compare at the
    # precision actually published.
    PREC = 5e-5
    bad = []
    if (comp, lost) != (ec, el):
        bad.append(f"completion {comp}/{lost} vs published {ec}/{el}")
    if abs(gp - eg) > PREC:
        bad.append(f"pooled gap {gp:.6f} vs published {eg:.4f}")
    if es is not None and abs(gs - es) > PREC:
        bad.append(f"per-seed gap {gs:.6f} vs published {es:.4f}")
    if bad:
        print("\nFAIL -- seeds 0-29 do not reproduce the published cell:")
        for b in bad:
            print("  " + b)
        print("Something other than the seed count changed. Do not use this "
              "corpus until it is explained.")
        sys.exit(1)
    print("\nOK: seeds 0-29 reproduce the published cell to the\n    precision published (4 dp).")


if __name__ == "__main__":
    main()
