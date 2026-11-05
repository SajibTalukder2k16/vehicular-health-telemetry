#!/bin/bash
# Does the CROSS-STREAM freshness signal actually beat the own-stream one?
#
# docs/ABLATION_CROSS_STREAM.md compares `aimd` against `aimdSelf` at a single
# shared freshnessTarget (the 5 s default). At 10 seeds on real corridors that
# comparison resolves cleanly -- aimdSelf gains +2.86 +/- 0.85 pp of timely
# vitals and loses -7.21 +/- 2.03 pp of timely camera -- but it cannot support
# any claim about which signal is BETTER, because the two arms do not sit at
# the same operating point. aimdSelf throttles harder (its backoff:probe ratio
# is worse on every corridor), so it is buying vitals with camera. A policy
# tuned more conservatively would do the same thing with either signal.
#
# This is exactly the error the static baseline originally made, and which
# docs/CORRIDOR_REGIME.md's oracle audit had to correct: comparing a controller
# against ONE configuration of the alternative instead of against the
# alternative's whole frontier. The fix is the same. Sweep freshnessTarget for
# BOTH arms, build each arm's own Pareto frontier, and compare camera at
# matched vitals.
#
# Targets 2/3/7/10 s here; the 5 s column already exists in
# simulations/corridorpop/results_seeds10/ and is read from there by
# tools/analyze_target_frontier.py, so each arm gets a five-point frontier.
# freshnessTarget does not affect the static dropPace arm, so only the two
# controller arms are swept.
#
# 7 corridors x 2 arms x 4 targets x 10 seeds = 560 runs.
#
# Seeding, concurrency, scratch vetting and the completion test are all in
# tools/lib_campaign.sh -- see the note there on why the scratch guard is
# shared rather than copied.
#
# Idempotent: validated cells are skipped, so it can be re-run to fill gaps.
#
# Usage: corridor_target_sweep.sh [scratch-dir]
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NED="$ROOT/src:$ROOT/simulations:$ROOT/../inet4.7/src:$ROOT/../Simu5G/src"
LIB="$ROOT/../Simu5G/src/simu5g"
BIN="$ROOT/src/out/clang-release/paperrebuild"
OUT="$ROOT/simulations/corridorpop/results_targets"
# Deliberately NOT under /tmp; check_scratch() vets whatever it is pointed at.
SCRATCH="${1:-$HOME/.cache/paperrebuild-vec}"
LOG="$OUT/campaign.log"

source "$(dirname "$0")/lib_campaign.sh"

# Overridable so the command construction can be smoke-tested on one cheap
# cell, and so a gap-filling re-run can be narrowed to what is missing.
SEEDS="${SEEDS:-0 1 2 3 4 5 6 7 8 9}"
TARGETS="${TARGETS:-2 3 7 10}"
ARMS="${ARMS:-aimd aimdSelf}"
CORRIDORS="${CORRIDORS:-$CORRIDOR_LIST}"

mkdir -p "$OUT" "$SCRATCH"
cd "$ROOT/simulations/corridorpop" || exit 1
[ -x "$BIN" ] || { echo "no binary at $BIN -- source setenv and make first" >&2; exit 1; }
check_scratch || exit 1

run_cell() {
    local c="$1" arm="$2" tgt="$3" s="$4"
    local tag="${c}-${arm}-t$(printf '%02d' "$tgt")-s$(printf '%02d' "$s")"
    local sca="$OUT/$tag.sca"
    done_already "$sca" && return 0
    "$BIN" -u Cmdenv -c "$c" -r "$BGUES20_RUN" -n "$NED" -l "$LIB" \
        --cmdenv-express-mode=true --cmdenv-status-frequency=5000s \
        --seed-set="$s" \
        "--*.ue.app[0].admissionPolicy=\"$arm\"" \
        "--*.ue.app[0].freshnessTarget=${tgt}s" \
        '--*.server.app[0].feedbackInterval=200ms' \
        '--*.ue.app[0].cameraRate=1000kbps' \
        '--*.ue.app[0].cameraBurst=262144B' \
        --output-scalar-file="$sca" \
        --output-vector-file="$SCRATCH/$tag.vec" \
        >> "$LOG" 2>&1 \
        || echo "FAILED $tag" >> "$LOG"
    # Vectors exist only so they do not land in the ini's default results/ and
    # overwrite tracked baselines. Dropping them on exit bounds peak scratch
    # use by the slot count instead of by the campaign size.
    rm -f "$SCRATCH/$tag.vec" "$SCRATCH/$tag.vci"
}

count() { echo $#; }
PER_CORRIDOR=$(( $(count $ARMS) * $(count $TARGETS) * $(count $SEEDS) ))
EXPECTED=$(( PER_CORRIDOR * $(count $CORRIDORS) ))

echo "=== corridor_target_sweep started $(date -Is), expecting $EXPECTED ===" >> "$LOG"
for c in $CORRIDORS; do
    J="$(slots_for "$c")"
    echo "--- $c ($J slots) $(date -Is) ---" >> "$LOG"
    for s in $SEEDS; do
        for tgt in $TARGETS; do
            for arm in $ARMS; do
                while [ "$(jobs -rp | wc -l)" -ge "$J" ]; do wait -n; done
                run_cell "$c" "$arm" "$tgt" "$s" &
            done
        done
    done
    wait
    echo "--- $c done, $(ls "$OUT"/${c}-*.sca 2>/dev/null | wc -l)/$PER_CORRIDOR $(date -Is) ---" >> "$LOG"
done
wait
echo "=== corridor_target_sweep finished $(date -Is) ===" >> "$LOG"

echo "scalar files: $(ls "$OUT"/*.sca 2>/dev/null | wc -l)/$EXPECTED"
python3 -I "$ROOT/tools/validate_runs.py" "$OUT"
