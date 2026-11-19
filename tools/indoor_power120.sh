#!/bin/sh
# 120 seeds: resolve the two contrasts that 30 seeds could not.
#
# WHY THIS RUN EXISTS
#   Two results in docs/INDOOR_BACKHAUL_RESULT.md are reported as failures to
#   detect rather than as effects, because 30 seeds yield only ~1.2
#   escalations per run and 18-20 usable per-seed medians per cell:
#
#     Q1  the gap step from a stationary unloaded cellular edge to a mobile
#         loaded one: 1.54x, p = 0.156
#     Q2  the cold/warm grant mechanism -- a run's FIRST escalation slower
#         than those after it: 2.10x, p = 0.262
#     Q3  (bonus, same corpus) completion over the backhaul step:
#         100 % against 91.4 %, clustered p = 0.081
#
#   Quadrupling the seeds roughly halves the standard errors. If these effect
#   sizes are real they should resolve; if they do not, the effects are
#   smaller than the point estimates suggest, which is equally worth knowing.
#
# WHAT 120 SEEDS DOES **NOT** FIX
#   Power is not validity. Q1 still changes mobility, load and the
#   observation window together, so a significant result there licenses
#   "these three together move the gap", never "mobility moves the gap". And
#   nothing here varies coverage alone, so the withdrawn coverage attribution
#   of section 8a stays withdrawn no matter how this comes out.
#
# THERE IS NO PAYLOAD CONFOUND -- CORRECTED 2026-11-18
#   An earlier version of this header said the cellular corpus ran its camera
#   at 4 KiB in CondHealthy against 53,167 B indoors, and this driver left
#   CondHealthy at its ini default to "match". That was WRONG and the
#   validator caught it: seeds 0-29 gave 25/12 complete/lost against a
#   published 31/6.
#
#   The error came from trusting analysis/escalation_vec/config_manifest.csv,
#   which records 4KiB for CondHealthy. A .sca carries TWO `config` lines for
#   an overridden parameter -- the override and the ini line -- and the
#   manifest kept the ini one. The authoritative value is the `par` line, and
#   in the published corpus it reads:
#
#     par CorridorNet.rig.camera messageLength 53167B
#
#   for ALL FOUR conditions, in both the ladder and the gate corpora. The
#   payload was always matched. CondHealthy is therefore run at 53,167 B
#   here, like everything else.
#
#   The 4 KiB arm is kept as a SENSITIVITY check on payload, which is all it
#   ever was, not as a confound correction.
#
# BUILT-IN VALIDATION
#   Seeds 0-29 are the same seed-sets the published corpora used, so the
#   first 30 seeds of each arm MUST reproduce the published numbers exactly.
#   tools/verify_power120.py checks that before any 120-seed number is
#   believed. If it fails, something other than the seed count changed and
#   nothing here is interpretable.
#
# PREDICTIONS, RECORDED BEFORE THE RUN (2026-11-18)
#   P1  Seeds 0-29 reproduce the published cells exactly: indoor LTE E4 gap
#       0.0680 pooled / 0.1320 per-seed, completion 32/35; RoomMatched5GHz
#       E4 gap 0.0350, completion 35/35; CondHealthy E4 gap 0.1920,
#       completion 31/37.
#   P2  Q1 becomes significant. z scales about as sqrt(n): z = 1.418 at
#       n = 20/18 implies z ~ 2.8 at n ~ 80/72, so p ~ 0.005. If p stays
#       above 0.05 the 1.54x point estimate was optimistic.
#   P3  Q2 becomes significant but marginally -- z = 1.121 scales to ~2.2,
#       p ~ 0.03. This is the one I expect to be closest to the line.
#   P4  Q3 becomes significant: clustered p = 0.081 should fall to ~0.005.
#   P5  The POINT ESTIMATES barely move. 30 seeds is thin for a p-value but
#       not biased, so I expect the ratios to stay inside 1.3-1.8x (Q1) and
#       1.8-2.4x (Q2). If a ratio moves a lot, the 30-seed estimate was
#       unstable and the published table needs a note.
#
#   SCORE THESE HONESTLY. P5 is the one that would most embarrass the
#   published tables, which is why it is written down.
set -e

ROOT=$(cd "$(dirname "$0")/.." && pwd)
BIN="$ROOT/src/out/clang-release/paperrebuild"
NED="$ROOT/src:$ROOT/simulations:$ROOT/../inet4.7/src:$ROOT/../Simu5G/src"
LIB="$ROOT/../Simu5G/src/simu5g"
SEEDS=${SEEDS:-119}            # 0..119
J=${J:-12}
ARMS="ref:0 e1:512 e2:3584 e3:57344 e4:138000"
CAM_INTERVAL=0.0166667s

[ -x "$BIN" ] || { echo "build src/ first: $BIN missing" >&2; exit 1; }

n=0
throttle() { n=$((n+1)); if [ $((n % J)) -eq 0 ]; then wait; fi; return 0; }

# ---- the two CorridorNet arms + CondHealthy --------------------------
# This network names its server `server`, which the pilot ini's selective
# vector-recording block already matches, so no recording overrides here.
# The edge app is ue.app[0]: in CorridorNet the UE IS the edge device.
cell_pilot() {       # cell_pilot <tag> <config> <cam bytes|->
    tag=$1; cfg=$2; cam=$3
    OUT="$ROOT/simulations/pilot/results_$tag"
    mkdir -p "$OUT"
    cd "$ROOT/simulations/pilot"
    for arm in $ARMS; do
        label=${arm%%:*}; bytes=${arm##*:}
        for s in $(seq 0 "$SEEDS"); do
            if [ "$cam" = "-" ]; then
                set -- "--*.rig.camera.sendInterval=${CAM_INTERVAL}"
            else
                set -- "--*.rig.camera.sendInterval=${CAM_INTERVAL}" \
                       "--*.rig.camera.messageLength=${cam}"
            fi
            "$BIN" -u Cmdenv -c "$cfg" -r 0 -n "$NED" -l "$LIB" \
                -f "$ROOT/simulations/pilot/omnetpp.ini" \
                --cmdenv-express-mode=true --cmdenv-status-frequency=5000s \
                --seed-set="$s" \
                '--*.ue.app[0].admissionPolicy="none"' \
                "--*.ue.app[0].cameraTerminatesAtEdge=true" \
                "--*.ue.app[0].evidenceBytes=${bytes}B" \
                "$@" \
                --output-scalar-file="$OUT/${cfg}-${label}-s${s}.sca" \
                --output-vector-file="$OUT/${cfg}-${label}-s${s}.vec" \
                > /dev/null 2>&1 &
            throttle
        done
    done
    wait
    echo "$tag: $(ls "$OUT"/*.sca 2>/dev/null | wc -l) runs"
}

# ---- the room arm ----------------------------------------------------
# RoomNet names its server `cloud`, so the two recording overrides are what
# make the escalation vectors exist at all. Without them every run completes
# and records nothing.
cell_room() {
    OUT="$ROOT/simulations/room/results_room5g_120"
    mkdir -p "$OUT"
    cd "$ROOT/simulations/room"
    for arm in $ARMS; do
        label=${arm%%:*}; bytes=${arm##*:}
        for s in $(seq 0 "$SEEDS"); do
            "$BIN" -u Cmdenv -c RoomMatched5GHz -r 0 -n "$NED" -l "$LIB" \
                -f "$ROOT/simulations/room/omnetpp.ini" \
                --cmdenv-express-mode=true --cmdenv-status-frequency=5000s \
                --seed-set="$s" \
                '--*.edgeHost.app[0].admissionPolicy="none"' \
                "--*.edgeHost.app[0].cameraTerminatesAtEdge=true" \
                "--*.edgeHost.app[0].evidenceBytes=${bytes}B" \
                "--*.rig.camera.sendInterval=${CAM_INTERVAL}" \
                "--*.rig.camera.messageLength=53167B" \
                '--*.cloud.app[0].e2eDelayAlarm:vector.vector-recording=true' \
                '--*.cloud.app[0].e2eDelayEvidence:vector.vector-recording=true' \
                --output-scalar-file="$OUT/RoomMatched5GHz-${label}-s${s}.sca" \
                --output-vector-file="$OUT/RoomMatched5GHz-${label}-s${s}.vec" \
                > /dev/null 2>&1 &
            throttle
        done
    done
    wait
    echo "room5g_120: $(ls "$OUT"/*.sca 2>/dev/null | wc -l) runs"
}

cell_pilot indoor_lte_120      CondIndoorLte 53167B
cell_pilot indoor_lte_4k_120   CondIndoorLte 4KiB
cell_pilot healthy_120         CondHealthy   53167B
cell_room
echo "done"
