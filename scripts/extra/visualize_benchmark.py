#!/usr/bin/env python3
"""
Visualize benchmarking metrics.
Usage: python visualize_benchmark.py
"""
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

# Set style
sns.set_style("whitegrid")
plt.rcParams["figure.figsize"] = (10, 6)

# Output directory
results_dir = "/home/bilal/FYP/results/benchmark"
fig_dir = os.path.join(results_dir, "figures")
os.makedirs(fig_dir, exist_ok=True)

# ----------------------------------------------------------------------
# 1. Class‑level (product) comparison: Assembly vs Bins
# ----------------------------------------------------------------------
class_assembly = pd.read_csv(os.path.join(results_dir, "assembly_product_metrics.tsv"), sep="\t")
class_bins = pd.read_csv(os.path.join(results_dir, "bin_product_metrics.tsv"), sep="\t")

# Add a column to identify the level
class_assembly["Level"] = "Assembly (class)"
class_bins["Level"] = "Bins (class)"

class_df = pd.concat([class_assembly, class_bins], ignore_index=True)
class_df = class_df[class_df["Metric"].isin(["Precision", "Recall", "F1"])]

# Pivot for easier plotting
class_pivot = class_df.pivot(index="Level", columns="Metric", values="Value")
print("Class‑level metrics:\n", class_pivot)

# Bar plot
ax = class_pivot.plot(kind="bar", rot=0, color=["#2ecc71", "#3498db", "#9b59b6"])
plt.title("Class‑level BGC Detection Performance")
plt.ylabel("Score")
plt.ylim(0, 1.05)
plt.legend(loc="lower right")
plt.tight_layout()
plt.savefig(os.path.join(fig_dir, "class_level_comparison.png"), dpi=150)
plt.close()

# ----------------------------------------------------------------------
# 2. Instance‑level (BLAST) comparison: Assembly vs Bins
# ----------------------------------------------------------------------
inst_assembly = pd.read_csv(os.path.join(results_dir, "instance_metrics.tsv"), sep="\t")
inst_bins = pd.read_csv(os.path.join(results_dir, "bin_instance_metrics.tsv"), sep="\t")

inst_assembly["Level"] = "Assembly (instance)"
inst_bins["Level"] = "Bins (instance)"

inst_df = pd.concat([inst_assembly, inst_bins], ignore_index=True)
inst_df = inst_df[inst_df["Metric"].isin(["Precision", "Recall", "F1"])]

inst_pivot = inst_df.pivot(index="Level", columns="Metric", values="Value")
print("\nInstance‑level metrics:\n", inst_pivot)

ax = inst_pivot.plot(kind="bar", rot=0, color=["#2ecc71", "#3498db", "#9b59b6"])
plt.title("Instance‑level BGC Detection Performance (≥90% identity, ≥50% coverage)")
plt.ylabel("Score")
plt.ylim(0, 1.05)
plt.legend(loc="lower right")
plt.tight_layout()
plt.savefig(os.path.join(fig_dir, "instance_level_comparison.png"), dpi=150)
plt.close()

# ----------------------------------------------------------------------
# 3. Per‑bin instance metrics heatmap
# ----------------------------------------------------------------------
per_bin = pd.read_csv(os.path.join(results_dir, "per_bin_summary.tsv"), sep="\t")
# Keep only numeric columns for heatmap
bin_metrics = per_bin.set_index("Bin")[["Precision", "Recall", "F1"]]

plt.figure(figsize=(8, max(4, len(bin_metrics)*0.3)))
sns.heatmap(bin_metrics, annot=True, fmt=".3f", cmap="YlGnBu", cbar_kws={'label': 'Score'})
plt.title("Per‑bin BGC Detection Performance")
plt.tight_layout()
plt.savefig(os.path.join(fig_dir, "per_bin_heatmap.png"), dpi=150)
plt.close()

# ----------------------------------------------------------------------
# 4. Stacked bar chart of TP, FP, FN counts (assembly vs bins)
# ----------------------------------------------------------------------
counts_assembly = inst_assembly[inst_assembly["Metric"].isin(["TP", "FP", "FN"])].copy()
counts_bins = inst_bins[inst_bins["Metric"].isin(["TP", "FP", "FN"])].copy()

counts_assembly["Level"] = "Assembly"
counts_bins["Level"] = "Bins"
counts_df = pd.concat([counts_assembly, counts_bins], ignore_index=True)

# Pivot to have Metrics as columns
counts_pivot = counts_df.pivot(index="Level", columns="Metric", values="Value")
print("\nCounts:\n", counts_pivot)

# Plot stacked bars
counts_pivot[["TP", "FP", "FN"]].plot(kind="bar", stacked=True, color=["#27ae60", "#e74c3c", "#95a5a6"], rot=0)
plt.title("BGC Counts (TP / FP / FN) at Instance Level")
plt.ylabel("Number of BGCs")
plt.legend(loc="upper right")
plt.tight_layout()
plt.savefig(os.path.join(fig_dir, "counts_stacked.png"), dpi=150)
plt.close()

# ----------------------------------------------------------------------
# 5. (Optional) Bar chart for top bins only (e.g., those with F1 > 0)
# ----------------------------------------------------------------------
top_bins = per_bin[per_bin["F1"] > 0].sort_values("F1", ascending=False).head(5)
if not top_bins.empty:
    ax = top_bins.plot(x="Bin", y=["Precision", "Recall", "F1"], kind="bar", rot=45,
                       color=["#2ecc71", "#3498db", "#9b59b6"])
    plt.title("Top 5 Bins by F1 Score")
    plt.ylabel("Score")
    plt.ylim(0, 1.05)
    plt.tight_layout()
    plt.savefig(os.path.join(fig_dir, "top_bins.png"), dpi=150)
    plt.close()

print(f"\nAll figures saved to {fig_dir}")