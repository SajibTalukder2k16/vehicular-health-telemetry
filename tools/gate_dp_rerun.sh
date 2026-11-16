#!/bin/bash
# Re-run ONLY the dropPace arms of the gate sweep, after the 2026-11-12
# staleness-timestamp fix in EdgeApp.cc (getCreationTime, not getArrivalTime).
#
# WHY
#   The staleness test was `simTime() - head->getArrivalTime() > cameraMaxAge`.
#   Evidence is built with `new` inside escalate() and handed on by function
#   call -- never SENT -- so its arrival time is never stamped and reads 0.
#   The test therefore degenerated to `simTime() > cameraMaxAge`: once the
#   clock passed maxAge, EVERY pending chunk was discarded no matter how long
#   it had actually waited. That is what produced C4.2's headline
#   "dropPace delivers only 45-47% of the evidence". It was an artefact.
#
#   Proof, before and after, CondCongested seed 3, 792 chunks emitted:
#     before, maxAge 8s    -> 416 stale-dropped, 365 received
#     before, maxAge 2000s ->   0 stale-dropped, 785 received   (> sim horizon)
#     after,  maxAge 0.5s  ->  64 stale-dropped, 719 received
#     after,  maxAge 2s    ->   0 stale-dropped, 785 received
#
# WHAT IS NOT RE-RUN, AND WHY THAT IS SAFE
#   The 12 pace arms and the `none` baseline -- 1,560 runs -- are untouched by
#   this fix. POLICY_PACE never reaches a staleness branch: one is guarded by
#   `policy == POLICY_DROPPACE` in drainPending(), the other by
#   dropsStaleCamera() in the closed-loop path, which pace does not use. Those
#   runs already confirmed all three propositions of GATE_DERIVATION.md and
#   stand as measured.
#
# PREDICTION, RECORDED BEFORE THE RUN -- GATE_DERIVATION.md Prop 4
#   Staleness discard fires IFF cameraMaxAge < drain time = (B - b)/r.
#   At B=138,000 B, b=65,536 B, r=1 Mbps the drain is 0.5797 s, so:
#     maxAge 0.5 s        -> fires, but only on the tail past 0.5 s
#     maxAge 1, 2, 4, 8 s -> NEVER fires; delivered fraction equals the `none`
#                            arm, and dispatch latency equals it too
#   i.e. the inherited cameraMaxAge = 2 s is a THIRD structural no-op, after
#   the bucket (Prop 1) and pacing's Pareto loss (Props 2-3). If that holds,
#   all three inherited gate parameters do nothing useful on evidence traffic.
#
# Usage: OUT_DIR=<dir> gate_dp_rerun.sh [jobs]
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
CAM_INTERVAL=0.0166667s      # 60 fps -- mandatory, see gate_sweep.sh
EV=138000

n=0
for cond in CondHealthy CondCongested CondTransient CondOutage; do
    for spec in dp05:0.5s dp1:1s dp2:2s dp4:4s dp8:8s; do
        label=${spec%%:*}
        age=${spec##*:}
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
done
wait
echo "dropPace re-run written: $n of 600"
