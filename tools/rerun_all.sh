#!/bin/bash
# Re-run every campaign under the 5-stream RNG mapping, restartable.
#
# WHY: until 2026-10-15 every module shared rng-0, so any factor that changed
# how many packets were transmitted shifted the global draw order and changed
# when the exponentially-spaced sensors fired. Comparisons were therefore made
# across different offered workloads. Measured on the de-confounded cells at
# repetition 0, vitals generation spanned 1297-1427 (10%) and OBD 637-738
# (16%) across cells that differ only in link type. After the fix all eight
# cells share an identical workload.
#
# Separating `**.rig.*` was not enough: BleLink's per-PDU error draws and the
# edge's volatile processingTime live under that pattern too, so changing link
# type still perturbed generation. Sources are now on stream 1, rig links and
# edge on 4.
#
# Each invocation works for roughly <minutes> and then stops, skipping runs
# that already completed, so it can be driven in bounded chunks.
#
# Usage: rerun_all.sh [minutes] [jobs]
set -u
BUDGET=$(( ${1:-9} * 60 ))
J=${2:-8}
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NED="$ROOT/src:$ROOT/simulations:$ROOT/../inet4.7/src:$ROOT/../Simu5G/src"
LIB="$ROOT/../Simu5G/src/simu5g"
BIN="$ROOT/src/out/clang-release/paperrebuild"
START=$(date +%s)

over_budget() { [ $(( $(date +%s) - START )) -ge $BUDGET ]; }

# dir  config  resultdir  runfilter(optional)
JOBS="
corridorA:RuralEdgeDeconf:results_deconf
corridorA:RuralBufferSweep:results_buf
corridorA:MechNone:results_mech
corridorA:MechSweep:results_mech
room:Room24GHz:results
room:Room5GHz:results
room:Room5GHzCameraBle:results
room:RoomMatched24GHz:results_matched
room:RoomMatched5GHz:results_matched
dc_case:DcDriveAtt:results
dc_case:DcDriveTmo:results
dc_case:DcDriveVzw:results
dc_case:DcDriveLegacy8:results
va_case:VaDriveAtt:results
va_case:VaDriveTmo:results
va_case:VaDriveVzw:results
va_case:VaDriveLegacy8:results
corridorA:SensUrban:results_sens
corridorA:SensRural:results_sens
corridorA:Urban:results
corridorA:Rural:results
"

for spec in $JOBS; do
    over_budget && { echo "budget reached"; exit 0; }
    dir=${spec%%:*}; rest=${spec#*:}
    cfg=${rest%%:*}; rdir=${rest#*:}
    cd "$ROOT/simulations/$dir" || continue
    mkdir -p "$rdir"
    # how many runs does this config have?
    total=$("$BIN" -u Cmdenv -c "$cfg" -n "$NED" -l "$LIB" -q numruns 2>/dev/null | grep -oP 'Number of runs: \K[0-9]+' | head -1)
    [ -z "$total" ] && { echo "SKIP $dir/$cfg (cannot determine run count)"; continue; }
    done_n=$(grep -l packetsGenerated "$rdir"/${cfg}-*.sca 2>/dev/null | wc -l)
    [ "$done_n" -ge "$total" ] && { echo "OK   $dir/$cfg $done_n/$total"; continue; }
    echo "RUN  $dir/$cfg $done_n/$total"
    n=0
    for r in $(seq 0 $((total-1))); do
        over_budget && break
        # skip runs whose scalar file already looks complete
        existing=$(ls "$rdir"/${cfg}-*#${r}.sca 2>/dev/null | head -1)
        [ -n "$existing" ] && grep -q packetsGenerated "$existing" 2>/dev/null && continue
        "$BIN" -u Cmdenv -c "$cfg" -r "$r" -n "$NED" -l "$LIB" \
            --cmdenv-express-mode=true --cmdenv-status-frequency=5000s \
            --result-dir="$rdir" > /dev/null 2>&1 &
        n=$((n+1)); [ $((n % J)) -eq 0 ] && wait
    done
    wait
    echo "     -> $(grep -l packetsGenerated "$rdir"/${cfg}-*.sca 2>/dev/null | wc -l)/$total"
done
echo "ALL CAMPAIGNS COMPLETE"
