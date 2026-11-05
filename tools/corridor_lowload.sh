#!/bin/bash
# Does the headline hold at the OTHER background-load level?
#
# Every corridor number in this project -- the regime finding, the oracle
# audit, the +34.8 +/- 13.9 pp headline -- comes from bgues=20 alone. The
# corridorpop ini crosses numBgUes = ${bgues=2,20} and says why:
#
#   "whether a corridor is 'contention-limited' is only meaningful relative to
#    an assumed background load, so sweep two levels and report the regime as a
#    function of load rather than asserting one number."
#
# Half that data was never collected. With the signal-design question closed
# (docs/ABLATION_CROSS_STREAM.md) the static-vs-adaptive result is the paper's
# only contribution, so it rests entirely on one assumed load level. This fills
# the other one.
#
# Same cells as the bgues=20 campaign so the two are directly comparable:
# 7 corridors x (5 static caps + aimd + aimdSelf) x 10 seeds = 490 runs, at
# -r $BGUES2_RUN instead of -r $BGUES20_RUN. File naming matches
# results_seeds10/ exactly, so tools/analyze_static_oracle.py and
# tools/analyze_corridor_ablation.py both run on this directory unchanged.
#
# Expected: the controller helps LESS at low load, which would confirm the
# regime story with data rather than assumption. If it helps equally the win is
# not really about contention and docs/CORRIDOR_REGIME.md needs rewriting; if
# it helps more, the mechanism is not understood. Recording the expectation
# here so it cannot be revised after the fact.
#
# Seeding, concurrency, scratch vetting and the completion test come from
# tools/lib_campaign.sh.
#
# Idempotent: validated cells are skipped, so it can be re-run to fill gaps.
#
# Usage: corridor_lowload.sh [scratch-dir]
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NED="$ROOT/src:$ROOT/simulations:$ROOT/../inet4.7/src:$ROOT/../Simu5G/src"
LIB="$ROOT/../Simu5G/src/simu5g"
BIN="$ROOT/src/out/clang-release/paperrebuild"
OUT="$ROOT/simulations/corridorpop/results_lowload"
# Deliberately NOT under /tmp; check_scratch() vets whatever it is pointed at.
SCRATCH="${1:-$HOME/.cache/paperrebuild-vec}"
LOG="$OUT/campaign.log"

source "$(dirname "$0")/lib_campaign.sh"

SEEDS="${SEEDS:-0 1 2 3 4 5 6 7 8 9}"
CAPS="${CAPS:-200 400 600 800 1000}"
CORRIDORS="${CORRIDORS:-$CORRIDOR_LIST}"

mkdir -p "$OUT" "$SCRATCH"
cd "$ROOT/simulations/corridorpop" || exit 1
[ -x "$BIN" ] || { echo "no binary at $BIN -- source setenv and make first" >&2; exit 1; }
check_scratch || exit 1

run_cell() {
    local c="$1" arm="$2" s="$3"; shift 3
    local tag="${c}-${arm}-s$(printf '%02d' "$s")"
    local sca="$OUT/$tag.sca"
    done_already "$sca" && return 0
    "$BIN" -u Cmdenv -c "$c" -r "$BGUES2_RUN" -n "$NED" -l "$LIB" \
        --cmdenv-express-mode=true --cmdenv-status-frequency=5000s \
        --seed-set="$s" \
        "$@" \
        '--*.ue.app[0].cameraBurst=262144B' \
        --output-scalar-file="$sca" \
        --output-vector-file="$SCRATCH/$tag.vec" \
        >> "$LOG" 2>&1 \
        || echo "FAILED $tag" >> "$LOG"
    # Vectors exist only so they do not land in the ini's default results/ and
    # overwrite tracked baselines; dropping them on exit bounds peak scratch
    # use by the slot count rather than by the campaign size.
    rm -f "$SCRATCH/$tag.vec" "$SCRATCH/$tag.vci"
}

count() { echo $#; }
PER_CORRIDOR=$(( ($(count $CAPS) + 2) * $(count $SEEDS) ))
EXPECTED=$(( PER_CORRIDOR * $(count $CORRIDORS) ))

echo "=== corridor_lowload started $(date -Is), expecting $EXPECTED ===" >> "$LOG"
for c in $CORRIDORS; do
    J="$(slots_for "$c")"
    echo "--- $c ($J slots) $(date -Is) ---" >> "$LOG"
    for s in $SEEDS; do
        for cap in $CAPS; do
            while [ "$(jobs -rp | wc -l)" -ge "$J" ]; do wait -n; done
            run_cell "$c" "static$cap" "$s" \
                '--*.ue.app[0].admissionPolicy="dropPace"' \
                "--*.ue.app[0].cameraRate=${cap}kbps" &
        done
        for arm in aimd aimdSelf; do
            while [ "$(jobs -rp | wc -l)" -ge "$J" ]; do wait -n; done
            run_cell "$c" "$arm" "$s" \
                "--*.ue.app[0].admissionPolicy=\"$arm\"" \
                '--*.server.app[0].feedbackInterval=200ms' \
                '--*.ue.app[0].cameraRate=1000kbps' &
        done
    done
    wait
    echo "--- $c done, $(ls "$OUT"/${c}-*.sca 2>/dev/null | wc -l)/$PER_CORRIDOR $(date -Is) ---" >> "$LOG"
done
wait
echo "=== corridor_lowload finished $(date -Is) ===" >> "$LOG"

echo "scalar files: $(ls "$OUT"/*.sca 2>/dev/null | wc -l)/$EXPECTED"
python3 -I "$ROOT/tools/validate_runs.py" "$OUT"
