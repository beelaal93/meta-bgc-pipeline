#!/usr/bin/env python3
"""
Parse BLAST results to compute instance-level TP, FP, FN.
Uses ≥90% identity and ≥50% coverage of both query and subject.
"""
import argparse
import pandas as pd

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--blast", required=True, help="BLAST output in tabular format (outfmt 6)")
    parser.add_argument("--truth_fasta", required=True, help="Truth sequences FASTA (to get subject lengths)")
    parser.add_argument("--detected_fasta", required=True, help="Detected sequences FASTA (to get query lengths)")
    parser.add_argument("--out", required=True, help="Output TSV with metrics")
    parser.add_argument("--identity", type=float, default=90.0, help="Minimum identity percentage")
    parser.add_argument("--coverage", type=float, default=50.0, help="Minimum coverage percentage")
    args = parser.parse_args()

    # Read lengths from FASTA files
    from Bio import SeqIO
    truth_len = {rec.id: len(rec.seq) for rec in SeqIO.parse(args.truth_fasta, "fasta")}
    detected_len = {rec.id: len(rec.seq) for rec in SeqIO.parse(args.detected_fasta, "fasta")}

    # Read BLAST results
    cols = ["qseqid", "sseqid", "pident", "length", "qlen", "slen", "qstart", "qend", "sstart", "send", "evalue", "bitscore"]
    df = pd.read_csv(args.blast, sep="\t", names=cols)

    # Filter by identity
    df = df[df["pident"] >= args.identity]

    # Compute query coverage and subject coverage
    df["qcov"] = (df["qend"] - df["qstart"] + 1) / df["qlen"] * 100
    df["scov"] = (df["send"] - df["sstart"] + 1) / df["slen"] * 100

    # Filter by coverage (both query and subject >= threshold)
    df = df[(df["qcov"] >= args.coverage) & (df["scov"] >= args.coverage)]

    # For each detected BGC, keep the best hit (lowest evalue, highest bitscore)
    best_hits = df.loc[df.groupby("qseqid")["bitscore"].idxmax()]

    # True positives: detected BGCs that have a valid hit
    tp_detected = set(best_hits["qseqid"])
    tp_truth = set(best_hits["sseqid"])

    # All detected BGCs
    all_detected = set(detected_len.keys())
    all_truth = set(truth_len.keys())

    fp = all_detected - tp_detected
    fn = all_truth - tp_truth
    tp = len(tp_detected)

    precision = tp / (tp + len(fp)) if (tp + len(fp)) > 0 else 0.0
    recall    = tp / (tp + len(fn)) if (tp + len(fn)) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    stats = pd.DataFrame({
        "Metric": ["TP", "FP", "FN", "Precision", "Recall", "F1"],
        "Value": [tp, len(fp), len(fn), precision, recall, f1]
    })
    stats.to_csv(args.out, sep="\t", index=False)
    print(stats)

if __name__ == "__main__":
    main()
