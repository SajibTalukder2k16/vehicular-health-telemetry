#!/bin/bash
# AIMD against the strongest static baseline, on held-out seeds 0-9.
#
# Re-run after two corrections that invalidated the first pass:
#   - RNG stream separation, so every policy sees an identical offered
#     workload (before it drifted: vitals 1370/1326/1354 across policies)
#   - CondOutage geometry, which previously put the far site 18.9 km away and
#     tripped Simu5G's 10 km RMa validity assert on some seeds
#
# Caps are those re-tuned on development seeds 100-104 (unchanged by the
# corrections): healthy 100k, congested 400k, transient 200k, outage 200k.
# AIMD gets a 1000 kbps ceiling and adapts below it.
#
# Usage: pilot_head2head.sh <condition> <policy> [jobs]
set -u
cond=$1; pol=$2; J=${3:-5}
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NED="$ROOT/src:$ROOT/simulations:$ROOT/../inet4.7/src:$ROOT/../Simu5G/src"
LIB="$ROOT/../Simu5G/src/simu5g"
BIN="$ROOT/src/out/clang-release/paperrebuild"
OUT="$ROOT/simulations/pilot/results_h2h"
mkdir -p "$OUT"
cd "$ROOT/simulations/pilot"

case "$cond" in
    CondHealthy)   cap=100 ;;
    CondCongested) cap=400 ;;
    CondTransient) cap=200 ;;
    CondOutage)    cap=200 ;;
    *) echo "unknown condition $cond" >&2; exit 1 ;;
esac
# The adaptive policies get a 1000 kbps CEILING and adapt below it; the static
# ones get the tuned cap as their fixed rate. aimdSelf is the cross-stream
# ablation (docs/RELATED_WORK.md) and must get the identical ceiling to aimd,
# or the comparison confounds the signal source with the rate bound.
case "$pol" in
    aimd|aimdSelf) rate=1000 ;;
    *)             rate=$cap ;;
esac

n=0
for s in 0 1 2 3 4 5 6 7 8 9; do
    out="$OUT/${cond}-${pol}-s${s}.sca"
    [ -s "$out" ] && grep -q packetsGenerated "$out" 2>/dev/null && continue
    "$BIN" -u Cmdenv -c "$cond" -r 0 -n "$NED" -l "$LIB" \
        --cmdenv-express-mode=true --cmdenv-status-frequency=5000s \
        --seed-set="$s" \
        "--*.ue.app[0].admissionPolicy=\"$pol\"" \
        '--*.server.app[0].feedbackInterval=200ms' \
        "--*.ue.app[0].cameraRate=${rate}kbps" \
        '--*.ue.app[0].cameraBurst=262144B' \
        '--**.server.app[*].**.vector-recording=true' \
        --output-scalar-file="$out" \
        --output-vector-file="$OUT/${cond}-${pol}-s${s}.vec" > /dev/null 2>&1 &
    n=$((n+1)); [ $((n % J)) -eq 0 ] && wait
done
wait
echo "$cond/$pol: $(grep -l packetsGenerated "$OUT/${cond}-${pol}"-s*.sca 2>/dev/null | wc -l)/10"
