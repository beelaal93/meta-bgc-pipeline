#!/usr/bin/env python3
"""
META BGC – Flask Web Interface (with CheckM2 + DFAST‑QC Taxonomy)
Enhanced with real‑time stop and sample feedback.
"""

import os
import json
import threading
import subprocess
import time
import glob
import signal
import stat
import psutil
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'meta-bgc-secret'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024 * 1024  # 50 GB
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ---------- Fixed Paths ----------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SCRIPT_DIR = os.path.join(BASE_DIR, 'scripts')
LOG_DIR = os.path.join(BASE_DIR, 'logs')
DATA_DIR = os.path.join(BASE_DIR, 'data', 'raw_reads')
RESULTS_DIR = os.path.join(BASE_DIR, 'results')
CONFIG_FILE = os.path.join(BASE_DIR, '.meta_bgc_config.json')

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

# ---------- Ensure scripts executable ----------
def make_scripts_executable():
    if not os.path.exists(SCRIPT_DIR):
        print(f"WARNING: Script directory {SCRIPT_DIR} does not exist.")
        return
    for f in os.listdir(SCRIPT_DIR):
        if f.endswith('.sh'):
            path = os.path.join(SCRIPT_DIR, f)
            st = os.stat(path)
            os.chmod(path, st.st_mode | stat.S_IEXEC)
            print(f"Made executable: {f}")

make_scripts_executable()

# ---------- Default I/O ----------
DEFAULT_OUTPUTS = {
    'fetch_convert': DATA_DIR,
    'qc': os.path.join(RESULTS_DIR, '01_qc'),
    'assembly': os.path.join(RESULTS_DIR, '02_assembly'),
    'binning': os.path.join(RESULTS_DIR, '03_binning'),
    'checkm2': os.path.join(RESULTS_DIR, '04_bin_quality', 'checkm2'),
    'dfast_qc': os.path.join(RESULTS_DIR, '04_bin_taxonomy'),
    'antismash': os.path.join(RESULTS_DIR, '05_bgc', 'antismash'),
    'deepbgc': os.path.join(RESULTS_DIR, '05_deepbgc'),
    'compare': os.path.join(RESULTS_DIR, '06_comparison'),
    'bigscape': os.path.join(RESULTS_DIR, '07_network_analysis')
}

DEFAULT_INPUTS = {
    'fetch_convert': None,
    'qc': DATA_DIR,
    'assembly': os.path.join(RESULTS_DIR, '01_qc', 'clean_reads'),
    'binning': os.path.join(RESULTS_DIR, '02_assembly'),
    'checkm2': os.path.join(RESULTS_DIR, '03_binning'),
    'dfast_qc': os.path.join(RESULTS_DIR, '03_binning'),
    'antismash': os.path.join(RESULTS_DIR, '03_binning'),
    'deepbgc': None,
    'compare': None,
    'bigscape': os.path.join(RESULTS_DIR, '05_bgc', 'antismash')
}

# ---------- Custom I/O ----------
CUSTOM_INPUTS = {}
CUSTOM_OUTPUTS = {}

def load_config():
    global CUSTOM_INPUTS, CUSTOM_OUTPUTS
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                cfg = json.load(f)
                CUSTOM_INPUTS = cfg.get('inputs', {})
                CUSTOM_OUTPUTS = cfg.get('outputs', {})
        except:
            pass

def save_config():
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump({
                'inputs': CUSTOM_INPUTS,
                'outputs': CUSTOM_OUTPUTS,
                'updated': datetime.now().isoformat()
            }, f, indent=2)
        return True
    except:
        return False

load_config()

def get_input(step_id):
    return CUSTOM_INPUTS.get(step_id, DEFAULT_INPUTS.get(step_id))

def get_output(step_id):
    return CUSTOM_OUTPUTS.get(step_id, DEFAULT_OUTPUTS.get(step_id))

for step_id in DEFAULT_OUTPUTS:
    os.makedirs(get_output(step_id), exist_ok=True)

# ---------- Step Definitions ----------
STEPS = [
    {'id': 'fetch_convert', 'name': 'Fetch & Convert', 'script': None, 'env': 'fetch_env',
     'desc': 'Download SRA and convert to FASTQ', 'icon': 'fa-cloud-download-alt', 'color': '#3b82f6',
     'params': {
         'mirror': {'type': 'select', 'options': ['auto','ebi','ncbi'], 'default': 'auto', 'label': 'Mirror'},
         'max_size': {'type': 'text', 'default': '100G', 'label': 'Max Size'},
         'threads': {'type': 'number', 'default': 6, 'min': 1, 'max': 16, 'label': 'Threads'},
         'compress': {'type': 'select', 'options': ['gzip','pigz','none'], 'default': 'pigz', 'label': 'Compression'}
     }},
    {'id': 'qc', 'name': 'Quality Control', 'script': '01_quality_control.sh', 'env': 'qc_env',
     'desc': 'Trim reads, FastQC', 'icon': 'fa-microscope', 'color': '#ef4444',
     'params': {
         'qual_threshold': {'type': 'number', 'default': 20, 'min':1,'max':40, 'label':'Quality'},
         'min_length': {'type': 'number', 'default': 50, 'min':20,'max':100, 'label':'Min Length'},
         'unqual_percent': {'type': 'number', 'default': 40, 'min':1,'max':100, 'label':'Max Unqualified %'},
         'cut_front': {'type': 'number', 'default': 0, 'min':0,'max':50, 'label':'Cut Front'},
         'cut_tail': {'type': 'number', 'default': 0, 'min':0,'max':50, 'label':'Cut Tail'},
         'threads': {'type': 'number', 'default': 6, 'min':1,'max':32, 'label':'Threads'}
     }},
    {'id': 'assembly', 'name': 'Assembly', 'script': '02_assembly.sh', 'env': 'assembly_env',
     'desc': 'MEGAHIT assembly', 'icon': 'fa-project-diagram', 'color': '#f59e0b',
     'params': {
         'min_contig_len': {'type': 'number', 'default': 500, 'min':200,'max':10000, 'label':'Min Contig'},
         'k_min': {'type': 'number', 'default': 21, 'min':11,'max':127, 'label':'K-min'},
         'k_max': {'type': 'number', 'default': 141, 'min':21,'max':255, 'label':'K-max'},
         'k_step': {'type': 'number', 'default': 10, 'min':2,'max':28, 'label':'K-step'},
         'preset': {'type': 'select', 'options': ['meta-sensitive','meta-large','fast'], 'default':'meta-sensitive','label':'Preset'},
         'threads': {'type': 'number', 'default': 6, 'min':1,'max':32, 'label':'Threads'}
     }},
    {'id': 'binning', 'name': 'Binning', 'script': '03_binning.sh', 'env': 'binning_env',
     'desc': 'MetaBAT2 binning', 'icon': 'fa-object-group', 'color': '#10b981',
     'params': {
         'min_contig_len': {'type': 'number', 'default': 1500, 'min':1000,'max':10000, 'label':'Min Contig'},
         'min_bin_size': {'type': 'number', 'default': 200000, 'min':50000,'max':1000000, 'label':'Min Bin Size'},
         'max_edges': {'type': 'number', 'default': 200, 'min':50,'max':1000, 'label':'Max Edges'},
         'min_cv': {'type': 'number', 'default': 0, 'min':0,'max':10, 'label':'Min CV'},
         'threads': {'type': 'number', 'default': 6, 'min':1,'max':32, 'label':'Threads'}
     }},
    {'id': 'checkm2', 'name': 'CheckM2', 'script': '04_checkm2.sh', 'env': 'checkm2_env',
     'desc': 'Bin quality assessment', 'icon': 'fa-check-double', 'color': '#f97316',
     'params': {
         'completeness': {'type': 'number', 'default': 50, 'min':0,'max':100, 'label':'Min Completeness (%)'},
         'contamination': {'type': 'number', 'default': 10, 'min':0,'max':100, 'label':'Max Contamination (%)'},
         'threads': {'type': 'number', 'default': 6, 'min':1,'max':16, 'label':'Threads'}
     }},
    {'id': 'dfast_qc', 'name': 'DFAST‑QC Taxonomy', 'script': '04_dfast_qc.sh', 'env': 'dfast_qc_db_env',
     'desc': 'Taxonomic classification of bins', 'icon': 'fa-dna', 'color': '#10b981',
     'params': {
         'min_completeness': {'type': 'number', 'default': 50, 'min':0,'max':100, 'label':'Min Completeness'},
         'max_contamination': {'type': 'number', 'default': 10, 'min':0,'max':100, 'label':'Max Contamination'},
         'min_contig_len': {'type': 'number', 'default': 0, 'min':0,'max':10000, 'label':'Min Contig Len'},
         'threads': {'type': 'number', 'default': 6, 'min':1,'max':16, 'label':'Threads'}
     }},
    {'id': 'antismash', 'name': 'antiSMASH', 'script': '04_antismash.sh', 'env': 'antismash_env',
     'desc': 'BGC prediction', 'icon': 'fa-dna', 'color': '#22c55e',
     'params': {
         'taxon': {'type': 'select', 'options': ['bacteria','fungi'], 'default':'bacteria','label':'Taxon'},
         'min_length': {'type': 'number', 'default': 3000, 'min':1000,'max':10000, 'label':'Min BGC Length'},
         'genefinder': {'type': 'select', 'options': ['prodigal','glimmerhmm'], 'default':'prodigal','label':'Gene Finder'},
         'clusterblast': {'type': 'select', 'options': ['loose','strict'], 'default':'loose','label':'ClusterBlast'},
         'hmmer_strictness': {'type': 'select', 'options': ['strict','relaxed'], 'default':'strict','label':'HMM Strictness'},
         'threads': {'type': 'number', 'default': 6, 'min':1,'max':32, 'label':'Threads'}
     }},
    # ========== DEEP BGC (with automatic summary & HTML report) ==========
    {'id': 'deepbgc', 'name': 'DeepBGC', 'script': '05_deepbgc.sh', 'env': 'deepbgc_env',
     'desc': 'Deep learning BGC detection', 'icon': 'fa-brain', 'color': '#a855f7',
     'params': {
         'score_threshold': {'type': 'number', 'default': 0.5, 'min':0.0,'max':1.0,'step':0.1,'label':'Score'},
         'prodigal_mode': {'type': 'select', 'options': ['meta','single'], 'default':'meta','label':'Prodigal Mode'},
         'min_nucl_length': {'type': 'number', 'default': 3000, 'min':1000,'max':10000, 'label':'Min Length'},
         'merge_gap': {'type': 'number', 'default': 0, 'min':0,'max':10000, 'label':'Merge Gap'},
         'detector': {'type': 'select', 'options': ['deepbgc','clusterfinder'], 'default':'deepbgc','label':'Detector'}
     }},
    {'id': 'compare', 'name': 'Comparison', 'script': '06_compare.sh', 'env': 'viz_env',
     'desc': 'Compare antiSMASH & DeepBGC', 'icon': 'fa-chart-bar', 'color': '#06b6d4',
     'params': {
         'format': {'type': 'select', 'options': ['png','pdf','svg'], 'default':'png','label':'Format'},
         'dpi': {'type': 'number', 'default': 300, 'min':72,'max':600, 'label':'DPI'},
         'theme': {'type': 'select', 'options': ['whitegrid','darkgrid','white','dark'], 'default':'whitegrid','label':'Theme'},
         'min_genes': {'type': 'number', 'default': 1, 'min':1,'max':20, 'label':'Min Genes'},
         'title': {'type': 'text', 'default': 'BGC Analysis', 'label':'Title'}
     }},
    {'id': 'bigscape', 'name': 'BiG-SCAPE', 'script': '07_bigscape.sh', 'env': 'bigscape_py311',
     'desc': 'Gene cluster networking', 'icon': 'fa-network-wired', 'color': '#3b82f6',
     'params': {
         'cutoffs': {'type': 'text', 'default': '0.30,0.50', 'label':'GCF Cutoffs'},
         'min_length': {'type': 'number', 'default': 2000, 'min':1000,'max':10000, 'label':'Min BGC Length'},
         'clan_cutoff': {'type': 'number', 'default': 0.30, 'min':0.0,'max':1.0,'step':0.05, 'label':'Clan Cutoff'},
         'include_singletons': {'type': 'checkbox', 'default': True, 'label':'Include Singletons'},
         'mix_classes': {'type': 'checkbox', 'default': True, 'label':'Mix Classes'},
         'threads': {'type': 'number', 'default': 6, 'min':1,'max':16, 'label':'Threads'}
     }}
]

# ---------- Pipeline State ----------
class PipelineState:
    def __init__(self):
        self.running = False
        self.current_step = None
        self.current_sample = None
        self.step_status = {i: 'idle' for i in range(len(STEPS))}
        self.step_progress = {i: 0 for i in range(len(STEPS))}
        self.step_pid = None
        self.stop_requested = False
        self.history = []
        self.samples = []
        self.params = {}
        self.run_all_stop = False

pipeline_state = PipelineState()

# ---------- Helper Functions ----------
def check_input_availability(step_idx):
    step = STEPS[step_idx]
    if step['id'] == 'fetch_convert':
        return {'available': True, 'message': 'SRA IDs needed (entered in UI)'}
    in_dir = get_input(step['id'])
    if in_dir is None:
        return {'available': True, 'message': 'No input required'}
    if not os.path.exists(in_dir):
        return {'available': False, 'message': f"Directory missing: {in_dir}"}
    if not os.listdir(in_dir):
        return {'available': False, 'message': f"Directory empty: {in_dir}"}
    return {'available': True, 'message': 'Input ready'}

def build_command(step_idx, params, samples):
    step = STEPS[step_idx]
    step_params = params.get(step['id'], {})
    threads = step_params.get('threads', 6)
    out_dir = get_output(step['id'])

    if step['id'] == 'fetch_convert':
        if not samples:
            return None
        cmds = []
        for sra in samples:
            download_cmd = f"bash {SCRIPT_DIR}/00_a_download.sh {out_dir} {sra}"
            convert_cmd = f"bash {SCRIPT_DIR}/00_b_convert.sh {out_dir} {sra}"
            cmds.append(f"{download_cmd} && {convert_cmd}")
        return ' && '.join(cmds)

    elif step['id'] == 'qc':
        in_dir = get_input('qc')
        env = (f"export QC_QUAL={step_params.get('qual_threshold',20)} "
               f"QC_LEN={step_params.get('min_length',50)} "
               f"QC_UNQUAL={step_params.get('unqual_percent',40)} "
               f"QC_FRONT={step_params.get('cut_front',0)} "
               f"QC_TAIL={step_params.get('cut_tail',0)}")
        return f"{env} && bash {SCRIPT_DIR}/{step['script']} {in_dir} {out_dir} {threads}"

    elif step['id'] == 'assembly':
        in_dir = get_input('assembly')
        env = (f"export ASM_MIN={step_params.get('min_contig_len',500)} "
               f"ASM_KMIN={step_params.get('k_min',21)} "
               f"ASM_KMAX={step_params.get('k_max',141)} "
               f"ASM_KSTEP={step_params.get('k_step',10)} "
               f"ASM_PRESET={step_params.get('preset','meta-sensitive')}")
        return f"{env} && bash {SCRIPT_DIR}/{step['script']} {in_dir} {out_dir} {threads}"

    elif step['id'] == 'binning':
        in_dir = get_input('binning')
        reads_dir = get_output('qc') + '/clean_reads'
        env = (f"export BIN_MIN_LEN={step_params.get('min_contig_len',1500)} "
               f"BIN_MIN_SIZE={step_params.get('min_bin_size',200000)} "
               f"BIN_MAX_EDGES={step_params.get('max_edges',200)} "
               f"BIN_MIN_CV={step_params.get('min_cv',0)}")
        return f"{env} && bash {SCRIPT_DIR}/{step['script']} {in_dir} {reads_dir} {out_dir} {threads}"

    elif step['id'] == 'checkm2':
        in_dir = get_input('checkm2')
        env = (f"export CHECKM2_COMPLETENESS={step_params.get('completeness',50)} "
               f"CHECKM2_CONTAMINATION={step_params.get('contamination',10)}")
        return f"{env} && bash {SCRIPT_DIR}/{step['script']} {in_dir} {out_dir} {threads}"

    elif step['id'] == 'dfast_qc':
        in_dir = get_input('dfast_qc')
        env = (f"export DFAST_MIN_COMPLETENESS={step_params.get('min_completeness',50)} "
               f"DFAST_MAX_CONTAMINATION={step_params.get('max_contamination',10)} "
               f"DFAST_MIN_CONTIG_LEN={step_params.get('min_contig_len',0)}")
        return f"{env} && bash {SCRIPT_DIR}/{step['script']} {in_dir} {out_dir} {threads}"

    elif step['id'] == 'antismash':
        in_dir = get_input('antismash')
        assembly_dir = get_output('assembly')
        env = (f"export AS_TAXON={step_params.get('taxon','bacteria')} "
               f"AS_MINLEN={step_params.get('min_length',3000)} "
               f"AS_GENEFINDER={step_params.get('genefinder','prodigal')} "
               f"AS_CB={step_params.get('clusterblast','loose')} "
               f"AS_HMMER={step_params.get('hmmer_strictness','strict')}")
        return f"{env} && bash {SCRIPT_DIR}/{step['script']} {in_dir} {out_dir} {threads} {assembly_dir}"

    elif step['id'] == 'deepbgc':
        # Main DeepBGC script
        env = (f"export PROJ_OUT={RESULTS_DIR} "
               f"DEEP_SCORE={step_params.get('score_threshold',0.5)} "
               f"DEEP_PRODIGAL={step_params.get('prodigal_mode','meta')} "
               f"DEEP_MIN_LEN={step_params.get('min_nucl_length',3000)} "
               f"DEEP_MERGE={step_params.get('merge_gap',0)} "
               f"DEEP_DETECTOR={step_params.get('detector','deepbgc')}")
        main_cmd = f"{env} && bash {SCRIPT_DIR}/{step['script']}"

        # Aggregation script – outputs to a subfolder "deepbgc_evaluation"
        eval_dir = os.path.join(get_output('deepbgc'), 'deepbgc_evaluation')
        # Ensure directory exists
        os.makedirs(eval_dir, exist_ok=True)
        summary_cmd = f"bash {SCRIPT_DIR}/05_deepbgc_summary_final.sh {get_output('deepbgc')} {eval_dir}"

        # HTML report generator – reads from the evaluation folder
        # (We have modified generate_deepbgc_report.py to accept the input directory as argument)
        report_cmd = f"python3 {SCRIPT_DIR}/generate_deepbgc_report.py {eval_dir}"

        # Chain them: main succeeds → summary → report
        return f"{main_cmd} && {summary_cmd} && {report_cmd}"

    elif step['id'] == 'compare':
        anti_dir = get_output('antismash')
        deep_dir = get_output('deepbgc')
        env = (f"export VIZ_FMT={step_params.get('format','png')} "
               f"VIZ_DPI={step_params.get('dpi',300)} "
               f"VIZ_THEME={step_params.get('theme','whitegrid')} "
               f"VIZ_MIN_GENES={step_params.get('min_genes',1)} "
               f"VIZ_TITLE='{step_params.get('title','BGC Analysis')}'")
        return f"{env} && bash {SCRIPT_DIR}/{step['script']} {anti_dir} {deep_dir} {out_dir}"

    elif step['id'] == 'bigscape':
        env = (f"export PROJ_OUT={RESULTS_DIR} "
               f"BIG_CUTOFFS={step_params.get('cutoffs','0.30,0.50')} "
               f"BIG_MIN_LEN={step_params.get('min_length',2000)} "
               f"BIG_CLAN={step_params.get('clan_cutoff',0.30)} "
               f"BIG_SINGLE={'--include_singletons' if step_params.get('include_singletons',True) else ''} "
               f"BIG_MIX={'--mix' if step_params.get('mix_classes',True) else ''}")
        return f"{env} && bash {SCRIPT_DIR}/{step['script']}"

    return None

def terminate_process(process):
    """Forcefully kill the process group."""
    try:
        pgid = os.getpgid(process.pid)
        # Send SIGTERM to the whole group
        os.killpg(pgid, signal.SIGTERM)
        # Wait a moment, then SIGKILL if still alive
        time.sleep(1)
        if process.poll() is None:
            os.killpg(pgid, signal.SIGKILL)
    except Exception as e:
        print(f"Error terminating process: {e}")

def run_command(cmd, step_idx):
    step = STEPS[step_idx]
    log_file = os.path.join(LOG_DIR, f"step_{step_idx}.log")

    def emit_log(line, level='info'):
        socketio.emit('log_line', {
            'step': step_idx,
            'time': datetime.now().strftime('%H:%M:%S'),
            'level': level,
            'message': line
        })

    emit_log(f"Starting {step['name']}...", 'info')
    pipeline_state.step_status[step_idx] = 'running'
    pipeline_state.step_progress[step_idx] = 0
    pipeline_state.current_step = step_idx
    pipeline_state.current_sample = None

    socketio.emit('current_step', {
        'step_idx': step_idx,
        'step_name': step['name'],
        'icon': step['icon'],
        'color': step['color']
    })

    socketio.emit('status_update', {
        'step': step_idx,
        'status': 'running',
        'progress': 0,
        'output_dir': get_output(step['id'])
    })

    conda_base = os.path.expanduser('~/miniconda3')
    if step['env'] == 'base':
        activate = f"source {conda_base}/etc/profile.d/conda.sh && conda activate base"
    else:
        env_path = os.path.join(BASE_DIR, 'envs', step['env'])
        activate = f"source {conda_base}/etc/profile.d/conda.sh && conda activate {env_path}"
    full_cmd = f"{activate} && {cmd}"
    emit_log(f"Full command: {full_cmd}", 'debug')

    with open(log_file, 'w') as f:
        process = subprocess.Popen(
            full_cmd,
            shell=True,
            executable='/bin/bash',
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            preexec_fn=os.setsid   # Create a new session so we can kill the whole process group
        )
        pipeline_state.step_pid = process.pid

        if pipeline_state.samples:
            pipeline_state.current_sample = pipeline_state.samples[0]
            socketio.emit('current_sample', {'sample': pipeline_state.current_sample})

        for line in iter(process.stdout.readline, ''):
            # Check for stop request **before** processing each line
            if pipeline_state.stop_requested or pipeline_state.run_all_stop:
                emit_log("Stop requested, terminating...", 'warning')
                terminate_process(process)
                break
            line = line.strip()
            if line:
                f.write(line + '\n')
                f.flush()
                emit_log(line)
                lower = line.lower()
                if 'sample' in lower and ':' in lower:
                    parts = line.split()
                    for i, p in enumerate(parts):
                        if p.lower() == 'sample' and i+1 < len(parts):
                            candidate = parts[i+1].strip(':,;')
                            if candidate:
                                pipeline_state.current_sample = candidate
                                socketio.emit('current_sample', {'sample': candidate})
                if 'complete' in line.lower() or 'done' in line.lower():
                    prog = min(100, pipeline_state.step_progress[step_idx] + 5)
                    pipeline_state.step_progress[step_idx] = prog
                    socketio.emit('progress', {'step': step_idx, 'progress': prog})
        process.wait()

    if pipeline_state.stop_requested or pipeline_state.run_all_stop:
        pipeline_state.step_status[step_idx] = 'idle'
        pipeline_state.step_progress[step_idx] = 0
        emit_log("⏹ Step stopped by user", 'warning')
        socketio.emit('status_update', {'step': step_idx, 'status': 'idle', 'progress': 0})
    elif process.returncode == 0:
        pipeline_state.step_status[step_idx] = 'complete'
        pipeline_state.step_progress[step_idx] = 100
        emit_log(f"✓ {step['name']} completed", 'success')
        socketio.emit('status_update', {'step': step_idx, 'status': 'complete', 'progress': 100})
    else:
        pipeline_state.step_status[step_idx] = 'error'
        emit_log(f"✗ {step['name']} failed with exit code {process.returncode}", 'error')
        socketio.emit('status_update', {'step': step_idx, 'status': 'error'})

    pipeline_state.current_step = None
    pipeline_state.current_sample = None
    pipeline_state.step_pid = None
    pipeline_state.stop_requested = False
    socketio.emit('current_step', None)
    socketio.emit('current_sample', None)

def step_worker(step_idx, samples, params):
    pipeline_state.samples = samples
    check = check_input_availability(step_idx)
    if not check['available']:
        socketio.emit('log_line', {
            'step': step_idx,
            'time': datetime.now().strftime('%H:%M:%S'),
            'level': 'error',
            'message': f"Cannot run: {check['message']}"
        })
        pipeline_state.step_status[step_idx] = 'error'
        pipeline_state.running = False
        return

    cmd = build_command(step_idx, params, samples)
    if not cmd:
        socketio.emit('log_line', {
            'step': step_idx,
            'time': datetime.now().strftime('%H:%M:%S'),
            'level': 'error',
            'message': "Failed to build command (check input files)"
        })
        pipeline_state.step_status[step_idx] = 'error'
        pipeline_state.running = False
        return

    pipeline_state.running = True
    run_command(cmd, step_idx)
    pipeline_state.running = False
    pipeline_state.history.append({
        'step': STEPS[step_idx]['name'],
        'status': pipeline_state.step_status[step_idx],
        'time': datetime.now().strftime('%H:%M:%S')
    })
    socketio.emit('history_update', pipeline_state.history)

# ---------- Routes ----------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/steps')
def get_steps():
    out = []
    for s in STEPS:
        out.append({
            'id': s['id'],
            'name': s['name'],
            'desc': s['desc'],
            'icon': s['icon'],
            'color': s['color'],
            'input': get_input(s['id']),
            'output': get_output(s['id']),
            'has_input': get_input(s['id']) is not None
        })
    return jsonify(out)

@app.route('/api/params/<int:step_idx>')
def get_params(step_idx):
    if 0 <= step_idx < len(STEPS):
        return jsonify(STEPS[step_idx]['params'])
    return jsonify({})

@app.route('/api/status')
def get_status():
    return jsonify({
        'running': pipeline_state.running,
        'current_step': pipeline_state.current_step,
        'current_sample': pipeline_state.current_sample,
        'step_status': pipeline_state.step_status,
        'step_progress': pipeline_state.step_progress,
        'history': pipeline_state.history[-10:]
    })

@app.route('/api/samples')
def list_samples():
    samples = set()
    for f in glob.glob(os.path.join(DATA_DIR, "*.fastq*")):
        base = os.path.basename(f)
        if '_1.fastq' in base or '_2.fastq' in base:
            samp = base.replace('_1.fastq.gz','').replace('_2.fastq.gz','').replace('.fastq.gz','')
            samples.add(samp)
    return jsonify(sorted(samples))

@app.route('/api/check_input/<int:step_idx>')
def check_input_route(step_idx):
    return jsonify(check_input_availability(step_idx))

@app.route('/api/run', methods=['POST'])
def run_step():
    data = request.json
    step_idx = data['step_idx']
    samples = data.get('samples', [])
    params = data.get('params', {})
    if pipeline_state.running:
        return jsonify({'error': 'Another step is already running'}), 409
    pipeline_state.params = params
    pipeline_state.run_all_stop = False
    thread = threading.Thread(target=step_worker, args=(step_idx, samples, params))
    thread.daemon = True
    thread.start()
    return jsonify({'status': 'started'})

@app.route('/api/run_all', methods=['POST'])
def run_all():
    data = request.json
    samples = data.get('samples', [])
    params = data.get('params', {})
    if pipeline_state.running:
        return jsonify({'error': 'Pipeline already running'}), 409

    def sequence():
        pipeline_state.run_all_stop = False
        for i in range(len(STEPS)):
            if pipeline_state.run_all_stop:
                socketio.emit('log_line', {
                    'step': i,
                    'time': datetime.now().strftime('%H:%M:%S'),
                    'level': 'warning',
                    'message': "Run-all stopped by user"
                })
                break
            check = check_input_availability(i)
            if not check['available']:
                socketio.emit('log_line', {
                    'step': i,
                    'time': datetime.now().strftime('%H:%M:%S'),
                    'level': 'error',
                    'message': f"Skipping {STEPS[i]['name']}: {check['message']}"
                })
                continue
            pipeline_state.running = True
            step_worker(i, samples, params)
            time.sleep(2)
        pipeline_state.running = False
        pipeline_state.run_all_stop = False

    thread = threading.Thread(target=sequence)
    thread.daemon = True
    thread.start()
    return jsonify({'status': 'started'})

@app.route('/api/stop', methods=['POST'])
def stop():
    pipeline_state.stop_requested = True
    pipeline_state.run_all_stop = True
    return jsonify({'status': 'stopping'})

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    filename = secure_filename(file.filename)
    save_path = os.path.join(DATA_DIR, filename)
    file.save(save_path)
    return jsonify({'status': 'ok', 'filename': filename})

@app.route('/api/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        data = request.json
        global CUSTOM_INPUTS, CUSTOM_OUTPUTS
        CUSTOM_INPUTS = data.get('inputs', {})
        CUSTOM_OUTPUTS = data.get('outputs', {})
        save_config()
        return jsonify({'status': 'ok'})
    else:
        return jsonify({
            'inputs': {k: get_input(k) for k in DEFAULT_INPUTS},
            'outputs': {k: get_output(k) for k in DEFAULT_OUTPUTS}
        })

@app.route('/api/results_tree')
def results_tree():
    def build_tree(path, depth=0, max_depth=4):
        if depth >= max_depth or not os.path.exists(path):
            return None
        items = []
        try:
            for f in sorted(os.listdir(path)):
                full = os.path.join(path, f)
                if os.path.isdir(full):
                    children = build_tree(full, depth+1, max_depth)
                    items.append({'name': f, 'type': 'dir', 'children': children})
                else:
                    items.append({'name': f, 'type': 'file'})
        except PermissionError:
            pass
        return items
    return jsonify(build_tree(RESULTS_DIR, max_depth=4))

@app.route('/api/system')
def system_stats():
    cpu = psutil.cpu_percent()
    mem = psutil.virtual_memory().percent
    disk = psutil.disk_usage(RESULTS_DIR).percent
    net = psutil.net_io_counters()
    return jsonify({
        'cpu': cpu,
        'memory': mem,
        'disk': disk,
        'net_sent': net.bytes_sent / 1024**2,
        'net_recv': net.bytes_recv / 1024**2
    })

if __name__ == '__main__':
    print("""
╔══════════════════════════════════════════════════════════════╗
║                    META BGC - WEB INTERFACE                  ║
║          (with CheckM2 + DFAST‑QC Taxonomy)                   ║
╠══════════════════════════════════════════════════════════════╣
║  • Step 0: Fetch & Convert                                   ║
║  • Steps 1‑9: QC, Assembly, Binning, CheckM2, DFAST‑QC,     ║
║              antiSMASH, DeepBGC, Comparison, BiG-SCAPE       ║
║  • DeepBGC now includes automatic summary & HTML report      ║
║  • Real‑time step & sample display                           ║
║  • Immediate stop on request (SIGTERM + SIGKILL)             ║
╠══════════════════════════════════════════════════════════════╣
║  Access: http://localhost:5000                               ║
╚══════════════════════════════════════════════════════════════╝
    """)
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)