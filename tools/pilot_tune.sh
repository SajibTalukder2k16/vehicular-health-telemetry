#!/bin/bash
# Tune the static camera cap per condition, on DEVELOPMENT seeds only.
#
# The evaluation uses seed-set 0..9 (the default, via seed-set = ${repetition}).
# Tuning here uses seed-set 100..104, so the cap is never chosen on the seeds
# it is later judged on.
#
# cameraBurst is raised to 262144 B (4+ frames) because the 65536 B default
# holds only 1.07 of a 61440 B frame, which burst-limits the drop policy above
# ~600 kbps and would make the sweep meaningless at the top end.
#
# Usage: pilot_tune.sh [jobs]
set -u
J=${1:-8}
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NED="$ROOT/src:$ROOT/simulations:$ROOT/../inet4.7/src:$ROOT/../Simu5G/src"
LIB="$ROOT/../Simu5G/src/simu5g"
BIN="$ROOT/src/out/clang-release/paperrebuild"
OUT="$ROOT/simulations/pilot/results_tune"
mkdir -p "$OUT"
cd "$ROOT/simulations/pilot"

DEV_SEEDS="100 101 102 103 104"
BURST=262144

run_one() {   # condition rate seed
    local cond=$1 rate=$2 seed=$3
    "$BIN" -u Cmdenv -c "$cond" -r 0 -n "$NED" -l "$LIB" \
        --cmdenv-express-mode=true --cmdenv-status-frequency=5000s \
        --seed-set="$seed" \
        '--*.ue.app[0].admissionPolicy="drop"' \
        "--*.ue.app[0].cameraRate=${rate}kbps" \
        "--*.ue.app[0].cameraBurst=${BURST}B" \
        --output-scalar-file="$OUT/${cond}-r${rate}-s${seed}.sca" \
        --output-vector-file="$OUT/${cond}-r${rate}-s${seed}.vec" \
        > /dev/null 2>&1
}

n=0
for cond in CondCongested CondTransient CondOutage; do
    for rate in 200 400 600 800 1000; do
        for s in $DEV_SEEDS; do
            run_one "$cond" "$rate" "$s" &
            n=$((n+1)); [ $((n % J)) -eq 0 ] && wait
        done
    done
done
# the healthy condition carries 4 KiB frames (~66 kbps offered), so only low
# caps are meaningful there
for rate in 50 100 200; do
    for s in $DEV_SEEDS; do
        run_one CondHealthy "$rate" "$s" &
        n=$((n+1)); [ $((n % J)) -eq 0 ] && wait
    done
done
wait
echo "tuning runs written: $(ls "$OUT"/*.sca 2>/dev/null | wc -l)"
