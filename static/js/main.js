// Initialize particles
particlesJS.load('particles-js', '/static/particles.json', () => console.log('Particles loaded'));

const socket = io();
let steps = [];
let stepParams = {};
let samples = [];
let running = false;
let currentStepIdx = null;

// Load steps
async function loadSteps() {
    const res = await fetch('/api/steps');
    steps = await res.json();
    renderSteps();
}

function renderSteps() {
    const grid = document.getElementById('steps-grid');
    grid.innerHTML = steps.map((step, idx) => `
        <div class="step-card" id="step-card-${idx}" onclick="selectStep(${idx})">
            <div class="step-header">
                <div class="step-icon" style="background:${step.color}"><i class="fas ${step.icon}"></i></div>
                <span class="step-number">Step ${idx+1}</span>
            </div>
            <div class="step-title">${step.name}</div>
            <div class="step-desc">${step.desc}</div>
            <div class="step-status" id="status-${idx}"><i class="fas fa-circle"></i> Ready</div>
            <div class="progress-bar" id="progress-bar-${idx}" style="display:none;">
                <div class="progress-fill" id="progress-${idx}" style="width:0%"></div>
            </div>
            <div class="step-actions">
                <button class="btn-run" onclick="runStep(${idx}); event.stopPropagation();" id="run-btn-${idx}">Run</button>
                <button class="btn-config" onclick="openParams(${idx}); event.stopPropagation();"><i class="fas fa-cog"></i></button>
            </div>
        </div>
    `).join('');
}

// Sample management
function switchTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
    document.getElementById('sra-panel').style.display = tab === 'sra' ? 'block' : 'none';
    document.getElementById('local-panel').style.display = tab === 'local' ? 'block' : 'none';
}

function addSamples() {
    const input = document.getElementById('sra-input');
    const ids = input.value.trim().split(/\s+/).filter(id => /^SRR\d+$/i.test(id));
    if (!ids.length) { alert('Enter valid SRA IDs'); return; }
    ids.forEach(id => { if (!samples.includes(id)) { samples.push(id); renderSample(id); } });
    input.value = '';
}

function renderSample(id) {
    const container = document.getElementById('samples-container');
    if (samples.length === 1) container.innerHTML = '';
    const chip = document.createElement('div');
    chip.className = 'sample-chip';
    chip.innerHTML = `<i class="fas fa-vial"></i> ${id} <button onclick="removeSample('${id}')"><i class="fas fa-times"></i></button>`;
    container.appendChild(chip);
}

function removeSample(id) {
    samples = samples.filter(s => s !== id);
    document.querySelectorAll('.sample-chip').forEach(c => { if (c.innerText.includes(id)) c.remove(); });
    if (!samples.length) document.getElementById('samples-container').innerHTML = '<div class="empty-state">No samples</div>';
}

async function uploadLocal() {
    const files = document.getElementById('local-files').files;
    for (let f of files) {
        const fd = new FormData(); fd.append('file', f);
        const res = await fetch('/api/upload', { method:'POST', body:fd });
        if (res.ok) addLog('system','success',`Uploaded ${f.name}`);
    }
    loadSamples();
}

async function loadSamples() {
    const res = await fetch('/api/samples');
    const list = await res.json();
    document.getElementById('samples-container').innerHTML = list.map(s => 
        `<div class="sample-chip"><i class="fas fa-vial"></i> ${s} <button onclick="removeSample('${s}')"><i class="fas fa-times"></i></button></div>`
    ).join('');
    samples = list;
}

// Step execution
async function runStep(idx) {
    if (running) { alert('Already running'); return; }
    const check = await fetch(`/api/check_input/${idx}`).then(r=>r.json());
    if (!check.available && !confirm(`Warning: ${check.message}\nContinue?`)) return;

    running = true; currentStepIdx = idx; updateUIState();
    const step = steps[idx];
    const params = stepParams[step.id] || {};
    await fetch('/api/run', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ step_idx: idx, samples, params })
    });
}

async function runAll() {
    if (!samples.length) { alert('Add samples first'); return; }
    if (!confirm('Run all steps?')) return;
    running = true; updateUIState();
    await fetch('/api/run_all', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ samples, params: stepParams })
    });
}

async function stopPipeline() {
    if (!confirm('Stop?')) return;
    await fetch('/api/stop', {method:'POST'});
}

// Parameters
async function openParams(idx) {
    const step = steps[idx];
    document.getElementById('param-title').innerText = `${step.name} Parameters`;
    const res = await fetch(`/api/params/${idx}`);
    const paramDefs = await res.json();
    const body = document.getElementById('param-body');
    body.innerHTML = Object.entries(paramDefs).map(([k,def]) => `
        <div class="param-group">
            <label class="param-label">${def.label}</label>
            ${renderParamInput(k, def, step.id)}
        </div>
    `).join('');
    document.getElementById('param-modal').dataset.stepIdx = idx;
    openModal('param-modal');
}

function renderParamInput(key, def, stepId) {
    const val = stepParams[stepId]?.[key] ?? def.default;
    if (def.type === 'select') {
        return `<select class="param-input" id="param-${key}" data-key="${key}">${def.options.map(o => `<option ${o==val?'selected':''}>${o}</option>`).join('')}</select>`;
    } else if (def.type === 'checkbox') {
        return `<label><input type="checkbox" class="param-input" id="param-${key}" data-key="${key}" ${val?'checked':''}> Enable</label>`;
    } else if (def.type === 'number') {
        return `<input type="number" class="param-input" id="param-${key}" value="${val}" min="${def.min}" max="${def.max}" step="${def.step||1}">`;
    } else {
        return `<input type="text" class="param-input" id="param-${key}" value="${val}">`;
    }
}

function saveParams() {
    const modal = document.getElementById('param-modal');
    const stepIdx = modal.dataset.stepIdx;
    const stepId = steps[stepIdx].id;
    const inputs = modal.querySelectorAll('.param-input');
    const params = {};
    inputs.forEach(inp => {
        let val = inp.type==='checkbox' ? inp.checked : inp.value;
        if (inp.type==='number') val = parseFloat(val);
        params[inp.dataset.key] = val;
    });
    stepParams[stepId] = params;
    closeModal('param-modal');
    addLog('system','info',`Params saved for ${steps[stepIdx].name}`);
}

// Settings
async function openSettings() {
    const res = await fetch('/api/settings');
    const data = await res.json();
    const body = document.getElementById('settings-body');
    body.innerHTML = steps.map(step => `
        <div class="io-group">
            <div class="io-group-header"><i class="fas ${step.icon}" style="color:${step.color}"></i> ${step.name}</div>
            <div class="io-row">
                ${step.has_input ? `
                <div>
                    <div class="io-label">Input</div>
                    <input type="text" class="io-input" id="input-${step.id}" value="${data.inputs[step.id] || ''}" placeholder="${step.input}">
                    <div class="io-default">Default: ${step.input}</div>
                </div>` : '<div></div>'}
                <div>
                    <div class="io-label">Output</div>
                    <input type="text" class="io-input" id="output-${step.id}" value="${data.outputs[step.id] || ''}" placeholder="${step.output}">
                    <div class="io-default">Default: ${step.output}</div>
                </div>
            </div>
        </div>
    `).join('');
    openModal('settings-modal');
}

async function saveSettings() {
    const inputs = {};
    const outputs = {};
    steps.forEach(step => {
        const inp = document.getElementById(`input-${step.id}`);
        if (inp && inp.value.trim()) inputs[step.id] = inp.value.trim();
        const out = document.getElementById(`output-${step.id}`);
        if (out && out.value.trim()) outputs[step.id] = out.value.trim();
    });
    await fetch('/api/settings', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ inputs, outputs })
    });
    closeModal('settings-modal');
    loadSteps(); // refresh paths
    addLog('system','success','Settings saved');
}

function resetToDefaults() {
    if (!confirm('Reset all paths to defaults?')) return;
    steps.forEach(step => {
        const inp = document.getElementById(`input-${step.id}`);
        if (inp) inp.value = '';
        const out = document.getElementById(`output-${step.id}`);
        if (out) out.value = '';
    });
}

// Results
async function loadResults() {
    const res = await fetch('/api/results_tree');
    const tree = await res.json();
    const container = document.getElementById('results-body');
    container.innerHTML = renderTree(tree);
}

function renderTree(nodes) {
    if (!nodes || !nodes.length) return '<div class="empty-state">No results</div>';
    return nodes.map(n => {
        if (n.type === 'dir') {
            return `<div class="tree-item"><span class="tree-folder">📁 ${n.name}</span>${n.children ? renderTree(n.children) : ''}</div>`;
        } else {
            return `<div class="tree-item"><span class="tree-file">📄 ${n.name}</span></div>`;
        }
    }).join('');
}

// System stats
async function updateStats() {
    const res = await fetch('/api/system');
    const stats = await res.json();
    document.getElementById('cpu-val').innerText = Math.round(stats.cpu) + '%';
    document.getElementById('cpu-bar').style.width = stats.cpu + '%';
    document.getElementById('mem-val').innerText = Math.round(stats.memory) + '%';
    document.getElementById('mem-bar').style.width = stats.memory + '%';
    document.getElementById('disk-val').innerText = Math.round(stats.disk) + '%';
    document.getElementById('disk-bar').style.width = stats.disk + '%';
    document.getElementById('net-val').innerText = (stats.net_sent + stats.net_recv).toFixed(1);
}

// Logging
function addLog(source, level, message) {
    const time = new Date().toLocaleTimeString();
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.innerHTML = `<span class="log-time">[${time}]</span><span class="log-level ${level}">${level}</span><span class="log-message">${escapeHtml(message)}</span>`;
    document.getElementById('terminal-body').appendChild(entry);
    entry.scrollIntoView();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function clearLogs() { document.getElementById('terminal-body').innerHTML = ''; }
function downloadLogs() {
    const logs = Array.from(document.querySelectorAll('.log-entry')).map(e => e.textContent).join('\n');
    const blob = new Blob([logs], {type:'text/plain'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `meta_bgc_${new Date().toISOString().slice(0,10)}.log`; a.click();
}

// Modal helpers
function openModal(id) { document.getElementById(id).classList.add('active'); }
function closeModal(id) { document.getElementById(id).classList.remove('active'); }

// UI state
function updateUIState() {
    document.getElementById('stop-btn').disabled = !running;
    document.getElementById('run-all-btn').disabled = running;
    document.getElementById('status-dot').className = running ? 'status-dot running' : 'status-dot';
    document.getElementById('status-text').innerText = running ? 'Running...' : 'Ready';
    steps.forEach((_,i) => {
        const btn = document.getElementById(`run-btn-${i}`);
        if (btn) btn.disabled = running;
    });
}

// Socket listeners
socket.on('log_line', (data) => {
    addLog(data.step, data.level, data.message);
    if (data.step !== undefined && steps[data.step]) document.getElementById('current-op').innerText = steps[data.step].name;
});
socket.on('status_update', (data) => {
    const statusEl = document.getElementById(`status-${data.step}`);
    const card = document.getElementById(`step-card-${data.step}`);
    const progBar = document.getElementById(`progress-bar-${data.step}`);
    if (statusEl) {
        const icons = { running:'<i class="fas fa-spinner fa-spin"></i> Running', complete:'<i class="fas fa-check"></i> Complete', error:'<i class="fas fa-exclamation"></i> Error', idle:'<i class="fas fa-circle"></i> Ready' };
        statusEl.innerHTML = icons[data.status] || data.status;
        card.className = `step-card ${data.status}`;
    }
    if (data.status === 'running') {
        progBar.style.display = 'block';
        running = true; currentStepIdx = data.step;
    } else {
        progBar.style.display = 'none';
        if (currentStepIdx === data.step) { running = false; currentStepIdx = null; }
    }
    updateUIState();
});
socket.on('progress', (data) => {
    const fill = document.getElementById(`progress-${data.step}`);
    if (fill) fill.style.width = data.progress + '%';
});
socket.on('history_update', (history) => {
    const list = document.getElementById('history-list');
    list.innerHTML = history.slice(-10).map(h => 
        `<div style="display:flex; justify-content:space-between; padding:0.5rem; border-bottom:1px solid var(--border);">
            <span><i class="fas fa-${h.status==='complete'?'check-circle':'exclamation-circle'}" style="color:${h.status==='complete'?'var(--success)':'var(--danger)'}"></i> ${h.step}</span>
            <span style="color:var(--text-light);">${h.time}</span>
        </div>`
    ).join('');
});

// NEW: Listen for current step and sample updates
socket.on('current_step', (data) => {
    const stepDisplay = document.getElementById('current-op');
    if (data && data.step_name) {
        stepDisplay.innerHTML = `<i class="fas ${data.icon}" style="color:${data.color}"></i> ${data.step_name}`;
    } else {
        stepDisplay.innerHTML = '';
    }
});

socket.on('current_sample', (data) => {
    let sampleBadge = document.getElementById('current-sample');
    if (!sampleBadge) {
        // Create badge if not exists
        sampleBadge = document.createElement('span');
        sampleBadge.id = 'current-sample';
        sampleBadge.className = 'badge bg-info ms-3';
        document.querySelector('.status-badge').appendChild(sampleBadge);
    }
    if (data && data.sample) {
        sampleBadge.innerHTML = `<i class="fas fa-vial"></i> Sample: ${data.sample}`;
        sampleBadge.style.display = 'inline-block';
    } else {
        sampleBadge.style.display = 'none';
    }
});

// Initialize
window.onload = async () => {
    await loadSteps();
    await loadSamples();
    setInterval(updateStats, 2000);
};

// Expose globals
window.switchTab = switchTab;
window.addSamples = addSamples;
window.removeSample = removeSample;
window.uploadLocal = uploadLocal;
window.runStep = runStep;
window.runAll = runAll;
window.stopPipeline = stopPipeline;
window.openParams = openParams;
window.saveParams = saveParams;
window.openSettings = openSettings;
window.saveSettings = saveSettings;
window.resetToDefaults = resetToDefaults;
window.openModal = openModal;
window.closeModal = closeModal;
window.loadResults = loadResults;
window.clearLogs = clearLogs;
window.downloadLogs = downloadLogs;
window.checkAllInputs = async () => {
    let msg = '';
    for (let i=0; i<steps.length; i++) {
        const check = await fetch(`/api/check_input/${i}`).then(r=>r.json());
        msg += `${steps[i].name}: ${check.available ? '✓' : '✗'} ${check.message}\n`;
    }
    alert(msg);
};
window.resetAll = () => { if (confirm('Reset all steps?')) window.location.reload(); };
