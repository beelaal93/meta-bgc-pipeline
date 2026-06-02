#!/bin/bash
# ==============================================================================
# SCRIPT: 00_a_download.sh (Multi‑sample, skips existing FASTQ)
# ENV: fetch_env (sra-tools 3.0+)
# PURPOSE: Download one or more SRA runs sequentially, skip if FASTQ already exists
# USAGE:   00_a_download.sh <OUTPUT_DIR> <SRR1> [SRR2] ...
# ==============================================================================

OUTPUT_DIR="$1"
shift   # Remove first argument, leaving all SRR IDs

if [ $# -eq 0 ]; then
    echo -e "\033[0;31m[ERROR] No SRA accessions provided.\033[0m"
    echo "Usage: $0 <OUTPUT_DIR> <SRR1> [SRR2] ..."
    exit 1
fi

ENV_PATH="$HOME/FYP/envs/fetch_env"

# --- Activate environment (once) ---
source "$HOME/miniconda3/etc/profile.d/conda.sh" 2>/dev/null || source "$HOME/anaconda3/etc/profile.d/conda.sh" 2>/dev/null

if [ -d "$ENV_PATH" ]; then
    conda activate "$ENV_PATH"
else
    echo -e "\033[0;31m[ERROR] 'fetch_env' not found at $ENV_PATH\033[0m"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"
cd "$OUTPUT_DIR" || exit 1

# --- Track failures and skips ---
FAILED=""
SKIPPED=""
SUCCESS_COUNT=0
TOTAL=$#

# --- Function to check if FASTQ already exists ---
fastq_exists() {
    local id="$1"
    # Check for common FASTQ patterns (compressed or uncompressed)
    if ls "${id}".fastq.gz 2>/dev/null || ls "${id}".fastq 2>/dev/null || \
       ls "${id}_1.fastq.gz" 2>/dev/null || ls "${id}_1.fastq" 2>/dev/null; then
        return 0  # exists
    fi
    return 1  # does not exist
}

# --- Process each SRR ID sequentially ---
for SRR_ID in "$@"; do
    echo -e "\n=========================================="
    echo "Processing: $SRR_ID ($((SUCCESS_COUNT+1)) of $TOTAL)"
    echo "=========================================="

    # --- Skip if FASTQ already present ---
    if fastq_exists "$SRR_ID"; then
        echo -e "\033[0;33m[SKIP] FASTQ for $SRR_ID already exists. No download needed.\033[0m"
        SKIPPED="$SKIPPED $SRR_ID"
        ((SUCCESS_COUNT++))   # count as success (no action needed)
        continue
    fi

    # --- Find EBI mirror URL for .sra ---
    PREFIX="${SRR_ID:0:3}"
    PREFIX_LOWER=$(echo "$PREFIX" | tr '[:upper:]' '[:lower:]')
    NUMERIC_PART="${SRR_ID:3}"
    LAST_DIGIT="${NUMERIC_PART: -1}"
    LAST_THREE="${NUMERIC_PART: -3}"
    PART1="${SRR_ID:0:6}"

    URL1="https://ftp.sra.ebi.ac.uk/vol1/${PREFIX_LOWER}/$PART1/00$LAST_DIGIT/$SRR_ID/$SRR_ID"
    URL2="https://ftp.sra.ebi.ac.uk/vol1/${PREFIX_LOWER}/$PART1/$LAST_THREE/$SRR_ID/$SRR_ID"
    URL3="https://ftp.sra.ebi.ac.uk/vol1/${PREFIX_LOWER}/$PART1/$SRR_ID/$SRR_ID"

    FINAL_URL=""
    if wget -q --spider "$URL1"; then FINAL_URL="$URL1";
    elif wget -q --spider "$URL2"; then FINAL_URL="$URL2";
    elif wget -q --spider "$URL3"; then FINAL_URL="$URL3";
    fi

    if [ -n "$FINAL_URL" ]; then
        echo "   [STRATEGY A] Downloading from EBI Mirror: $SRR_ID"
        wget -c --show-progress "$FINAL_URL" -O "${SRR_ID}.sra"
    else
        echo "   [STRATEGY A] EBI mirror failed for $SRR_ID."
        echo "   [STRATEGY B] Switching to NCBI prefetch..."
        vdb-config --restore-defaults > /dev/null 2>&1
        prefetch "$SRR_ID" --force all --max-size 100G --output-directory . --verify yes
        if [ -d "$SRR_ID" ] && [ -f "$SRR_ID/$SRR_ID.sra" ]; then
            mv "$SRR_ID/$SRR_ID.sra" .
            rmdir "$SRR_ID"
        fi
    fi

    # --- Verification ---
    if [ -f "${SRR_ID}.sra" ] && [ "$(stat -c%s "${SRR_ID}.sra")" -gt 10000 ]; then
        echo -e "\033[0;32m[SUCCESS] Downloaded: ${SRR_ID}.sra\033[0m"
        ((SUCCESS_COUNT++))
    else
        echo -e "\033[0;31m[FAILED] ${SRR_ID} could not be downloaded.\033[0m"
        rm -f "${SRR_ID}.sra"
        FAILED="$FAILED $SRR_ID"
    fi
done

# --- Final summary ---
echo -e "\n=========================================="
echo "All downloads finished."
echo "Successful (new downloads + skipped): $SUCCESS_COUNT / $TOTAL"
if [ -n "$SKIPPED" ]; then
    echo -e "Skipped (FASTQ already exists):$SKIPPED"
fi
if [ -n "$FAILED" ]; then
    echo -e "\033[0;31mFailed:$FAILED\033[0m"
    exit 1
else
    echo -e "\033[0;32mAll SRA files processed successfully.\033[0m"
    exit 0
fi