#!/bin/bash
# ==============================================================================
# SCRIPT: 01_quality_control.sh (Rewritten – Robust QC Pipeline)
# PURPOSE: Run FastQC (raw) → fastp (trimming) → FastQC (clean)
# INPUT:   $1 = input directory (raw FASTQ, e.g., results/fetch_convert)
#          $2 = output directory (where QC results will be stored)
#          $3 = threads (optional, default = 4)
# ENV:     qc_env (must contain fastp, fastqc)
# PARAMS:  QC_QUAL, QC_LEN, QC_UNQUAL, QC_FRONT, QC_TAIL (exported by app.py)
# ==============================================================================

set -euo pipefail

# ------------------------------------------------------------------------------
# 1. Parse arguments and create directories
# ------------------------------------------------------------------------------
INPUT_DIR="$1"
OUTPUT_DIR="$2"
THREADS="${3:-4}"

RAW_QC_DIR="$OUTPUT_DIR/fastqc_raw"
CLEAN_QC_DIR="$OUTPUT_DIR/fastqc_clean"
FASTP_DIR="$OUTPUT_DIR/fastp_reports"
CLEAN_DIR="$OUTPUT_DIR/clean_reads"

mkdir -p "$RAW_QC_DIR" "$CLEAN_QC_DIR" "$FASTP_DIR" "$CLEAN_DIR"

# ------------------------------------------------------------------------------
# 2. Logging function
# ------------------------------------------------------------------------------
log() {
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') - $*" | tee -a "$OUTPUT_DIR/qc_pipeline.log"
}

# ------------------------------------------------------------------------------
# 3. Activate conda environment (with explicit error checking)
# ------------------------------------------------------------------------------
source "$HOME/miniconda3/etc/profile.d/conda.sh" 2>/dev/null ||
    source "$HOME/anaconda3/etc/profile.d/conda.sh" 2>/dev/null ||
    { log "ERROR: Conda not found. Please install Miniconda/Anaconda."; exit 1; }

ENV_PATH="$HOME/FYP/envs/qc_env"
if ! conda activate "$ENV_PATH"; then
    log "ERROR: Cannot activate $ENV_PATH. Check that the environment exists."
    exit 1
fi

# Verify required tools are present
for tool in fastp fastqc; do
    if ! command -v "$tool" &> /dev/null; then
        log "ERROR: $tool not found in $ENV_PATH. Please install it."
        exit 1
    fi
done

# ------------------------------------------------------------------------------
# 4. Read QC parameters (from environment, with safe defaults)
# ------------------------------------------------------------------------------
V_QUAL="${QC_QUAL:-20}"
V_LEN="${QC_LEN:-50}"
V_UNQUAL="${QC_UNQUAL:-40}"
V_FRONT="${QC_FRONT:-0}"
V_TAIL="${QC_TAIL:-0}"

log "=========================================="
log "QC Pipeline started"
log "Input:  $INPUT_DIR"
log "Output: $OUTPUT_DIR"
log "Threads: $THREADS"
log "Parameters: qual=$V_QUAL, min_len=$V_LEN, unqual=$V_UNQUAL, front=$V_FRONT, tail=$V_TAIL"
log "=========================================="

# ------------------------------------------------------------------------------
# 5. Helper: flexible R1/R2 detection
# ------------------------------------------------------------------------------
find_r1_files() {
    # Find files that look like R1 (paired-end first read)
    # Patterns: _1.fastq.gz, _R1.fastq.gz, _1.fastq, _R1.fastq
    find "$INPUT_DIR" -type f \( \
        -name "*_1.fastq.gz" -o \
        -name "*_R1.fastq.gz" -o \
        -name "*_1.fastq" -o \
        -name "*_R1.fastq" \) | sort
}

derive_r2() {
    local r1="$1"
    local r2=""
    # Try different naming conventions
    r2="${r1/_1.fastq.gz/_2.fastq.gz}"
    [ -f "$r2" ] && echo "$r2" && return
    r2="${r1/_R1.fastq.gz/_R2.fastq.gz}"
    [ -f "$r2" ] && echo "$r2" && return
    r2="${r1/_1.fastq/_2.fastq}"
    [ -f "$r2" ] && echo "$r2" && return
    r2="${r1/_R1.fastq/_R2.fastq}"
    [ -f "$r2" ] && echo "$r2" && return
    # No R2 found – single‑end case
    echo ""
}

# ------------------------------------------------------------------------------
# 6. Main processing loop
# ------------------------------------------------------------------------------
R1_FILES=$(find_r1_files)
if [ -z "$R1_FILES" ]; then
    log "ERROR: No R1 FASTQ files found in $INPUT_DIR. Check naming convention."
    exit 1
fi

for R1 in $R1_FILES; do
    R2=$(derive_r2 "$R1")
    # Determine sample name (remove path and trailing patterns)
    SAMPLE=$(basename "$R1" | sed -E 's/_(1|R1)(\.fastq(\.gz)?)$//')
    log "----------------------------------------"
    log "Processing sample: $SAMPLE"
    log "  R1: $R1"
    [ -n "$R2" ] && log "  R2: $R2" || log "  (single‑end mode)"

    # Output file paths
    CLEAN_R1="$CLEAN_DIR/${SAMPLE}_clean_1.fastq.gz"
    CLEAN_R2="$CLEAN_DIR/${SAMPLE}_clean_2.fastq.gz"
    [ -z "$R2" ] && CLEAN_R1="$CLEAN_DIR/${SAMPLE}_clean.fastq.gz"

    # Skip if cleaning already done
    if [ -f "$CLEAN_R1" ] && { [ -z "$R2" ] || [ -f "$CLEAN_R2" ]; }; then
        log "  [SKIP] Cleaned reads already exist."
        # Still run FastQC on existing clean files if missing
        if [ ! -f "$CLEAN_QC_DIR/${SAMPLE}_clean_1_fastqc.html" ]; then
            log "  [FastQC] Generating report for existing clean reads..."
            if [ -z "$R2" ]; then
                fastqc -t "$THREADS" -o "$CLEAN_QC_DIR" "$CLEAN_R1"
            else
                fastqc -t "$THREADS" -o "$CLEAN_QC_DIR" "$CLEAN_R1" "$CLEAN_R2"
            fi
        fi
        continue
    fi

    # --------------------------------------------------------------------------
    # Step A: Raw FastQC (only if not already present)
    # --------------------------------------------------------------------------
    if [ ! -f "$RAW_QC_DIR/${SAMPLE}_1_fastqc.html" ]; then
        log "  [1/3] Running FastQC on raw reads..."
        if [ -z "$R2" ]; then
            fastqc -t "$THREADS" -o "$RAW_QC_DIR" "$R1"
        else
            fastqc -t "$THREADS" -o "$RAW_QC_DIR" "$R1" "$R2"
        fi
    else
        log "  [1/3] Raw FastQC reports already exist – skipping."
    fi

    # --------------------------------------------------------------------------
    # Step B: fastp trimming
    # --------------------------------------------------------------------------
    log "  [2/3] Running fastp trimming..."

    # Build optional cut arguments (only if value > 0)
    CUT_ARGS=""
    if [ "$V_FRONT" -gt 0 ]; then
        CUT_ARGS="$CUT_ARGS --cut_front --cut_front_window_size=4 --cut_front_mean_quality=$V_QUAL"
    fi
    if [ "$V_TAIL" -gt 0 ]; then
        CUT_ARGS="$CUT_ARGS --cut_tail --cut_tail_window_size=4 --cut_tail_mean_quality=$V_QUAL"
    fi

    # fastp command for paired‑end or single‑end
    FASTP_LOG="$FASTP_DIR/${SAMPLE}_fastp.log"
    if [ -n "$R2" ]; then
        # Paired‑end
        fastp \
            -i "$R1" -I "$R2" \
            -o "$CLEAN_R1" -O "$CLEAN_R2" \
            -q "$V_QUAL" -l "$V_LEN" -u "$V_UNQUAL" \
            $CUT_ARGS \
            --detect_adapter_for_pe \
            --thread "$THREADS" \
            --compression 6 \
            -h "$FASTP_DIR/${SAMPLE}_fastp.html" \
            -j "$FASTP_DIR/${SAMPLE}_fastp.json" \
            > "$FASTP_LOG" 2>&1
    else
        # Single‑end
        fastp \
            -i "$R1" \
            -o "$CLEAN_R1" \
            -q "$V_QUAL" -l "$V_LEN" -u "$V_UNQUAL" \
            $CUT_ARGS \
            --thread "$THREADS" \
            --compression 6 \
            -h "$FASTP_DIR/${SAMPLE}_fastp.html" \
            -j "$FASTP_DIR/${SAMPLE}_fastp.json" \
            > "$FASTP_LOG" 2>&1
    fi

    if [ $? -ne 0 ] || [ ! -s "$CLEAN_R1" ]; then
        log "  ERROR: fastp failed for $SAMPLE. Check log: $FASTP_LOG"
        exit 1
    fi
    log "  fastp completed successfully."

    # --------------------------------------------------------------------------
    # Step C: Clean FastQC
    # --------------------------------------------------------------------------
    log "  [3/3] Running FastQC on cleaned reads..."
    if [ -z "$R2" ]; then
        fastqc -t "$THREADS" -o "$CLEAN_QC_DIR" "$CLEAN_R1"
    else
        fastqc -t "$THREADS" -o "$CLEAN_QC_DIR" "$CLEAN_R1" "$CLEAN_R2"
    fi

    log "  Finished sample $SAMPLE"
done

# ------------------------------------------------------------------------------
# 7. Final summary
# ------------------------------------------------------------------------------
log "=========================================="
log "QC Pipeline finished successfully at $(date)"
log "Reports:"
log "  Raw FastQC:      $RAW_QC_DIR"
log "  Clean FastQC:    $CLEAN_QC_DIR"
log "  fastp reports:   $FASTP_DIR"
log "  Cleaned reads:   $CLEAN_DIR"
log "=========================================="