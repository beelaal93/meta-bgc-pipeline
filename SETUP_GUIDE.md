# 🧬 MetaGenome BGC Discovery - Web Interface
## FYP Setup & Usage Guide

---

## 📁 WHERE TO PUT WHAT

### Your FYP folder structure should look like this:
```
~/FYP/
├── scripts/                 ← Your existing .sh scripts go here (already there)
│   ├── 00_a_download.sh
│   ├── 00_b_convert.sh
│   ├── 01_quality_control.sh
│   ├── 02_assembly.sh
│   ├── 03_binning.sh
│   ├── 04_antismash.sh
│   ├── 04_checkm.sh
│   ├── 05_deepbgc.sh
│   ├── 06_compare.sh
│   ├── 06_compare_bgcs.py
│   └── 07_bigscape.sh
│
├── web_ui/                  ← CREATE THIS FOLDER
│   └── index.html           ← PASTE web UI file here
│
├── server.py                ← PASTE server.py here (root of FYP/)
├── requirements.txt         ← PASTE this here too
│
├── envs/                    ← Your conda environments (already there)
├── data/raw_reads/          ← SRA downloads go here
├── results/                 ← Pipeline outputs go here
└── logs/                    ← Log files go here
```

---

## 🚀 INSTALLATION (ONE-TIME SETUP)

### Step 1: Install Python dependencies
```bash
cd ~/FYP
pip install flask psutil --break-system-packages
# OR if using conda base:
conda activate base
pip install flask psutil
```

### Step 2: Copy files to the right places
```bash
# Copy server.py to FYP root
cp server.py ~/FYP/server.py

# Create and copy web UI folder
mkdir -p ~/FYP/web_ui
cp web_ui/index.html ~/FYP/web_ui/index.html
```

### Step 3: Make sure scripts are executable
```bash
chmod +x ~/FYP/scripts/*.sh
```

---

## ▶️ RUNNING THE WEB INTERFACE

```bash
cd ~/FYP
python server.py
```

Then open your browser and go to:
```
http://localhost:5050
```

Or from another machine on your network:
```
http://<your-laptop-ip>:5050
```

To find your IP:
```bash
ip addr show | grep inet
# or
hostname -I
```

---

## 🎮 HOW TO USE THE INTERFACE

### Dashboard
- See all pipeline steps at a glance
- Real-time CPU, RAM, and disk usage
- Quick-run any step with one click

### SRA Download Page
- Enter one or multiple SRA accession IDs (e.g., SRR1234567)
- Uses EBI fast mirrors first, falls back to NCBI
- Downloads and converts to fastq.gz automatically

### Pipeline Control
- Run steps individually or click "Auto-Run All"
- Each step shows current status (Ready/Running/Done/Failed)

### Parameters Page
- Expand each tool section to configure
- All parameters match exactly what the shell scripts expect
- Click "Save Parameters" — they persist in browser storage

### Live Monitor
- Real-time terminal output from running jobs
- CPU/RAM gauges
- Job history

### Results Browser
- See output directories and file counts

### Logs Page
- View full log files for any completed job

---

## 🔧 TROUBLESHOOTING

### "Connection refused" on port 5050
```bash
# Check if server is running
ps aux | grep server.py
# Restart it
python ~/FYP/server.py
```

### Steps fail immediately
```bash
# Check if your conda envs exist
ls ~/FYP/envs/
# You should see: qc_env, assembly_env, binning_env, etc.
# Go to Settings page in the UI to see which are missing
```

### Scripts not found
```bash
# Verify scripts directory
ls ~/FYP/scripts/
# All .sh files should be there
```

### psutil not available (system monitor shows error)
```bash
pip install psutil --break-system-packages
```

---

## 📌 QUICK COMMANDS

```bash
# Start server
cd ~/FYP && python server.py

# Run in background (keep terminal free)
cd ~/FYP && nohup python server.py > logs/web_server.log 2>&1 &

# Stop background server
pkill -f "python server.py"

# Check server log
tail -f ~/FYP/logs/web_server.log
```

---

## 🏗️ TECH STACK

- **Backend**: Python Flask (lightweight, no heavy dependencies)
- **Frontend**: Pure HTML/CSS/JS (no framework, fast load)
- **Streaming**: Server-Sent Events (SSE) for live log output
- **Fonts**: Syne + JetBrains Mono (professional & readable)
- **Port**: 5050 (change in server.py if needed)

---

*FYP — Metagenomic BGC Discovery System | Web Interface v12.0*
