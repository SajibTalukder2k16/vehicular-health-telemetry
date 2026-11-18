#!/bin/sh
# The evidence ladder indoors: is the delivery failure a property of the
# MOBILE UPLINK, or of requiring complete evidence?
#
# WHY THIS RUN EXISTS
#   The paper measures that 16-49 % of emitted escalations never deliver
#   complete evidence at E4. All four conditions are cellular. A reader can
#   reasonably ask whether that is a property of the architecture -- of
#   demanding whole payloads before acting -- or of the mobile uplink those
#   four conditions share. Nothing in the paper currently answers it.
#
#   The v05 work had an indoor arm and retired it with that framing. Its
#   corpus cannot be reused: simulations/room/omnetpp.ini sets no
#   evidenceBytes at all, runs the camera at 2 Hz, and predates
#   cameraTerminatesAtEdge. So this is a re-run, not a re-analysis.
#
# THE CONTROL
#   Same rig, same evidence ladder, same 60 fps camera, same edge. The ONLY
#   difference from the ladder campaign is the backhaul: 802.11 instead of
#   LTE. That is what the RoomMatched* configs were built for.
#
# PREDICTIONS, RECORDED BEFORE THE RUN (2026-11-18)
#   P1  Completion at E4 will exceed 95 % in both bands, against 51-84 % on
#       cellular. If it does not, the failure is NOT simply the uplink and
#       the paper's framing needs to change.
#   P2  The dispatch gap at E4 will be of order tens of milliseconds. A
#       138 kB burst over a ~30 Mb/s medium is ~37 ms of transmission,
#       against 0.19-0.46 s measured on cellular.
#   P3  C2' will still hold in DIRECTION -- the alert flat or falling while
#       the gap grows with payload -- but compressed into a range where it
#       does not matter operationally.
#   P4  The two bands will be indistinguishable, as they were in v05 on the
#       timeliness metric. If they differ, the WLAN is binding somewhere and
#       P1-P3 need re-reading.
#
#   SCORE THESE HONESTLY. Two of this project's recorded predictions were
#   wrong, and one was right for the wrong reason.
set -e

ROOT=$(cd "$(dirname "$0")/.." && pwd)
BIN="$ROOT/src/out/clang-release/paperrebuild"
NED="$ROOT/src:$ROOT/simulations:$ROOT/../inet4.7/src:$ROOT/../Simu5G/src"
# Same library the vehicular ladder driver loads; simu5g pulls in INET.
LIB="$ROOT/../Simu5G/src/simu5g"
INI="$ROOT/simulations/room/omnetpp.ini"
OUT="$ROOT/simulations/room/results_room_ladder"
J=${J:-12}

[ -x "$BIN" ] || { echo "build src/ first: $BIN missing" >&2; exit 1; }
mkdir -p "$OUT"
cd "$ROOT/simulations/room"

# Identical to tools/escalation_pilot.sh. 53,167 B at 60 fps is 25.5 Mb/s,
# the PRV-grade rate of PLAN_2026-11.md section 5.2.
CAM_INTERVAL=0.0166667s
CAM_BYTES=53167B
ARMS="ref:0 e1:512 e2:3584 e3:57344 e4:138000"
CONDS="RoomMatched24GHz RoomMatched5GHz"

# The room network names its server `cloud`; simulations/pilot names it
# `server`, so that ini's selective vector-recording block does not match
# here. Without the two overrides below every run records zero escalation
# samples -- the campaign would complete and be useless. Checked on a smoke
# run before launching: 0 samples without them, 200 with.

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
                --output-scalar-file="$OUT/${cond}-${label}-s${s}.sca" \
                --output-vector-file="$OUT/${cond}-${label}-s${s}.vec" \
                > /dev/null 2>&1 &
            n=$((n+1)); [ $((n % J)) -eq 0 ] && wait
        done
    done
done
wait
echo "room ladder runs written: $(ls "$OUT"/*.sca 2>/dev/null | wc -l) of $n"
