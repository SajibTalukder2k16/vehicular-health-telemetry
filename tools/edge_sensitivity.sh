#!/bin/bash
# M4 SENSITIVITY: what does a correctly-sourced edge processing time do to
# time-to-dispatch? 480 runs.
#
# WHY THIS RUN EXISTS
#   The ini's `*.rig.edge.processingTime = uniform(0.5ms, 2ms)` is unsourced and
#   11-190x too fast (docs/PARAMETER_PROVENANCE.md §A.2). Under C2' the edge sits
#   INSIDE the dispatch budget -- C1 assigns the inference to the edge, and the
#   server cannot verify until the edge has produced both the alert and the
#   evidence -- so this parameter biases the paper's headline quantity rather
#   than a side figure. Until it is priced, NO absolute time-to-dispatch is
#   reportable.
#
#   It is run as a two-level factor rather than a new default, so the 2,280
#   escalation runs already on disk keep their meaning and remain comparable.
#
# THE TWO LEVELS, both measured, both from the same paper
#   Kim M, Koo J, "Embedded System Performance Analysis for Implementing a
#   Portable Drowsiness Detection System for Drivers", Technologies 2023,
#   11(1):8 (arXiv:2209.15148). Average total processing time to run the
#   drowsiness detection model:
#       PC-class  (Beelink Mini PC)  22.73 ms
#       embedded  (Jetson Nano)      94.27 ms
#   Constants, not distributions: the paper reports means, and its per-stage
#   tables did not survive text extraction, so inventing a spread around them
#   would be inventing a number. The existing uniform(0.5ms, 2ms) arm supplies
#   the "what if the edge were free" end of the comparison.
#
# A WALL FOUND BEFORE THE RUN, WHICH CHANGED ITS DESIGN
#   A probe at 94.27 ms exposed something the latency question had hidden. The
#   edge consumes camera frames -- C1 terminates them there -- so the per-frame
#   inference cost must fit the frame interval, or the queue grows without
#   bound. Measured in the probe: 69,673 of 84,186 packets DROPPED, 82.8%, with
#   only 14,513 of 82,083 camera frames forwarded. The arithmetic needs no
#   simulator:
#
#       grade                fps   budget/frame   PC 22.73ms   embedded 94.27ms
#       PRV (C1 requires)     60      16.67 ms    1.36x OVER      5.66x OVER
#       common HRV figure     30      33.33 ms    fits            2.83x OVER
#       HR floor              20      50.00 ms    fits            1.89x OVER
#
#       sustainable rate: PC-class 44.0 fps, embedded 10.6 fps
#
#   So NEITHER measured platform sustains PRV-grade sensing, and the embedded
#   one does not reach the 20 fps HR floor. That is a THIRD capacity wall, on
#   compute, derived exactly as C1 derives the link walls -- and it squeezes C1
#   from the other side: PRV-grade camera sensing is infeasible in the cloud
#   (link) AND at this edge (compute), on these numbers.
#
#   CAVEAT, and it matters: Kim & Koo measure a blink-based drowsiness pipeline,
#   not rPPG PRV extraction. Using their per-frame cost as the rPPG cost is an
#   extrapolation, and the wall is indicative rather than settled. Closing it
#   needs a measured per-frame cost for an rPPG-PRV pipeline, which this project
#   does not have and will not invent.
#
# THE RUNGS, AND WHY THERE ARE TWO FRAME RATES
#   E2' (14,400 B) and E4 (138,000 B) at policy none -- the two rungs the
#   paper's claims rest on: the waveform rung at the W that LF/HF requires, and
#   the image-plus rung where the modality cost is largest. Both already exist
#   at the unsourced edge value (E2' in results_phase2/, E4 in
#   results_escalation_vec/), so each 60 fps arm has a matched baseline at the
#   same seeds.
#
#   But a saturated edge answers the latency question with a queue overflow
#   rather than a latency shift. So the arm set has two halves:
#
#     60 fps (PRV-grade, as every prior run) -- shows the wall, and measures
#       what a sourced edge does to dispatch when the edge cannot keep up.
#     30 fps + matched baseline -- the largest common frame rate that PC-class
#       inference FITS (22.73 ms <= 33.33 ms). This is where the clean
#       edge-latency sensitivity can be read, because nothing is shedding.
#       Note that 30 fps is the "common figure for variability" the plan's §5.1
#       cites before Cerina revises it to 60 for PRV -- so this half is
#       HRV-grade, not PRV-grade, and that is the point: it is the regime in
#       which the architecture actually runs.
#
# PREDICTION, RECORDED BEFORE THE RUN
#   The shift should be first-order ADDITIVE -- about +21 ms at PC-class and
#   +93 ms at embedded on every absolute delay -- and the dispatch GAP should be
#   close to INVARIANT, because the alert and its evidence are both produced at
#   the edge and shift together. If that holds, every contrast reported so far
#   survives untouched and only the absolute numbers move.
#   If the gap is NOT invariant, the cause is second-order: moving the
#   escalation instant by tens of milliseconds makes it meet different radio
#   conditions, which matters most in CondTransient and CondOutage where
#   coverage changes fastest. Either outcome is worth having.
#
# Usage: OUT_DIR=<dir> edge_sensitivity.sh [jobs]
set -u
J=${1:-12}
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NED="$ROOT/src:$ROOT/simulations:$ROOT/../inet4.7/src:$ROOT/../Simu5G/src"
LIB="$ROOT/../Simu5G/src/simu5g"
BIN="$ROOT/src/out/clang-release/paperrebuild"
OUT="${OUT_DIR:-$ROOT/simulations/pilot/results_edge}"
mkdir -p "$OUT"
cd "$ROOT/simulations/pilot"

CAM_BYTES=53167B

# Arm labels carry no '-': the result-file name parser splits on it.
# label:bytes:edgeProcessingTime:cameraInterval
ARMS="e2bPC:14400:22.73ms:0.0166667s \
      e2bEMB:14400:94.27ms:0.0166667s \
      e4PC:138000:22.73ms:0.0166667s \
      e4EMB:138000:94.27ms:0.0166667s \
      e2bB30:14400:uniform(0.5ms,2ms):0.0333333s \
      e2bPC30:14400:22.73ms:0.0333333s \
      e4B30:138000:uniform(0.5ms,2ms):0.0333333s \
      e4PC30:138000:22.73ms:0.0333333s"

n=0
for cond in CondHealthy CondCongested CondTransient CondOutage; do
    for spec in $ARMS; do
        label=${spec%%:*}
        rest=${spec#*:}
        bytes=${rest%%:*}
        rest2=${rest#*:}
        edge=${rest2%%:*}
        caminterval=${rest2##*:}
        for s in $(seq 0 29); do
            "$BIN" -u Cmdenv -c "$cond" -r 0 -n "$NED" -l "$LIB" \
                --cmdenv-express-mode=true --cmdenv-status-frequency=5000s \
                --seed-set="$s" \
                '--*.ue.app[0].admissionPolicy="none"' \
                "--*.ue.app[0].cameraTerminatesAtEdge=true" \
                "--*.ue.app[0].evidenceBytes=${bytes}B" \
                "--*.rig.edge.processingTime=${edge}" \
                "--*.rig.camera.sendInterval=${caminterval}" \
                "--*.rig.camera.messageLength=${CAM_BYTES}" \
                --output-scalar-file="$OUT/${cond}-${label}-s${s}.sca" \
                --output-vector-file="$OUT/${cond}-${label}-s${s}.vec" \
                > /dev/null 2>&1 &
            n=$((n+1)); [ $((n % J)) -eq 0 ] && wait
        done
    done
done
wait
echo "edge sensitivity runs written: $(ls "$OUT"/*.sca 2>/dev/null | wc -l) of $n"
