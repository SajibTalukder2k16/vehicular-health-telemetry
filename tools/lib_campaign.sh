# Shared machinery for the corridor campaign runners. Sourced, not executed.
#
# This exists because the scratch-space guard below is safety-critical and must
# not drift between runners. Its absence already cost one campaign: vectors were
# redirected to /tmp, which on this box is a 7.7 GB *tmpfs* -- RAM, not disk --
# so they consumed memory, drove the box 3.1 GB into swap, filled the volume,
# and 277 of 490 runs then aborted in milliseconds while the runner cheerfully
# logged corridors "complete" in two seconds. One copy, one place to fix.
#
# Usage: source "$(dirname "$0")/lib_campaign.sh"
# Expects SCRATCH and OUT to be set by the caller.

# --- seeding -----------------------------------------------------------------
# simulations/corridorpop/omnetpp.ini sets `repeat = 3` with
# `seed-set = ${repetition}` crossed with `numBgUes = ${bgues=2,20}`, so the
# run-index space is 6 and runs 3,4,5 ARE the three seeds of the bgues=20 arm.
# Raising `repeat` would renumber every run in the existing archive. So every
# runner holds -r $BGUES20_RUN and overrides --seed-set per run instead.
#
# Verified rather than assumed: `-r 3 --seed-set=0` reproduced
# results_ctl/c08-aimd-3.sca with every scalar bit-identical.
# Run indices for the two background-load levels, both verified against the
# archive: run 3 is bgues=20/repetition 0, run 0 is bgues=2/repetition 0.
BGUES20_RUN=3
BGUES2_RUN=0

CORRIDOR_LIST="c08 c09 c10 c11 c12 c13 c14"

# --- concurrency -------------------------------------------------------------
# A c08 run is ~900 MB RSS measured (18 eNodeBs, full X2 mesh); smaller
# corridors cost proportionally less. validate_runs.py notes the OOM killer
# fires here, and an OOM'd run leaves a file that still greps as complete, so
# slots are set per corridor from eNodeB count and kept short of the limit.
#
# Sized for a box reporting 31 GB with 24 cores (it was 15.7 GB before a
# 2026-10-30 restart, and the earlier counts of 10/11/14/16 were sized to
# that). At 20 concurrent c08 runs this is ~18 GB, leaving ~11 GB spare, so the
# binding constraint is now the 24 cores rather than memory. Re-check `free -g`
# before raising these further: the earlier values were briefly set on the
# inference that memory pressure came only from a tmpfs, which was wrong.
slots_for() {
    case "$1" in
        c08|c10) echo 20 ;;  # 18 eNodeBs
        c09)     echo 20 ;;  # 15
        c11|c12) echo 22 ;;  # 8, 7
        c13|c14) echo 22 ;;  # 5, 1
        *)       echo 20 ;;
    esac
}

# --- scratch vetting ---------------------------------------------------------
# A campaign that runs out of scratch space does not stop; it keeps launching
# runs that fail instantly and leaves a directory of truncated scalar files.
# Refuse to start instead. tmpfs is named explicitly because that is the trap
# that actually fired: it looks like disk and spends RAM.
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
    if [ "${avail_mb:-0}" -lt 2048 ]; then
        echo "scratch $SCRATCH has only ${avail_mb:-0} MB free -- refusing." >&2
        return 1
    fi
    echo "scratch $SCRATCH: $fstype, ${avail_mb} MB free"
}

# --- completion test ---------------------------------------------------------
# Mirrors tools/validate_runs.py rather than grepping for one string: a run
# killed mid-write still contains "packetsGenerated" somewhere and would pass
# the weaker test, then read as zeros in the exporter.
done_already() {
    local f="$1"
    [ -s "$f" ] || return 1
    grep -qE 'scalar \S*\.rig\.wearable packetsGenerated [1-9]' "$f" || return 1
    grep -qE 'scalar \S*\.rig\.camera packetsGenerated [1-9]' "$f" || return 1
    return 0
}
