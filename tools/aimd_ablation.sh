#!/bin/bash
# Is the CROSS-STREAM freshness signal load-bearing?
#
# A reviewer who knows A3L-FEC (arXiv:2410.05852), which drives sender rate
# from the receiver-measured age violation of the stream being adapted, asks
# the obvious question: why must the signal come from a DIFFERENT stream? Just
# measure the throttled stream's own freshness. See docs/RELATED_WORK.md.
#
# aimdSelf is aimd with one substituted field -- freshestCamera in place of
# freshestVitals -- and nothing else changed: same control law, same ceiling,
# same target, increment and backoff. So the only difference between the two
# arms is where the harm signal comes from.
#
# Both arms are re-run here rather than reusing simulations/pilot/results_h2h,
# for two reasons: the verified head-to-head results stay untouched, and both
# arms get bucketRate vector recording, without which the result -- whether
# the rate climbs or collapses to the probe floor -- is invisible.
#
# Note on the shared freshnessTarget: camera is generated every 0.5 s against
# vitals' exponential(1 s), so camera's age floor is LOWER and 5 s is the
# generous setting for aimdSelf, not a handicap. aimd_ablation_sweep.sh sweeps
# it anyway so the outcome cannot be a tuning artifact.
#
# Usage: aimd_ablation.sh [jobs]
set -u
J=${1:-4}
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NED="$ROOT/src:$ROOT/simulations:$ROOT/../inet4.7/src:$ROOT/../Simu5G/src"
LIB="$ROOT/../Simu5G/src/simu5g"
BIN="$ROOT/src/out/clang-release/paperrebuild"
OUT="$ROOT/simulations/pilot/results_ablation"
mkdir -p "$OUT"
cd "$ROOT/simulations/pilot"

n=0
for cond in CondHealthy CondCongested CondTransient CondOutage; do
    for pol in aimd aimdSelf; do
        for s in 0 1 2 3 4 5 6 7 8 9; do
            out="$OUT/${cond}-${pol}-s${s}.sca"
            [ -s "$out" ] && grep -q packetsGenerated "$out" 2>/dev/null && continue
            "$BIN" -u Cmdenv -c "$cond" -r 0 -n "$NED" -l "$LIB" \
                --cmdenv-express-mode=true --cmdenv-status-frequency=5000s \
                --seed-set="$s" \
                "--*.ue.app[0].admissionPolicy=\"$pol\"" \
                '--*.server.app[0].feedbackInterval=200ms' \
                '--*.ue.app[0].cameraRate=1000kbps' \
                '--*.ue.app[0].cameraBurst=262144B' \
                '--*.ue.app[0].**.vector-recording=true' \
                --output-scalar-file="$out" \
                --output-vector-file="$OUT/${cond}-${pol}-s${s}.vec" > /dev/null 2>&1 &
            n=$((n+1)); [ $((n % J)) -eq 0 ] && wait
        done
    done
done
wait
echo "ablation runs: $(grep -l packetsGenerated "$OUT"/*.sca 2>/dev/null | wc -l)/80"
