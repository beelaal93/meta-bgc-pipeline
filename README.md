# 🧬 MetaBGC: Automated Pipeline for Biosynthetic Gene Cluster Discovery

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.0+-green.svg)](https://flask.palletsprojects.com)
[![Status](https://img.shields.io/badge/status-active-success.svg)](#)

## 🔬 Overview
**MetaBGC** is an automated, high-throughput pipeline designed for the detection of Biosynthetic Gene Clusters (BGCs) and the annotation of secondary metabolites within metagenomic datasets. 

By wrapping heavy-duty computational biology tools in a lightweight Flask web interface, this pipeline streamlines the transition from raw sequencing data to actionable genomic insights. It offers researchers real-time execution monitoring, dynamic parameter tuning, and comprehensive comparative analytics.

## ✨ Key Features
* **End-to-End Automation:** Handles raw SRA/FASTQ acquisition[cite: 1, 2], quality control[cite: 3], assembly[cite: 4], and binning[cite: 5] seamlessly.
* **Dual-Engine BGC Detection:** Integrates both rule-based (antiSMASH[cite: 6]) and deep learning-based (DeepBGC[cite: 9]) prediction models.
* **Automated Analytics:** Generates interactive HTML reports, Seaborn/Matplotlib visualizations, and CSV summaries comparing BGC outputs[cite: 11, 12, 14].
* **Web-GUI Integration:** Features a real-time Flask/SocketIO dashboard for monitoring pipeline progress and adjusting execution parameters.

## 🛠️ Architecture & Integrated Tools

| Stage | Integrated Tools | Function |
| :--- | :--- | :--- |
| **Data Acquisition** | SRA Toolkit, `fasterq-dump` | SRA downloading and FASTQ conversion[cite: 1, 2] |
| **Quality Control** | `fastp`, FastQC | Read trimming, adapter removal, and quality assessment[cite: 3] |
| **Metagenomic Assembly** | MEGAHIT, QUAST | Contig generation via custom k-mers and assembly evaluation[cite: 4] |
| **Genome Binning** | Bowtie2, SAMtools, MetaBAT2 | Read mapping and coverage-based contig binning[cite: 5] |
| **Bin QC & Taxonomy** | CheckM2, DFAST-QC | Completeness/contamination assessment and taxonomic classification[cite: 7, 8] |
| **BGC Prediction** | antiSMASH, DeepBGC | Secondary metabolite annotation and deep-learning detection[cite: 6, 9] |
| **Network Analysis** | BiG-SCAPE | Gene Cluster Family (GCF) clustering via Pfam databases[cite: 13] |
| **Orchestration & Viz** | Flask, SocketIO, Pandas, Seaborn | Web interface and comparative analytical reporting[cite: 12, 15] |

## 🖥️ Installation & Setup

### System Requirements
* **OS:** Linux / WSL2 (Ubuntu 20.04+)
* **Environment:** Miniconda or Anaconda3
* **Hardware:** Multi-core CPU (8+ threads recommended), 16GB+ RAM, ~100 GB free disk space (for required databases).

### 1. Clone the Repository
```bash
git clone [https://github.com/beelaal93/meta-bgc-pipeline.git](https://github.com/beelaal93/meta-bgc-pipeline.git)
cd meta-bgc-pipeline
2. Environment ConfigurationMetaBGC uses isolated Conda environments to prevent dependency conflicts. Import the provided YAML files to construct the required environments:  Bash# Example: Creating the web UI and pipeline environments
conda env create -f envs/viz_env.yml
conda env create -f envs/assembly_env.yml
# (Repeat for all environments listed in the envs/ directory)
Note: Ensure all required databases (e.g., Pfam, CheckM2, DeepBGC) are downloaded and paths are updated in your local .meta_bgc_config.json.🚀 UsageLaunch the pipeline orchestrator:Bashpython scripts/app.py
Open http://localhost:5000 in your web browser to access the dashboard[cite: 15].Pipeline Parameter TuningThe web interface allows dynamic adjustment of critical parameters, including[cite: 15]:Assembly: k-min, k-max, k-step, minimum contig length.Binning: Minimum bin size, max edges.CheckM2/DFAST-QC: Completeness and contamination thresholds.BGC Detection: antiSMASH strictness, DeepBGC score thresholds, and prodigal modes.📊 Output & ReportingUpon completion, MetaBGC generates comparative statistics mapping the overlap between antiSMASH and DeepBGC outputs:  SampleantiSMASH BGCsDeepBGC BGCsIntersect/OverlapSRR_Sample_011295Results are exported as interactive HTML files located in the results/06_comparison/ directory.📁 Repository StructurePlaintextmeta-bgc-pipeline/
├── scripts/          # Core Bash execution scripts and Python analytics
├── envs/             # Conda environment YAML exports
├── databases/        # Instructions and paths for genomic databases
├── data/             # Raw FASTQ/SRA uploads (gitignored)
├── results/          # Pipeline outputs and HTML reports (gitignored)
├── logs/             # Step-by-step execution logs (gitignored)
├── app.py            # Flask web interface orchestrator
└── README.md
🤝 ContributingContributions, issues, and feature requests are welcome! Feel free to check the issues page.📄 LicenseThis project is licensed under the MIT License - see the LICENSE file for details.✉️ ContactMuhammad BilalEmail: beelaal5293@gmail.comGitHub: @beelaal93