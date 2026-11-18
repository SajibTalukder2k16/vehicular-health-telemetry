#!/usr/bin/env python3
"""Extract the sensor-link scalars the indoor tables need into one gzipped CSV.

The indoor corpora are ~1 GB of .sca/.vec and are not committed. The latency
tables regenerate from tools/extract_vec.py's output; this is the other half
-- the camera-link load and the wearable's vitals delivery, which are scalars
rather than vectors and so are not in that extract.

Only the seven scalars the published tables use are kept. Output columns:

    corpus,label,seed,metric,value

`label` is the .sca basename with the -s<seed> suffix removed, which is the
arm identifier the drivers write (e.g. `RoomBleCam-e4`, `rate-k4f30`,
`share-0.05`). Keeping it verbatim means the analysis tool needs no table of
corpus-specific naming conventions.

    python3 tools/extract_indoor_scalars.py <out.csv.gz> <results_dir> [...]
"""
import csv
import glob
import gzip
import os
import re
import sys

SCA = re.compile(r"^scalar\s+\S*\.(?P<mod>camera|camLink|wearable|bleWearable"
                 r"|app\[0\])\s+(?P<name>\S+)\s+(?P<val>\S+)")
TAG = re.compile(r"^(?P<label>.+)-s(?P<seed>\d+)$")
WANT = {"camera.packetSent:count", "camLink.packetsDropped",
        "camLink.queueBytes:timeavg", "wearable.packetSent:count",
        "bleWearable.packetsDropped", "bleWearable.queueBytes:timeavg",
        "app[0].received_vitals",
        # The TRUE delivered counter. `sent - dropped` is accepted traffic,
        # not goodput: a frame undropped but still queued at termination is
        # counted as delivered by that subtraction and is not. BleLink and
        # WifiLink emit linkDelay only when a message COMPLETES, so its
        # count is what actually arrived. On the BLE camera the two differ
        # (524 delivered against 525 accepted); at `rate-prv2`, where the
        # queue holds a whole frame, they differ by more.
        "camLink.linkDelay:count", "camLink.linkDelay:mean",
        "bleWearable.linkDelay:count", "bleWearable.linkDelay:mean"}

# `statistic <module> <name>` opens a block of `field <k> <v>` lines, so the
# two statistics above are not on `scalar` lines and need the block parsed.
STAT = re.compile(r"^statistic\s+\S*\.(?P<mod>camLink|bleWearable)\s+"
                  r"(?P<name>linkDelay):stats\s*$")
FIELD = re.compile(r"^field\s+(?P<k>count|mean)\s+(?P<v>\S+)")


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    out_path, dirs = sys.argv[1], sys.argv[2:]
    rows = files = 0
    with gzip.open(out_path, "wt", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["corpus", "label", "seed", "metric", "value"])
        for d in dirs:
            corpus = os.path.basename(os.path.normpath(d))
            paths = sorted(glob.glob(os.path.join(d, "*.sca")))
            if not paths:
                sys.exit(f"no .sca files in {d}")
            for p in paths:
                m = TAG.match(os.path.basename(p)[:-4])
                if not m:
                    continue
                files += 1
                with open(p) as f:
                    pend = None          # module of the open statistic block
                    for line in f:
                        st = STAT.match(line)
                        if st:
                            pend = st["mod"]
                            continue
                        if pend:
                            fl = FIELD.match(line)
                            if fl:
                                key = f'{pend}.linkDelay:{fl["k"]}'
                                if key in WANT:
                                    w.writerow([corpus, m["label"],
                                                m["seed"], key, fl["v"]])
                                    rows += 1
                                continue
                            if not line.startswith("field"):
                                pend = None
                        s = SCA.match(line)
                        if not s:
                            continue
                        key = f'{s["mod"]}.{s["name"]}'
                        if key not in WANT:
                            continue
                        try:
                            float(s["val"])
                        except ValueError:
                            continue
                        w.writerow([corpus, m["label"], m["seed"], key,
                                    s["val"]])
                        rows += 1
    mb = os.path.getsize(out_path) / 1e6
    print(f"files: {files}  rows: {rows}  -> {out_path} ({mb:.2f} MB)")


if __name__ == "__main__":
    main()
