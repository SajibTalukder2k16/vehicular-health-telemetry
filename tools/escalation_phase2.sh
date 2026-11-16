#!/bin/bash
# PHASE 2, re-specified (docs/PLAN_2026-11.md §10). Two questions, 480 runs.
#
# Phase 2's original spec -- sweep evidence volume x deferral policy -- lost
# both its axes when C2 was refuted. The volume axis was answered for free from
# the Gate A corpus (docs/VERIFICATION_FRONTIER.md). What remains is:
#
# QUESTION 1 -- the E2' rung, 120 runs.
#   The paper's central design rule is "verify from the waveform, never from the
#   image". Its size depends on the HRV analysis window W, and W is now sourced
#   rather than presumed: Munoz et al., PLOS ONE 10(9):e0138921, 2015 (N=3,387,
#   PREVEND) recommends 30 s for SDNN and 10 s for RMSSD, but states that its
#   "conclusions do not apply to HRV parameters in the frequency domain"
#   because HF needs >=60 s and LF >=120 s. C1's variability case uses LF/HF.
#
#   So the rung that the frequency-domain case actually requires is W = 120 s:
#       120 s x 30 Hz x 4 B = 14,400 B
#   against E2's 3,584 B (W = 30 s) -- derived identically, see
#   docs/PARAMETER_PROVENANCE.md §A.5. 14,400 B falls BETWEEN the measured E2
#   and E3 arms, and the design rule is a claim about exactly that point, so it
#   is measured here rather than interpolated.
#
# QUESTION 2 -- does deferral still help? 360 runs.
#   C4.1 (volume reduction beats temporal spreading) and C4.2 (staleness
#   discard is free) were measured as ALERT protection rules, under the traffic
#   model C1 invalidates. Under C2' the alert needs no protection -- it arrives
#   sooner when evidence accompanies it -- and dispatch waits on the evidence.
#   Deferring or discarding evidence can therefore only delay or defeat
#   verification. PREDICTION, RECORDED BEFORE THE RUN: both rules invert.
#
#   RQ4's actual wording is "do the gate's existing design rules transfer to
#   evidence scheduling?", so the gate keeps its EXISTING settings from the
#   mechanism layer rather than being retuned for evidence. Those are the
#   EdgeApp.ned defaults, which this ini does not override:
#       cameraRate 1Mbps, cameraBurst 65536B, cameraQueueCapacity 262144B,
#       cameraMaxAge 2s
#
#   THE BUCKET ARITHMETIC MATTERS, AND IT DECIDES THE ARM SET.
#   A burst smaller than the bucket depth is admitted whole, instantly, so
#   pacing is a NO-OP by construction:
#       E1   512 B  <  65536 B  -> no-op
#       E2  3584 B  <  65536 B  -> no-op
#       E2' 14400 B <  65536 B  -> no-op
#       E3 57344 B  <  65536 B  -> no-op        <-- note this
#       E4 138000 B >  65536 B  -> 72464 B must wait for tokens at 1 Mbps
#                                  (125 kB/s) = ~0.58 s of pacing
#   So the inherited gate DOES NOT ENGAGE AT ALL below E4. E3/pace is run
#   anyway, as the explicit demonstration of that no-op -- a null that is
#   structural rather than statistical, and worth showing rather than asserting.
#
#   dropPace adds cameraMaxAge = 2 s. Under C2' discarding stale evidence does
#   not cost latency, it costs VERIFICATION: the server never receives what it
#   needs and cannot dispatch at all. Expect failures to replace delays, which
#   is the "principled" half of C4.2 turning into the harmful half.
#
# ARMS: e2b/none, e3/pace, e4/pace, e4/dropPace -- 4 arms x 4 conditions x 30
# seeds = 480 runs. Seeds 0-29, matched to the Gate A corpus, so e2b pairs
# directly against that corpus's ref/E2/E3 arms and the pace/dropPace arms pair
# against its policy-none arms at the same rung.
#
# Usage: OUT_DIR=<dir> escalation_phase2.sh [jobs]
set -u
J=${1:-8}
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NED="$ROOT/src:$ROOT/simulations:$ROOT/../inet4.7/src:$ROOT/../Simu5G/src"
LIB="$ROOT/../Simu5G/src/simu5g"
BIN="$ROOT/src/out/clang-release/paperrebuild"
OUT="${OUT_DIR:-$ROOT/simulations/pilot/results_phase2}"
mkdir -p "$OUT"
cd "$ROOT/simulations/pilot"

# identical to the Gate A pilot, so the corpora are comparable
CAM_INTERVAL=0.0166667s
CAM_BYTES=53167B

# label:bytes:policy
ARMS="e2b:14400:none e3:57344:pace e4:138000:pace e4dp:138000:dropPace"

n=0
for cond in CondHealthy CondCongested CondTransient CondOutage; do
    for spec in $ARMS; do
        label=${spec%%:*}
        rest=${spec#*:}
        bytes=${rest%%:*}
        pol=${rest##*:}
        for s in $(seq 0 29); do
            "$BIN" -u Cmdenv -c "$cond" -r 0 -n "$NED" -l "$LIB" \
                --cmdenv-express-mode=true --cmdenv-status-frequency=5000s \
                --seed-set="$s" \
                "--*.ue.app[0].admissionPolicy=\"${pol}\"" \
                "--*.ue.app[0].cameraTerminatesAtEdge=true" \
                "--*.ue.app[0].evidenceBytes=${bytes}B" \
                "--*.rig.camera.sendInterval=${CAM_INTERVAL}" \
                "--*.rig.camera.messageLength=${CAM_BYTES}" \
                --output-scalar-file="$OUT/${cond}-${label}-s${s}.sca" \
                --output-vector-file="$OUT/${cond}-${label}-s${s}.vec" \
                > /dev/null 2>&1 &
            n=$((n+1)); [ $((n % J)) -eq 0 ] && wait
        done
    done
done
wait
echo "phase 2 runs written: $(ls "$OUT"/*.sca 2>/dev/null | wc -l) of $n"
