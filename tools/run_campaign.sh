#!/bin/bash
# Phase 4 campaign: Family A factorial + Family B case studies, 30 seeds each.
# Usage: run_campaign.sh [jobs]   (default 20)
J=${1:-20}
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NED="$ROOT/src:$ROOT/simulations:$ROOT/../inet4.7/src:$ROOT/../Simu5G/src"
LIB="$ROOT/../Simu5G/src/simu5g"
BIN="$ROOT/src/out/clang-release/paperrebuild"
source /home/sajib/omnetpp-6.4.0/setenv >/dev/null 2>&1
set -u

run() { # dir config extra...
    local dir=$1 cfg=$2; shift 2
    cd "$ROOT/simulations/$dir"
    echo "[$(date +%H:%M:%S)] START $dir/$cfg"
    opp_runall -j"$J" "$BIN" -u Cmdenv -c "$cfg" -n "$NED" -l "$LIB" "$@" > "campaign_$cfg.log" 2>&1
    echo "[$(date +%H:%M:%S)] DONE  $dir/$cfg (sca: $(ls results/$cfg-*.sca 2>/dev/null | wc -l))"
}

# Family A (scalars + histograms only)
run corridorA Urban
run corridorA Rural

# Family B (30 seeds scalars; then 3 seeds with vectors for AoI/handover analysis,
# kept in results/vec_subset/ so they don't double-count in aggregation)
run dc_case DcDrive
run va_case VaDrive
for case in dc_case:DcDrive va_case:VaDrive; do
    dir=${case%%:*}; cfg=${case#*:}
    cd "$ROOT/simulations/$dir"
    mkdir -p results/vec_subset
    for r in 0 1 2; do
        "$BIN" -u Cmdenv -c "$cfg" -r $r -n "$NED" -l "$LIB" \
            '--**.server.app[*].**.vector-recording=true' \
            '--**.ue.cellularNic.phy.**.vector-recording=true' \
            --output-vector-file="results/vec_subset/$cfg-vec-$r.vec" \
            --output-scalar-file="results/vec_subset/$cfg-vec-$r.sca" \
            >> "campaign_$cfg.log" 2>&1 &
    done
    wait
    echo "[$(date +%H:%M:%S)] DONE  $dir/$cfg vector subset"
done

echo "[$(date +%H:%M:%S)] CAMPAIGN COMPLETE"
