#!/usr/bin/env python3
"""
Generate an antiSMASH-like HTML report from DeepBGC aggregated CSVs.
Usage: python generate_deepbgc_report.py [input_dir]
"""

import csv
import os
import sys
from pathlib import Path
from collections import Counter
from datetime import datetime

# ----------------------------------------------------------------------
# Determine input directory
# ----------------------------------------------------------------------
if len(sys.argv) > 1:
    INPUT_DIR = Path(sys.argv[1])
else:
    PROJ_OUT = os.environ.get('PROJ_OUT', str(Path.home() / 'FYP/results'))
    INPUT_DIR = Path(PROJ_OUT) / 'deepbgc_bgcs'   # fallback

ALL_BGCS = INPUT_DIR / 'all_bgcs.csv'
COUNTS = INPUT_DIR / 'bgc_counts.csv'
OUTPUT_HTML = INPUT_DIR / 'deepbgc_report.html'

# ----------------------------------------------------------------------
# Read data
# ----------------------------------------------------------------------
def read_csv_to_dicts(path):
    with open(path) as f:
        reader = csv.DictReader(f)
        return list(reader)

all_bgcs = read_csv_to_dicts(ALL_BGCS)
counts = read_csv_to_dicts(COUNTS)

# ----------------------------------------------------------------------
# Prepare data structures
# ----------------------------------------------------------------------
by_sample = {}
for row in all_bgcs:
    key = (row['sample'], row['source'], row['bin_id'])
    by_sample.setdefault(key, []).append(row)

product_counts = Counter(row['product'] for row in all_bgcs)

total_bgcs = len(all_bgcs)
total_length = sum(int(row['length']) for row in all_bgcs)
avg_score = sum(float(row['score']) for row in all_bgcs) / total_bgcs if total_bgcs else 0

# ----------------------------------------------------------------------
# Generate HTML
# ----------------------------------------------------------------------
html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>DeepBGC Overview Report</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1400px; margin: auto; background: white; padding: 20px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #2c3e50; margin-top: 30px; }}
        h3 {{ color: #2c3e50; margin-top: 20px; }}
        .summary-box {{ background: #ecf0f1; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .summary-item {{ display: inline-block; margin-right: 40px; }}
        .summary-label {{ font-weight: bold; color: #7f8c8d; }}
        .summary-value {{ font-size: 24px; color: #2c3e50; }}
        table {{ border-collapse: collapse; width: 100%; margin: 15px 0; background: white; }}
        th {{ background-color: #3498db; color: white; padding: 10px; text-align: left; }}
        td {{ padding: 8px 10px; border-bottom: 1px solid #ddd; }}
        tr:hover {{ background-color: #f1f9ff; }}
        .bin-id {{ font-family: monospace; }}
        .score-high {{ background-color: #d4edda; }}
        .score-medium {{ background-color: #fff3cd; }}
        .score-low {{ background-color: #f8d7da; }}
        .product-badge {{ background: #3498db; color: white; border-radius: 12px; padding: 2px 8px; font-size: 0.9em; }}
        .collapsible {{ background-color: #ecf0f1; color: #2c3e50; cursor: pointer; padding: 10px; width: 100%; border: none; text-align: left; outline: none; font-size: 16px; font-weight: bold; border-radius: 5px; margin-top: 10px; }}
        .active, .collapsible:hover {{ background-color: #bdc3c7; }}
        .content {{ padding: 0 18px; display: none; overflow: hidden; background-color: white; border: 1px solid #ddd; }}
        .product-bar {{ display: inline-block; height: 20px; background-color: #3498db; margin-right: 5px; }}
        .product-row {{ margin: 5px 0; }}
        .footer {{ margin-top: 40px; font-size: 0.9em; color: #7f8c8d; text-align: center; border-top: 1px solid #ddd; padding-top: 15px; }}
    </style>
</head>
<body>
<div class="container">
    <h1>🧬 DeepBGC BGC Overview</h1>
    <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>

    <div class="summary-box">
        <div class="summary-item">
            <div class="summary-label">Total BGCs</div>
            <div class="summary-value">{total_bgcs}</div>
        </div>
        <div class="summary-item">
            <div class="summary-label">Total length (bp)</div>
            <div class="summary-value">{total_length:,}</div>
        </div>
        <div class="summary-item">
            <div class="summary-label">Average score</div>
            <div class="summary-value">{avg_score:.3f}</div>
        </div>
    </div>

    <h2>Product class distribution</h2>
    <div style="margin: 20px 0;">
"""

max_count = max(product_counts.values()) if product_counts else 1
for product, count in sorted(product_counts.items(), key=lambda x: -x[1]):
    percent = count / max_count * 100
    html += f"""
        <div class="product-row">
            <span style="display: inline-block; width: 120px;"><strong>{product}</strong></span>
            <span style="display: inline-block; width: 50px;">{count}</span>
            <span class="product-bar" style="width: {percent}%; background-color: #3498db;">&nbsp;</span>
        </div>
"""

html += """
    </div>

    <h2>Per‑sample / bin summary</h2>
    <table>
        <tr>
            <th>Sample</th>
            <th>Source</th>
            <th>Bin ID</th>
            <th>BGC count</th>
            <th>Total length</th>
            <th>Avg score</th>
        </tr>
"""

for row in sorted(counts, key=lambda x: (x['sample'], x['source'], x['bin_id'])):
    html += f"""
        <tr>
            <td>{row['sample']}</td>
            <td>{row['source']}</td>
            <td class="bin-id">{row['bin_id']}</td>
            <td>{row['bgc_count']}</td>
            <td>{int(row['total_length']):,}</td>
            <td>{float(row['avg_score']):.3f}</td>
        </tr>
"""

html += """
    </table>

    <h2>Detailed BGC lists</h2>
"""

for (sample, source, bin_id), bgcs in sorted(by_sample.items()):
    if source == 'assembly':
        title = f"{sample} (assembly)"
    else:
        title = f"{sample} – bin {bin_id}"
    bgcs_sorted = sorted(bgcs, key=lambda x: (x['contig'], int(x['start'])))

    html += f"""
    <button class="collapsible">{title} – {len(bgcs)} BGCs</button>
    <div class="content">
        <table>
            <tr>
                <th>Contig</th>
                <th>Start</th>
                <th>End</th>
                <th>Length</th>
                <th>Score</th>
                <th>Product</th>
            </tr>
    """

    for b in bgcs_sorted:
        score = float(b['score'])
        if score >= 0.8:
            score_class = 'score-high'
        elif score >= 0.6:
            score_class = 'score-medium'
        else:
            score_class = 'score-low'

        html += f"""
            <tr class="{score_class}">
                <td>{b['contig']}</td>
                <td>{b['start']}</td>
                <td>{b['end']}</td>
                <td>{b['length']}</td>
                <td>{score:.4f}</td>
                <td><span class="product-badge">{b['product']}</span></td>
            </tr>
        """

    html += """
        </table>
    </div>
    """

html += """
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
        Report generated from DeepBGC aggregated data.<br>
        Columns: score ≥0.8 = green, 0.6–0.8 = yellow, <0.6 = red.
    </div>
</div>
</body>
</html>
"""

with open(OUTPUT_HTML, 'w') as f:
    f.write(html)

print(f"✅ Report generated: {OUTPUT_HTML}")