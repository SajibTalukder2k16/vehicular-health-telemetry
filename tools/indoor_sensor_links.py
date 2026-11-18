#!/usr/bin/env python3
"""Sensor-link load for the indoor campaigns: what each link carries, and the
share the wearable needs.

WHY THIS SCRIPT EXISTS
  The camera-link and wearable-share tables of docs/BLE_CAMERA_RESULT.md and
  docs/INDOOR_BACKHAUL_RESULT.md were first produced inline. That is the same
  reproducibility gap that docs/ROOM_LADDER_RESULT.md carried until
  tools/analyze_room_ladder.py replaced its inline analysis, so it is closed
  the same way, and for the same reason: an inline number cannot be checked
  and cannot be re-derived after the corpus is deleted.

WHAT IT REPORTS
  --camera   offered / dropped / delivered per arm, which is what promotes
             C1's WLAN and BLE rows from derived to measured. `delivered` is
             computed from the drop ratio and the offered rate, not read from
             a counter, so it is a goodput and not a link-layer figure.
  --share    the wearable's vitals against its share of the BLE connection
             interval. Reports DELIVERED, not just dropped: in the stalled
             arms the drop counter reads 57.53 % while delivery is zero, the
             remainder stranded in a queue that never drains. Reporting the
             drop rate alone would describe a partial problem where the truth
             is total failure -- the same metric trap as maxAge = 0.5 s in
             docs/COMPLETION_RESULT.md section 5a.

  Takes either a directory of .sca files or a committed .csv.gz extract from
  tools/extract_indoor_scalars.py.

    python3 -I tools/indoor_sensor_links.py <corpus> [--camera] [--share]
"""
import argparse
import collections
import csv
import glob
import gzip
import os
import re
import statistics
import sys

SCA = re.compile(r"^scalar\s+\S*\.(?P<mod>camera|camLink|wearable|bleWearable"
                 r"|app\[0\])\s+(?P<name>\S+)\s+(?P<val>\S+)")
TAG = re.compile(r"^(?P<label>.+)-s(?P<seed>\d+)$")
SHARE = re.compile(r"^share-(?P<u>[0-9.]+)$")

# Offered rate per camera-sweep arm: (frame bytes, fps). The sweep's whole
# point is that "BLE cannot carry the camera" is true of one camera and false
# of another, so the arm label alone is not enough -- the rate must be stated.
RATE = {"prv": (53167, 60), "prv2": (53167, 2), "k4f60": (4096, 60),
        "k4f30": (4096, 30), "k4f10": (4096, 10)}
WANT = {"camera.packetSent:count", "camLink.packetsDropped",
        "camLink.queueBytes:timeavg", "wearable.packetSent:count",
        "bleWearable.packetsDropped", "bleWearable.queueBytes:timeavg",
        "app[0].received_vitals",
        "camLink.linkDelay:count", "camLink.linkDelay:mean",
        "bleWearable.linkDelay:count", "bleWearable.linkDelay:mean"}
STAT = re.compile(r"^statistic\s+\S*\.(?P<mod>camLink|bleWearable)\s+"
                  r"linkDelay:stats\s*$")
FIELD = re.compile(r"^field\s+(?P<k>count|mean)\s+(?P<v>\S+)")
WINDOW = 300.0   # s; every room configuration's sim-time-limit


def load(src):
    """-> {label: {metric: [value per seed]}}"""
    agg = collections.defaultdict(lambda: collections.defaultdict(list))
    if src.endswith(".csv.gz"):
        with gzip.open(src, "rt", newline="") as fh:
            for r in csv.DictReader(fh):
                agg[r["label"]][r["metric"]].append(float(r["value"]))
        return agg
    for p in sorted(glob.glob(os.path.join(src, "*.sca"))):
        m = TAG.match(os.path.basename(p)[:-4])
        if not m:
            continue
        with open(p) as fh:
            pend = None
            for line in fh:
                st = STAT.match(line)
                if st:
                    pend = st["mod"]
                    continue
                if pend:
                    fl = FIELD.match(line)
                    if fl:
                        key = f'{pend}.linkDelay:{fl["k"]}'
                        if key in WANT:
                            agg[m["label"]][key].append(float(fl["v"]))
                        continue
                    if not line.startswith("field"):
                        pend = None
                s = SCA.match(line)
                if not s:
                    continue
                key = f'{s["mod"]}.{s["name"]}'
                if key in WANT:
                    try:
                        agg[m["label"]][key].append(float(s["val"]))
                    except ValueError:
                        pass
    return agg


def mean(agg, label, metric, default=float("nan")):
    v = agg[label].get(metric)
    return statistics.mean(v) if v else default


def camera_table(agg):
    labels = [k for k in agg if agg[k].get("camera.packetSent:count")]
    print("CAMERA SENSOR LINK")
    print("  `accepted` is offered x (1 - dropped/sent): an ESTIMATE that")
    print("  counts a frame still queued at termination as delivered.")
    print("  `delivered` is measured -- linkDelay fires only on completion.")
    print(f"  {'arm':18s} {'frame B':>8s} {'fps':>4s} {'offered':>9s} "
          f"{'sent':>7s} {'dropped':>8s} {'drop %':>7s} {'accepted':>9s} "
          f"{'delivered':>10s} {'ms/frame':>9s} {'queue B':>8s}")
    for lab in sorted(labels):
        sent = mean(agg, lab, "camera.packetSent:count")
        drop = mean(agg, lab, "camLink.packetsDropped", 0.0)
        q = mean(agg, lab, "camLink.queueBytes:timeavg")
        key = lab.split("-")[-1]
        # Every ladder arm (RoomBleCam-*, RoomWifiCam*-*, RoomMatched*-*) runs
        # the camera at PRV grade; only the `rate-` sweep varies it. So an arm
        # not in RATE is PRV grade by construction, not unknown.
        B, fps = RATE.get(key, (53167, 60))
        off = B * 8 * fps / 1e6
        deliv = off * (1 - drop / sent) if sent else float("nan")
        bs, fs = f"{B}", f"{fps}"
        pct = 100 * drop / sent if sent else float("nan")
        got = mean(agg, lab, "camLink.linkDelay:count")
        dly = mean(agg, lab, "camLink.linkDelay:mean")
        # measured goodput: completed frames x bytes over the window
        meas = got * B * 8 / WINDOW / 1e6 if got == got else float("nan")
        print(f"  {lab:18s} {bs:>8s} {fs:>4s} {off:9.2f} {sent:7.0f} "
              f"{drop:8.0f} {pct:7.2f} {deliv:9.3f} {meas:10.3f} "
              f"{1e3*dly:9.3f} {q:8.0f}")


def share_table(agg):
    # ONLY the share sweep. Every other arm also records vitals counters, and
    # including them printed 30 spurious rows at a share of -1 -- the arms are
    # not a sweep of anything and their wearable link is untouched.
    labels = [k for k in agg if SHARE.match(k)
              and agg[k].get("wearable.packetSent:count")]
    if not labels:
        return
    print("\nWEARABLE VITALS vs ITS SHARE OF THE BLE CONNECTION INTERVAL")
    print("  a PDU costs 2,468 us of a 30 ms interval, so below 2468/30000 =")
    print("  0.08227 not one PDU fits and the link transmits nothing at all")
    print(f"  {'share':>8s} {'budget ms':>10s} {'sent':>7s} {'dropped':>8s} "
          f"{'drop %':>7s} {'DELIVERED':>10s} {'queue B':>9s}")

    def keyf(k):
        return float(SHARE.match(k)["u"])
    for lab in sorted(labels, key=keyf, reverse=True):
        u = keyf(lab)
        sent = mean(agg, lab, "wearable.packetSent:count")
        drop = mean(agg, lab, "bleWearable.packetsDropped", 0.0)
        got = mean(agg, lab, "app[0].received_vitals", 0.0)
        q = mean(agg, lab, "bleWearable.queueBytes:timeavg")
        pct = 100 * drop / sent if sent else float("nan")
        flag = "   <- stalled" if got == 0 else ""
        print(f"  {u:8.4f} {u*30:10.2f} {sent:7.0f} {drop:8.1f} {pct:7.2f} "
              f"{got:10.1f} {q:9.0f}{flag}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus")
    ap.add_argument("--camera", action="store_true")
    ap.add_argument("--share", action="store_true")
    a = ap.parse_args()
    agg = load(a.corpus)
    if not agg:
        sys.exit(f"no usable scalars in {a.corpus}")
    print(f"corpus: {a.corpus}\n")
    if a.camera or not (a.camera or a.share):
        camera_table(agg)
    if a.share or not (a.camera or a.share):
        share_table(agg)


if __name__ == "__main__":
    main()
