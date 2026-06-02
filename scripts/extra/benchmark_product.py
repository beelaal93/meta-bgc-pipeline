#!/usr/bin/env python3
"""
Benchmark BGC detection by product class.
Usage: benchmark_product.py --truth DIR --detected DIR --out TSV
"""
import os, glob, argparse
from Bio import SeqIO
import pandas as pd

def extract_products_from_gbk(gbk_files):
    """Extract product classes from antiSMASH region GenBank files."""
    products = []
    for f in gbk_files:
        with open(f) as handle:
            for rec in SeqIO.parse(handle, "genbank"):
                for feat in rec.features:
                    if feat.type in ("cluster", "protocluster"):
                        product = feat.qualifiers.get("product", ["unknown"])[0]
                        products.append(product)
    return products

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--truth", required=True)
    parser.add_argument("--detected", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    truth_files = glob.glob(os.path.join(args.truth, "**", "*region*.gbk"), recursive=True)
    detected_files = glob.glob(os.path.join(args.detected, "**", "*region*.gbk"), recursive=True)

    truth_products = set(extract_products_from_gbk(truth_files))
    detected_products = set(extract_products_from_gbk(detected_files))

    tp = len(detected_products.intersection(truth_products))
    fp = len(detected_products - truth_products)
    fn = len(truth_products - detected_products)

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
