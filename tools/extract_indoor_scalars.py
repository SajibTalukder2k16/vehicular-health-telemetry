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
        "app[0].received_vitals"}


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
                    for line in f:
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
