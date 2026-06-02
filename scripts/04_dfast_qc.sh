#!/bin/bash
# Safe shell options (pipefail only if supported)
set -euo
if set -o | grep -q pipefail; then
    set -o pipefail
fi

# ==============================================================================
# SCRIPT: 04_dfast_qc.sh (Taxonomy‑only)
# PURPOSE: Run DFAST‑QC on all bins (bin.*.fa) for taxonomy only.
#          Completeness/contamination (CheckM) is disabled.
# INPUT:   $1 = bin directory (e.g. results/03_binning)
#          $2 = output directory (e.g. results/04_bin_taxonomy)
#          $3 = threads (optional)
# ENV:     dfast_qc_db_env (must contain dfast_qc executable)
# DB:      ~/FYP/databases/dfast_qc_db/dqc_reference_compact
# ==============================================================================

BIN_DIR="$1"
OUT_DIR="$2"
THREADS="${3:-4}"

# Fixed paths
PROJECT_DIR="$HOME/FYP"
ENV_PATH="$PROJECT_DIR/envs/dfast_qc_db_env"
DB_DIR="$PROJECT_DIR/databases/dfast_qc_db/dqc_reference_compact"

# Activate environment
source "$HOME/miniconda3/etc/profile.d/conda.sh" 2>/dev/null || \
source "$HOME/anaconda3/etc/profile.d/conda.sh" 2>/dev/null

if [ ! -d "$ENV_PATH" ]; then
    echo "ERROR: DFAST‑QC environment not found at $ENV_PATH" >&2
    exit 1
fi
conda activate "$ENV_PATH"

# Check that dfast_qc is available
if ! command -v dfast_qc &> /dev/null; then
    echo "ERROR: 'dfast_qc' command not found in environment $ENV_PATH" >&2
    exit 1
fi

# Check database directory
if [ ! -d "$DB_DIR" ]; then
    echo "ERROR: DFAST‑QC database not found at $DB_DIR" >&2
    exit 1
fi

mkdir -p "$OUT_DIR"
GLOBAL_LOG="$OUT_DIR/dfast_qc_global.log"
echo "=== DFAST‑QC (Taxonomy‑only) started at $(date) ===" | tee -a "$GLOBAL_LOG"
echo "Bin directory : $BIN_DIR" | tee -a "$GLOBAL_LOG"
echo "Output dir    : $OUT_DIR" | tee -a "$GLOBAL_LOG"
echo "Database      : $DB_DIR" | tee -a "$GLOBAL_LOG"
echo "Threads       : $THREADS" | tee -a "$GLOBAL_LOG"
echo "" | tee -a "$GLOBAL_LOG"

# Find all sample subdirectories (each containing bin.*.fa files)
find "$BIN_DIR" -maxdepth 1 -mindepth 1 -type d | sort | while read -r sample_dir; do
    sample=$(basename "$sample_dir")
    sample_out="$OUT_DIR/$sample"
    mkdir -p "$sample_out"

    echo "----------------------------------------" | tee -a "$GLOBAL_LOG"
    echo "Processing sample: $sample" | tee -a "$GLOBAL_LOG"

    # Find all bin files matching bin.[0-9]*.fa (numerical bins only)
    bin_files=()
    while IFS= read -r -d '' f; do
        bin_files+=("$f")
    done < <(find "$sample_dir" -maxdepth 1 -type f -name "bin.[0-9]*.fa" -print0)

    if [ ${#bin_files[@]} -eq 0 ]; then
        echo "   No numerical bins found – skipping." | tee -a "$GLOBAL_LOG"
        continue
    fi
    echo "   Found ${#bin_files[@]} bins: ${bin_files[*]}" | tee -a "$GLOBAL_LOG"

    # Create a simple list of all bins processed (optional)
    all_bins_list="$sample_out/all_bins.txt"
    > "$all_bins_list"

    # Run DFAST‑QC on each bin (CheckM disabled)
    for bin_file in "${bin_files[@]}"; do
        bin_name=$(basename "$bin_file" .fa)
        bin_out="$sample_out/$bin_name"
        mkdir -p "$bin_out"

        echo "   [RUNNING] $bin_name" | tee -a "$GLOBAL_LOG"

        # DFAST‑QC command – using correct flags: -i, -o, -r, -t, --force, and --disable_cc
        dfast_qc \
            -i "$bin_file" \
            -o "$bin_out" \
            -r "$DB_DIR" \
            -t "$THREADS" \
            --force \
            --disable_cc \
            > "$bin_out/dfast_qc.log" 2>&1

        # Check for successful completion by looking for taxonomy result
        if [ -f "$bin_out/tc_result.tsv" ]; then
            echo "         ✓ Taxonomy result generated" | tee -a "$GLOBAL_LOG"
            echo "$bin_name" >> "$all_bins_list"
        else
            echo "         [ERROR] Taxonomy result missing – check log" | tee -a "$GLOBAL_LOG"
        fi
    done

    # Mark sample as done
    touch "$sample_out/dfast_qc.done"
    echo "   Sample $sample finished at $(date)" | tee -a "$GLOBAL_LOG"
done

echo "========================================" | tee -a "$GLOBAL_LOG"
echo "DFAST‑QC (Taxonomy‑only) processing complete at $(date)" | tee -a "$GLOBAL_LOG"