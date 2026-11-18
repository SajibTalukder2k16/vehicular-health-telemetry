#!/usr/bin/env python3
"""Extract the escalation latency vectors from a .vec corpus into one gzipped
CSV, so the per-escalation dispatch table is reproducible from the repository
without the 956 MB corpus.

Only the two vectors the result depends on are kept -- e2eDelayAlarm and
e2eDelayEvidence. Everything else in the corpus's .vec files is either empty
(see the ordering warning in simulations/pilot/omnetpp.ini) or irrelevant here.

Output columns:

    condition,arm,seed,kind,recv_time,delay,creation

`kind` is "alarm" or "evidence"; `creation` is recv_time - delay, which is what
groups chunks to their escalation. NOTE that an alarm's creation stamp is its
sensor creation time at the rig while an evidence chunk's is at the edge, so the
two differ by the edge processing time -- see tools/dispatch_times.py for why
that matters and what tolerance to use.

    python3 tools/extract_vec.py <results_dir> <out.csv.gz>
"""
import csv
import glob
import gzip
import os
import re
import sys

NAME = re.compile(r"^(?P<cond>[A-Za-z0-9_]+?)-(?P<arm>.+?)(?:-s(?P<seed>\d+))?\.vec$")
WANT = {"e2eDelayAlarm": "alarm", "e2eDelayEvidence": "evidence"}


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    results_dir, out_path = sys.argv[1], sys.argv[2]
    paths = sorted(glob.glob(os.path.join(results_dir, "*.vec")))
    if not paths:
        sys.exit(f"no .vec files in {results_dir}")

    nrows = nfiles = 0
    with gzip.open(out_path, "wt", newline="", compresslevel=9) as fh:
        w = csv.writer(fh)
        w.writerow(["condition", "arm", "seed", "kind", "recv_time", "delay", "creation"])
        for path in paths:
            m = NAME.match(os.path.basename(path))
            if not m:
                print(f"skipped (unparsable name): {path}", file=sys.stderr)
                continue
            cond, arm, seed = m["cond"], m["arm"], (m["seed"] or "")
            nfiles += 1
            ids = {}
            with open(path) as f:
                for line in f:
                    if line.startswith("vector "):
                        p = line.split()
                        if len(p) >= 4:
                            base = p[3].split(":")[0]
                            if base in WANT:
                                ids[p[1]] = WANT[base]
                        continue
                    if not line[:1].isdigit():
                        continue
                    p = line.split()
                    if len(p) != 4 or p[0] not in ids:
                        continue
                    t, v = float(p[2]), float(p[3])
                    w.writerow([cond, arm, seed, ids[p[0]], p[2], p[3],
                                repr(round(t - v, 9))])
                    nrows += 1

    print(f"files: {nfiles}  rows: {nrows}  -> {out_path} "
          f"({os.path.getsize(out_path) / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
