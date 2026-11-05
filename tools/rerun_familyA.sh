#!/bin/bash
# Re-run Family A (Urban 4320 + Rural 2880 = 7200 runs) under the five-stream
# RNG mapping, in bounded restartable chunks.
#
# WHY: until the mapping was fixed, every module shared rng-0, so any factor
# that changed how many packets were transmitted shifted the global draw order
# and changed when the exponentially-spaced sensors fired. Family A's factors
# (ISD, speed, payload, background load, edge type) all do that, so every main
# effect was computed across slightly different offered workloads. The large
# effects should be robust; the NULL results are the ones at risk, because
# they claim absence of an effect at a magnitude smaller than the drift.
#
# Background jobs do not survive session boundaries on this box and the OOM
# killer fires if too many run at once, so this works for a bounded time and
# exits, skipping runs that already look complete. Invoke repeatedly.
#
# A run counts as complete only if its sensor-generation scalar is present and
# non-zero -- a run killed mid-write still contains the string
# "packetsGenerated" elsewhere in the file (see tools/validate_runs.py).
#
# Usage: rerun_familyA.sh [minutes] [jobs]
set -u
BUDGET=$(( ${1:-9} * 60 ))
J=${2:-10}
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NED="$ROOT/src:$ROOT/simulations:$ROOT/../inet4.7/src:$ROOT/../Simu5G/src"
LIB="$ROOT/../Simu5G/src/simu5g"
BIN="$ROOT/src/out/clang-release/paperrebuild"
OUT="$ROOT/simulations/corridorA/results_v2"
mkdir -p "$OUT"
cd "$ROOT/simulations/corridorA"
START=$(date +%s)

# Build the set of already-complete run numbers ONCE per config. Checking
# each run individually meant one glob plus one grep over a multi-megabyte
# .sca file per run, and with 1430 completed runs that consumed an entire
# 8-minute budget before launching anything.
#
# A run counts as complete only if its sensor-generation scalar is present and
# non-zero: a run killed mid-write still contains "packetsGenerated" elsewhere
# in the file (see tools/validate_runs.py).
scan_complete() {   # config -> writes completed run numbers to $DONEFILE
    local cfg=$1
    : > "$DONEFILE"
    ls "$OUT/$cfg-"*.sca >/dev/null 2>&1 || return 0
    grep -l -m1 "rig\.wearable packetsGenerated [1-9]" "$OUT/$cfg-"*.sca 2>/dev/null \
        | sed 's/.*#\([0-9]*\)\.sca/\1/' | sort -n > "$DONEFILE"
}

DONEFILE=$(mktemp)
trap 'rm -f "$DONEFILE"' EXIT

for spec in Urban:4320 Rural:2880; do
    cfg=${spec%%:*}; total=${spec#*:}
    echo "scanning $cfg for completed runs ..."
    scan_complete "$cfg"
    done_n=$(wc -l < "$DONEFILE")
    echo "=== $cfg: $done_n/$total complete ==="
    n=0
    for r in $(seq 0 $((total-1))); do
        [ $(( $(date +%s) - START )) -ge $BUDGET ] && { wait; echo "budget reached in $cfg at run $r"; exit 0; }
        grep -qx "$r" "$DONEFILE" && continue
        "$BIN" -u Cmdenv -c "$cfg" -r "$r" -n "$NED" -l "$LIB" \
            --cmdenv-express-mode=true --cmdenv-status-frequency=5000s \
            --result-dir="$OUT" > /dev/null 2>&1 &
        n=$((n+1)); [ $((n % J)) -eq 0 ] && wait
    done
    wait
    echo "$cfg complete: $(ls "$OUT/$cfg-"*.sca 2>/dev/null | wc -l)/$total"
done
echo "FAMILY A COMPLETE"
