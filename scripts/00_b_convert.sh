#!/bin/bash
# ==============================================================================
# SCRIPT: 00_b_convert.sh (SRA → FASTQ only if needed)
# ==============================================================================
OUTPUT_DIR="$1"
SRR_ID="$2"

# 1. ACTIVATE BASE ENV
source "$HOME/miniconda3/etc/profile.d/conda.sh" 2>/dev/null || source "$HOME/anaconda3/etc/profile.d/conda.sh" 2>/dev/null
conda activate base

cd "$OUTPUT_DIR" || exit 1

echo -e "\n[2/2] POST-DOWNLOAD PROCESSING (Env: $(basename "$CONDA_PREFIX"))..."

# 2. CHECK FOR EXISTING FASTQ FILES (from EBI download)
FASTQ_FOUND=false
if [ -f "${SRR_ID}_1.fastq.gz" ] || [ -f "${SRR_ID}_1.fastq" ]; then
    FASTQ_FOUND=true
elif [ -f "${SRR_ID}.fastq.gz" ] || [ -f "${SRR_ID}.fastq" ]; then
    # Single-end case
    FASTQ_FOUND=true
fi

if [ "$FASTQ_FOUND" = true ]; then
    echo "   [INFO] FASTQ files already exist. Skipping conversion."
    # Ensure they are compressed if not already
    for f in "${SRR_ID}"*.fastq; do
        [ -f "$f" ] && gzip "$f"
    done
    echo "   [SUCCESS] FASTQ files ready (downloaded directly)."
    exit 0
fi

# 3. CHECK FOR SRA FILE (from NCBI prefetch)
if [ ! -f "${SRR_ID}.sra" ]; then
    echo "   [ERROR] Neither FASTQ files nor ${SRR_ID}.sra found."
    echo "   [FIX] Please run Step 0 (Download) first."
    exit 1
fi

# 4. UNLOCK CONFIG (RefSeq Fix)
if command -v vdb-config &> /dev/null; then
    vdb-config --restore-defaults > /dev/null 2>&1
fi
unset NCBI_VDB_REMOTES

# 5. CONVERT SRA TO FASTQ
echo "   [INFO] Converting ${SRR_ID}.sra to FASTQ..."
fasterq-dump "./${SRR_ID}.sra" \
    --split-files \
    --threads 6 \
    --progress \
    --force

# 6. COMPRESS & CLEANUP
if ls "${SRR_ID}"*.fastq 1> /dev/null 2>&1; then
    echo -e "\n   [INFO] Compressing FASTQ files..."
    if command -v pigz &> /dev/null; then
        pigz -p 6 "${SRR_ID}"*.fastq
    else
        gzip "${SRR_ID}"*.fastq
    fi
    echo "   [CLEANUP] Removing raw SRA file..."
    rm -f "${SRR_ID}.sra"
    echo "   [SUCCESS] FASTQ files ready (converted from SRA)."
else
    echo -e "\n   [ERROR] Conversion failed – no FASTQ files generated."
    exit 1
fi