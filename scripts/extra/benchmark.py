#!/usr/bin/env python3
"""
Benchmark BGC detection: compare pipeline antiSMASH results against ground truth.
Usage: benchmark.py --truth DIR --detected DIR --out TSV [--threshold 0.5]
"""
import os, glob, argparse
from Bio import SeqIO
import pandas as pd
from intervaltree import IntervalTree

def parse_bgcs_from_gbk(gbk_files):
    """Extract BGC intervals from antiSMASH region GenBank files."""
    bgcs = []
    for f in gbk_files:
        with open(f) as handle:
            for rec in SeqIO.parse(handle, "genbank"):
                contig = rec.id
                for feat in rec.features:
                    if feat.type in ("cluster", "protocluster"):
                        product = feat.qualifiers.get("product", ["unknown"])[0]
                        start = int(feat.location.start) + 1
                        end = int(feat.location.end)
                        bgcs.append({
                            "file": os.path.basename(f),
                            "contig": contig,
                            "product": product,
                            "start": start,
                            "end": end,
                            "length": end - start + 1
                        })
    return pd.DataFrame(bgcs)

def build_interval_tree(df):
    """Build an interval tree keyed by contig."""
    trees = {}
    for _, row in df.iterrows():
        contig = row["contig"]
        if contig not in trees:
            trees[contig] = IntervalTree()
        trees[contig].addi(row["start"], row["end"]+1, row["product"])
    return trees

def calculate_overlap(true_tree, detected_df, overlap_threshold=0.5):
    """Match detected BGCs to truth intervals based on overlap."""
    tp = 0
    detected_matched = set()
    for _, row in detected_df.iterrows():
        contig = row["contig"]
        if contig not in true_tree:
            continue
        intervals = true_tree[contig].overlap(row["start"], row["end"]+1)
        for iv in intervals:
            overlap_len = min(row["end"], iv.end-1) - max(row["start"], iv.begin) + 1
            if overlap_len <= 0:
                continue
            overlap_frac_det = overlap_len / row["length"]
            overlap_frac_true = overlap_len / (iv.end - iv.begin)
            if overlap_frac_det >= overlap_threshold and overlap_frac_true >= overlap_threshold:
                tp += 1
                detected_matched.add((contig, iv.begin, iv.end))
                break
    return tp, detected_matched

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--truth", required=True)
    parser.add_argument("--detected", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()

    # Use *region*.gbk to match both ground truth and detected file naming
    truth_files = glob.glob(os.path.join(args.truth, "**", "*region*.gbk"), recursive=True)
    detected_files = glob.glob(os.path.join(args.detected, "**", "*region*.gbk"), recursive=True)

    truth_df = parse_bgcs_from_gbk(truth_files)
    detected_df = parse_bgcs_from_gbk(detected_files)

    # Build interval trees for truth
    truth_trees = build_interval_tree(truth_df)

    # Count TP
    tp, matched_set = calculate_overlap(truth_trees, detected_df, args.threshold)

    # FP: detected BGCs that did not match any truth interval
    fp = len(detected_df) - tp

    # FN: truth intervals that were not matched
    all_truth_intervals = set()
    for _, row in truth_df.iterrows():
        all_truth_intervals.add((row["contig"], row["start"], row["end"]))
    fn = len(all_truth_intervals - matched_set)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    stats = pd.DataFrame({
        "Metric": ["TP", "FP", "FN", "Precision", "Recall", "F1"],
        "Value": [tp, fp, fn, precision, recall, f1]
    })
    stats.to_csv(args.out, sep="\t", index=False)
    print(stats)

if __name__ == "__main__":
    main()
