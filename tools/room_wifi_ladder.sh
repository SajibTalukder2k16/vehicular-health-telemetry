#!/bin/sh
# The indoor camera on the WLAN: does a PRV-grade stream fit, and does its
# load stay off the escalation path?
#
# WHY THIS RUN EXISTS
#   tools/room_ladder.sh ran the indoor control with the camera on a WIRED
#   sensor link, matching the vehicular campaign. That is the right control
#   but it is not the realistic indoor installation: an indoor camera is
#   normally on the wireless LAN. Two claims the paper makes are untested
#   until it is.
#
#   (a) C1's WLAN WALL. Section "Capacity Constraints on Inference Placement"
#       puts a PRV-grade camera at 25.5 Mb/s against an 802.11a/g DCF ceiling
#       of 30.9 Mb/s quiet and 6.18 Mb/s with the medium 80 % held by other
#       stations. Those two numbers are DERIVED from the framing and timing
#       parameters of src/links/WifiLink.ned; they have never been measured
#       against a stream of that rate. If the derivation is right the camera
#       fits on a quiet medium with 21 % to spare and fails on a busy one.
#
#   (b) THE PARTITION'S ISOLATION. The derived architecture's whole point is
#       that raw frames terminate at the edge and never cross the backhaul.
#       src/apps/EdgeApp.cc:657 implements this by counting and DELETING each
#       camera frame with no service cost. If that is the truth of the model,
#       then saturating the camera's own link must leave the escalation path
#       untouched. That is a falsifiable statement about the architecture, and
#       it is worth more than one more latency table.
#
#   The camera is the stream that moves between configurations. The wearable
#   stays on BLE throughout -- a body-worn device talks BLE indoors too.
#
# THE LINK, AND WHERE ITS CEILING COMES FROM
#   camLink takes WifiLink's defaults: 802.11a/g, bitrate 54 Mbps, ackBitrate
#   24 Mbps, slotTime 9us, sifs 16us, phyHeaderTime 20us, cwMin 15,
#   maxMsduPayload 1500B, queueCapacity 65536B. Per 1500 B fragment one DCF
#   cycle costs DIFS 34us + mean backoff 67.5us + T_data 246.4us + SIFS 16us
#   + T_ack 24.7us = 388.6us, which is 30.9 Mb/s. mediumBusyFraction f
#   stretches every cycle by 1/(1-f), so f=0.8 gives 6.18 Mb/s. Those are the
#   two WLAN rows of the C1 table, re-derived here.
#
#   A 53,167 B frame is 36 fragments, so ~13.8 ms of medium time, and the
#   65,536 B queue holds about 1.2 frames.
#
# PREDICTIONS, RECORDED BEFORE THE RUN (2026-11-18)
#   P1  QUIET MEDIUM FITS. 25.5 Mb/s offered against 30.9 Mb/s is 0.83x, so
#       RoomWifiCam delivers the camera with essentially no drops and a
#       per-frame link delay near 13.8 ms. If it drops frames, the 30.9 Mb/s
#       ceiling in the C1 table is wrong and the table must change.
#   P2  BUSY MEDIUM FAILS. At f=0.8 the ceiling is 6.18 Mb/s, which is 4.13x
#       oversubscribed. The queue holds ~1.2 frames, so predict >= 70 % of
#       camera frames dropped (1 - 6.18/25.5 = 75.8 % is the fluid estimate).
#   P3  COMPLETION IS UNCHANGED. Escalation completion stays at 100 % at every
#       rung in BOTH configurations, as in the wired control, because camera
#       frames are deleted at the edge and never reach the backhaul.
#   P4  THE GAP IS UNCHANGED. The E4 dispatch gap is indistinguishable across
#       wired / WLAN-idle / WLAN-busy-80 %. This is the strong one. If the gap
#       MOVES, then the camera is coupled to the escalation path by some route
#       the architecture says does not exist, and that route must be found and
#       named before any of this is written up. A null result here is the
#       informative outcome; a non-null one is a bug hunt.
#
#   SCORE THESE HONESTLY. Of this project's recorded predictions so far, two
#   were wrong and one was right for the wrong reason. P4 is the one most
#   likely to embarrass the architecture, which is why it is written down.
set -e

ROOT=$(cd "$(dirname "$0")/.." && pwd)
BIN="$ROOT/src/out/clang-release/paperrebuild"
NED="$ROOT/src:$ROOT/simulations:$ROOT/../inet4.7/src:$ROOT/../Simu5G/src"
LIB="$ROOT/../Simu5G/src/simu5g"
INI="$ROOT/simulations/room/omnetpp.ini"
OUT="$ROOT/simulations/room/results_room_wifi"
J=${J:-12}

[ -x "$BIN" ] || { echo "build src/ first: $BIN missing" >&2; exit 1; }
mkdir -p "$OUT"
cd "$ROOT/simulations/room"

# Identical to tools/room_ladder.sh and tools/escalation_pilot.sh.
CAM_INTERVAL=0.0166667s
CAM_BYTES=53167B
ARMS="ref:0 e1:512 e2:3584 e3:57344 e4:138000"
CONDS="RoomWifiCam RoomWifiCamBusy80"

# As in room_ladder.sh: the room network names its server `cloud`, so the
# pilot ini's selective vector-recording block does not match it and the two
# overrides below are what make the escalation vectors exist at all.
# The camLink vectors are what P1 and P2 are scored on.

n=0
for cond in $CONDS; do
    for arm in $ARMS; do
        label=${arm%%:*}
        bytes=${arm##*:}
        for s in $(seq 0 29); do
            "$BIN" -u Cmdenv -c "$cond" -r 0 -n "$NED" -l "$LIB" -f "$INI" \
                --cmdenv-express-mode=true --cmdenv-status-frequency=5000s \
                --seed-set="$s" \
                '--*.edgeHost.app[0].admissionPolicy="none"' \
                "--*.edgeHost.app[0].cameraTerminatesAtEdge=true" \
                "--*.edgeHost.app[0].evidenceBytes=${bytes}B" \
                "--*.rig.camera.sendInterval=${CAM_INTERVAL}" \
                "--*.rig.camera.messageLength=${CAM_BYTES}" \
                '--*.cloud.app[0].e2eDelayAlarm:vector.vector-recording=true' \
                '--*.cloud.app[0].e2eDelayEvidence:vector.vector-recording=true' \
                '--*.rig.camLink.linkDelay:vector.vector-recording=true' \
                '--*.rig.camLink.queueBytes:vector.vector-recording=true' \
                --output-scalar-file="$OUT/${cond}-${label}-s${s}.sca" \
                --output-vector-file="$OUT/${cond}-${label}-s${s}.vec" \
                > /dev/null 2>&1 &
            n=$((n+1)); [ $((n % J)) -eq 0 ] && wait
        done
    done
done
wait
echo "room wifi ladder runs written: $(ls "$OUT"/*.sca 2>/dev/null | wc -l) of $n"
