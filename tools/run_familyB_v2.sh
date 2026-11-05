#!/bin/bash
# Family B re-run with corrected site selection (2026-10-02).
#
# Supersedes the pooled/8-densest tower sets. Each config models ONE operator
# and keeps every site that is among the 2 nearest anywhere on the route, which
# preserves the route's distance-to-nearest-site profile exactly (see the AUDIT
# block in each towers_*.ini). The Legacy8 configs reproduce the superseded
# selection so the artifact can be quantified rather than just asserted.
#
# Usage: run_familyB_v2.sh [jobs]   (default 20)
J=${1:-20}
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NED="$ROOT/src:$ROOT/simulations:$ROOT/../inet4.7/src:$ROOT/../Simu5G/src"
LIB="$ROOT/../Simu5G/src/simu5g"
BIN="$ROOT/src/out/clang-release/paperrebuild"
source /home/sajib/omnetpp-6.4.0/setenv >/dev/null 2>&1
set -u

run() { # dir config
    local dir=$1 cfg=$2
    cd "$ROOT/simulations/$dir"
    echo "[$(date +%H:%M:%S)] START $dir/$cfg"
    opp_runall -j"$J" "$BIN" -u Cmdenv -c "$cfg" -n "$NED" -l "$LIB" \
        --cmdenv-express-mode=true --cmdenv-status-frequency=500s \
        > "campaign_$cfg.log" 2>&1
    echo "[$(date +%H:%M:%S)] DONE  $dir/$cfg (sca: $(ls results/$cfg-*.sca 2>/dev/null | wc -l))"
}

vecs() { # dir config
    local dir=$1 cfg=$2
    cd "$ROOT/simulations/$dir"
    mkdir -p results/vec_subset
    for r in 0 1 2; do
        "$BIN" -u Cmdenv -c "$cfg" -r $r -n "$NED" -l "$LIB" \
            --cmdenv-express-mode=true --cmdenv-status-frequency=500s \
            '--**.server.app[*].**.vector-recording=true' \
            '--**.ue.cellularNic.phy.**.vector-recording=true' \
            --output-vector-file="results/vec_subset/$cfg-vec-$r.vec" \
            --output-scalar-file="results/vec_subset/$cfg-vec-$r.sca" \
            >> "campaign_$cfg.log" 2>&1 &
    done
    wait
    echo "[$(date +%H:%M:%S)] DONE  $dir/$cfg vector subset"
}

for c in DcDriveAtt DcDriveTmo DcDriveVzw DcDriveLegacy8; do run dc_case "$c"; done
for c in VaDriveAtt VaDriveTmo VaDriveVzw VaDriveLegacy8; do run va_case "$c"; done
for c in DcDriveAtt DcDriveTmo DcDriveVzw DcDriveLegacy8; do vecs dc_case "$c"; done
for c in VaDriveAtt VaDriveTmo VaDriveVzw VaDriveLegacy8; do vecs va_case "$c"; done

echo "[$(date +%H:%M:%S)] FAMILY B v2 COMPLETE"
