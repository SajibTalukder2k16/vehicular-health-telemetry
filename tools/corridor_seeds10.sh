#!/bin/bash
# Raise the corridor headline from 3 seeds to 10.
#
# docs/CORRIDOR_REGIME.md's oracle audit (commit 85e1d2ea1) concluded the
# controller beats a per-corridor-tuned static cap by +28.0 +/- 22.1 pp of
# timely camera. The point estimate is the paper's load-bearing number and the
# interval is wide enough that a reviewer can reasonably ask whether it clears
# zero at all -- it does, but only just, and on 3 seeds per cell. This re-runs
# every cell of that comparison at 10 seeds.
#
# SEEDING. simulations/corridorpop/omnetpp.ini sets `repeat = 3` with
# `seed-set = ${repetition}` and crosses it with `numBgUes = ${bgues=2,20}`, so
# the run-index space is 6 and runs 3,4,5 ARE the three seeds of the bgues=20
# arm (seedsets 0,1,2). Raising `repeat` would renumber every run in the
# existing archive, so instead this keeps `-r 3` -- which fixes bgues=20 and
# every other iteration variable -- and overrides `--seed-set` per run.
# Command-line options outrank the ini, so seed-set wins over ${repetition}.
#
# That equivalence was verified before launching, not assumed: `-r 3
# --seed-set=0` reproduced results_ctl/c08-aimd-3.sca with every scalar
# bit-identical, the only additions being the bucketRate statistics that did
# not exist when the baseline was recorded. The same diff incidentally confirms
# that the dropsStaleCamera() refactor left the `aimd` arm unchanged.
#
# VECTORS must be redirected explicitly and must NOT be kept.
#
# The redirect itself is non-negotiable: --output-scalar-file alone leaves
# vectors landing in the ini's default results/, overwriting the tracked
# baseline .vec files for these configs (see aimd_sensitivity.sh -- this has
# already happened once). But they must not be kept either: .vec is Git-LFS
# tracked, a c08 vector file is ~22 MB, and 490 of them is ~11 GB of LFS
# holding data no analyzer reads. The scalars carry everything the analysis
# uses.
#
# So each run's vector file is deleted the moment that run exits. Peak usage is
# then bounded by the number of concurrent slots, not by the campaign size.
#
# The first attempt at this pointed the redirect at /tmp, which on this box is
# a 7.7 GB *tmpfs* -- RAM, not disk. The vectors filled it, and because tmpfs
# pages are memory the box went 3.1 GB into swap and then returned ENOSPC;
# 277 of 490 runs failed, the later corridors "completing" in two seconds with
# zero output. Hence check_scratch() below: the scratch directory is verified
# to be on a real filesystem with room before a single run is launched. Space
# for intermediate files is a precondition, not an afterthought.
#
# CONCURRENCY is memory-bound, not CPU-bound: one c08 run peaks at ~1.0 GB RSS
# on 18 eNodeBs with a full X2 mesh, against 24 cores and ~13 GB free.
# tools/validate_runs.py notes the OOM killer fires here often, and an OOM'd
# run leaves a file that still greps as complete, so slots are set per corridor
# from its eNodeB count and kept short of what the memory would just allow.
# (The earlier, far tighter slot counts were compensating for the tmpfs
# footprint described above rather than for the simulations themselves.)
#
# 7 corridors x (5 static caps + aimd + aimdSelf) x 10 seeds = 490 runs.
#
# Seeds 0-2 duplicate the existing 3-seed archive rather than reusing it, so
# that the whole 10-seed dataset comes from one binary under one naming scheme.
# Idempotent: validated cells are skipped, so it can be re-run to fill gaps.
#
# Usage: corridor_seeds10.sh [scratch-dir]
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NED="$ROOT/src:$ROOT/simulations:$ROOT/../inet4.7/src:$ROOT/../Simu5G/src"
LIB="$ROOT/../Simu5G/src/simu5g"
BIN="$ROOT/src/out/clang-release/paperrebuild"
OUT="$ROOT/simulations/corridorpop/results_seeds10"
# Deliberately NOT under /tmp: see the vectors note above. Overridable, but
# check_scratch() vets whatever it is pointed at.
SCRATCH="${1:-$HOME/.cache/paperrebuild-vec}"
LOG="$OUT/campaign.log"

# Overridable so the exact command construction can be smoke-tested on one
# cheap cell, and so a gap-filling re-run can be narrowed to what is missing.
SEEDS="${SEEDS:-0 1 2 3 4 5 6 7 8 9}"
CAPS="${CAPS:-200 400 600 800 1000}"
CORRIDORS="${CORRIDORS:-c08 c09 c10 c11 c12 c13 c14}"

mkdir -p "$OUT" "$SCRATCH"
cd "$ROOT/simulations/corridorpop" || exit 1
[ -x "$BIN" ] || { echo "no binary at $BIN -- source setenv and make first" >&2; exit 1; }

# A campaign that runs out of scratch space does not stop; it keeps launching
# runs that fail in milliseconds and leaves a directory of truncated scalar
# files. Refuse to start instead. tmpfs is called out by name because that is
# the trap that actually fired: it looks like disk and spends RAM.
check_scratch() {
    local fstype avail_mb
    fstype=$(df -PT "$SCRATCH" 2>/dev/null | awk 'NR==2{print $2}')
    avail_mb=$(df -Pm "$SCRATCH" 2>/dev/null | awk 'NR==2{print $4}')
    case "$fstype" in
        tmpfs|ramfs)
            echo "scratch $SCRATCH is $fstype (RAM-backed) -- refusing." >&2
            echo "Pass a directory on a real filesystem as \$1." >&2
            return 1 ;;
    esac
    # Only concurrent runs' vectors exist at once (each is deleted on exit),
    # but allow generous headroom for the widest slot count.
    if [ "${avail_mb:-0}" -lt 2048 ]; then
        echo "scratch $SCRATCH has only ${avail_mb:-0} MB free -- refusing." >&2
        return 1
    fi
    echo "scratch $SCRATCH: $fstype, ${avail_mb} MB free"
}
check_scratch || exit 1

# eNodeB count per corridor drives the slot count: 18 sites with a full mesh
# costs ~1.1 GB, 1 site costs a fraction of that.
slots_for() {
    case "$1" in
        c08|c10) echo 10 ;;  # 18 eNodeBs, ~1.0 GB RSS each
        c09)     echo 11 ;;  # 15
        c11|c12) echo 14 ;;  # 8, 7
        c13|c14) echo 16 ;;  # 5, 1
        *)       echo 10 ;;
    esac
}

# A cell is done only if the scalar file holds a non-zero generation count for
# both sensor streams. Mirrors tools/validate_runs.py's rule rather than
# grepping for one string, because an OOM-killed run passes that weaker test.
done_already() {
    local f="$1"
    [ -s "$f" ] || return 1
    grep -qE 'scalar \S*\.rig\.wearable packetsGenerated [1-9]' "$f" || return 1
    grep -qE 'scalar \S*\.rig\.camera packetsGenerated [1-9]' "$f" || return 1
    return 0
}

run_cell() {
    local c="$1" arm="$2" s="$3"; shift 3
    local tag="${c}-${arm}-s$(printf '%02d' "$s")"
    local sca="$OUT/$tag.sca"
    done_already "$sca" && return 0
    "$BIN" -u Cmdenv -c "$c" -r 3 -n "$NED" -l "$LIB" \
        --cmdenv-express-mode=true --cmdenv-status-frequency=5000s \
        --seed-set="$s" \
        "$@" \
        '--*.ue.app[0].cameraBurst=262144B' \
        --output-scalar-file="$sca" \
        --output-vector-file="$SCRATCH/$tag.vec" \
        >> "$LOG" 2>&1 \
        || echo "FAILED $tag" >> "$LOG"
    # Drop the vectors immediately: they exist only so they do not land in the
    # ini's default results/, and keeping them bounds peak scratch use by the
    # slot count rather than by the campaign size.
    rm -f "$SCRATCH/$tag.vec" "$SCRATCH/$tag.vci"
}

count() { echo $#; }
PER_CORRIDOR=$(( ($(count $CAPS) + 2) * $(count $SEEDS) ))
EXPECTED=$(( PER_CORRIDOR * $(count $CORRIDORS) ))

started=0
echo "=== corridor_seeds10 started $(date -Is), expecting $EXPECTED ===" >> "$LOG"

for c in $CORRIDORS; do
    J="$(slots_for "$c")"
    echo "--- $c ($J slots) $(date -Is) ---" >> "$LOG"
    for s in $SEEDS; do
        # static arms: fixed cap, paced to it, no feedback loop
        for cap in $CAPS; do
            while [ "$(jobs -rp | wc -l)" -ge "$J" ]; do wait -n; done
            run_cell "$c" "static$cap" "$s" \
                '--*.ue.app[0].admissionPolicy="dropPace"' \
                "--*.ue.app[0].cameraRate=${cap}kbps" &
            started=$((started+1))
        done
        # controller arms: 1000 kbps ceiling, 200 ms feedback
        for arm in aimd aimdSelf; do
            while [ "$(jobs -rp | wc -l)" -ge "$J" ]; do wait -n; done
            run_cell "$c" "$arm" "$s" \
                "--*.ue.app[0].admissionPolicy=\"$arm\"" \
                '--*.server.app[0].feedbackInterval=200ms' \
                '--*.ue.app[0].cameraRate=1000kbps' &
            started=$((started+1))
        done
    done
    wait
    echo "--- $c complete, $(ls "$OUT"/${c}-*.sca 2>/dev/null | wc -l)/$PER_CORRIDOR files $(date -Is) ---" >> "$LOG"
done
wait

echo "=== corridor_seeds10 finished $(date -Is), launched $started ===" >> "$LOG"
echo "scalar files: $(ls "$OUT"/*.sca 2>/dev/null | wc -l)/$EXPECTED"
python3 -I "$ROOT/tools/validate_runs.py" "$OUT"
