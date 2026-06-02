#!/bin/bash
# ==============================================================================
# SCRIPT: 06_compare.sh
# ENV: viz_env (Python 3.9, Pandas, Matplotlib, Biopython, seaborn, matplotlib-venn)
# USAGE: 06_compare.sh [antismash_dir] [deepbgc_dir] [out_dir]
# ==============================================================================
PROJECT_DIR="$HOME/FYP"
SCRIPT_DIR="$PROJECT_DIR/scripts"
ENV_PATH="$PROJECT_DIR/envs/viz_env"

# Default directories (used if arguments not provided)
DEFAULT_ANTI="$PROJECT_DIR/results/05_bgc/antismash"
DEFAULT_DEEP="$PROJECT_DIR/results/05_deepbgc"
DEFAULT_OUT="$PROJECT_DIR/results/06_comparison"

# Use arguments if supplied, otherwise defaults
ANTI_DIR="${1:-$DEFAULT_ANTI}"
DEEP_DIR="${2:-$DEFAULT_DEEP}"
OUT_DIR="${3:-$DEFAULT_OUT}"

# 1. Activate Visualization Environment
source "$HOME/miniconda3/etc/profile.d/conda.sh" 2>/dev/null || source "$HOME/anaconda3/etc/profile.d/conda.sh" 2>/dev/null

if [ -d "$ENV_PATH" ]; then
    conda activate "$ENV_PATH"
else
    echo -e "\n[ERROR] 'viz_env' not found!"
    echo "Please create it with: conda create -p $ENV_PATH python=3.9 pandas matplotlib seaborn biopython matplotlib-venn"
    exit 1
fi

mkdir -p "$OUT_DIR"

echo -e "\n\033[0;36m=== STARTING BGC COMPARISON ===\033[0m"
echo "   Environment : $(conda info | grep 'active environment' | cut -d : -f 2)"
echo "   antiSMASH   : $ANTI_DIR"
echo "   DeepBGC     : $DEEP_DIR"

# 2. Run Analysis
python3 "$SCRIPT_DIR/06_compare_bgcs.py" \
    --antismash_dir "$ANTI_DIR" \
    --deepbgc_dir "$DEEP_DIR" \
    --out_dir "$OUT_DIR"

# 3. Check success
if [ -f "$OUT_DIR/comparison_done.txt" ]; then
    echo -e "\n\033[0;32m[DONE] Results generated in $OUT_DIR\033[0m"
else
    echo -e "\n\033[0;31m[ERROR] Comparison failed. Check logs.\033[0m"
    exit 1
fi