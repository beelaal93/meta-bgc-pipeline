#!/usr/bin/env python3
"""
Extract nucleotide sequences from antiSMASH region GBK files and write to FASTA.
Usage: extract_bgc_seqs.py --input DIR --output FASTA
"""
import os, glob, argparse
from Bio import SeqIO

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Directory containing region*.gbk files (searched recursively)")
    parser.add_argument("--output", required=True, help="Output FASTA file")
    args = parser.parse_args()

    gbk_files = glob.glob(os.path.join(args.input, "**", "*region*.gbk"), recursive=True)
    with open(args.output, "w") as out_fa:
        for gbk in gbk_files:
            for record in SeqIO.parse(gbk, "genbank"):
                # Use the filename + region info as a unique ID
                base = os.path.basename(gbk).replace(".gbk", "")
                seq_id = f"{base}|{record.id}"
                out_fa.write(f">{seq_id}\n{str(record.seq)}\n")

    print(f"Extracted {len(gbk_files)} region files to {args.output}")

if __name__ == "__main__":
    main()
