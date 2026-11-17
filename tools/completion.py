#!/usr/bin/env python3
"""Readiness under a FULL-EVIDENCE policy: completion, censoring and loss.

WHY THIS EXISTS
  Every dispatch number this project has published was the maximum end-to-end
  delay over the chunks of a burst that ARRIVED. Under the response policy the
  paper actually models -- the server verifies before dispatching -- that is
  not readiness. If one chunk of the burst never arrives, the receiver never
  has what the policy requires, and the max over the survivors is a number
  about a burst that was never ready.

  An external review raised this on 2026-11-16. It is correct, and it moves
  results, so this tool exists to measure the thing properly instead of
  arguing about it.

THE THREE-WAY CLASSIFICATION
  A burst at rung R is expected to carry EXPECTED[R] chunks (1 / 3 / 41 / 99,
  read off the data as the modal count per rung and consistent with the rung's
  byte size). For each escalation:

    COMPLETE  every expected chunk arrived -> readiness is well defined, and
              equals max(alert, slowest chunk)
    CENSORED  incomplete AND it is the LAST escalation of its run -> the
              simulation horizon cut the burst off in flight. This is a
              measurement boundary, not a system failure, and it must not be
              counted as either a success or a loss.
    LOST      incomplete and NOT last -> the run continued past it, so the
              missing chunks are genuinely missing.

  The discriminator is sound because horizon truncation can affect at most one
  burst per run, which is the argument VERIFICATION_FRONTIER.md section 4 uses
  for the aggregate deficit. Here it is applied per escalation.

WHAT TO REPORT, AND WHY BOTH
  Neither number alone is honest, and this tool prints both:

    completion rate   COMPLETE / (COMPLETE + LOST), censored excluded.
                      For a full-evidence policy this is the primary result:
                      an escalation that never completes never becomes ready.

    latency | complete   median gap among COMPLETE escalations only. This is
                      SMALLER than the previously published figure, because
                      conditioning on completion removes the slow bursts --
                      it is survivorship bias, and must be labelled as
                      conditional wherever it appears.

  The previously published figure was neither: a median over a mixture in
  which incomplete bursts contributed an understated value.

    python3 -I tools/completion.py [extract.csv.gz ...]
"""
import collections
import csv
import gzip
import math
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dispatch_times import pair_bursts  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONDS = ["CondHealthy", "CondCongested", "CondTransient", "CondOutage"]

# chunks per burst, by rung. Modal received count per rung in the corpus,
# consistent with each rung's byte size; printed below so it can be checked.
EXPECTED = {"e1": 1, "e2": 3, "e2b": 11, "e3": 41, "e4": 99}
BYTES = {"e1": 512.0, "e2": 3584.0, "e2b": 14400.0,
         "e3": 57344.0, "e4": 138000.0}
TOL = 1e-2


def load(path):
    per = collections.defaultdict(lambda: ([], {}))
    with gzip.open(path, "rt", newline="") as fh:
        for r in csv.DictReader(fh):
            k = (r["condition"], r["arm"], r["seed"])
            al, ch = per[k]
            if r["kind"] == "alarm":
                al.append((float(r["creation"]), float(r["delay"])))
            else:
                ch.setdefault(round(float(r["creation"]), 6), []).append(
                    float(r["delay"]))
    return per


def classify(per, arm, cond, exp):
    """-> (complete, censored, lost, [gap among complete])

    `exp` is the expected chunk count, passed in explicitly. An earlier
    version looked it up from a module global that --expect mutated into a
    defaultdict; that was twice wrong (.get() does not fire the factory, and
    the global made the lookup depend on call order) and it silently reported
    the wrong arm's completion. Passing the number in removes the class of
    bug, not just the instance.
    """
    comp = cens = lost = 0
    gaps = []
    for (c, a, s), (al, ch) in per.items():
        if c != cond or a != arm or not ch:
            continue
        keys = sorted(ch)
        last = keys[-1]
        full = {}
        for t in keys:
            if exp is None or len(ch[t]) >= exp:
                comp += 1
                full[t] = ch[t]
            elif t == last:
                cens += 1
            else:
                lost += 1
        for r in pair_bursts(al, full, TOL):
            if r[2] > 0:
                gaps.append(r[1] - r[0])
    return comp, cens, lost, gaps


def fit(xs, ys):
    lx = [math.log10(x) for x in xs]
    ly = [math.log10(y) for y in ys]
    n = len(lx)
    mx, my = sum(lx) / n, sum(ly) / n
    sxx = sum((a - mx) ** 2 for a in lx)
    m = sum((a - mx) * (b - my) for a, b in zip(lx, ly)) / sxx
    c = my - m * mx
    ss = sum((b - (m * a + c)) ** 2 for a, b in zip(lx, ly))
    st = sum((b - my) ** 2 for b in ly)
    return m, (1 - ss / st if st else float("nan"))


def main():
    # The gate corpus names its arms by POLICY (none, p64k1, dp05...) and runs
    # every one of them at E4, so the rung cannot be read off the arm name.
    # --expect N sets the expected chunk count for all arms.
    argv = sys.argv[1:]
    force = None
    if "--expect" in argv:
        i = argv.index("--expect")
        force = int(argv[i + 1])
        del argv[i:i + 2]
    paths = argv or [
        os.path.join(ROOT, "analysis/escalation_vec/escalation_latencies.csv.gz")]
    for path in paths:
        per = load(path)
        allarms = {a for (_, a, _) in per}
        arms = sorted(allarms if force else allarms & set(EXPECTED))
        print("=" * 76)
        print(f"corpus: {path}")
        print("=" * 76)
        print(f"{'arm':4s} {'condition':14s} {'esc':>5s} {'compl':>6s} "
              f"{'cens':>5s} {'lost':>5s} {'completion':>11s} "
              f"{'gap|complete':>13s}")
        print("-" * 76)
        summary = {}
        for arm in arms:
            for cond in CONDS:
                exp = force if force else EXPECTED[arm]
                comp, cens, lost, gaps = classify(
                    per, arm, cond, exp)
                n = comp + cens + lost
                if not n:
                    continue
                denom = comp + lost
                rate = comp / denom if denom else float("nan")
                med = statistics.median(gaps) if gaps else float("nan")
                summary[(arm, cond)] = (rate, med)
                print(f"{arm:4s} {cond:14s} {n:5d} {comp:6d} {cens:5d} "
                      f"{lost:5d} {100*rate:10.1f}% {med:13.4f}")
            print()

        print("COMPLETION RATE is the primary figure for a full-evidence "
              "policy;\nGAP|COMPLETE is conditional on completion and is "
              "therefore optimistic.\n")

        shaped = [a for a in arms if a in BYTES and a != "e1"]
        if len(shaped) >= 3:
            print(f"{'condition':15s} {'slope':>7s} {'R2':>7s}   "
                  f"(log-log fit of gap|complete on bytes)")
            for cond in CONDS:
                pts = [(BYTES[a], summary[(a, cond)][1]) for a in shaped
                       if (a, cond) in summary
                       and summary[(a, cond)][1] == summary[(a, cond)][1]]
                if len(pts) >= 3:
                    m, r2 = fit([p[0] for p in pts], [p[1] for p in pts])
                    print(f"{cond:15s} {m:7.2f} {r2:7.3f}")
            print(f"\n  fitted on {len(shaped)} payload sizes "
                  f"({', '.join(shaped)}) -- too few to exclude a knee; "
                  f"the\n  claim this supports is proportionality over the "
                  f"sizes tested, nothing more.")


if __name__ == "__main__":
    main()
