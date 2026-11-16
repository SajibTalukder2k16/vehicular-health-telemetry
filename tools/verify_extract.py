#!/usr/bin/env python3
"""Verify that a tools/extract_sca.py extract is a faithful, lossless record of
the kept categories in a .sca corpus.

The extract is the committed artifact and the corpus is not, so the claim
"nothing measured was lost" has to be checkable by someone who has only the
repository plus the corpus. This script is that check.

It streams both in the same order and compares every value exactly, as text,
so a reformatted float counts as a difference. It also checks, independently,
that each histogram's bin counts sum to that statistic's `count` field -- which
catches a truncated or mis-parsed histogram that a row-by-row comparison of two
outputs from the same parser would not.

    python3 tools/verify_extract.py <results_dir> <extract.csv.gz>

Exit status 0 and "OK" on success; non-zero with the first mismatch otherwise.
"""
import csv
import glob
import gzip
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_sca import parse_name  # noqa: E402


def corpus_rows(results_dir):
    """Re-walk the corpus, yielding the rows an extract must contain, in order."""
    for path in sorted(glob.glob(os.path.join(results_dir, "*.sca"))):
        key = parse_name(os.path.basename(path))
        if key is None:
            continue
        cond, arm, seed = key
        cur = None
        with open(path) as f:
            for line in f:
                t = line.split()
                if not t:
                    continue
                kind = t[0]
                if kind == "scalar" and len(t) >= 4:
                    cur = None
                    yield (cond, arm, seed, t[1], t[2], "", t[3])
                elif kind == "statistic" and len(t) >= 3:
                    cur = (t[1], t[2])
                elif kind == "field" and cur and len(t) >= 3:
                    yield (cond, arm, seed, cur[0], cur[1], t[1], t[2])
                elif kind == "bin" and cur and len(t) >= 3:
                    yield (cond, arm, seed, cur[0], cur[1], "bin:" + t[1], t[2])
                elif kind in ("par", "config"):
                    cur = None
                elif kind != "attr":
                    cur = None


def histogram_integrity(results_dir):
    """For every histogram, compare sum(bin counts) against the `count` field."""
    bad, checked = [], 0
    for path in sorted(glob.glob(os.path.join(results_dir, "*.sca"))):
        cur, count, binsum, seen_bins = None, None, 0.0, False
        with open(path) as f:
            def close():
                nonlocal bad, checked
                if cur and seen_bins and count is not None:
                    checked += 1
                    if not math.isclose(binsum, count, rel_tol=0, abs_tol=0.5):
                        bad.append((os.path.basename(path), cur[0], cur[1],
                                    count, binsum))
            for line in f:
                t = line.split()
                if not t:
                    continue
                if t[0] == "statistic":
                    close()
                    cur, count, binsum, seen_bins = (t[1], t[2]), None, 0.0, False
                elif t[0] == "field" and cur and len(t) >= 3 and t[1] == "count":
                    try:
                        count = float(t[2])
                    except ValueError:
                        count = None
                elif t[0] == "bin" and cur and len(t) >= 3:
                    seen_bins = True
                    try:
                        binsum += float(t[2])
                    except ValueError:
                        pass
                elif t[0] not in ("attr", "bin", "field"):
                    close()
                    cur, count, binsum, seen_bins = None, None, 0.0, False
            close()
    return checked, bad


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    results_dir, extract = sys.argv[1], sys.argv[2]

    n = 0
    with gzip.open(extract, "rt", newline="") as fh:
        rd = csv.reader(fh)
        header = next(rd)
        if header != ["condition", "arm", "seed", "module", "name", "field", "value"]:
            sys.exit(f"FAIL: unexpected header {header}")
        for want in corpus_rows(results_dir):
            try:
                got = tuple(next(rd))
            except StopIteration:
                sys.exit(f"FAIL: extract ended early at corpus row {n + 1}: {want}")
            if got != want:
                sys.exit(f"FAIL: row {n + 1} differs\n  corpus:  {want}\n  extract: {got}")
            n += 1
        extra = sum(1 for _ in rd)
        if extra:
            sys.exit(f"FAIL: extract has {extra} rows beyond the corpus")

    checked, bad = histogram_integrity(results_dir)
    if bad:
        for row in bad[:10]:
            print(f"  histogram mismatch: {row}", file=sys.stderr)
        sys.exit(f"FAIL: {len(bad)} of {checked} histograms do not sum to their count")

    print(f"OK: {n} values match exactly; "
          f"{checked} histograms sum to their recorded count")


if __name__ == "__main__":
    main()
