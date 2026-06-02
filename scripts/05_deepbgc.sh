#!/bin/bash
set -euo pipefail

# --- Database path ---
export DEEPBGC_DB="${DEEPBGC_DB:-$HOME/FYP/databases/deepbgc_db}"

# --- SAFETY LIMITS for 16 GB RAM ---
# Maximum number of DeepBGC instances to run at once.
# 3 jobs × ~3 GB = 9 GB, safe margin for Windows.
JOBS=3

# --- CPU optimisation (each job uses 4 threads) ---
export HMMER_NCPU=4
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
export NUMEXPR_NUM_THREADS=4
# TensorFlow logging level (suppress warnings if you like)
export TF_CPP_MIN_LOG_LEVEL=2

# --- Parameters from environment (customisable via app.py) ---
V_SCORE=${DEEP_SCORE:-0.5}
V_PROD=${DEEP_PRODIGAL:-meta}
V_MINLEN=${DEEP_MIN_LEN:-3000}
V_MERGE=${DEEP_MERGE:-0}
V_DETECT=${DEEP_DETECTOR:-deepbgc}

# --- Paths ---
PROJ_OUT="${PROJ_OUT:-$HOME/FYP/results}"
ENV_PATH="$HOME/FYP/envs/deepbgc_env"
ASM_DIR="$PROJ_OUT/02_assembly"
BIN_DIR="$PROJ_OUT/03_binning"
OUT_BASE="$PROJ_OUT/05_deepbgc"
export OUT_BASE

# --- Activate environment ---
source "$HOME/miniconda3/etc/profile.d/conda.sh" 2>/dev/null || \
source "$HOME/anaconda3/etc/profile.d/conda.sh" 2>/dev/null
conda activate "$ENV_PATH"

mkdir -p "$OUT_BASE"
echo -e "\n\033[0;36m=== DEEPBGC (Score:$V_SCORE Model:$V_DETECT) – SAFE PARALLEL ($JOBS jobs) ===\033[0m"

# --- Prodigal flag ---
PROD_FLAG="--prodigal-meta-mode"
[ "$V_PROD" == "single" ] && PROD_FLAG=""

# --- Worker function ---
run_deep() {
    local in="$1"
    local out="$2"
    if [ -f "$out/LOG.txt" ]; then
        echo "   Skipping $(basename "$in") (already done)"
        return 0
    fi
    mkdir -p "$out"
    echo "   Running on $(basename "$in")"
    deepbgc pipeline "$in" \
        --output "$out" \
        --score "$V_SCORE" \
        $PROD_FLAG \
        --min-nucl "$V_MINLEN" \
        --merge-max-protein-gap "$V_MERGE" \
        --detector "$V_DETECT" \
        > "$out/run.log" 2>&1 && touch "$out/LOG.txt"
}
export -f run_deep
export V_SCORE V_PROD V_MINLEN V_MERGE V_DETECT PROD_FLAG

# --- Process assemblies (3 at a time) ---
echo "Processing assemblies from $ASM_DIR"
find "$ASM_DIR" -maxdepth 2 -name "*.contigs.fa" | grep -v "/intermediate_contigs/" | \
while read -r f; do
    id=$(basename "$(dirname "$f")")
    id_clean="${id%_clean_1.fastq.gz}"
    echo "$f" "$OUT_BASE/${id_clean}_Assembly"
done | xargs -P $JOBS -n 2 bash -c 'run_deep "$1" "$2"' _

# --- Process bins (3 at a time) ---
echo "Processing bins from $BIN_DIR"
find "$BIN_DIR" -name "*.fa" | grep -E "/bin\.[0-9]+\.fa$" | \
while read -r f; do
    id=$(basename "$(dirname "$f")")
    bin=$(basename "$f" .fa)
    echo "$f" "$OUT_BASE/${id}_Bins/$bin"
done | xargs -P $JOBS -n 2 bash -c 'run_deep "$1" "$2"' _

echo -e "\n\033[0;32m[DEEPBGC COMPLETE]\033[0m"