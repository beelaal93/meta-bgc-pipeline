#!/bin/bash
set -euo pipefail

PROJECT_DIR="$HOME/FYP"
INPUT_DIR="$PROJECT_DIR/results/05_bgc/antismash"      # Updated from 04_bgc to 05_bgc
OUTPUT_DIR="$PROJECT_DIR/results/07_network_analysis"
ENV_PATH="$PROJECT_DIR/envs/bigscape_py311"
PFAM_HMM="$PROJECT_DIR/databases/antismash_db/pfam/35.0/Pfam-A.hmm"

source "$HOME/miniconda3/etc/profile.d/conda.sh" 2>/dev/null || \
source "$HOME/anaconda3/etc/profile.d/conda.sh" 2>/dev/null
conda activate "$ENV_PATH"

mkdir -p "$OUTPUT_DIR"

echo -e "\n\033[0;36m=== BiG-SCAPE: GCF NETWORK ANALYSIS ===\033[0m"
echo "Input:  $INPUT_DIR"
echo "Output: $OUTPUT_DIR"
echo "Pfam:   $PFAM_HMM"

# Verify Pfam is pressed (indexed)
if [ ! -f "${PFAM_HMM}.h3f" ]; then
    echo -e "\033[0;33mPfam not indexed – running hmmpress...\033[0m"
    hmmpress "$PFAM_HMM"
fi

bigscape cluster \
    -i "$INPUT_DIR" \
    -o "$OUTPUT_DIR" \
    --pfam-path "$PFAM_HMM" \
    --gcf-cutoffs 0.30,0.50 \
    --include-singletons \
    --mix \
    -c 4 \
    --verbose

echo -e "\n\033[0;32m[SUCCESS] Network generated in $OUTPUT_DIR\033[0m"
echo "Open '$OUTPUT_DIR/html_output/index.html' in your browser."
