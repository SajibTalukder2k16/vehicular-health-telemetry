#!/bin/sh
# Can the indoor camera be a Bluetooth device too?
#
# WHY THIS RUN EXISTS
#   The wearable is on BLE in every configuration in this project, and that
#   is the realistic choice -- body-worn sensors are overwhelmingly BLE. The
#   obvious follow-on question is whether the camera can be BLE as well, so
#   that the whole rig is one radio technology. C1 says no at PRV grade, by
#   the largest margin in its table, and that margin has never been measured.
#
#   This driver runs three things, in order of what they settle:
#
#   PART A  the evidence ladder with the camera on BLE, at the same PRV-grade
#           rate as the wired and WLAN campaigns, so the three sensor links
#           are directly comparable. 150 runs.
#   PART B  a camera-rate sweep, because "BLE cannot carry the camera" is
#           true at PRV grade and false in general. The useful engineering
#           answer is WHICH camera BLE carries, so the sweep walks frame size
#           and frame rate across the ceiling. 150 runs.
#   PART C  a sweep of the WEARABLE's share of its own BLE radio, which is
#           the question Parts A and B cannot answer. See the warning below.
#           150 runs.
#
# THE CEILING, DERIVED BEFORE MEASURING IT
#   From src/links/BleLink.cc's connection-event loop with the NED defaults:
#   appBytesPerPdu = 251 - 7 = 244 B; airBytes = 244 + 7 + 10 = 261 B;
#   pduTime = 261*8/1Mbps + 2*150us + 80us = 2,468 us; a 30 ms connection
#   interval fits floor(30000/2468) = 12 PDUs, so 12 * 244 = 2,928 B per
#   interval = 0.781 Mb/s. docs/BLE_VALIDATION.md measures 0.737 Mb/s; the
#   5.6 % shortfall is PDU quantisation on the last fragment of a message,
#   so the EFFECTIVE ceiling depends on message size and is nearer the
#   theoretical figure for large frames than for small ones.
#
# !! WHAT PARTS A AND B CANNOT SHOW -- READ BEFORE QUOTING THEM !!
#   src/nodes/SensorRig.ned gives the camera its own BleLink instance,
#   separate from `bleWearable`, and the alarm is EDGE-GENERATED: line 68 is
#   `alarm.out --> edge.in++`, with no sensor-link hop at all. So in this
#   model a saturating BLE camera cannot delay the alert, and that is a
#   property of the MODEL's structure, not a finding about Bluetooth. A real
#   deployment would put both streams on one radio, and the vitals that
#   trigger detection would contend with the camera.
#
#   Part C bounds that risk instead of ignoring it. `maxCiUtilization` is the
#   usable fraction of the connection interval, i.e. exactly the share a
#   competing stream leaves. Sweeping it on bleWearable asks: if a greedy BLE
#   camera took most of the radio, what would happen to the 512 B/s vitals
#   stream? The answer is reported as a sensitivity bound, not as a
#   measurement of contention, because the contention itself is not modelled.
#
# PREDICTIONS, RECORDED BEFORE THE RUN (2026-11-18)
#   P1  PART A. The BLE camera drops 96-98 % of frames. Offered 25.5 Mb/s
#       against a ~0.78 Mb/s ceiling leaves ~3.1 % deliverable, and the
#       65,536 B queue holds barely one 53,167 B frame. If the drop rate is
#       materially below 96 %, C1's BLE row is wrong.
#   P2  PART A. Completion stays 100 % and the E4 gap stays 0.0350 s, as in
#       the wired and WLAN arms -- because of the structural reason above,
#       NOT because BLE is harmless. Scoring this as a success would be
#       misreading it; it is a consistency check on the model.
#   P3  PART B. A 4 KiB camera at 10 fps is 0.33 Mb/s and FITS, with ~2.4x
#       of headroom. simulations/room/omnetpp.ini labels that configuration
#       "documented-infeasible", which the arithmetic contradicts. I expect
#       near-zero drops and therefore expect to have to correct that label.
#   P4  PART B. 4 KiB at 60 fps is 1.97 Mb/s and does NOT fit; expect
#       ~60 % drops. The feasible frontier should sit between 20 and 25 fps
#       at 4 KiB.
#   P5  PART C. The vitals stream is 512 B/s, about 0.5 % of the BLE
#       ceiling, so it should survive down to a very small share. I expect
#       no vitals loss until maxCiUtilization falls below ~0.05.
#
#   SCORE THESE HONESTLY. P3 predicts that a label in this repository is
#   wrong, and P2 is written so that a "pass" must not be reported as one.
set -e

ROOT=$(cd "$(dirname "$0")/.." && pwd)
BIN="$ROOT/src/out/clang-release/paperrebuild"
NED="$ROOT/src:$ROOT/simulations:$ROOT/../inet4.7/src:$ROOT/../Simu5G/src"
LIB="$ROOT/../Simu5G/src/simu5g"
INI="$ROOT/simulations/room/omnetpp.ini"
OUT="$ROOT/simulations/room/results_room_ble"
J=${J:-12}

[ -x "$BIN" ] || { echo "build src/ first: $BIN missing" >&2; exit 1; }
mkdir -p "$OUT"
cd "$ROOT/simulations/room"

ARMS="ref:0 e1:512 e2:3584 e3:57344 e4:138000"
PRV_INTERVAL=0.0166667s
PRV_BYTES=53167B

# As in the other room drivers: this network names its server `cloud`, so the
# two vector-recording overrides are what make the escalation vectors exist.
#
# NOTE: the throttle below is `if ...; then wait; fi`, not `[ ... ] && wait`.
# The latter returns 1 whenever the test is false, which inside a function
# makes the function return 1, which under `set -e` exits the script -- it
# did, silently, in 0.02 s with 0 runs written. The other room drivers use
# the && form inline in a loop where it happens not to bite.
n=0
launch() {   # launch <tag> <extra args...>
    tag=$1; shift
    "$BIN" -u Cmdenv -c RoomBleCam -r 0 -n "$NED" -l "$LIB" -f "$INI" \
        --cmdenv-express-mode=true --cmdenv-status-frequency=5000s \
        '--*.edgeHost.app[0].admissionPolicy="none"' \
        "--*.edgeHost.app[0].cameraTerminatesAtEdge=true" \
        '--*.cloud.app[0].e2eDelayAlarm:vector.vector-recording=true' \
        '--*.cloud.app[0].e2eDelayEvidence:vector.vector-recording=true' \
        "$@" \
        --output-scalar-file="$OUT/${tag}.sca" \
        --output-vector-file="$OUT/${tag}.vec" > /dev/null 2>&1 &
    n=$((n+1))
    if [ $((n % J)) -eq 0 ]; then wait; fi
    return 0
}

# ---- PART A: the ladder, camera on BLE at PRV grade -------------------
for arm in $ARMS; do
    label=${arm%%:*}; bytes=${arm##*:}
    for s in $(seq 0 29); do
        launch "RoomBleCam-${label}-s${s}" \
            "--*.edgeHost.app[0].evidenceBytes=${bytes}B" \
            "--*.rig.camera.sendInterval=${PRV_INTERVAL}" \
            "--*.rig.camera.messageLength=${PRV_BYTES}" \
            --seed-set="$s"
    done
done
wait
echo "part A (ladder, BLE camera at PRV grade): $(ls "$OUT"/RoomBleCam-*.sca 2>/dev/null | wc -l) runs"

# ---- PART B: which camera does BLE actually carry? -------------------
# label:bytes:interval. Offered rate = bytes*8/interval.
#   prv    53,167 B @ 60 fps = 25.50 Mb/s   -- PRV grade
#   prv2   53,167 B @  2 fps =  0.85 Mb/s   -- just above the ceiling
#   k4f60   4,096 B @ 60 fps =  1.97 Mb/s
#   k4f30   4,096 B @ 30 fps =  0.98 Mb/s
#   k4f10   4,096 B @ 10 fps =  0.33 Mb/s   -- the "infeasible" label
RATES="prv:53167B:0.0166667s prv2:53167B:0.5s k4f60:4096B:0.0166667s \
       k4f30:4096B:0.0333333s k4f10:4096B:0.1s"
for r in $RATES; do
    label=$(echo "$r" | cut -d: -f1)
    bytes=$(echo "$r" | cut -d: -f2)
    iv=$(echo "$r" | cut -d: -f3)
    for s in $(seq 0 29); do
        launch "rate-${label}-s${s}" \
            "--*.edgeHost.app[0].evidenceBytes=138000B" \
            "--*.rig.camera.sendInterval=${iv}" \
            "--*.rig.camera.messageLength=${bytes}" \
            --seed-set="$s"
    done
done
wait
echo "part B (camera-rate sweep): $(ls "$OUT"/rate-*.sca 2>/dev/null | wc -l) runs"

# ---- PART C: what share of the radio does the wearable need? ---------
# A sensitivity bound on sharing one BLE radio, NOT a contention measurement.
for u in 1.0 0.5 0.2 0.05 0.01; do
    for s in $(seq 0 29); do
        launch "share-${u}-s${s}" \
            "--*.edgeHost.app[0].evidenceBytes=138000B" \
            "--*.rig.camera.sendInterval=${PRV_INTERVAL}" \
            "--*.rig.camera.messageLength=${PRV_BYTES}" \
            "--*.rig.bleWearable.maxCiUtilization=${u}" \
            --seed-set="$s"
    done
done
wait
echo "part C (wearable radio share): $(ls "$OUT"/share-*.sca 2>/dev/null | wc -l) runs"
echo "total written: $(ls "$OUT"/*.sca 2>/dev/null | wc -l) of $n"
