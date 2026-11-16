#!/usr/bin/env python3
"""Extract every recorded number from an OMNeT++ .sca corpus into one
gzipped long-format CSV, so the numbers can be committed and reviewed without
committing the corpus.

Why this exists
---------------
An OMNeT++ .sca file is mostly not data. In this project's escalation pilot a
572 KB .sca holds ~2,000 scalars/statistic fields and ~2,560 histogram bins,
against 5,850 `attr` lines (titles and units) and 3,319 `par` lines (the
resolved run configuration) -- both near-identical across every run in the
corpus, and both already recoverable from the .ini plus the NED files. Dropping
them turns 513 MB into 15 MB with no loss of recorded measurement.

What is kept
------------
  * every `scalar`
  * every `field` of every `statistic` (count/mean/stddev/min/max/sum/sqrsum)
  * every histogram `bin`, as field `bin:<lower-edge>`

What is dropped
---------------
  * `attr`   -- titles, units, interpolation modes: presentation metadata
  * `par`    -- the resolved parameter values; the .ini and the NED files are
                the authority, and `--manifest` writes the distinct sets out
  * `config` -- likewise, written by `--manifest`
  * `.vec` / `.vci` -- not read at all. NB: with `**.vector-recording = false`
                these files contain declarations and zero samples.

Faithfulness is verifiable, not asserted: any analysis that reads only the
three kept categories gives identical results from the extract and from the
corpus. See analysis/escalation_sr/README.md for the check that was run.

Usage
-----
    python3 tools/extract_sca.py <results_dir> <out.csv.gz> [--manifest <out.csv>]

File names are parsed as `<Config>-<arm>-s<seed>.sca`; anything else is parsed
as `<Config>-<rest>.sca` with `arm` set to <rest> and `seed` empty.
"""
import argparse
import csv
import glob
import gzip
import os
import re
import sys

NAME = re.compile(r"^(?P<cond>[A-Za-z0-9_]+?)-(?P<arm>.+?)(?:-s(?P<seed>\d+))?\.sca$")


def parse_name(basename):
    m = NAME.match(basename)
    if not m:
        return None
    return m["cond"], m["arm"], (m["seed"] or "")


def extract(results_dir, out_path, manifest_path=None):
    paths = sorted(glob.glob(os.path.join(results_dir, "*.sca")))
    if not paths:
        sys.exit(f"no .sca files in {results_dir}")

    seen_cfg = {}
    nrows = nfiles = 0
    with gzip.open(out_path, "wt", newline="", compresslevel=9) as fh:
        w = csv.writer(fh)
        w.writerow(["condition", "arm", "seed", "module", "name", "field", "value"])
        for path in paths:
            key = parse_name(os.path.basename(path))
            if key is None:
                print(f"skipped (unparsable name): {path}", file=sys.stderr)
                continue
            cond, arm, seed = key
            nfiles += 1
            cur = None  # (module, statname) of the statistic block we are inside
            with open(path) as f:
                for line in f:
                    t = line.split()
                    if not t:
                        continue
                    kind = t[0]
                    if kind == "scalar" and len(t) >= 4:
                        cur = None
                        w.writerow([cond, arm, seed, t[1], t[2], "", t[3]])
                        nrows += 1
                    elif kind == "statistic" and len(t) >= 3:
                        cur = (t[1], t[2])
                    elif kind == "field" and cur and len(t) >= 3:
                        w.writerow([cond, arm, seed, cur[0], cur[1], t[1], t[2]])
                        nrows += 1
                    elif kind == "bin" and cur and len(t) >= 3:
                        w.writerow([cond, arm, seed, cur[0], cur[1], "bin:" + t[1], t[2]])
                        nrows += 1
                    elif kind in ("par", "config"):
                        # configuration: recorded once per (condition, arm)
                        if manifest_path is not None:
                            seen_cfg.setdefault((cond, arm), {})[
                                (kind, t[1] if kind == "config" else " ".join(t[1:2]))
                            ] = " ".join(t[2:]) if kind == "config" else " ".join(t[2:])
                        cur = None
                    elif kind != "attr":
                        cur = None

    if manifest_path is not None:
        with open(manifest_path, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["condition", "arm", "kind", "key", "value"])
            for (cond, arm), d in sorted(seen_cfg.items()):
                for (kind, key), val in sorted(d.items()):
                    w.writerow([cond, arm, kind, key, val])

    print(f"files: {nfiles}  rows: {nrows}  -> {out_path} "
          f"({os.path.getsize(out_path) / 1e6:.1f} MB)")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results_dir")
    ap.add_argument("out_csv_gz")
    ap.add_argument("--manifest", default=None,
                    help="also write the distinct par/config sets per (condition, arm)")
    a = ap.parse_args()
    extract(a.results_dir, a.out_csv_gz, a.manifest)


if __name__ == "__main__":
    main()
