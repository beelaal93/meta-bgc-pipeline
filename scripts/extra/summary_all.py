#!/usr/bin/env python3
"""
Summarize all benchmarking results: class‑level, instance‑level, per‑bin.
Optionally integrates CheckM2 bin quality.
Generates a markdown table and combined plots.
"""
import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from tabulate import tabulate

# -------------------- Configuration --------------------
BASE_DIR = os.path.expanduser("~/FYP/results/benchmark")
CHECKM2_FILE = os.path.expanduser("~/FYP/results/04_bin_quality/checkm2/quality_report.tsv")
OUTPUT_DIR = os.path.join(BASE_DIR, "summary")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# -------------------- Helper functions --------------------
def read_metrics(file_path):
    """Read a two‑column TSV (Metric, Value) and return a dict."""
    if not os.path.exists(file_path):
        print(f"Warning: {file_path} not found")
        return {}
    df = pd.read_csv(file_path, sep="\t")
    return dict(zip(df["Metric"], df["Value"]))

def format_float(x):
    return f"{x:.3f}" if isinstance(x, float) else str(x)

# -------------------- 1. Class‑level metrics --------------------
print("\n=== Class‑level (product) metrics ===\n")
class_assembly = read_metrics(os.path.join(BASE_DIR, "assembly_product_metrics.tsv"))
class_bins = read_metrics(os.path.join(BASE_DIR, "bin_product_metrics.tsv"))

class_df = pd.DataFrame({
    "Metric": ["TP", "FP", "FN", "Precision", "Recall", "F1"],
    "Assembly": [class_assembly.get(m, 0) for m in ["TP", "FP", "FN", "Precision", "Recall", "F1"]],
    "Bins":     [class_bins.get(m, 0) for m in ["TP", "FP", "FN", "Precision", "Recall", "F1"]]
})
print(tabulate(class_df, headers="keys", tablefmt="grid", floatfmt=".3f"))

# -------------------- 2. Instance‑level (BLAST) metrics --------------------
print("\n=== Instance‑level (BLAST) metrics (≥90% identity, ≥50% coverage) ===\n")
inst_assembly = read_metrics(os.path.join(BASE_DIR, "instance_metrics.tsv"))
inst_bins = read_metrics(os.path.join(BASE_DIR, "bin_instance_metrics.tsv"))

inst_df = pd.DataFrame({
    "Metric": ["TP", "FP", "FN", "Precision", "Recall", "F1"],
    "Assembly": [inst_assembly.get(m, 0) for m in ["TP", "FP", "FN", "Precision", "Recall", "F1"]],
    "Bins":     [inst_bins.get(m, 0) for m in ["TP", "FP", "FN", "Precision", "Recall", "F1"]]
})
print(tabulate(inst_df, headers="keys", tablefmt="grid", floatfmt=".3f"))

# -------------------- 3. Per‑bin instance metrics --------------------
per_bin_file = os.path.join(BASE_DIR, "per_bin_summary.tsv")
if os.path.exists(per_bin_file):
    per_bin = pd.read_csv(per_bin_file, sep="\t")
    print("\n=== Per‑bin instance metrics ===\n")
    print(tabulate(per_bin, headers="keys", tablefmt="grid", floatfmt=".3f"))

    # Summary stats
    print("\n--- Summary statistics for bins ---")
    stats = per_bin[["Precision", "Recall", "F1"]].describe().loc[["mean", "std", "min", "max"]]
    print(tabulate(stats, headers="keys", tablefmt="grid", floatfmt=".3f"))

    # -------------------- 4. Merge with CheckM2 bin quality (if available) --------------------
    if os.path.exists(CHECKM2_FILE):
        checkm = pd.read_csv(CHECKM2_FILE, sep="\t")
        # Assume bin names in CheckM2 match folder names (e.g., "bin.2")
        checkm["Bin"] = checkm["Name"].astype(str)
        merged = pd.merge(per_bin, checkm[["Bin", "Completeness", "Contamination"]], on="Bin", how="left")
        print("\n=== Per‑bin metrics with CheckM2 quality ===\n")
        print(tabulate(merged, headers="keys", tablefmt="grid", floatfmt=".3f"))
        # Save merged file
        merged.to_csv(os.path.join(OUTPUT_DIR, "per_bin_with_quality.tsv"), sep="\t", index=False)
    else:
        print("\nCheckM2 file not found; skipping quality integration.")
else:
    print("\nPer‑bin summary not found; run per‑bin loop first.")

# -------------------- 5. Save master summary table --------------------
master = pd.DataFrame({
    "Level": ["Class (assembly)", "Class (bins)", "Instance (assembly)", "Instance (bins)"],
    "TP": [class_assembly.get("TP", 0), class_bins.get("TP", 0),
           inst_assembly.get("TP", 0), inst_bins.get("TP", 0)],
    "FP": [class_assembly.get("FP", 0), class_bins.get("FP", 0),
           inst_assembly.get("FP", 0), inst_bins.get("FP", 0)],
    "FN": [class_assembly.get("FN", 0), class_bins.get("FN", 0),
           inst_assembly.get("FN", 0), inst_bins.get("FN", 0)],
    "Precision": [class_assembly.get("Precision", 0), class_bins.get("Precision", 0),
                  inst_assembly.get("Precision", 0), inst_bins.get("Precision", 0)],
    "Recall": [class_assembly.get("Recall", 0), class_bins.get("Recall", 0),
               inst_assembly.get("Recall", 0), inst_bins.get("Recall", 0)],
    "F1": [class_assembly.get("F1", 0), class_bins.get("F1", 0),
           inst_assembly.get("F1", 0), inst_bins.get("F1", 0)]
})
master.to_csv(os.path.join(OUTPUT_DIR, "master_summary.tsv"), sep="\t", index=False)
print("\n=== Master summary table (saved to master_summary.tsv) ===\n")
print(tabulate(master, headers="keys", tablefmt="grid", floatfmt=".3f"))

# -------------------- 6. Generate combined plots --------------------
# Plot 1: Class‑level vs Instance‑level comparison (bars)
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle("BGC Detection Performance Summary", fontsize=16)

# Class‑level bar
ax = axes[0, 0]
class_plot = class_df.melt(id_vars="Metric", var_name="Level", value_name="Score")
sns.barplot(data=class_plot[class_plot["Metric"].isin(["Precision", "Recall", "F1"])],
            x="Metric", y="Score", hue="Level", ax=ax, palette=["#3498db", "#2ecc71"])
ax.set_title("Class‑level (product)")
ax.set_ylim(0, 1.05)
ax.legend(loc="lower right")

# Instance‑level bar
ax = axes[0, 1]
inst_plot = inst_df.melt(id_vars="Metric", var_name="Level", value_name="Score")
sns.barplot(data=inst_plot[inst_plot["Metric"].isin(["Precision", "Recall", "F1"])],
            x="Metric", y="Score", hue="Level", ax=ax, palette=["#3498db", "#2ecc71"])
ax.set_title("Instance‑level (BLAST, ≥90% ident, ≥50% cov)")
ax.set_ylim(0, 1.05)
ax.legend(loc="lower right")

# Counts stacked bar
ax = axes[1, 0]
counts_df = master[master["Level"].str.contains("Instance")].copy()
counts_df.set_index("Level", inplace=True)
counts_df[["TP", "FP", "FN"]].plot(kind="bar", stacked=True, ax=ax,
                                   color=["#27ae60", "#e74c3c", "#95a5a6"])
ax.set_title("Instance‑level BGC counts")
ax.set_ylabel("Number of BGCs")
ax.legend(loc="upper right")

# Per‑bin F1 distribution (if available)
ax = axes[1, 1]
if os.path.exists(per_bin_file):
    per_bin = pd.read_csv(per_bin_file, sep="\t")
    sns.histplot(per_bin["F1"], bins=10, ax=ax, kde=True, color="#9b59b6")
    ax.set_title("Distribution of per‑bin F1 scores")
    ax.set_xlabel("F1")
    ax.set_ylabel("Number of bins")
else:
    ax.text(0.5, 0.5, "No per‑bin data", ha="center", va="center", transform=ax.transAxes)
    ax.set_title("Per‑bin F1 (not available)")

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "summary_panel.png"), dpi=150)
print(f"\nSummary panel saved to {OUTPUT_DIR}/summary_panel.png")

# -------------------- 7. Optional: Per‑bin heatmap with quality --------------------
if os.path.exists(per_bin_file) and os.path.exists(CHECKM2_FILE):
    merged = merged.set_index("Bin")
    # Select columns for heatmap
    heat_cols = ["Precision", "Recall", "F1", "Completeness", "Contamination"]
    heat_data = merged[heat_cols].fillna(0)
    plt.figure(figsize=(10, max(4, len(heat_data)*0.3)))
    sns.heatmap(heat_data, annot=True, fmt=".2f", cmap="viridis", cbar_kws={'label': 'Score'})
    plt.title("Per‑bin performance and quality")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "per_bin_quality_heatmap.png"), dpi=150)
    print("Per‑bin quality heatmap saved.")

print("\nAll done! Check the 'summary' folder for tables and figures.")
