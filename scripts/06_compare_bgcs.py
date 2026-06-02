#!/usr/bin/env python3
"""
Comprehensive BGC comparison: antiSMASH vs DeepBGC
Now includes antiSMASH assemblies and bins, DeepBGC assemblies and bins.
Generates an HTML report with per‑bin/assembly tables, statistics, and plots.
"""

import os
import glob
import argparse
import logging
from pathlib import Path

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from Bio import SeqIO
from matplotlib_venn import venn2

# ==============================================================================
# Logging setup
# ==============================================================================
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# ==============================================================================
# Helper functions
# ==============================================================================
def extract_sample_bin_from_path(path, tool):
    """
    Extract sample name and bin ID from a file path.
    For antiSMASH:
        - assembly: .../antismash/sample_Assembly/*.region*.gbk  -> bin_id='assembly'
        - bins:     .../antismash/sample_Bins/bin.1/*.region*.gbk -> bin_id='bin.1'
    For DeepBGC:
        - assembly: .../05_deepbgc/sample_Assembly/*.bgc.gbk        -> bin_id='assembly'
        - bins:     .../05_deepbgc/sample_Bins/bin.1/*.bgc.gbk      -> bin_id='bin.1'
    """
    path = Path(path)
    parts = path.parts

    if tool == 'antismash':
        # Look for '_Assembly' folder (assembly level)
        for i, part in enumerate(parts):
            if part.endswith('_Assembly'):
                sample = part[:-9]  # remove '_Assembly'
                return sample, 'assembly'
        # Look for '_Bins' folder (bin level)
        for i, part in enumerate(parts):
            if part.endswith('_Bins'):
                sample = part[:-5]  # remove '_Bins'
                # Next part should be bin folder (e.g., bin.1)
                if i+1 < len(parts) and parts[i+1].startswith('bin.'):
                    bin_id = parts[i+1]
                    return sample, bin_id
        # If nothing matched
        return 'unknown', 'unknown'

    elif tool == 'deepbgc':
        # DeepBGC assembly: folder ends with '_Assembly'
        for part in parts:
            if part.endswith('_Assembly'):
                sample = part[:-9]
                return sample, 'assembly'
        # DeepBGC bins: folder ends with '_Bins'
        for i, part in enumerate(parts):
            if part.endswith('_Bins'):
                sample = part[:-5]
                # Next part should be bin folder
                if i+1 < len(parts) and parts[i+1].startswith('bin.'):
                    bin_id = parts[i+1]
                    return sample, bin_id
        return 'unknown', None
    return 'unknown', None

def calculate_gc(seq):
    """Return GC percentage of a nucleotide sequence."""
    if not seq:
        return 0.0
    seq = seq.upper()
    gc = seq.count('G') + seq.count('C')
    return (gc / len(seq)) * 100

def parse_antismash_gbk(gbk_path):
    """Extract BGC info from antiSMASH region GBK files."""
    records = []
    try:
        for record in SeqIO.parse(gbk_path, "genbank"):
            if len(record.seq) < 200:
                continue
            # Find product class
            product = "unknown"
            for feat in record.features:
                if feat.type in ("cluster", "protocluster", "cand_cluster"):
                    product = feat.qualifiers.get("product", ["unknown"])[0]
                    break
            gene_count = sum(1 for f in record.features if f.type == "CDS")
            gc = calculate_gc(str(record.seq))
            size_kb = len(record.seq) / 1000.0
            # Extract contig name from record.id (usually like "k141_xxx")
            contig = record.id.split()[0] if record.id else "unknown"
            records.append({
                'tool': 'antiSMASH',
                'sample': 'unknown',          # will fill later
                'bin_id': None,
                'contig': contig,
                'start': 0,                   # antiSMASH regions are extracted, start=0
                'end': len(record.seq),
                'length': len(record.seq),
                'size_kb': size_kb,
                'product': product.replace('_', ' ').title(),
                'gene_count': gene_count,
                'gc_content': gc,
                'source_file': str(gbk_path)
            })
    except Exception as e:
        logger.warning(f"Failed to parse antiSMASH GBK {gbk_path}: {e}")
    return records

def parse_deepbgc_gbk(gbk_path):
    """Extract BGC info from DeepBGC .bgc.gbk files."""
    records = []
    try:
        for record in SeqIO.parse(gbk_path, "genbank"):
            if len(record.seq) < 200:
                continue
            # Find product class – stored in 'cluster' feature
            product = "unknown"
            for feat in record.features:
                if feat.type == "cluster":
                    product = feat.qualifiers.get("product", [None])[0]
                    if not product:
                        note = feat.qualifiers.get("note", [""])[0]
                        if "product:" in note:
                            product = note.split("product:")[-1].split()[0]
                    break
            gene_count = sum(1 for f in record.features if f.type == "CDS")
            gc = calculate_gc(str(record.seq))
            size_kb = len(record.seq) / 1000.0
            # Contig name can be extracted from record.id (may be like "k141_1165_2-4196.1")
            contig = record.id.split('_')[0] if '_' in record.id else record.id
            records.append({
                'tool': 'DeepBGC',
                'sample': 'unknown',
                'bin_id': None,
                'contig': contig,
                'start': 1,
                'end': len(record.seq),
                'length': len(record.seq),
                'size_kb': size_kb,
                'product': product.replace('_', ' ').title() if product else 'Unknown',
                'gene_count': gene_count,
                'gc_content': gc,
                'source_file': str(gbk_path)
            })
    except Exception as e:
        logger.warning(f"Failed to parse DeepBGC GBK {gbk_path}: {e}")
    return records

def parse_deepbgc_tsv(tsv_path, sample, bin_id):
    """
    Fallback: parse DeepBGC TSV if GBK not available.
    TSV columns: sequence_id, nucl_start, nucl_end, product_class, deepbgc_score, etc.
    """
    records = []
    try:
        df = pd.read_csv(tsv_path, sep='\t')
        if 'product_class' in df.columns:
            prod_col = 'product_class'
        elif 'product' in df.columns:
            prod_col = 'product'
        else:
            return records
        for _, row in df.iterrows():
            if pd.isna(row[prod_col]):
                continue
            length = row.get('nucl_end', 0) - row.get('nucl_start', 0) + 1
            if length <= 0:
                length = row.get('nucl_length', 0)
            records.append({
                'tool': 'DeepBGC',
                'sample': sample,
                'bin_id': bin_id,
                'contig': row.get('sequence_id', ''),
                'start': row.get('nucl_start', 0),
                'end': row.get('nucl_end', 0),
                'length': length,
                'size_kb': length / 1000.0,
                'product': str(row[prod_col]).replace('_', ' ').title(),
                'gene_count': row.get('num_proteins', 0),
                'gc_content': 0.0,  # not available
                'source_file': str(tsv_path)
            })
    except Exception as e:
        logger.warning(f"Failed to parse TSV {tsv_path}: {e}")
    return records

# ==============================================================================
# Main comparison function
# ==============================================================================
def generate_report(antismash_dir, deepbgc_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    sns.set_theme(style="whitegrid")

    all_records = []

    # ---- antiSMASH assembly level ----
    logger.info("Scanning antiSMASH assembly GBK files...")
    anti_asm_files = glob.glob(os.path.join(antismash_dir, "*_Assembly", "*.region*.gbk"), recursive=False)
    logger.info(f"Found {len(anti_asm_files)} antiSMASH assembly region files")
    for gbk in anti_asm_files:
        sample, bin_id = extract_sample_bin_from_path(gbk, 'antismash')
        records = parse_antismash_gbk(gbk)
        for r in records:
            r['sample'] = sample
            r['bin_id'] = bin_id
        all_records.extend(records)

    # ---- antiSMASH bin level ----
    logger.info("Scanning antiSMASH bin GBK files...")
    anti_bin_files = glob.glob(os.path.join(antismash_dir, "*_Bins", "bin.*", "*.region*.gbk"), recursive=True)
    logger.info(f"Found {len(anti_bin_files)} antiSMASH bin region files")
    for gbk in anti_bin_files:
        sample, bin_id = extract_sample_bin_from_path(gbk, 'antismash')
        records = parse_antismash_gbk(gbk)
        for r in records:
            r['sample'] = sample
            r['bin_id'] = bin_id
        all_records.extend(records)

    # ---- DeepBGC assembly level ----
    logger.info("Scanning DeepBGC assembly GBK files...")
    deep_asm_files = glob.glob(os.path.join(deepbgc_dir, "*_Assembly", "*.bgc.gbk"), recursive=False)
    logger.info(f"Found {len(deep_asm_files)} DeepBGC assembly GBK files")
    for gbk in deep_asm_files:
        sample, bin_id = extract_sample_bin_from_path(gbk, 'deepbgc')
        records = parse_deepbgc_gbk(gbk)
        for r in records:
            r['sample'] = sample
            r['bin_id'] = bin_id
        all_records.extend(records)

    # ---- DeepBGC bin level ----
    logger.info("Scanning DeepBGC bin GBK files...")
    deep_bin_files = glob.glob(os.path.join(deepbgc_dir, "*_Bins", "bin.*", "*.bgc.gbk"), recursive=True)
    logger.info(f"Found {len(deep_bin_files)} DeepBGC bin GBK files")
    for gbk in deep_bin_files:
        sample, bin_id = extract_sample_bin_from_path(gbk, 'deepbgc')
        records = parse_deepbgc_gbk(gbk)
        for r in records:
            r['sample'] = sample
            r['bin_id'] = bin_id
        all_records.extend(records)

    # ---- Fallback to TSV if no DeepBGC GBK found (though you have GBKs) ----
    if not deep_asm_files and not deep_bin_files:
        logger.warning("No DeepBGC GBK files found, falling back to TSV...")
        deep_tsv_files = glob.glob(os.path.join(deepbgc_dir, "*_Assembly", "*.bgc.tsv"), recursive=False)
        deep_tsv_files += glob.glob(os.path.join(deepbgc_dir, "*_Bins", "bin.*", "*.bgc.tsv"), recursive=True)
        for tsv in deep_tsv_files:
            sample, bin_id = extract_sample_bin_from_path(tsv, 'deepbgc')
            records = parse_deepbgc_tsv(tsv, sample, bin_id)
            all_records.extend(records)

    if not all_records:
        logger.error("No BGC data collected. Check input directories.")
        return

    df = pd.DataFrame(all_records)
    # Remove duplicates (if any)
    df.drop_duplicates(subset=['tool', 'sample', 'bin_id', 'contig', 'start', 'end'], inplace=True)

    # Save raw data
    df.to_csv(os.path.join(out_dir, "bgc_comparison_raw.csv"), index=False)
    logger.info(f"Saved raw data ({len(df)} records) to {out_dir}/bgc_comparison_raw.csv")

    # ==========================================================================
    # Summary statistics
    # ==========================================================================
    # Overall per tool
    overall_stats = df.groupby('tool').agg(
        count=('product', 'count'),
        mean_size_kb=('size_kb', 'mean'),
        median_size_kb=('size_kb', 'median'),
        mean_gene_count=('gene_count', lambda x: x[x>0].mean()),
        mean_gc=('gc_content', lambda x: x[x>0].mean())
    ).reset_index()
    overall_stats.to_csv(os.path.join(out_dir, "overall_stats.csv"), index=False)

    # Per sample and per bin (including assembly as a special bin)
    per_bin_stats = df.groupby(['sample', 'bin_id', 'tool']).agg(
        count=('product', 'count'),
        total_length=('length', 'sum'),
        mean_score=('score', 'mean') if 'score' in df.columns else ('length', lambda x: 0)
    ).reset_index()
    per_bin_stats.to_csv(os.path.join(out_dir, "per_bin_stats.csv"), index=False)

    # ==========================================================================
    # Plots (fixed seaborn deprecation warnings)
    # ==========================================================================
    plot_dir = os.path.join(out_dir, "plots")
    os.makedirs(plot_dir, exist_ok=True)

    # 1. Overall count comparison (bar chart)
    plt.figure(figsize=(6,5))
    sns.countplot(data=df, x='tool', order=['antiSMASH', 'DeepBGC'])
    plt.title('Total BGCs detected')
    plt.ylabel('Count')
    plt.tight_layout()
    plt.savefig(os.path.join(plot_dir, '01_total_counts.png'), dpi=300)
    plt.close()

    # 2. Per‑bin/assembly counts (for groups with both tools)
    # Create a pivot table for plotting
    pivot_counts = per_bin_stats.pivot_table(index=['sample', 'bin_id'], columns='tool', values='count', fill_value=0).reset_index()
    pivot_counts = pivot_counts[(pivot_counts['antiSMASH']>0) | (pivot_counts['DeepBGC']>0)]
    if not pivot_counts.empty:
        # Simplify index for plotting
        pivot_counts['label'] = pivot_counts['sample'] + ' | ' + pivot_counts['bin_id'].astype(str)
        ax = pivot_counts.set_index('label')[['antiSMASH', 'DeepBGC']].plot(kind='bar', figsize=(max(8, len(pivot_counts)*0.4), 6))
        plt.title('BGC counts per sample/bin (where either tool found BGCs)')
        plt.ylabel('Count')
        plt.tight_layout()
        plt.savefig(os.path.join(plot_dir, '02_per_bin_counts.png'), dpi=300)
        plt.close()

    # 3. Product class distribution (top 15)
    top_classes = df['product'].value_counts().head(15).index
    df_top = df[df['product'].isin(top_classes)]
    plt.figure(figsize=(14,8))
    sns.countplot(data=df_top, y='product', hue='tool', palette='viridis', order=top_classes)
    plt.title('Top 15 BGC classes')
    plt.xlabel('Count')
    plt.tight_layout()
    plt.savefig(os.path.join(plot_dir, '03_class_distribution.png'), dpi=300)
    plt.close()

    # 4. Size distribution (violin plot) – fixed deprecation
    plt.figure(figsize=(8,6))
    sns.violinplot(data=df, x='tool', y='size_kb', hue='tool', palette='mako', legend=False)
    plt.title('BGC size distribution')
    plt.ylabel('Size (kb)')
    plt.tight_layout()
    plt.savefig(os.path.join(plot_dir, '04_size_violin.png'), dpi=300)
    plt.close()

    # 5. Gene count distribution (if available)
    if df['gene_count'].sum() > 0:
        plt.figure(figsize=(8,6))
        sns.boxplot(data=df[df['gene_count']>0], x='tool', y='gene_count', hue='tool', palette='Set2', legend=False)
        plt.title('Gene count per BGC')
        plt.ylabel('Number of genes')
        plt.tight_layout()
        plt.savefig(os.path.join(plot_dir, '05_gene_count.png'), dpi=300)
        plt.close()

    # 6. GC content (if available)
    if df['gc_content'].sum() > 0:
        plt.figure(figsize=(8,6))
        sns.violinplot(data=df[df['gc_content']>0], x='tool', y='gc_content', hue='tool', palette='mako', legend=False)
        plt.title('GC content distribution')
        plt.ylabel('GC %')
        plt.tight_layout()
        plt.savefig(os.path.join(plot_dir, '06_gc_content.png'), dpi=300)
        plt.close()

    # ==========================================================================
    # HTML report generation
    # ==========================================================================
    html_path = os.path.join(out_dir, "comparison_report.html")
    with open(html_path, 'w') as f:
        f.write("""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>BGC Comparison: antiSMASH vs DeepBGC</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1400px; margin: auto; background: white; padding: 20px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
        h2 { color: #2c3e50; margin-top: 30px; }
        h3 { color: #2c3e50; margin-top: 20px; }
        .summary-box { background: #ecf0f1; padding: 15px; border-radius: 5px; margin: 20px 0; }
        .summary-item { display: inline-block; margin-right: 40px; }
        .summary-label { font-weight: bold; color: #7f8c8d; }
        .summary-value { font-size: 24px; color: #2c3e50; }
        table { border-collapse: collapse; width: 100%; margin: 15px 0; background: white; }
        th { background-color: #3498db; color: white; padding: 10px; text-align: left; }
        td { padding: 8px 10px; border-bottom: 1px solid #ddd; }
        tr:hover { background-color: #f1f9ff; }
        .bin-id { font-family: monospace; }
        .tool-anti { background-color: #e8f4f8; }
        .tool-deep { background-color: #fff0e0; }
        .collapsible { background-color: #ecf0f1; color: #2c3e50; cursor: pointer; padding: 10px; width: 100%%; border: none; text-align: left; outline: none; font-size: 16px; font-weight: bold; border-radius: 5px; margin-top: 10px; }
        .active, .collapsible:hover { background-color: #bdc3c7; }
        .content { padding: 0 18px; display: none; overflow: hidden; background-color: white; border: 1px solid #ddd; }
        .footer { margin-top: 40px; font-size: 0.9em; color: #7f8c8d; text-align: center; border-top: 1px solid #ddd; padding-top: 15px; }
        .plot-img { max-width: 100%%; height: auto; margin: 10px 0; border: 1px solid #ddd; }
        .note { background: #fff3cd; border-left: 4px solid #ffc107; padding: 10px; margin: 10px 0; }
    </style>
</head>
<body>
<div class="container">
    <h1>🔬 BGC Comparison: antiSMASH vs DeepBGC</h1>
    <p>Generated on """ + pd.Timestamp.now().strftime('%Y-%m-%d %H:%M') + """</p>

    <div class="note">
        <strong>Note:</strong> Clicking on GBK links may not open directly in your browser due to security restrictions.
        To view a GBK file, right‑click the link and select "Save link as…", then open it with a text editor or GenBank viewer.
    </div>

    <div class="summary-box">
        <div class="summary-item">
            <div class="summary-label">Total antiSMASH BGCs</div>
            <div class="summary-value">""" + str(len(df[df['tool']=='antiSMASH'])) + """</div>
        </div>
        <div class="summary-item">
            <div class="summary-label">Total DeepBGC BGCs</div>
            <div class="summary-value">""" + str(len(df[df['tool']=='DeepBGC'])) + """</div>
        </div>
        <div class="summary-item">
            <div class="summary-label">Samples with bins/assemblies</div>
            <div class="summary-value">""" + str(df[df['bin_id'].notna()]['sample'].nunique()) + """</div>
        </div>
    </div>

    <h2>Overall statistics per tool</h2>
    """ + overall_stats.to_html(index=False, float_format='%.2f') + """

    <h2>Plots</h2>
    <div style="display: flex; flex-wrap: wrap; justify-content: space-around;">
        <div style="width: 45%%; margin: 10px;">
            <h3>Total counts</h3>
            <img class="plot-img" src="plots/01_total_counts.png" alt="Total counts">
        </div>
        <div style="width: 45%%; margin: 10px;">
            <h3>Class distribution</h3>
            <img class="plot-img" src="plots/03_class_distribution.png" alt="Class distribution">
        </div>
        <div style="width: 45%%; margin: 10px;">
            <h3>Size distribution</h3>
            <img class="plot-img" src="plots/04_size_violin.png" alt="Size distribution">
        </div>
        <div style="width: 45%%; margin: 10px;">
            <h3>Gene count</h3>
            <img class="plot-img" src="plots/05_gene_count.png" alt="Gene count">
        </div>
    </div>

    <h2>Per‑sample/bin BGC counts</h2>
    """ + per_bin_stats.to_html(index=False, float_format='%.2f') + """

    <h2>Detailed BGC lists by sample/bin</h2>
""")

        # Group by sample and bin_id, and sort keys for consistent order
        grouped = df.groupby(['sample', 'bin_id'])
        sorted_keys = sorted(grouped.groups.keys(), key=lambda x: (x[0], x[1] if x[1] else ''))
        for sample, bin_id in sorted_keys:
            if bin_id is None or pd.isna(bin_id):
                continue
            group = grouped.get_group((sample, bin_id))
            # Create a readable title
            if bin_id == 'assembly':
                title = f"{sample} (assembly)"
            else:
                title = f"{sample} – {bin_id}"
            anti_group = group[group['tool'] == 'antiSMASH']
            deep_group = group[group['tool'] == 'DeepBGC']

            f.write(f"""
    <button class="collapsible">{title} (antiSMASH: {len(anti_group)} | DeepBGC: {len(deep_group)})</button>
    <div class="content">
        <table>
            <tr>
                <th>Tool</th>
                <th>Contig</th>
                <th>Start</th>
                <th>End</th>
                <th>Length</th>
                <th>Product</th>
                <th>Genes</th>
                <th>GC%</th>
                <th>File</th>
            </tr>
""")
            for _, row in group.sort_values(['tool', 'contig', 'start']).iterrows():
                tool_class = 'tool-anti' if row['tool'] == 'antiSMASH' else 'tool-deep'
                f.write(f"""
            <tr class="{tool_class}">
                <td>{row['tool']}</td>
                <td>{row['contig']}</td>
                <td>{row['start']}</td>
                <td>{row['end']}</td>
                <td>{row['length']}</td>
                <td>{row['product']}</td>
                <td>{row['gene_count']}</td>
                <td>{row['gc_content']:.1f}</td>
                <td><a href="file://{row['source_file']}" target="_blank">GBK</a></td>
            </tr>
""")
            f.write("""
        </table>
    </div>
""")

        f.write("""
    <script>
        var coll = document.getElementsByClassName("collapsible");
        for (var i = 0; i < coll.length; i++) {
            coll[i].addEventListener("click", function() {
                this.classList.toggle("active");
                var content = this.nextElementSibling;
                if (content.style.display === "block") {
                    content.style.display = "none";
                } else {
                    content.style.display = "block";
                }
            });
        }
    </script>

    <div class="footer">
        Report generated from antiSMASH and DeepBGC outputs.<br>
        Data files: <a href="bgc_comparison_raw.csv">bgc_comparison_raw.csv</a>, 
        <a href="overall_stats.csv">overall_stats.csv</a>, 
        <a href="per_bin_stats.csv">per_bin_stats.csv</a>
    </div>
</div>
</body>
</html>
""")

    logger.info(f"HTML report generated: {html_path}")
    with open(os.path.join(out_dir, "comparison_done.txt"), "w") as f:
        f.write("Comparison completed successfully.\n")

# ==============================================================================
# Command line interface
# ==============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare antiSMASH and DeepBGC results")
    parser.add_argument("--antismash_dir", required=True, help="Path to antiSMASH results folder")
    parser.add_argument("--deepbgc_dir", required=True, help="Path to DeepBGC results folder")
    parser.add_argument("--out_dir", required=True, help="Output directory for comparison results")
    args = parser.parse_args()
    generate_report(args.antismash_dir, args.deepbgc_dir, args.out_dir)