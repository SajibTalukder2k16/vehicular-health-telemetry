#!/bin/bash
# Does aimdSelf fail because the self-signal is broken, or because 5 s was the
# wrong target for it?
#
# aimd_ablation.sh runs both arms at the shared 5 s target. That is the fair
# single-variable comparison, but it invites the reply that the ablation was
# simply mistuned -- the same objection we had to answer for the static cap,
# which is why the static baseline is tuned per condition.
#
# So sweep the target for aimdSelf alone, wide. The two tails are informative
# in opposite directions:
#
#   small target -> backs off constantly, rate pinned at the probe floor,
#                   camera starved. Control that does nothing but throttle.
#   large target -> almost never backs off, rate climbs to the ceiling, and
#                   the policy degenerates into FIFO. Control that does
#                   nothing at all.
#
# The claim to test is not "aimdSelf is always worse on camera" -- at a loose
# enough target it trivially delivers camera by not controlling. It is that NO
# target reaches the joint point aimd reaches, because the self-signal cannot
# distinguish "the link is congested" from "I throttled myself". Both metrics
# are therefore reported per setting, not just camera.
#
# Dev seeds 100-102, so the held-out seeds 0-9 stay held out.
#
# Usage: aimd_ablation_sweep.sh [jobs]
set -u
J=${1:-4}
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NED="$ROOT/src:$ROOT/simulations:$ROOT/../inet4.7/src:$ROOT/../Simu5G/src"
LIB="$ROOT/../Simu5G/src/simu5g"
BIN="$ROOT/src/out/clang-release/paperrebuild"
# Scalars AND vectors both go here -- see the note in aimd_sensitivity.sh.
OUT="$ROOT/simulations/pilot/results_ablation_sweep"
mkdir -p "$OUT"
cd "$ROOT/simulations/pilot"

TARGETS="1 2 3 5 7 10 20"
SEEDS="100 101 102"

n=0
for cond in CondCongested CondTransient; do
    for tgt in $TARGETS; do
        for s in $SEEDS; do
            out="$OUT/${cond}-tgt${tgt}-s${s}.sca"
            [ -s "$out" ] && grep -q packetsGenerated "$out" 2>/dev/null && continue
            "$BIN" -u Cmdenv -c "$cond" -r 0 -n "$NED" -l "$LIB" \
                --cmdenv-express-mode=true --cmdenv-status-frequency=5000s \
                --seed-set="$s" \
                '--*.ue.app[0].admissionPolicy="aimdSelf"' \
                '--*.server.app[0].feedbackInterval=200ms' \
                '--*.ue.app[0].cameraRate=1000kbps' \
                '--*.ue.app[0].cameraBurst=262144B' \
                "--*.ue.app[0].freshnessTarget=${tgt}s" \
                --output-scalar-file="$out" \
                --output-vector-file="$OUT/${cond}-tgt${tgt}-s${s}.vec" > /dev/null 2>&1 &
            n=$((n+1)); [ $((n % J)) -eq 0 ] && wait
        done
    done
done
wait
echo "sweep runs: $(grep -l packetsGenerated "$OUT"/*.sca 2>/dev/null | wc -l)/42"
