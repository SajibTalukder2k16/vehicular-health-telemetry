#!/bin/bash
# Controller comparison on MEASURED infrastructure, 60 KiB video payload.
#
# Connects the two halves of the study: the corrected corridor evaluation and
# the controller, which until now was only tested on synthetic chains.
#
# Static baseline cap. The usual rule -- maximise camera subject to vitals
# >= 90% -- is degenerate here because no cap reaches 90% and vitals barely
# responds to the cap at all (88.1% at 200k against 87.4% at 1000k, a 0.7 pp
# move for a 68.7 pp change in camera). Picking "max vitals" would hand the
# static policy a 200k cap that sacrifices 68.7 pp of camera for 0.7 pp of
# vitals, which is a strawman. Instead: among caps whose vitals is within
# 1 pp of the best achievable, take the one with the most camera. That gives
# 1000k. Both 200k and 1000k are run so the frontier is visible.
#
# Usage: corridor_h2h.sh <config> <policy> <rate_kbps> [jobs]
set -u
cfg=$1; pol=$2; rate=$3; J=${4:-4}
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NED="$ROOT/src:$ROOT/simulations:$ROOT/../inet4.7/src:$ROOT/../Simu5G/src"
LIB="$ROOT/../Simu5G/src/simu5g"
BIN="$ROOT/src/out/clang-release/paperrebuild"
case "$cfg" in
    Dc*) dir=dc_case ;;
    Va*) dir=va_case ;;
    *) echo "unknown config $cfg" >&2; exit 1 ;;
esac
OUT="$ROOT/simulations/$dir/results_video"
mkdir -p "$OUT"
cd "$ROOT/simulations/$dir"

n=0
for s in 0 1 2 3 4 5 6 7 8 9; do
    out="$OUT/${cfg}-${pol}${rate}-s${s}.sca"
    [ -s "$out" ] && grep -q packetsGenerated "$out" 2>/dev/null && continue
    "$BIN" -u Cmdenv -c "$cfg" -r 0 -n "$NED" -l "$LIB" \
        --cmdenv-express-mode=true --cmdenv-status-frequency=5000s \
        --seed-set="$s" \
        "--*.ue.app[0].admissionPolicy=\"$pol\"" \
        '--*.server.app[0].feedbackInterval=200ms' \
        "--*.ue.app[0].cameraRate=${rate}kbps" \
        '--*.ue.app[0].cameraBurst=262144B' \
        --output-scalar-file="$out" > /dev/null 2>&1 &
    n=$((n+1)); [ $((n % J)) -eq 0 ] && wait
done
wait
echo "$cfg/$pol$rate: $(grep -l packetsGenerated "$OUT/${cfg}-${pol}${rate}"-s*.sca 2>/dev/null | wc -l)/10"
