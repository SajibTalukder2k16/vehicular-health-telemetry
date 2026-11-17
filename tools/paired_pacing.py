#!/usr/bin/env python3
"""Does pacing ever make an individual escalation ready sooner?

THE QUESTION, AND WHY THE DETAILS DECIDE THE ANSWER
  The propositions bound a cell MEDIAN. They say nothing about any single
  escalation, and the paper needs a measurement of that to avoid being read as
  claiming more than it shows. Two choices decide the number, and both were
  got wrong before an external review caught them.

  1. WHICH ESCALATIONS COUNT. A pair is only usable when the evidence
     completed in BOTH arms, because only then do two readiness instants
     exist. An earlier version paired every matched trigger, which admitted
     bursts whose "gap" was a maximum over the chunks that happened to arrive
     -- not a readiness time at all. That inflated the denominator from 192 to
     381.

  2. WHICH QUANTITY IS COMPARED. "Completes sooner" is about the readiness
     instant, so the comparison is on DISPATCH. Comparing the gap
     (dispatch - alert) answers a different question, because the alert's own
     arrival also moves between arms. On this corpus the two differ: 27 of 192
     on dispatch, 23 of 192 on gap.

  Both are reported below so the distinction stays visible.

    python3 -I tools/paired_pacing.py [arm ...]      default: p64k1 p16k1
"""
import collections
import csv
import gzip
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dispatch_times import pair_bursts  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONDS = ["CondHealthy", "CondCongested", "CondTransient", "CondOutage"]
EXPECTED_E4 = 99
TOL = 1e-2


def load(path):
    per = collections.defaultdict(lambda: ([], {}))
    with gzip.open(path, "rt", newline="") as fh:
        for r in csv.DictReader(fh):
            al, ch = per[(r["condition"], r["arm"], r["seed"])]
            if r["kind"] == "alarm":
                al.append((float(r["creation"]), float(r["delay"])))
            else:
                ch.setdefault(round(float(r["creation"]), 6), []).append(
                    float(r["delay"]))
    return per


def events(per, cond, arm):
    """-> {seed: {creation: {alert, dispatch, chunks}}}"""
    out = {}
    for (c, a, s), (al, ch) in per.items():
        if c != cond or a != arm:
            continue
        d = {}
        for (cr, _), r in zip(sorted(al), pair_bursts(sorted(al), ch, TOL)):
            d[round(cr, 6)] = {"alert": r[0], "dispatch": r[1], "chunks": r[2]}
        out[s] = d
    return out


def main():
    arms = sys.argv[1:] or ["p64k1", "p16k1"]
    per = load(os.path.join(ROOT, "analysis/gate/escalation_latencies.csv.gz"))
    for arm in arms:
        print(f"\n{arm} vs no gate")
        print(f"  {'condition':14s} {'matched':>8s} {'both complete':>14s} "
              f"{'sooner (disp)':>14s} {'sooner (gap)':>13s}")
        tm = tv = td = tg = 0
        for cond in CONDS:
            b, t = events(per, cond, "none"), events(per, cond, arm)
            m = v = sd = sg = 0
            for s in b.keys() & t.keys():
                for cr in b[s].keys() & t[s].keys():
                    m += 1
                    B, T = b[s][cr], t[s][cr]
                    if B["chunks"] >= EXPECTED_E4 and T["chunks"] >= EXPECTED_E4:
                        v += 1
                        sd += T["dispatch"] < B["dispatch"] - 1e-12
                        sg += (T["dispatch"] - T["alert"]
                               < B["dispatch"] - B["alert"] - 1e-12)
            print(f"  {cond:14s} {m:8d} {v:14d} {sd:14d} {sg:13d}")
            tm, tv, td, tg = tm + m, tv + v, td + sd, tg + sg
        print(f"  {'TOTAL':14s} {tm:8d} {tv:14d} {td:14d} {tg:13d}")
        if tv:
            print(f"  -> {td} of {tv} ({100*td/tv:.1f}%) ready sooner under "
                  f"pacing, comparing dispatch;")
            print(f"     {tg} of {tv} ({100*tg/tv:.1f}%) comparing the gap.")


if __name__ == "__main__":
    main()
