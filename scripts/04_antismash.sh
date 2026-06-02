#!/bin/bash
# Note: We use 'set -u' to catch missing variables, but NOT 'set -e'
# This ensures that if one bin fails, the script CONTINUES to the next one.
set -u

# --- 1. CONFIGURATION & INPUTS ---
V_TAXON=${AS_TAXON:-bacteria}
V_MINLEN=${AS_MINLEN:-3000}
V_GENE=${AS_GENEFINDER:-prodigal}
V_CB=${AS_CB:-loose}
V_HMM=${AS_HMMER:-strict}

# Arguments passed by the pipeline
BIN_INPUT_DIR="$1"
OUTPUT_DIR="$2"
THREADS="${3:-6}"

# Handle Assembly Directory (Argument 4)
if [ $# -ge 4 ]; then
    ASM_INPUT_DIR="$4"
else
    ASM_INPUT_DIR="${PROJ_OUT:-$HOME/FYP/results}/02_assembly"
fi

# --- 2. ENVIRONMENT SETUP ---
# Activate the environment from the full path
ENV_PATH="$HOME/FYP/envs/antismash_env"
source "$HOME/miniconda3/etc/profile.d/conda.sh" 2>/dev/null || source "$HOME/anaconda3/etc/profile.d/conda.sh" 2>/dev/null

if [ ! -d "$ENV_PATH" ]; then
    echo "ERROR: Environment not found at $ENV_PATH" >&2
    exit 1
fi

conda activate "$ENV_PATH" || { echo "ERROR: Could not activate $ENV_PATH"; exit 1; }

mkdir -p "$OUTPUT_DIR"

echo -e "\n\033[0;36m=== ANTISMASH PIPELINE ===\033[0m"
echo "   Inputs: Bins=$BIN_INPUT_DIR | Assembly=$ASM_INPUT_DIR"

# --- 3. THE WORKER FUNCTION ---
run_antismash() {
    local input_file="$1"
    local output_folder="$2"

    # A. Check for successful completion
    if [ -d "$output_folder" ] && [ -f "$output_folder/index.html" ]; then
        echo "   [SKIP] Already completed: $(basename "$output_folder")"
        return
    fi

    # B. Auto-clean partial/failed runs
    if [ -d "$output_folder" ]; then
        echo "   [RESET] Cleaning partial output: $output_folder"
        rm -rf "$output_folder"
    fi

    # C. Ensure the parent directory exists (for the log file)
    mkdir -p "$(dirname "$output_folder")"

    echo "   [RUNNING] Scanning $(basename "$input_file")..."

    # Set ClusterBlast flags
    CB_FLAGS=""
    if [ "$V_CB" == "strict" ]; then
        CB_FLAGS="--cb-knownclusters"
    else
        CB_FLAGS="--cb-general --cb-knownclusters --cb-subclusters"
    fi

    # D. RUN ANTISMASH
    antismash --taxon "$V_TAXON" \
        --output-dir "$output_folder" \
        --cpus "$THREADS" \
        --genefinding-tool "$V_GENE" \
        --minlength "$V_MINLEN" \
        --hmmdetection-strictness "$V_HMM" \
        $CB_FLAGS "$input_file" > "${output_folder}.log" 2>&1

    # E. Check Status
    if [ $? -eq 0 ]; then
        echo "     -> Success!"
        mv "${output_folder}.log" "$output_folder/run.log" 2>/dev/null
    else
        echo "     -> [ERROR] Failed. Check log: ${output_folder}.log"
        # SCRIPT CONTINUES...
    fi
}

# ==============================================================================
# STEP 1: PROCESS BINS (PRIORITY)
# ==============================================================================
echo -e "\n\033[0;33m--- Step 1: Processing Bins ---\033[0m"

if [ ! -d "$BIN_INPUT_DIR" ]; then
    echo "   [WARNING] Bin directory not found ($BIN_INPUT_DIR). Skipping..."
else
    # Find all 'bin.*.fa' files recursively
    count=$(find "$BIN_INPUT_DIR" -type f \( -name "bin.*.fa" -o -name "bin.*.fasta" \) | wc -l)
    
    if [ "$count" -eq 0 ]; then
        echo "   No bins found. Moving to assemblies."
    else
        find "$BIN_INPUT_DIR" -type f \( -name "bin.*.fa" -o -name "bin.*.fasta" \) | sort | while read bin_file; do
            filename=$(basename "$bin_file")
            
            # STRICT REGEX: Ensure it is 'bin.NUMBER.fa'
            if [[ ! "$filename" =~ bin\.[0-9]+\.(fa|fasta)$ ]]; then
                continue
            fi

            # Extract Sample Name & Bin ID
            sample_name=$(basename "$(dirname "$bin_file")")
            bin_id="${filename%.*}"
            
            target_out="$OUTPUT_DIR/${sample_name}_Bins/${bin_id}"
            run_antismash "$bin_file" "$target_out"
        done
    fi
fi

# ==============================================================================
# STEP 2: PROCESS ASSEMBLIES (ALWAYS RUNS)
# ==============================================================================
echo -e "\n\033[0;33m--- Step 2: Processing Assemblies ---\033[0m"

if [ ! -d "$ASM_INPUT_DIR" ]; then
    echo "   [WARNING] Assembly directory not found ($ASM_INPUT_DIR)."
else
    # Find assembly files
    find "$ASM_INPUT_DIR" -maxdepth 2 \( -name "*contigs.fa" -o -name "*contigs.fasta" -o -name "*scaffolds.fa" \) | sort | while read asm_file; do
        
        # Skip intermediate temp folders
        if [[ "$asm_file" == *"/intermediate_contigs/"* ]]; then
            continue
        fi

        # Get Sample Name & Clean it
        sample_name=$(basename "$(dirname "$asm_file")")
        sample_clean="${sample_name%_clean*}"
        sample_clean="${sample_clean%_1*}"

        target_out="$OUTPUT_DIR/${sample_clean}_Assembly"
        run_antismash "$asm_file" "$target_out"
    done
fi

echo -e "\n\033[0;32m[ANTISMASH PIPELINE COMPLETE]\033[0m"
