#!/bin/sh
# The indoor edge on a CELLULAR backhaul: which of the three differences
# actually caused the delivery failure?
#
# WHY THIS RUN EXISTS
#   docs/ROOM_LADDER_RESULT.md had to concede that the indoor control changes
#   THREE things at once against the cellular campaign: access technology
#   (802.11 vs LTE), competing traffic (none vs 4-20 background UEs), and the
#   observation window (300 s vs 320-1369 s). It therefore localises the
#   16-49 % delivery failure to "the mobile cellular setting as a whole" and
#   cannot say which part did it. That is an honest concession and a weak one.
#
#   This arm removes two of the three. It is CondHealthy's radio, channel
#   scenario, site layout and X2 mesh, with the edge UE held stationary 100 m
#   from eNodeB[0] and the background load removed, over the room's 300 s
#   window. The comparison grid then closes:
#
#                              | WLAN backhaul      | LTE backhaul
#     stationary, no load      | RoomMatched5GHz    | CondIndoorLte  <- new
#     mobile, with load        | --                 | CondHealthy..Outage
#
#   CondIndoorLte vs RoomMatched5GHz differs ONLY in the access technology.
#   CondIndoorLte vs CondHealthy differs only in mobility, load and window.
#   Between them they separate what the indoor control could not.
#
# PREDICTIONS, RECORDED BEFORE THE RUN (2026-11-18)
#   P1  Completion at E4 will be high -- above 95 % -- because the uplink is
#       unloaded and the UE never leaves coverage. If LTE alone, stationary
#       and unloaded, still fails to deliver whole bursts, then the access
#       technology IS the cause and the paper's framing of the room result
#       must change.
#   P2  The E4 dispatch gap will sit BETWEEN the WLAN's 0.0350 s and
#       CondHealthy's 0.1920 s, and closer to the WLAN end. LTE adds grant
#       acquisition that 802.11 does not, but removing mobility and
#       contention removes most of what made the cellular arm slow. A value
#       at or below 0.0350 s would say LTE's uplink is not intrinsically
#       worse; a value near 0.1920 s would say mobility and load were never
#       the point.
#   P3  Completion will be at or near 100 % at E1-E3, as in both the WLAN
#       arms and the cellular campaign's E1.
#   P4  The alert will be FLAT across the ladder, as indoors on WLAN, rather
#       than FALLING as it does on cellular. The falling alert was attributed
#       in docs/ROOM_LADDER_RESULT.md to cellular grant acquisition. This arm
#       is cellular, so if that attribution is right the alert should fall
#       here too -- which makes P4 as written the prediction that the
#       attribution is WRONG. Scoring it either way is informative, and the
#       two outcomes say opposite things, so it must be read before the table
#       is interpreted.
#
#   SCORE THESE HONESTLY. P2 and P4 are both written so that either outcome
#   costs the paper a sentence it currently has.
set -e

ROOT=$(cd "$(dirname "$0")/.." && pwd)
BIN="$ROOT/src/out/clang-release/paperrebuild"
NED="$ROOT/src:$ROOT/simulations:$ROOT/../inet4.7/src:$ROOT/../Simu5G/src"
LIB="$ROOT/../Simu5G/src/simu5g"
INI="$ROOT/simulations/pilot/omnetpp.ini"
OUT="$ROOT/simulations/pilot/results_indoor_lte"
J=${J:-12}

[ -x "$BIN" ] || { echo "build src/ first: $BIN missing" >&2; exit 1; }
mkdir -p "$OUT"
cd "$ROOT/simulations/pilot"

# Identical to tools/room_ladder.sh and tools/room_wifi_ladder.sh.
CAM_INTERVAL=0.0166667s
CAM_BYTES=53167B
ARMS="ref:0 e1:512 e2:3584 e3:57344 e4:138000"
CONDS="CondIndoorLte"

# A 4 KiB CAMERA CONTROL, added 2026-11-18 after external review.
#   The cellular corpus runs its camera at the size each condition's ini
#   sets -- 4 KiB in CondHealthy, 60 KiB in the other three -- NOT at the
#   53,167 B this driver uses, so the stationary-to-mobile step changes the
#   camera payload as well as mobility, load and window. Under the derived
#   partition that should not matter: frames terminate at the edge and never
#   cross the uplink. Set CAM4K=1 to re-run this arm at 4 KiB and check it
#   rather than assume it. Measured: the alert and the E4 gap are identical
#   (15.7 ms, 68.0 ms) and completion moves by one burst in 35.
#
#     CAM4K=1 sh tools/indoor_lte_ladder.sh
if [ "${CAM4K:-0}" = "1" ]; then
    CAM_BYTES=4096B
    OUT="$ROOT/simulations/pilot/results_indoor_lte_cam4k"
    mkdir -p "$OUT"
fi

# Unlike the room, this network names its server `server`, which the pilot
# ini's selective vector-recording block already matches -- so no
# vector-recording overrides are needed here. The edge app is ue.app[0], not
# edgeHost.app[0]: in CorridorNet the UE IS the edge device.

n=0
for cond in $CONDS; do
    for arm in $ARMS; do
        label=${arm%%:*}
        bytes=${arm##*:}
        for s in $(seq 0 29); do
            "$BIN" -u Cmdenv -c "$cond" -r 0 -n "$NED" -l "$LIB" -f "$INI" \
                --cmdenv-express-mode=true --cmdenv-status-frequency=5000s \
                --seed-set="$s" \
                '--*.ue.app[0].admissionPolicy="none"' \
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
echo "indoor lte ladder runs written: $(ls "$OUT"/*.sca 2>/dev/null | wc -l) of $n"
