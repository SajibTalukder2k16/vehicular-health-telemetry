#!/usr/bin/env python3
"""Check a results directory for truncated or malformed .sca files.

A run killed mid-write (the OOM killer fires often on this box) leaves a file
that still contains the string "packetsGenerated" somewhere, so a naive
`grep -l packetsGenerated` counts it as complete. It is not: the scalars are
partial, and the missing ones silently read as zero in the exporter, which
then quietly skews whatever cell the run belongs to.

A run is considered complete only if every required scalar is present and the
sensor-generation counters are non-zero.

Usage: validate_runs.py <results-dir> [more dirs...]
Exit status is 1 if any file is bad, so it can gate a pipeline.
"""
import glob
import os
import re
import sys

REQUIRED = [
    (r'scalar \S*\.rig\.wearable packetsGenerated (\S+)', 'vitals generated', True),
    (r'scalar \S*\.rig\.camera packetsGenerated (\S+)', 'camera generated', True),
    # Network-agnostic: the vehicular net names these CorridorNet.server /
    # CorridorNet.ue, the room net RoomNet.cloud / RoomNet.edgeHost. Match on
    # the scalar name alone rather than the module path.
    (r'scalar \S+ received_vitals (\S+)', 'vitals received', False),
    (r'scalar \S+ packetsSentToCloud (\S+)', 'sent to cloud', False),
]


def check(path):
    """Return a list of problems with this .sca file."""
    try:
        txt = open(path, errors='replace').read()
    except OSError as e:
        return [f'unreadable: {e}']
    problems = []
    for pattern, label, must_be_nonzero in REQUIRED:
        m = re.search(pattern, txt)
        if not m:
            problems.append(f'missing {label}')
        elif must_be_nonzero and float(m.group(1)) == 0:
            problems.append(f'{label} is zero')
    # Do NOT guess truncation from the final character: .sca files end with a
    # parameter dump whose last line can be anything ("... forwarding false").
    # The required-scalar check above is the reliable signal -- a run killed
    # mid-write loses its scalars section, which is what actually matters.
    return problems


def main(dirs):
    total = bad = 0
    for d in dirs:
        files = sorted(glob.glob(os.path.join(d, '*.sca')))
        if not files:
            print(f'{d}: no .sca files')
            continue
        d_bad = []
        for f in files:
            total += 1
            p = check(f)
            if p:
                bad += 1
                d_bad.append((os.path.basename(f), p))
        status = 'OK' if not d_bad else f'{len(d_bad)} BAD'
        print(f'{d}: {len(files)} files, {status}')
        for name, probs in d_bad[:10]:
            print(f'    {name}: {"; ".join(probs)}')
        if len(d_bad) > 10:
            print(f'    ... and {len(d_bad) - 10} more')
    print(f'\ntotal {total} files, {bad} bad')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:] or ['.']))
