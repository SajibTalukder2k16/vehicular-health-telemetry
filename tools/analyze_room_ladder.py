#!/usr/bin/env python3
"""Completion, dispatch gap, and camera-link load for the indoor ladder runs.

WHY THIS SCRIPT EXISTS
  docs/ROOM_LADDER_RESULT.md was produced by an inline analysis, so its
  provenance section could name only the driver. That is a reproducibility
  gap in exactly the kind of number the paper leans on, and the WLAN-camera
  run needs the same tables, so the analysis is written down once here and
  both corpora go through it.

WHAT IT REUSES, AND WHY THAT MATTERS
  Pairing and completion classification are imported from tools/dispatch_times
  and tools/completion, not re-implemented. Both have a history: the pairing
  window had to become signed because a symmetric one could pair an alert to
  its NEIGHBOUR's burst, and the censoring rule had to stop treating "last
  escalation of the run" as censored. A second copy of either would be free to
  drift back into the old bug, and the two tables would then disagree without
  anything flagging it.

  The one thing overridden is the horizon. completion.HORIZON holds the four
  cellular sim-time-limits (320/1369/1369/680 s); the room configurations run
  300 s, and with no entry the censoring test `t + t_obs > horizon` compares
  against infinity and censors nothing. Left alone that would silently report
  every incomplete burst as genuine loss.

  python3 -I tools/analyze_room_ladder.py <results_dir> [--horizon S]
"""
import argparse
import collections
import glob
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import completion                                      # noqa: E402
from dispatch_times import pair_bursts, parse_vec       # noqa: E402

EXPECTED = {"ref": None, "e1": 1, "e2": 3, "e3": 41, "e4": 99}
ARM_ORDER = ["ref", "e1", "e2", "e3", "e4"]
RUNG = {"ref": "none", "e1": "512B", "e2": "3.5KiB",
        "e3": "56KiB", "e4": "138kB"}
TOL = 1e-2
# <cond>-<arm>-s<seed>.sca|vec, as both room drivers name their outputs.
NAME = re.compile(r"^(?P<cond>[A-Za-z0-9]+)-(?P<arm>[A-Za-z0-9]+)-s(?P<seed>\d+)$")


def load_corpus(d):
    """-> {(cond, arm, seed): (alarms, {creation: [delay, ...]})}

    Accepts either a directory of .vec files or a committed .csv.gz extract
    from tools/extract_vec.py. The extract path exists so the indoor tables
    regenerate from the repository without the ~1 GB of raw output, which is
    what the paper's Reproducibility section claims of every table. The two
    inputs are checked against each other in tools/verify_indoor_extract.py.
    """
    if d.endswith(".csv.gz"):
        return completion.load(d)
    per = {}
    for p in sorted(glob.glob(os.path.join(d, "*.vec"))):
        m = NAME.match(os.path.basename(p)[:-4])
        if not m:
            continue
        per[(m["cond"], m["arm"], m["seed"])] = parse_vec(p)
    return per


# Camera-link scalars. `packetSent:count` is offered frames, `packetsDropped`
# is what the DCF model gave up on; their ratio is the only honest way to say
# whether the stream fitted, because a link that drops three frames in four
# still reports a perfectly healthy delay for the one that got through.
SCA = re.compile(r"^scalar\s+\S*\.(?P<mod>camera|camLink)\s+(?P<name>\S+)\s+(?P<val>\S+)")
WANT = {("camera", "packetSent:count"), ("camLink", "packetsDropped"),
        ("camLink", "linkDelay:mean"), ("camLink", "linkDelay:max"),
        ("camLink", "queueBytes:timeavg")}


def load_camlink(d):
    agg = collections.defaultdict(lambda: collections.defaultdict(list))
    for p in sorted(glob.glob(os.path.join(d, "*.sca"))):
        m = NAME.match(os.path.basename(p)[:-4])
        if not m:
            continue
        with open(p) as fh:
            for line in fh:
                s = SCA.match(line)
                if s and (s["mod"], s["name"]) in WANT:
                    try:
                        agg[(m["cond"], m["arm"])][
                            f'{s["mod"]}.{s["name"]}'].append(float(s["val"]))
                    except ValueError:
                        pass
    return agg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results_dir")
    ap.add_argument("--horizon", type=float, default=300.0,
                    help="sim-time-limit of the runs; the censoring test needs "
                         "it and defaults to the room configs' 300 s")
    a = ap.parse_args()

    per = load_corpus(a.results_dir)
    if not per:
        sys.exit(f"no parseable .vec files in {a.results_dir}")
    conds = sorted({c for c, _, _ in per})
    arms = [x for x in ARM_ORDER if x in {ar for _, ar, _ in per}]

    # The override the docstring warns about. Applied to every condition
    # present, and printed, so a reader can see which horizon produced the
    # censoring column rather than having to trust it.
    for c in conds:
        completion.HORIZON[c] = a.horizon
    print(f"corpus: {a.results_dir}")
    print(f"{len(per)} runs, horizon {a.horizon:g} s, pairing tol {TOL:g} s\n")

    print("COMPLETION  complete / (complete + lost); censored excluded")
    print(f"  {'condition':22s} " + " ".join(f"{RUNG[x]:>10s}" for x in arms))
    cens_total = 0
    for c in conds:
        cells = []
        for arm in arms:
            comp, cens, lost, _ = completion.classify(
                per, arm, c, EXPECTED[arm])
            cens_total += cens
            if EXPECTED[arm] is None:
                cells.append("-")
            elif comp + lost:
                cells.append(f"{100*comp/(comp+lost):.1f}% "
                             f"({comp+lost})")
            else:
                cells.append("n/a")
        print(f"  {c:22s} " + " ".join(f"{x:>10s}" for x in cells))
    print(f"  censored (excluded from the rates above): {cens_total}")

    print("\nDISPATCH  medians over escalations, s; gap conditional on completion")
    print(f"  {'condition':22s} {'arm':>5s} {'n':>5s} "
          f"{'alert':>9s} {'gap':>9s} {'dispatch':>9s}")
    for c in conds:
        for arm in arms:
            al, ga, di = [], [], []
            for (cc, aa, _), (alarms, ch) in per.items():
                if cc != c or aa != arm:
                    continue
                exp = EXPECTED[arm]
                full = ch if exp is None else {
                    t: v for t, v in ch.items() if len(v) >= exp}
                for r in pair_bursts(alarms, full, TOL):
                    al.append(r[0])
                    if r[2] > 0 or exp is None:
                        ga.append(r[1] - r[0])
                        di.append(r[1])
            if not al:
                continue
            print(f"  {c:22s} {arm:>5s} {len(ga):5d} "
                  f"{statistics.median(al):9.4f} "
                  f"{statistics.median(ga) if ga else float('nan'):9.4f} "
                  f"{statistics.median(di) if di else float('nan'):9.4f}")

    cam = load_camlink(a.results_dir)
    if not cam:
        return
    print("\nCAMERA SENSOR LINK  per-run means over seeds")
    print(f"  {'condition':22s} {'arm':>5s} {'offered':>10s} {'dropped':>10s} "
          f"{'drop %':>8s} {'delay ms':>9s} {'queue B':>9s}")
    for c in conds:
        for arm in arms:
            v = cam.get((c, arm))
            if not v:
                continue
            sent = statistics.mean(v.get("camera.packetSent:count", [0]))
            drop = statistics.mean(v.get("camLink.packetsDropped", [0]))
            dly = v.get("camLink.linkDelay:mean")
            qb = v.get("camLink.queueBytes:timeavg")
            print(f"  {c:22s} {arm:>5s} {sent:10.0f} {drop:10.0f} "
                  f"{100*drop/sent if sent else float('nan'):8.2f} "
                  f"{1e3*statistics.mean(dly) if dly else float('nan'):9.3f} "
                  f"{statistics.mean(qb) if qb else float('nan'):9.0f}")


if __name__ == "__main__":
    main()
