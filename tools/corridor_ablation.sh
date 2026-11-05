#!/bin/bash
# The cross-stream ablation on MEASURED corridor geometry.
#
# docs/ABLATION_CROSS_STREAM.md establishes on synthetic conditions that the
# self-signal arm self-deadlocks. Its stated limitation is that the contention
# on real corridors is milder than CondCongested (docs/CORRIDOR_REGIME.md), so
# the collapse should be less extreme there and the claim should not be
# generalised to real geometry without checking.
#
# This runs aimdSelf on exactly the contention-limited corridors c08-c14 that
# docs/CORRIDOR_REGIME.md identified, matching the aimd arm in
# simulations/corridorpop/results_ctl/ parameter for parameter:
#   1000 kbps ceiling, 262144 B burst, 200 ms feedback, runs 3-5
#   (= the bgues=20 arm of the $bgues iteration, 3 repetitions).
#
# Usage: corridor_ablation.sh [jobs]
set -u
J=${1:-3}
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NED="$ROOT/src:$ROOT/simulations:$ROOT/../inet4.7/src:$ROOT/../Simu5G/src"
LIB="$ROOT/../Simu5G/src/simu5g"
BIN="$ROOT/src/out/clang-release/paperrebuild"
# Scalars AND vectors both go here: --output-scalar-file alone leaves vectors
# landing in the ini's default results/, overwriting the tracked baseline .vec
# files for these configs. See the note in aimd_sensitivity.sh.
OUT="$ROOT/simulations/corridorpop/results_ctl"
mkdir -p "$OUT"
cd "$ROOT/simulations/corridorpop"

n=0
for c in c08 c09 c10 c11 c12 c13 c14; do
    for r in 3 4 5; do
        out="$OUT/${c}-aimdSelf-${r}.sca"
        [ -s "$out" ] && grep -q packetsGenerated "$out" 2>/dev/null && continue
        "$BIN" -u Cmdenv -c "$c" -r "$r" -n "$NED" -l "$LIB" \
            --cmdenv-express-mode=true --cmdenv-status-frequency=5000s \
            '--*.ue.app[0].admissionPolicy="aimdSelf"' \
            '--*.server.app[0].feedbackInterval=200ms' \
            '--*.ue.app[0].cameraRate=1000kbps' \
            '--*.ue.app[0].cameraBurst=262144B' \
            --output-scalar-file="$out" \
            --output-vector-file="$OUT/${c}-aimdSelf-${r}.vec" > /dev/null 2>&1 &
        n=$((n+1)); [ $((n % J)) -eq 0 ] && wait
    done
done
wait
echo "corridor ablation: $(grep -l packetsGenerated "$OUT"/*aimdSelf*.sca 2>/dev/null | wc -l)/21"
