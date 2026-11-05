#!/bin/bash
# Pilot evaluation on HELD-OUT seeds (seed-set 0..9), at the per-condition cap
# tuned in tools/pilot_tune.sh on development seeds 100..104:
#
#   CondHealthy    100 kbps
#   CondCongested  400 kbps
#   CondTransient  200 kbps
#   CondOutage     200 kbps
#
# Four working policies x four conditions x ten seeds = 160 runs. The three
# closed-loop policies are excluded: both feedback-driven designs are
# degenerate (see docs/PILOT_CONDITIONS.md) and would contribute nothing but
# zeros until the two pathologies are fixed.
#
# cameraBurst is 262144 B so the drop policy is not burst-limited.
#
# Usage: pilot_eval.sh [jobs]
set -u
J=${1:-8}
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NED="$ROOT/src:$ROOT/simulations:$ROOT/../inet4.7/src:$ROOT/../Simu5G/src"
LIB="$ROOT/../Simu5G/src/simu5g"
BIN="$ROOT/src/out/clang-release/paperrebuild"
OUT="$ROOT/simulations/pilot/results_eval"
mkdir -p "$OUT"
cd "$ROOT/simulations/pilot"

BURST=262144
cap_for() {
    case "$1" in
        CondHealthy)   echo 100 ;;
        CondCongested) echo 400 ;;
        CondTransient) echo 200 ;;
        CondOutage)    echo 200 ;;
    esac
}

n=0
for cond in CondHealthy CondCongested CondTransient CondOutage; do
    rate=$(cap_for "$cond")
    for pol in none drop pace dropPace; do
        for s in 0 1 2 3 4 5 6 7 8 9; do
            "$BIN" -u Cmdenv -c "$cond" -r 0 -n "$NED" -l "$LIB" \
                --cmdenv-express-mode=true --cmdenv-status-frequency=5000s \
                --seed-set="$s" \
                "--*.ue.app[0].admissionPolicy=\"$pol\"" \
                "--*.ue.app[0].cameraRate=${rate}kbps" \
                "--*.ue.app[0].cameraBurst=${BURST}B" \
                --output-scalar-file="$OUT/${cond}-${pol}-s${s}.sca" \
                --output-vector-file="$OUT/${cond}-${pol}-s${s}.vec" \
                > /dev/null 2>&1 &
            n=$((n+1)); [ $((n % J)) -eq 0 ] && wait
        done
    done
done
wait
echo "evaluation runs written: $(ls "$OUT"/*.sca 2>/dev/null | wc -l)"
