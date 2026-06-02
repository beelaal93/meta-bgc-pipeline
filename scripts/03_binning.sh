#!/bin/bash
set -euo pipefail

# --- 5 PARAMS (from interactive pipeline) ---
V_MIN_LEN=${BIN_MIN_LEN:-1500}
V_MIN_SIZE=${BIN_MIN_SIZE:-200000}
V_MAX_EDGE=${BIN_MAX_EDGES:-200}
V_MIN_CV=${BIN_MIN_CV:-0}          # default 0 for single‑sample
V_DEPTH=${BIN_DEPTH:-0}             # not used directly, kept for compatibility

ASSEMBLY_DIR="$1"
READS_DIR="$2"
OUTPUT_DIR="$3"
THREADS="${4:-6}"

# --- Activate environment ---
source "$HOME/miniconda3/etc/profile.d/conda.sh" 2>/dev/null || source "$HOME/anaconda3/etc/profile.d/conda.sh" 2>/dev/null
conda activate "$HOME/FYP/envs/binning_env"

mkdir -p "$OUTPUT_DIR"

echo -e "\n\033[0;36m=== BINNING (Len:$V_MIN_LEN Size:$V_MIN_SIZE Edges:$V_MAX_EDGE minCV:$V_MIN_CV) ===\033[0m"

# Loop over each assembly directory
find "$ASSEMBLY_DIR" -maxdepth 1 -mindepth 1 -type d | while read SAMPLE_PATH; do
    SAMPLE=$(basename "$SAMPLE_PATH")
    CONTIGS="$SAMPLE_PATH/${SAMPLE}.contigs.fa"
    SAMPLE_OUT="$OUTPUT_DIR/$SAMPLE"
    mkdir -p "$SAMPLE_OUT"
    
    LOG="$SAMPLE_OUT/binning.log"
    echo "=========================================" > "$LOG"
    echo "Starting binning for $SAMPLE at $(date)" >> "$LOG"
    echo "=========================================" >> "$LOG"

    if [ ! -f "$CONTIGS" ]; then
        echo "   [WARN] No contigs file for $SAMPLE, skipping." | tee -a "$LOG"
        continue
    fi

    if ls "$SAMPLE_OUT"/bin.*.fa 1> /dev/null 2>&1; then
        echo "   [SKIP] $SAMPLE already has bins." | tee -a "$LOG"
        continue
    fi

    echo "   Processing $SAMPLE ..." | tee -a "$LOG"

    # --- Derive read base name ---
    BASE="${SAMPLE%_clean_1.fastq.gz}"
    BASE="${BASE%_1.fastq.gz}"
    BASE="${BASE%_R1_clean.fastq.gz}"
    BASE="${BASE%_1_clean.fastq.gz}"

    # Locate read files
    R1=""; R2=""
    for candidate in "$READS_DIR/${BASE}_clean_1.fastq.gz" \
                     "$READS_DIR/${BASE}_1_clean.fastq.gz" \
                     "$READS_DIR/${BASE}_R1_clean.fastq.gz" \
                     "$READS_DIR/${SAMPLE}_clean_1.fastq.gz" \
                     "$READS_DIR/${SAMPLE}_1_clean.fastq.gz"; do
        if [ -f "$candidate" ]; then
            R1="$candidate"
            R2="${R1/_1/_2}"; R2="${R2/_R1/_R2}"
            if [ -f "$R2" ]; then
                echo "   Found reads: $(basename "$R1") and $(basename "$R2")" | tee -a "$LOG"
                break
            else
                R1=""
            fi
        fi
    done

    if [ -z "$R1" ] || [ -z "$R2" ]; then
        echo "   [ERROR] Could not find paired reads for $SAMPLE" | tee -a "$LOG"
        continue
    fi

    # --- Count long contigs ---
    long_contigs=$(awk -v min="$V_MIN_LEN" '/^>/ {if (len>=min) count++; len=0; next} {len+=length($0)} END {if (len>=min) count++; print count}' "$CONTIGS")
    echo "      Contigs >= $V_MIN_LEN bp: $long_contigs" | tee -a "$LOG"
    if [ "$long_contigs" -lt 2 ]; then
        echo "      [WARN] Too few long contigs – skipping binning." | tee -a "$LOG"
        continue
    fi

    # --- Build bowtie2 index ---
    echo "      Indexing contigs..." | tee -a "$LOG"
    if ! bowtie2-build "$CONTIGS" "$SAMPLE_OUT/index" >> "$LOG" 2>&1; then
        echo "      [ERROR] bowtie2-build failed." | tee -a "$LOG"
        continue
    fi

    # --- Map reads ---
    echo "      Mapping reads with bowtie2..." | tee -a "$LOG"
    if ! bowtie2 -x "$SAMPLE_OUT/index" \
                -1 "$R1" -2 "$R2" \
                -p "$THREADS" 2>> "$LOG" | \
         samtools view -bS - 2>> "$LOG" | \
         samtools sort -o "$SAMPLE_OUT/mapped.sorted.bam" - 2>> "$LOG"; then
        echo "      [ERROR] Read mapping failed." | tee -a "$LOG"
        continue
    fi

    # --- Calculate depth ---
    echo "      Calculating contig depth..." | tee -a "$LOG"
    if ! jgi_summarize_bam_contig_depths \
            --outputDepth "$SAMPLE_OUT/depth.txt" \
            "$SAMPLE_OUT/mapped.sorted.bam" >> "$LOG" 2>&1; then
        echo "      [ERROR] jgi_summarize_bam_contig_depths failed." | tee -a "$LOG"
        continue
    fi

    # --- Run MetaBAT2 (without --minContigDepth – it's not supported in all versions) ---
    metabat_cmd="metabat2 -i $CONTIGS -a $SAMPLE_OUT/depth.txt -o $SAMPLE_OUT/bin -t $THREADS -m $V_MIN_LEN -s $V_MIN_SIZE --maxEdges $V_MAX_EDGE --minCV $V_MIN_CV --unbinned"
    echo "      Running: $metabat_cmd" | tee -a "$LOG"
    set +e
    $metabat_cmd >> "$LOG" 2>&1
    metabat_exit=$?
    set -e
    echo "      MetaBAT2 finished with exit code $metabat_exit" >> "$LOG"

    # Check for crash / unknown option
    if [ $metabat_exit -eq 134 ] || [ $metabat_exit -eq 139 ]; then
        echo "      [ERROR] MetaBAT2 crashed (exit $metabat_exit). This may be due to an unsupported option or a bug." | tee -a "$LOG"
        echo "      Check your MetaBAT2 version and parameters." | tee -a "$LOG"
    fi

    # --- Count produced bins ---
    bin_count=$(ls "$SAMPLE_OUT"/bin.*.fa 2>/dev/null | wc -l)
    if [ "$bin_count" -eq 0 ]; then
        echo "      [WARN] MetaBAT2 produced no bins for $SAMPLE." | tee -a "$LOG"
        echo "      Check $LOG and consider adjusting parameters (especially --minCV)." | tee -a "$LOG"
    else
        echo "      Success: $bin_count bins created." | tee -a "$LOG"
        # Optional: clean up intermediate files
        # rm -f "$SAMPLE_OUT/mapped.sorted.bam" "$SAMPLE_OUT/index"*.bt2
    fi

    echo "   Finished $SAMPLE at $(date)" >> "$LOG"
    echo "" >> "$LOG"
done

echo -e "\n\033[0;32m[BINNING COMPLETE]\033[0m"
