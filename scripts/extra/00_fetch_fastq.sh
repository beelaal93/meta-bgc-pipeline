#!/bin/bash
# ==============================================================================
# SCRIPT: 00_fetch_fastq.sh (Unified – Uses fasterq-dump for all sources)
# ==============================================================================

set -eo pipefail

OUTPUT_DIR="$1"
SRR_ID="$2"
THREADS="${3:-6}"
LOG_FILE="${OUTPUT_DIR}/${SRR_ID}_fetch.log"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

log() { echo -e "$1" | tee -a "$LOG_FILE"; }
verify_file() { [ -f "$1" ] && [ "$(stat -c%s "$1" 2>/dev/null || echo 0)" -gt 10000 ]; }

cleanup() {
    if [ $? -ne 0 ]; then
        log "${RED}[FAILED] Download/conversion incomplete. Check $LOG_FILE${NC}"
    fi
    exit $?
}
trap cleanup EXIT

# Activate base environment (contains sra-tools)
source "$HOME/miniconda3/etc/profile.d/conda.sh" 2>/dev/null || source "$HOME/anaconda3/etc/profile.d/conda.sh" 2>/dev/null
conda activate base || { log "${RED}[ERROR] Cannot activate base env${NC}"; exit 1; }

mkdir -p "$OUTPUT_DIR" && cd "$OUTPUT_DIR" || exit 1
log "\n[PROCESSING] $SRR_ID at $(date)"

# ------------------------------------------------------------------------------
# Use fasterq-dump with Aspera preference (it will use EBI's fast pipe if possible)
# --ngc is not needed for public data
# ------------------------------------------------------------------------------
log "${BLUE}Downloading FASTQ via fasterq-dump (Aspera/EBI preferred)...${NC}"

# vdb-config ensures remotes are allowed
vdb-config --restore-defaults > /dev/null 2>&1 || true

# Run fasterq-dump
fasterq-dump "$SRR_ID" \
    --split-files \
    --threads "$THREADS" \
    --progress \
    --outdir . \
    --temp . \
    --force \
    2>&1 | tee -a "$LOG_FILE"

# ------------------------------------------------------------------------------
# Compress and cleanup
# ------------------------------------------------------------------------------
if ls "${SRR_ID}"*.fastq 1> /dev/null 2>&1; then
    log "${GREEN}FASTQ files generated, compressing...${NC}"
    if command -v pigz &> /dev/null; then
        pigz -p "$THREADS" "${SRR_ID}"*.fastq
    else
        gzip "${SRR_ID}"*.fastq
    fi
    log "${GREEN}[SUCCESS] FASTQ ready: $(ls ${SRR_ID}*.fastq.gz)${NC}"
    exit 0
else
    log "${RED}[ERROR] fasterq-dump produced no FASTQ files${NC}"
    exit 1
fi