#!/bin/bash
# GATE A: does the verification burst delay the alert it justifies?
#
# This is the pilot the project turns on (docs/PLAN_2026-11.md §10 Phase 1).
# C2 -- "the evidence that justifies the alert is what delays it" -- is
# currently supported only by runs that used a continuous 2 Hz camera stream
# on the backhaul, which is the traffic model C1 invalidates. Under the
# derived architecture the competing traffic is a BURST coincident with the
# emergency. That should concentrate the conflict rather than remove it, but
# that is a prediction, and this answers it on ~200 runs instead of 650.
#
# DESIGN
#   evidenceBytes is the only factor. Everything else is held fixed, and the
#   reference arm is evidenceBytes=0 -- alarm-only, i.e. the earlier corpus's
#   behaviour -- so the contrast isolates the burst.
#
#   Policy is 'none' ON PURPOSE. Unmanaged evidence goes out the instant it
#   is produced, which is the arm where the conflict must be worst. If the
#   burst does not delay the alert HERE, no policy is needed and C2 is dead.
#   Managed policies are Phase 2's job, not Gate A's.
#
#   Seeds are matched across arms and the ini gives the exogenous processes
#   their own RNG streams, so this is a paired design and must be analysed
#   as one -- see tools/analyze_escalation.py and the standing rule about
#   unpaired tests of paired designs.
#
# WHY 30 SEEDS AND NOT THE RAISED ALARM RATE
#   At the design rate, exponential(300 s), a drive yields about 2-8
#   escalations, so 10 seeds gives a thin denominator -- the same problem
#   docs/ALARM_RELIABILITY.md hit, where Wilson intervals were 12-20 pp wide
#   and it solved by raising the alarm rate tenfold for exposure.
#
#   That solution is NOT available here, and the reason matters. Raising the
#   rate tenfold with evidence attached would put ~80 bursts x up to 138 KB
#   on the drive, which is a continuous evidence load -- precisely the
#   continuous-stream regime C1 removed from the backhaul. The thing under
#   test is an ISOLATED burst coincident with an emergency, so distorting the
#   rate would answer a different question.
#
#   Power comes from seeds instead: 30, not 10. Three times the escalation
#   events at three times the compute, with the load left alone.
#
# THE EVIDENCE LADDER (docs/PLAN_2026-11.md §7), every size derived:
#   0        reference: no evidence at all
#   E1   512B  trusts the edge; verifies nothing independently
#   E2  3584B  pulse waveform -- server recomputes HR *and* HRV
#   E3 57344B  one 640x480 still -- posture, eye closure, no vitals
#   E4 138000B 10 s at HR-grade 0.110 Mb/s -- HR re-derived from video
#
#   E5 (95.7 MB, 30 s at PRV-grade 25.5 Mb/s) IS DELIBERATELY NOT RUN.
#   Its answer is arithmetic: 95.7 MB over the 3 Mb/s uplink benchmark is
#   255 s of transmission before any queueing, which is beyond any dispatch
#   budget. Simulating ~68,000 chunk packets per escalation to confirm a
#   transfer-time bound we can divide by hand is not a good use of compute.
#   The paper reports it as the analytic wall it is.
#
# WHAT IS *NOT* CHANGED HERE, and why
#   Edge processing stays at the ini's uniform(0.5ms, 2ms). It is unsourced
#   and ~2 orders too fast (M4), but re-sourcing it needs the DMS papers
#   retrieved, and this project does not write unretrieved numbers into a
#   model. It is common to every arm, so it cannot confound a contrast
#   between arms -- it shifts absolute latency, not the effect of evidence.
#
# OUTCOME, and why this script has been run three times
#   2026-11-08  results_escalation/     C2 refuted: 0 of 16 cells. The 1 s alert
#                                       tail traced to Simu5G modelling no PUCCH
#                                       and no Scheduling Request.
#   2026-11-09  results_escalation_sr/  Re-run on the corrected model
#                                       (patches/simu5g-scheduling-request.patch).
#                                       Conclusion unchanged, evidence stronger.
#   2026-11-10  results_escalation_vec/ Same runs again with per-escalation
#                                       vector recording for e2eDelayAlarm and
#                                       e2eDelayEvidence (omnetpp.ini, and note
#                                       the ordering warning there). The earlier
#                                       two corpora recorded NO vector samples,
#                                       so time-to-dispatch was only available
#                                       as a per-run maximum -- 30 numbers per
#                                       cell instead of ~140, and no CDF.
#                                       See docs/VERIFICATION_FRONTIER.md §1.
#   The question this script's header poses was answered in the first run. It is
#   left as written because it was the pre-registered question.
#
# Usage: OUT_DIR=<dir> escalation_pilot.sh [jobs]
set -u
J=${1:-8}
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NED="$ROOT/src:$ROOT/simulations:$ROOT/../inet4.7/src:$ROOT/../Simu5G/src"
LIB="$ROOT/../Simu5G/src/simu5g"
BIN="$ROOT/src/out/clang-release/paperrebuild"
OUT="${OUT_DIR:-$ROOT/simulations/pilot/results_escalation}"
mkdir -p "$OUT"
cd "$ROOT/simulations/pilot"

# PRV-grade camera on the sensor link: 25.52 Mb/s at 60 fps = 53167 B/frame
# (docs/PLAN_2026-11.md §5.2). cameraLinkType is WiredLink in this ini, so
# this does not saturate the sensor hop -- which is itself C1's consequence:
# a PRV-grade camera link cannot be wearable-class, and on 802.11a/g it has
# 1.21x headroom and fails outright once the medium is shared.
CAM_INTERVAL=0.0166667s
CAM_BYTES=53167B

# label:bytes
ARMS="ref:0 e1:512 e2:3584 e3:57344 e4:138000"

n=0
for cond in CondHealthy CondCongested CondTransient CondOutage; do
    for arm in $ARMS; do
        label=${arm%%:*}
        bytes=${arm##*:}
        for s in $(seq 0 29); do
            "$BIN" -u Cmdenv -c "$cond" -r 0 -n "$NED" -l "$LIB" \
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
echo "escalation pilot runs written: $(ls "$OUT"/*.sca 2>/dev/null | wc -l) of $n"
