#!/bin/bash
# Export the vector subsets (.vec) of the Family B case studies into the CSVs
# that analysis/figures_src/_shared.py:load_vec() reads.
#
#   analysis/vectors/<Config>_r<seed>.csv
#
# Usage: export_vectors.sh [config ...]    (default: all Family B v2 configs)
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/analysis/vectors"
# setenv calls exit() when sourced non-interactively, so use the
# tool path directly instead of putting it on PATH.
SCAVE="${OMNETPP_ROOT:-/home/sajib/omnetpp-6.4.0}/bin/opp_scavetool"
mkdir -p "$OUT"

CONFIGS=("$@")
if [ ${#CONFIGS[@]} -eq 0 ]; then
    CONFIGS=(DcDriveAtt DcDriveTmo DcDriveVzw DcDriveLegacy8
             VaDriveAtt VaDriveTmo VaDriveVzw VaDriveLegacy8)
fi

for cfg in "${CONFIGS[@]}"; do
    case "$cfg" in
        Dc*) dir=dc_case ;;
        Va*) dir=va_case ;;
        *)   echo "unknown config $cfg" >&2; exit 1 ;;
    esac
    for r in 0 1 2; do
        vec="$ROOT/simulations/$dir/results/vec_subset/$cfg-vec-$r.vec"
        if [ ! -f "$vec" ]; then
            echo "MISSING $vec" >&2
            continue
        fi
        "$SCAVE" export -f 'type =~ vector' -F CSV-R \
            -o "$OUT/${cfg}_r${r}.csv" "$vec" >/dev/null
        echo "wrote $OUT/${cfg}_r${r}.csv"
    done
done
