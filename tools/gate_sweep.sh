#!/bin/bash
# C4 CONFIRMATION SWEEP: does any gate configuration help the dispatch
# decision? 2,040 runs.
#
# WHY THIS RUN EXISTS
#   C4.1 and the structural null were measured at ONE inherited gate
#   configuration (cameraRate 1 Mbps, cameraBurst 65536 B, cameraMaxAge 2 s).
#   The honest limit was "the INHERITED rules do not transfer", which invites
#   the obvious reviewer response: retune it. docs/GATE_DERIVATION.md answers
#   that by DERIVING the gate's effect instead of measuring it:
#
#     Prop 1  the gate alters a burst IFF B > b            (exact)
#     Prop 2  pacing weakly INCREASES completion time, for every (b, r), by
#             work conservation -- so it can never speed dispatch under C2'
#     Prop 3  0 <= penalty <= (B - b)/r                    (a bound, NOT an
#             equality: tokens refill while the first b bytes are in flight)
#
#   This sweep does not test whether the derivation is plausible. It tries to
#   BREAK it, over the parameter space a reviewer would propose.
#
# THE ARMS
#   E4 only (138,000 B), because Prop 1 derives that nothing below E4 engages
#   at any b >= 65536 B -- and that claim is itself tested, by the b = 16 KiB
#   column, where E2' and E3 WOULD engage.
#
#     cameraBurst  16KiB 64KiB 128KiB 256KiB   (64KiB = the inherited value)
#     cameraRate   1Mbps 4Mbps 16Mbps
#
#   256 KiB = 262,144 B > 138,000 B, so the gate MUST disengage there.
#
# PREDICTIONS, RECORDED BEFORE THE RUN
#   1. POSITIVE CONTROL: b = 256KiB gives penalty EXACTLY 0.0000 against
#      policy=none, in all four conditions, on every statistic, at every rate.
#      If it does not, the derivation is wrong and nothing else here is
#      interpretable. This is the single most important cell in the sweep.
#   2. NO (b, r) yields a significant NEGATIVE penalty. Prop 2 forbids it.
#      One significant negative refutes Prop 2 -- which is why it is run.
#   3. The penalty falls monotonically in both b and r, -> 0 as b -> B or
#      r -> infinity, and stays <= (B - b)/r in every cell. At (16KiB, 1Mbps)
#      the bound is 0.9397 s; at (64KiB, 1Mbps), 0.5797 s; at (64KiB, 16Mbps),
#      0.0362 s; at 256KiB, exactly 0.
#   4. The realised FRACTION of the bound falls with condition severity
#      (measured 61/47/46/36 % at the inherited cell) at every (b, r), because
#      pacing delay hides behind radio transit.
#   5. Completeness does not improve with pacing at any (b, r) -- the Pareto
#      loss of GATE_DERIVATION.md section 5 is not an artefact of 1 Mbps.
#
# THE SECOND HALF: the cameraMaxAge axis, for C4.2
#   dropPace at E4, maxAge in {0.5, 1, 2, 4, 8} s, at the inherited (64KiB,
#   1Mbps). PREDICTION: dispatch latency improves monotonically as maxAge falls
#   while delivered fraction degrades monotonically, so the two NEVER agree.
#   That generalises C4.2 from one maxAge to the whole axis: there is no setting
#   at which dispatch latency is a safe score for a deferral policy.
#   This half also exercises the evidenceChunksStaleDropped counter added
#   2026-11-12, so the loss is attributable rather than pooled into
#   cameraStaleDropped (PHASE2_RESULT.md section 4).
#
# Usage: OUT_DIR=<dir> gate_sweep.sh [jobs]
set -u
J=${1:-12}
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NED="$ROOT/src:$ROOT/simulations:$ROOT/../inet4.7/src:$ROOT/../Simu5G/src"
LIB="$ROOT/../Simu5G/src/simu5g"
BIN="$ROOT/src/out/clang-release/paperrebuild"
OUT="${OUT_DIR:-$ROOT/simulations/pilot/results_gate}"
mkdir -p "$OUT"
cd "$ROOT/simulations/pilot"

CAM_BYTES=53167B
EV=138000          # E4 -- the only rung that engages the inherited bucket

# CAM_INTERVAL IS MANDATORY AND WAS OMITTED ONCE. The ini default is 2 Hz --
# the ORIGINAL camera rate, before C1 revised it to 60 fps for PRV. Every other
# corpus (escalation_pilot.sh, escalation_phase2.sh, edge_sensitivity.sh) sets
# it explicitly, so a run that leaves it out is at 3.53 pkt/s through the edge
# where the others are at 61.53, and is NOT comparable to them. The first
# launch of this sweep made exactly that mistake; 2,040 runs were discarded
# rather than stitched. The camera terminates at the edge, so this does not
# change uplink load -- which is why the error is invisible in the dispatch
# table and has to be caught by checking packetsForwarded.
CAM_INTERVAL=0.0166667s   # 60 fps, matching every other corpus

# Arm labels carry no '-': the result-file name parser splits on it.
# Part A: policy=pace, sweeping bucket depth x fill rate.
#   label:burstBytes:rate
ARMS_A="p16k1:16384:1Mbps   p16k4:16384:4Mbps   p16k16:16384:16Mbps \
        p64k1:65536:1Mbps   p64k4:65536:4Mbps   p64k16:65536:16Mbps \
        p128k1:131072:1Mbps p128k4:131072:4Mbps p128k16:131072:16Mbps \
        p256k1:262144:1Mbps p256k4:262144:4Mbps p256k16:262144:16Mbps"

# Part B: policy=dropPace, sweeping staleness horizon at the inherited gate.
#   label:maxAge
ARMS_B="dp05:0.5s dp1:1s dp2:2s dp4:4s dp8:8s"

# Part C: the INTERNAL baseline. policy=none bypasses the gate entirely, so
# cameraBurst and cameraRate are irrelevant and one arm serves all 12 pace
# cells. It exists so the penalty is computed WITHIN one corpus at matched
# seeds, rather than against Gate A's e4 arm in another -- the cross-corpus
# dependency is what let the camera-rate mismatch above go unnoticed.

n=0
for cond in CondHealthy CondCongested CondTransient CondOutage; do
    for spec in $ARMS_A; do
        label=${spec%%:*}; rest=${spec#*:}
        burst=${rest%%:*}; rate=${rest##*:}
        for s in $(seq 0 29); do
            "$BIN" -u Cmdenv -c "$cond" -r 0 -n "$NED" -l "$LIB" \
                --cmdenv-express-mode=true --cmdenv-status-frequency=5000s \
                --seed-set="$s" \
                '--*.ue.app[0].admissionPolicy="pace"' \
                "--*.ue.app[0].cameraTerminatesAtEdge=true" \
                "--*.ue.app[0].evidenceBytes=${EV}B" \
                "--*.ue.app[0].cameraBurst=${burst}B" \
                "--*.ue.app[0].cameraRate=${rate}" \
                "--*.rig.camera.messageLength=${CAM_BYTES}" \
                "--*.rig.camera.sendInterval=${CAM_INTERVAL}" \
                --output-scalar-file="$OUT/${cond}-${label}-s${s}.sca" \
                --output-vector-file="$OUT/${cond}-${label}-s${s}.vec" \
                > /dev/null 2>&1 &
            n=$((n+1)); [ $((n % J)) -eq 0 ] && wait
        done
    done
    for spec in $ARMS_B; do
        label=${spec%%:*}; age=${spec##*:}
        for s in $(seq 0 29); do
            "$BIN" -u Cmdenv -c "$cond" -r 0 -n "$NED" -l "$LIB" \
                --cmdenv-express-mode=true --cmdenv-status-frequency=5000s \
                --seed-set="$s" \
                '--*.ue.app[0].admissionPolicy="dropPace"' \
                "--*.ue.app[0].cameraTerminatesAtEdge=true" \
                "--*.ue.app[0].evidenceBytes=${EV}B" \
                "--*.ue.app[0].cameraMaxAge=${age}" \
                "--*.rig.camera.messageLength=${CAM_BYTES}" \
                "--*.rig.camera.sendInterval=${CAM_INTERVAL}" \
                --output-scalar-file="$OUT/${cond}-${label}-s${s}.sca" \
                --output-vector-file="$OUT/${cond}-${label}-s${s}.vec" \
                > /dev/null 2>&1 &
            n=$((n+1)); [ $((n % J)) -eq 0 ] && wait
        done
    done
    for s in $(seq 0 29); do
        "$BIN" -u Cmdenv -c "$cond" -r 0 -n "$NED" -l "$LIB" \
            --cmdenv-express-mode=true --cmdenv-status-frequency=5000s \
            --seed-set="$s" \
            '--*.ue.app[0].admissionPolicy="none"' \
            "--*.ue.app[0].cameraTerminatesAtEdge=true" \
            "--*.ue.app[0].evidenceBytes=${EV}B" \
            "--*.rig.camera.messageLength=${CAM_BYTES}" \
            "--*.rig.camera.sendInterval=${CAM_INTERVAL}" \
            --output-scalar-file="$OUT/${cond}-none-s${s}.sca" \
            --output-vector-file="$OUT/${cond}-none-s${s}.vec" \
            > /dev/null 2>&1 &
        n=$((n+1)); [ $((n % J)) -eq 0 ] && wait
    done
done
wait
echo "gate sweep runs written: $(ls "$OUT"/*.sca 2>/dev/null | wc -l) of $n"
