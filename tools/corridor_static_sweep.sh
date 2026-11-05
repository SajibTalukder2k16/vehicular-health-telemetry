#!/bin/bash
# ADVERSARIAL AUDIT of the controller's headline corridor result.
#
# docs/CORRIDOR_REGIME.md reports the controller beating the static cap by +24
# to +48 pp of camera on c08-c14. That comparison uses a SINGLE static rate --
# dropPace at 400 kbps -- across seven corridors whose site spacing runs from
# 4 km to 10 km. The document itself says one rate "over-throttles everywhere
# it is not exactly right, and it is exactly right nowhere."
#
# That is an admission that the baseline was handicapped, and it is the first
# thing a reviewer will attack. So build the strongest static baseline the data
# permits: sweep the cap per corridor, then let the static arm keep its BEST
# point on each corridor, chosen on the same seeds it is evaluated on.
#
# That is deliberately generous. Choosing a cap per corridor using the
# evaluation seeds is an ORACLE no deployment could implement -- it requires
# knowing each corridor's best rate in advance, which is the very thing the
# controller discovers in flight. Treating it as an upper bound is the point:
# if the controller still wins against the oracle, the headline is robust; if
# it does not, the headline was an artifact of a mismatched fixed rate and has
# to be withdrawn.
#
# 7 corridors x 5 caps x 3 seeds = 105 runs. The 400 kbps column duplicates
# results_thr/ deliberately, so every point comes from one invocation.
#
# Usage: corridor_static_sweep.sh [jobs]
set -u
J=${1:-3}
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NED="$ROOT/src:$ROOT/simulations:$ROOT/../inet4.7/src:$ROOT/../Simu5G/src"
LIB="$ROOT/../Simu5G/src/simu5g"
BIN="$ROOT/src/out/clang-release/paperrebuild"
# Scalars AND vectors both go here -- see the note in aimd_sensitivity.sh.
OUT="$ROOT/simulations/corridorpop/results_static"
mkdir -p "$OUT"
cd "$ROOT/simulations/corridorpop"

CAPS="200 400 600 800 1000"

n=0
for c in c08 c09 c10 c11 c12 c13 c14; do
    for cap in $CAPS; do
        for r in 3 4 5; do
            out="$OUT/${c}-static${cap}-${r}.sca"
            [ -s "$out" ] && grep -q packetsGenerated "$out" 2>/dev/null && continue
            "$BIN" -u Cmdenv -c "$c" -r "$r" -n "$NED" -l "$LIB" \
                --cmdenv-express-mode=true --cmdenv-status-frequency=5000s \
                '--*.ue.app[0].admissionPolicy="dropPace"' \
                "--*.ue.app[0].cameraRate=${cap}kbps" \
                '--*.ue.app[0].cameraBurst=262144B' \
                --output-scalar-file="$out" \
                --output-vector-file="$OUT/${c}-static${cap}-${r}.vec" > /dev/null 2>&1 &
            n=$((n+1)); [ $((n % J)) -eq 0 ] && wait
        done
    done
done
wait
echo "static sweep: $(grep -l packetsGenerated "$OUT"/*.sca 2>/dev/null | wc -l)/105"
