#!/bin/bash
# AIMD parameter sensitivity, on DEVELOPMENT seeds (100-102) only.
#
# The headline AIMD result used first-guess parameters -- 5 s freshness
# target, 40 kbps increment, 0.7 backoff -- that were never tuned. That is
# favourable framing only if the result survives perturbation: if +44 pp of
# camera collapses at a 4 s or 7 s target, it was luck.
#
# One-at-a-time around the baseline rather than a full factorial: 7 distinct
# settings, two informative conditions, three dev seeds = 42 runs.
#
# Usage: aimd_sensitivity.sh [jobs]
set -u
J=${1:-5}
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NED="$ROOT/src:$ROOT/simulations:$ROOT/../inet4.7/src:$ROOT/../Simu5G/src"
LIB="$ROOT/../Simu5G/src/simu5g"
BIN="$ROOT/src/out/clang-release/paperrebuild"
# Both scalar AND vector output must be redirected here. Passing only
# --output-scalar-file leaves vectors going to the ini's default results/
# directory, where they overwrite the tracked baseline .vec files for this
# config under a different policy's data. Fixed 2026-10-28 after this script's
# pattern was copied into the ablation runners and did exactly that.
OUT="$ROOT/simulations/pilot/results_sens_aimd"
mkdir -p "$OUT"
cd "$ROOT/simulations/pilot"

SEEDS="100 101 102"

# tag:target:increment:backoff  (base is the shared baseline point)
SETTINGS="base:5:40:0.7 tgt3:3:40:0.7 tgt7:7:40:0.7 inc20:5:20:0.7 inc80:5:80:0.7 bo50:5:40:0.5 bo85:5:40:0.85"

n=0
for cond in CondCongested CondTransient; do
    for set in $SETTINGS; do
        tag=${set%%:*}; rest=${set#*:}
        tgt=${rest%%:*}; rest=${rest#*:}
        inc=${rest%%:*}; bo=${rest#*:}
        for s in $SEEDS; do
            out="$OUT/${cond}-${tag}-s${s}.sca"
            [ -s "$out" ] && grep -q packetsGenerated "$out" 2>/dev/null && continue
            "$BIN" -u Cmdenv -c "$cond" -r 0 -n "$NED" -l "$LIB" \
                --cmdenv-express-mode=true --cmdenv-status-frequency=5000s \
                --seed-set="$s" \
                '--*.ue.app[0].admissionPolicy="aimd"' \
                '--*.server.app[0].feedbackInterval=200ms' \
                '--*.ue.app[0].cameraRate=1000kbps' \
                '--*.ue.app[0].cameraBurst=262144B' \
                "--*.ue.app[0].freshnessTarget=${tgt}s" \
                "--*.ue.app[0].probeIncrement=${inc}kbps" \
                "--*.ue.app[0].backoffFactor=${bo}" \
                --output-scalar-file="$out" \
                --output-vector-file="$OUT/${cond}-${tag}-s${s}.vec" > /dev/null 2>&1 &
            n=$((n+1)); [ $((n % J)) -eq 0 ] && wait
        done
    done
done
wait
echo "sensitivity runs: $(ls "$OUT"/*.sca 2>/dev/null | wc -l)/42"
