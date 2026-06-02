#!/bin/bash
# ==============================================================================
# 05_deepbgc_summary_final.sh – Aggregates DeepBGC results using correct column names
# ==============================================================================

set -euo pipefail

PROJ_OUT="${PROJ_OUT:-$HOME/FYP/results}"
DEEPBGC_DIR="${1:-$PROJ_OUT/05_deepbgc}"
OUTPUT_DIR="${2:-$PROJ_OUT/deepbgc_bgcs}"

mkdir -p "$OUTPUT_DIR"
echo "📁 Aggregating DeepBGC results from: $DEEPBGC_DIR"
echo "📁 Writing summaries to: $OUTPUT_DIR"

python3 - <<'EOF' "$DEEPBGC_DIR" "$OUTPUT_DIR"
import sys
import csv
from pathlib import Path

deepbgc_root = Path(sys.argv[1])
out_dir = Path(sys.argv[2])

# ----------------------------------------------------------------------
# Helper: parse a DeepBGC .bgc.tsv file with the known header
# ----------------------------------------------------------------------
def parse_bgc_tsv(tsv_path, sample, source, bin_id=None):
    rows = []
    try:
        with open(tsv_path) as f:
            # Read the first non-empty line (should be the header)
            first_line = None
            for line in f:
                line = line.strip()
                if line:
                    first_line = line
                    break
            if not first_line:
                return rows
            f.seek(0)

            # Detect header by splitting first line
            headers = [h.strip() for h in first_line.split('\t')]
            print(f"   📋 Headers in {tsv_path.name}: {headers}", file=sys.stderr)

            # Define column mapping (use exact names from your header)
            col_map = {}
            # Required fields and their exact column names
            required = {
                'contig': 'sequence_id',
                'start': 'nucl_start',
                'end': 'nucl_end',
                'length': 'nucl_length',
                'score': 'deepbgc_score',
                'product': 'product_class'
            }
            for key, colname in required.items():
                try:
                    col_map[key] = headers.index(colname)
                except ValueError:
                    print(f"   ❌ Column '{colname}' not found in {tsv_path.name}. Available headers: {headers}", file=sys.stderr)
                    return rows  # skip this file

            # If header starts with '#', skip that line (but ours doesn't)
            if first_line.startswith('#'):
                next(f)  # skip the comment line

            # Read data rows (skip header)
            reader = csv.reader(f, delimiter='\t')
            next(reader)  # skip header line

            for line_num, row in enumerate(reader, start=3):
                if not row:
                    continue
                try:
                    contig = row[col_map['contig']]
                    start = int(row[col_map['start']])
                    end = int(row[col_map['end']])
                    # Use provided length if available, else compute
                    if col_map['length'] < len(row) and row[col_map['length']].strip():
                        length = int(row[col_map['length']])
                    else:
                        length = end - start + 1
                    score = float(row[col_map['score']])
                    product = row[col_map['product']].strip() or 'unknown'
                except (ValueError, IndexError) as e:
                    print(f"   ⚠️  Warning: could not parse line {line_num} in {tsv_path}: {e}", file=sys.stderr)
                    continue

                rows.append({
                    'sample': sample,
                    'source': source,
                    'bin_id': bin_id if bin_id else '',
                    'contig': contig,
                    'start': start,
                    'end': end,
                    'length': length,
                    'score': score,
                    'product': product
                })
    except Exception as e:
        print(f"⚠️  Error processing {tsv_path}: {e}", file=sys.stderr)
    return rows

# ----------------------------------------------------------------------
# Collect all BGC records
# ----------------------------------------------------------------------
all_bgcs = []

# Assemblies
for asm_dir in deepbgc_root.glob('*_Assembly'):
    sample = asm_dir.name.replace('_Assembly', '')
    tsv_file = asm_dir / f"{asm_dir.name}.bgc.tsv"
    if tsv_file.exists():
        all_bgcs.extend(parse_bgc_tsv(tsv_file, sample, 'assembly'))

# Bins
for bins_parent in deepbgc_root.glob('*_Bins'):
    sample = bins_parent.name.replace('_Bins', '')
    for bin_dir in bins_parent.iterdir():
        if not bin_dir.is_dir():
            continue
        bin_id = bin_dir.name
        tsv_file = bin_dir / f"{bin_id}.bgc.tsv"
        if tsv_file.exists():
            all_bgcs.extend(parse_bgc_tsv(tsv_file, sample, 'bin', bin_id))

if not all_bgcs:
    print("❌ No BGC records parsed. Check the header output above for column mismatches.")
    sys.exit(1)

print(f"✅ Successfully parsed {len(all_bgcs)} BGC predictions.")

# ----------------------------------------------------------------------
# Write output CSVs
# ----------------------------------------------------------------------
fieldnames = ['sample', 'source', 'bin_id', 'contig', 'start', 'end',
              'length', 'score', 'product']

# All BGCs
with open(out_dir / 'all_bgcs.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(all_bgcs)

# Assembly only
asm_bgcs = [b for b in all_bgcs if b['source'] == 'assembly']
with open(out_dir / 'assembly_bgcs.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(asm_bgcs)

# Bins only
bin_bgcs = [b for b in all_bgcs if b['source'] == 'bin']
with open(out_dir / 'bins_bgcs.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(bin_bgcs)

# Counts summary
counts = []
groups = {}
for b in all_bgcs:
    key = (b['sample'], b['source'], b['bin_id'])
    groups.setdefault(key, []).append(b)

for (sample, source, bin_id), bgcs in groups.items():
    total_len = sum(b['length'] for b in bgcs)
    avg_score = sum(b['score'] for b in bgcs) / len(bgcs) if bgcs else 0
    counts.append({
        'sample': sample,
        'source': source,
        'bin_id': bin_id,
        'bgc_count': len(bgcs),
        'total_length': total_len,
        'avg_score': avg_score
    })

with open(out_dir / 'bgc_counts.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['sample','source','bin_id','bgc_count','total_length','avg_score'])
    writer.writeheader()
    writer.writerows(counts)

print("📊 Summary files created:")
print(f"   - {out_dir/'all_bgcs.csv'}")
print(f"   - {out_dir/'assembly_bgcs.csv'}")
print(f"   - {out_dir/'bins_bgcs.csv'}")
print(f"   - {out_dir/'bgc_counts.csv'}")
EOF

echo -e "\n✅ DeepBGC aggregation complete."