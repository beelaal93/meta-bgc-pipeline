#!/bin/bash
set -euo pipefail

V_COMPLETENESS=${CHECKM2_COMPLETENESS:-50}
V_CONTAMINATION=${CHECKM2_CONTAMINATION:-10}

BIN_DIR="$1"
OUTPUT_DIR="$2"
THREADS="${3:-6}"

# Set database file path
KNOWN_DB_FILE="$HOME/FYP/databases/CheckM2_database/checkm2_db.dmnd"
if [ ! -f "$KNOWN_DB_FILE" ]; then
    echo "ERROR: CheckM2 database not found at $KNOWN_DB_FILE"
    exit 1
fi
echo "Using CheckM2 database: $KNOWN_DB_FILE"

# Activate environment
ENV_PATH="$HOME/FYP/envs/checkm2_env"
source "$HOME/miniconda3/etc/profile.d/conda.sh" 2>/dev/null || source "$HOME/anaconda3/etc/profile.d/conda.sh" 2>/dev/null
conda activate "$ENV_PATH"

if ! command -v checkm2 &> /dev/null; then
    echo "ERROR: checkm2 command not found"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"
GLOBAL_LOG="$OUTPUT_DIR/checkm2_global.log"
echo "=== CheckM2 run at $(date) ===" | tee -a "$GLOBAL_LOG"
echo "BIN_DIR: $BIN_DIR" | tee -a "$GLOBAL_LOG"
echo "OUTPUT_DIR: $OUTPUT_DIR" | tee -a "$GLOBAL_LOG"
echo "THREADS: $THREADS" | tee -a "$GLOBAL_LOG"
echo "DATABASE: $KNOWN_DB_FILE" | tee -a "$GLOBAL_LOG"

process_sample() {
    local sample_dir="$1"
    local sample_name="$2"
    local sample_out="$OUTPUT_DIR/$sample_name"
    mkdir -p "$sample_out"

    echo "--- Processing sample: $sample_name ---" | tee -a "$GLOBAL_LOG"
    echo "   Source: $sample_dir" | tee -a "$GLOBAL_LOG"

    # Find real bins
    mapfile -t bin_files < <(find "$sample_dir" -maxdepth 1 -type f -name "bin.[0-9]*.fa" 2>/dev/null | sort)
    if [ ${#bin_files[@]} -eq 0 ]; then
        echo "   No real bins found" | tee -a "$GLOBAL_LOG"
        return
    fi
    echo "   Found ${#bin_files[@]} bins: ${bin_files[*]}" | tee -a "$GLOBAL_LOG"

    if [ -f "$sample_out/checkm2.done" ]; then
        echo "   Already processed" | tee -a "$GLOBAL_LOG"
        return
    fi
    rm -f "$sample_out/checkm2.failed"

    # Create a temporary directory in /tmp with a simple name
    TEMP_DIR="/tmp/checkm2_$$_$sample_name"
    rm -rf "$TEMP_DIR"
    mkdir -p "$TEMP_DIR"
    echo "   Using temporary directory: $TEMP_DIR" | tee -a "$GLOBAL_LOG"

    # Copy bins to temp dir
    for b in "${bin_files[@]}"; do
        cp "$b" "$TEMP_DIR/"
    done

    echo "   Copied bins to $TEMP_DIR" | tee -a "$GLOBAL_LOG"
    ls -la "$TEMP_DIR" | sed 's/^/       /' | tee -a "$GLOBAL_LOG"

    # Prepare log file
    LOG_FILE="$sample_out/checkm2_run.log"
    TMP_OUT=$(mktemp)

    # Run CheckM2 from the temp directory, explicitly specifying database path
    echo "   Running: checkm2 predict --input . --output-directory $sample_out --threads $THREADS -x fa --database_path $KNOWN_DB_FILE --force" | tee -a "$GLOBAL_LOG"
    (cd "$TEMP_DIR" && checkm2 predict \
        --input . \
        --output-directory "$sample_out" \
        --threads "$THREADS" \
        -x fa \
        --database_path "$KNOWN_DB_FILE" \
        --force) > "$TMP_OUT" 2>&1
    exit_code=$?

    mv "$TMP_OUT" "$LOG_FILE"

    # Clean up temp dir
    rm -rf "$TEMP_DIR"

    if [ $exit_code -ne 0 ]; then
        echo "   ERROR: CheckM2 failed (exit $exit_code)" | tee -a "$GLOBAL_LOG"
        echo "   Last 20 lines of log:" | tee -a "$GLOBAL_LOG"
        tail -20 "$LOG_FILE" | sed 's/^/       /' | tee -a "$GLOBAL_LOG"
        touch "$sample_out/checkm2.failed"
        return
    fi

    # Verify output
    if [ ! -f "$sample_out/quality_report.tsv" ]; then
        echo "   ERROR: quality_report.tsv not generated" | tee -a "$GLOBAL_LOG"
        touch "$sample_out/checkm2.failed"
        return
    fi

    # Filter good bins
    echo "   Filtering bins (completeness >= $V_COMPLETENESS, contamination <= $V_CONTAMINATION)" | tee -a "$GLOBAL_LOG"
    awk -F'\t' -v comp="$V_COMPLETENESS" -v cont="$V_CONTAMINATION" \
        'NR==1 {print $0; next} $2 >= comp && $3 <= cont {print $0}' \
        "$sample_out/quality_report.tsv" > "$sample_out/good_bins.tsv"

    good_count=$(tail -n +2 "$sample_out/good_bins.tsv" | wc -l)
    echo "   Good bins: $good_count" | tee -a "$GLOBAL_LOG"

    touch "$sample_out/checkm2.done"
    echo "   ✓ Completed" | tee -a "$GLOBAL_LOG"
}

# Main loop
mapfile -t subdirs < <(find "$BIN_DIR" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | sort)
if [ ${#subdirs[@]} -gt 0 ]; then
    echo "Found ${#subdirs[@]} sample directories" | tee -a "$GLOBAL_LOG"
    for sample_path in "${subdirs[@]}"; do
        sample_name=$(basename "$sample_path")
        process_sample "$sample_path" "$sample_name"
    done
else
    echo "No sample subdirectories found; checking $BIN_DIR directly" | tee -a "$GLOBAL_LOG"
    if ls "$BIN_DIR"/bin.[0-9]*.fa >/dev/null 2>&1; then
        process_sample "$BIN_DIR" "default_sample"
    else
        echo "No real bin files found in $BIN_DIR" | tee -a "$GLOBAL_LOG"
    fi
fi

echo "=== CheckM2 processing complete ===" | tee -a "$GLOBAL_LOG"