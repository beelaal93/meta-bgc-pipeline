#!/bin/bash
# ==============================================================================
# SCRIPT: 02_assembly.sh (v11.0 - Full Customization + QUAST)
# ==============================================================================
set -e

# --- 1. CONFIGURATION & CUSTOMIZATION ---
PROJECT_DIR="$HOME/FYP"
DEFAULT_IN="$PROJECT_DIR/results/01_qc/clean_reads"
DEFAULT_OUT="$PROJECT_DIR/results/02_assembly"
ENV_PATH="$PROJECT_DIR/envs/assembly_env"

# --- 5 MAJOR PARAMETERS (Reads from Interactive Pipeline or uses Defaults) ---
# If ASM_MIN is set by the menu, use it. Otherwise, default to 1000.
V_MIN=${ASM_MIN:-1000}
V_KMIN=${ASM_KMIN:-21}
V_KMAX=${ASM_KMAX:-141}
V_KSTEP=${ASM_KSTEP:-10}
V_PRESET=${ASM_PRESET:-"meta-sensitive"}
THREADS="${3:-6}" # Uses threads from pipeline or default 6

# --- 2. ACTIVATE ENVIRONMENT ---
source "$HOME/miniconda3/etc/profile.d/conda.sh" 2>/dev/null || source "$HOME/anaconda3/etc/profile.d/conda.sh" 2>/dev/null
conda activate "$ENV_PATH"

mkdir -p "$DEFAULT_OUT"

echo -e "\n\033[0;36m=== ASSEMBLY PIPELINE (Min:$V_MIN K:$V_KMIN-$V_KMAX Preset:$V_PRESET) ===\033[0m"

# Find Paired Clean Reads
find "$DEFAULT_IN" -name "*_clean_1.fastq.gz" -o -name "*_R1_clean.fastq.gz" | sort | while read R1_FILE; do
    
    # Determine R2 and Sample Name
    R2_FILE="${R1_FILE/_1_clean/_2_clean}"
    R2_FILE="${R2_FILE/_R1_clean/_R2_clean}"
    SAMPLE_NAME=$(basename "$R1_FILE" | sed 's/_[R1]*[1]*_clean.fastq.gz//')

    SAMPLE_OUT="$DEFAULT_OUT/$SAMPLE_NAME"
    CONTIGS_FILE="$SAMPLE_OUT/${SAMPLE_NAME}.contigs.fa"

    echo "--------------------------------------------------------"
    echo "Processing Sample: $SAMPLE_NAME"

    # Step A: Run MEGAHIT
    if [[ -f "$CONTIGS_FILE" ]]; then
        echo "   [SKIP] Assembly already exists for $SAMPLE_NAME"
    else
        echo "   [1/2] Running MEGAHIT with Custom Parameters..."
        rm -rf "$SAMPLE_OUT" # MEGAHIT requires output dir to be empty/not exist

        megahit \
            -1 "$R1_FILE" \
            -2 "$R2_FILE" \
            --out-dir "$SAMPLE_OUT" \
            --out-prefix "$SAMPLE_NAME" \
            --num-cpu-threads "$THREADS" \
            --min-contig-len "$V_MIN" \
            --k-min "$V_KMIN" \
            --k-max "$V_KMAX" \
            --k-step "$V_KSTEP" \
            --presets "$V_PRESET" \
            > "$DEFAULT_OUT/${SAMPLE_NAME}_assembly.log" 2>&1
        
        if [[ -f "$CONTIGS_FILE" ]]; then
            echo "         Success. Contigs saved."
            mv "$DEFAULT_OUT/${SAMPLE_NAME}_assembly.log" "$SAMPLE_OUT/assembly.log"
        else
            echo "   [FAIL] Assembly failed. Check log: $DEFAULT_OUT/${SAMPLE_NAME}_assembly.log"
            continue
        fi
    fi

    # Step B: Run QUAST (Quality Assessment)
    QUAST_OUT="$SAMPLE_OUT/quast_report"
    if [[ -f "$CONTIGS_FILE" ]]; then
        echo "   [2/2] Running QUAST Quality Check..."
        # We run this even if the folder exists to ensure the report matches your parameters
        quast.py "$CONTIGS_FILE" \
            -o "$QUAST_OUT" \
            --threads "$THREADS" \
            --min-contig "$V_MIN" \
            --labels "$SAMPLE_NAME" \
            --silent
        
        if [ -f "$QUAST_OUT/report.html" ]; then
            echo "         Report generated: $QUAST_OUT/report.html"
        else
            echo "         [WARN] QUAST failed to generate report. Check environment."
        fi
    fi

done

echo -e "\n\033[0;32m[SUCCESS] Assembly & QC Completed.\033[0m"
