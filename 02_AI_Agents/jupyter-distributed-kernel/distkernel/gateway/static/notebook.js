// DistKernel Notebook — Wallet Auth + AI Agents + Distributed Compute
// Part 1: State and Wallet Auth

let ws = null, sessionId = '', cells = [], workers = [], users = [];
let cellCounter = 0, pendingCells = {}, authToken = '', walletAddr = '';
let agentRunning = false, ollamaModels = [];
const WS_URL = 'ws://' + location.host + '/ws';
const LANGUAGE_OPTIONS = {
  python: ['python'],
  terminal: ['bash', 'zsh', 'sh'],
  markdown: ['markdown', 'md'],
};

// ── Wallet Auth ───────────────────────────
async function connectWallet() {
  const btn = document.getElementById('btn-connect');
  const status = document.getElementById('login-status');
  const addrEl = document.getElementById('wallet-addr');
  if (!window.ethereum) {
    document.getElementById('no-metamask').style.display = 'block';
    return;
  }
  btn.disabled = true;
  status.textContent = 'Connecting to MetaMask...';
  status.className = 'login-status';
  try {
    const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
    walletAddr = accounts[0];
    addrEl.textContent = walletAddr;
    status.textContent = 'Requesting challenge...';
    const chalResp = await fetch('/api/auth/challenge', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ address: walletAddr }),
    });
    const chal = await chalResp.json();
    if (!chal.nonce) throw new Error(chal.error || 'Challenge failed');
    status.textContent = 'Sign the message in MetaMask...';
    const signature = await window.ethereum.request({
      method: 'personal_sign',
      params: [chal.message, walletAddr],
    });
    status.textContent = 'Verifying...';
    const verResp = await fetch('/api/auth/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ address: walletAddr, nonce: chal.nonce, signature }),
    });
    const ver = await verResp.json();
    if (!ver.success) throw new Error(ver.error || 'Verification failed');
    authToken = ver.token;
    status.textContent = 'Authenticated!';
    status.className = 'login-status';
    setTimeout(enterApp, 500);
  } catch (err) {
    status.textContent = err.message || 'Connection failed';
    status.className = 'login-status login-error';
    btn.disabled = false;
  }
}

function enterApp() {
  document.getElementById('login-screen').style.display = 'none';
  const app = document.getElementById('app');
  app.classList.remove('hidden');
  const short = walletAddr.slice(0,6) + '...' + walletAddr.slice(-4);
  document.getElementById('user-badge').textContent = short;
  document.getElementById('toolbar-user').textContent = short;
  initNotebook();
  connectWS();
  fetchOllamaModels();
}

// ── WebSocket ─────────────────────────────
function connectWS() {
  ws = new WebSocket(WS_URL);
  ws.onopen = () => {
    document.getElementById('conn-badge').className = 'conn-badge on';
    document.getElementById('conn-badge').textContent = '● Connected';
    ws.send(JSON.stringify({
      type: 'session.create', ts: Date.now()/1000, id: uid(),
      name: 'Research-' + walletAddr.slice(0,8),
      routing: 'least_loaded', auth_token: authToken,
    }));
    ws.send(JSON.stringify({ type: 'worker.list.request', ts: Date.now()/1000, id: uid() }));
  };
  ws.onmessage = (e) => { try { handleMsg(JSON.parse(e.data)); } catch(err) { console.error(err); } };
  ws.onclose = () => {
    document.getElementById('conn-badge').className = 'conn-badge off';
    document.getElementById('conn-badge').textContent = '○ Disconnected';
    setTimeout(connectWS, 3000);
  };
  ws.onerror = () => {};
}

function handleMsg(msg) {
  switch(msg.type) {
    case 'session.info':
      sessionId = msg.session?.session_id || '';
      workers = msg.workers || []; renderWorkers(); break;
    case 'worker.list':
      workers = msg.workers || []; renderWorkers(); break;
    case 'user.list':
      users = msg.users || []; renderUsers(); break;
    case 'cell.output': handleCellOutput(msg); break;
    case 'cell.complete': handleCellComplete(msg); break;
    case 'cell.error': handleCellError(msg); break;
    case 'agent.status': handleAgentStatus(msg); break;
    case 'agent.cell': handleAgentCell(msg); break;
  }
}

// ── Ollama ────────────────────────────────
async function fetchOllamaModels() {
  try {
    const r = await fetch('/api/ollama/models');
    const d = await r.json();
    if (d.models && d.models.length > 0) {
      const sel = document.getElementById('agent-model');
      sel.innerHTML = d.models.map(m => '<option value="'+esc(m)+'">'+esc(m)+'</option>').join('');
      document.getElementById('agent-status').textContent = 'Ollama ready — ' + d.models.length + ' models';
    } else {
      document.getElementById('agent-status').textContent = 'Ollama not available — install from ollama.ai';
    }
  } catch(e) {
    document.getElementById('agent-status').textContent = 'Ollama not reachable';
  }
}

function startAgent() {
  if (!ws || ws.readyState !== 1 || !sessionId) return;
  const model = document.getElementById('agent-model').value;
  const goal = document.getElementById('agent-goal').value;
  ws.send(JSON.stringify({
    type: 'agent.start', ts: Date.now()/1000, id: uid(),
    session_id: sessionId, model: model, goal: goal,
    mode: 'mev', auth_token: authToken,
  }));
  agentRunning = true;
  document.getElementById('btn-agent-start').classList.remove('active');
  document.getElementById('btn-agent-pause').classList.add('active');
  document.getElementById('agent-status').textContent = 'Agent starting...';
}

function pauseAgent() {
  if (!ws || ws.readyState !== 1) return;
  ws.send(JSON.stringify({ type: 'agent.pause', ts: Date.now()/1000, id: uid(), session_id: sessionId }));
  document.getElementById('agent-status').textContent = 'Agent paused';
}

function stopAgent() {
  if (!ws || ws.readyState !== 1) return;
  ws.send(JSON.stringify({ type: 'agent.stop', ts: Date.now()/1000, id: uid(), session_id: sessionId }));
  agentRunning = false;
  document.getElementById('btn-agent-start').classList.add('active');
  document.getElementById('btn-agent-pause').classList.remove('active');
  document.getElementById('agent-status').textContent = 'Agent stopped';
}

function handleAgentStatus(msg) {
  const s = msg.agent_state || 'idle';
  const iter = msg.iteration || 0;
  const max = msg.max_iterations || 50;
  document.getElementById('agent-status').textContent =
    s === 'thinking' ? '🧠 Thinking... (iter ' + iter + '/' + max + ')' :
    s === 'executing' ? '⚡ Executing cell... (iter ' + iter + ')' :
    s === 'analyzing' ? '🔍 Analyzing output... (iter ' + iter + ')' :
    s === 'starting' ? '🚀 Agent starting...' :
    s === 'stopped' ? '⏹ Stopped after ' + iter + ' iterations' :
    'Agent: ' + s;
}

function handleAgentCell(msg) {
  const code = msg.code || '';
  if (!code.trim()) return;
  const idx = addCell(code, true, 'python', 'python');
  runCell(idx);
}

async function aiGenerateCell() {
  const model = document.getElementById('agent-model').value;
  const goal = document.getElementById('agent-goal').value;
  try {
    const r = await fetch('/api/ollama/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + authToken },
      body: JSON.stringify({ model, goal, context: getRecentOutputs() }),
    });
    const d = await r.json();
    if (d.code) { const idx = addCell(d.code, true, 'python', 'python'); runCell(idx); }
    else { alert(d.error || 'AI generation failed'); }
  } catch(e) { alert('AI generation failed: ' + e.message); }
}

function getRecentOutputs() {
  return cells.slice(-5).map(c => {
    const out = c.outputs.map(o => o.text || '').join('');
    return '# Cell:\n' + c.code + '\n# Output:\n' + out;
  }).join('\n---\n');
}

// ── Cell Management ───────────────────────
function initNotebook() {
  addCell('# Welcome to DistKernel — Distributed AI Notebook\n# Your wallet is your identity. AI agents write code. Workers execute it.\n# Press Shift+Enter to run a cell, or let the AI agent drive.\nimport sys, platform\nprint(f"Node: {platform.node()}")\nprint(f"Python {sys.version}")\nprint(f"Platform: {sys.platform}")', false, 'python', 'python');
  addCell('## Research Notes\n\n- This notebook supports Python, terminal, and markdown cells.\n- Terminal cells run on the host server.\n- Python cells route to distributed workers.\n- Markdown cells render locally for collaboration.', false, 'markdown', 'markdown');
  renderNotebook();
}

function addCell(code, isAI, cellMode, cellLanguage) {
  const idx = cells.length;
  const mode = cellMode || 'python';
  const language = cellLanguage || (LANGUAGE_OPTIONS[mode] ? LANGUAGE_OPTIONS[mode][0] : 'python');
  const cell = {
    id: uid(),
    code: code||'',
    outputs: [],
    status: 'idle',
    execCount: null,
    worker: '',
    isAI: !!isAI,
    author: isAI ? 'AI Agent' : walletAddr.slice(0,8),
    cellMode: mode,
    cellLanguage: language,
  };
  cells.push(cell);
  renderNotebook();
  setTimeout(() => { const ta = document.getElementById('input-' + cell.id); if (ta) { ta.focus(); autoResize(ta); } }, 50);
  return idx;
}

function removeCell(idx) { if (cells.length <= 1) return; cells.splice(idx, 1); renderNotebook(); }

function runCell(idx) {
  const cell = cells[idx];
  if (!cell || !ws || ws.readyState !== 1 || !sessionId) return;
  
  // Auto-detect shell commands and switch to terminal mode
  if (cell.cellMode === 'python' && looksLikeShellCommand(cell.code)) {
    cell.cellMode = 'terminal';
    cell.cellLanguage = 'bash';
    renderCell(idx);
  }
  
  if (cell.cellMode === 'markdown') {
    cell.outputs = [{ type: 'display', text: renderMarkdown(cell.code) }];
    cell.status = 'complete';
    cell.worker = 'local-markup';
    cellCounter++;
    cell.execCount = cellCounter;
    renderCell(idx);
    ws.send(JSON.stringify({
      type: 'execute.request', ts: Date.now()/1000, id: uid(),
      cell_id: cell.id + '-' + cellCounter,
      session_id: sessionId,
      code: cell.code,
      cell_mode: cell.cellMode,
      cell_language: cell.cellLanguage,
      auth_token: authToken,
    }));
    return;
  }
  cell.outputs = []; cell.status = 'running'; cell.worker = '';
  cellCounter++; cell.execCount = cellCounter;
  const cellId = cell.id + '-' + cellCounter;
  pendingCells[cellId] = idx;
  ws.send(JSON.stringify({ type: 'execute.request', ts: Date.now()/1000, id: uid(), cell_id: cellId, session_id: sessionId, code: cell.code, cell_mode: cell.cellMode, cell_language: cell.cellLanguage, auth_token: authToken }));
  renderCell(idx);
}

function runAllCells() { cells.forEach((_, idx) => runCell(idx)); }

function handleCellOutput(msg) {
  const idx = pendingCells[msg.cell_id]; if (idx === undefined) return;
  const cell = cells[idx]; if (!cell) return;
  const ot = msg.output_type, data = msg.data || {};
  if (ot === 'stream') cell.outputs.push({ type: 'stream', name: data.name, text: data.text });
  else if (ot === 'execute_result') { const p = data.data?.['text/plain']||''; const h = data.data?.['text/html']||''; cell.outputs.push({ type: 'result', text: h||p }); }
  else if (ot === 'display_data') { const h = data.data?.['text/html']||data.data?.['text/plain']||''; cell.outputs.push({ type: 'display', text: h }); }
  else if (ot === 'status') cell.worker = data.worker || '';
  renderCell(idx);
}

function handleCellComplete(msg) {
  const idx = pendingCells[msg.cell_id]; delete pendingCells[msg.cell_id]; if (idx === undefined) return;
  const cell = cells[idx];
  if (cell) { cell.status = 'complete'; cell.worker = msg.worker_id ? (workers.find(w => w.worker_id === msg.worker_id)?.name || msg.worker_id) : cell.worker; }
  renderCell(idx);
}

function handleCellError(msg) {
  const idx = pendingCells[msg.cell_id]; delete pendingCells[msg.cell_id]; if (idx === undefined) return;
  const cell = cells[idx];
  if (cell) { cell.status = 'error'; cell.outputs.push({ type: 'error', text: (msg.ename||'Error')+': '+(msg.evalue||'')+'\n'+(msg.traceback||[]).join('\n') }); }
  renderCell(idx);
}

// ── Render ────────────────────────────────
function renderWorkers() {
  const el = document.getElementById('worker-list');
  const busy = workers.filter(w => w.status === 'busy').length;
  const cpus = workers.reduce((s, w) => s + (w.capabilities?.cpu_count || 0), 0);
  const ram = workers.reduce((s, w) => s + (w.capabilities?.memory_mb || 0), 0);
  document.getElementById('stat-workers').textContent = workers.length;
  document.getElementById('stat-busy').textContent = busy;
  document.getElementById('stat-cpus').textContent = cpus;
  document.getElementById('stat-ram').textContent = (ram/1024).toFixed(1)+'G';
  if (!workers.length) { el.innerHTML = '<div class="empty-box">No nodes connected.<code>distkernel-worker --gateway '+WS_URL+'</code></div>'; return; }
  el.innerHTML = workers.map(w => {
    const c = w.capabilities||{}, cls = w.status==='busy'?'busy':w.status==='offline'?'offline':'idle';
    return '<div class="worker-card"><div class="wk-row"><span class="wk-name">'+esc(w.name||w.worker_id)+'</span><span class="wk-badge '+cls+'">'+w.status+(w.running_cells>0?' ('+w.running_cells+')':'')+'</span></div><div class="wk-meta">'+(c.platform||'?')+' · '+(c.cpu_count||'?')+' CPU · '+fmtMem(c.memory_mb)+'</div></div>';
  }).join('');
}

function renderUsers() {
  const el = document.getElementById('user-list');
  const collab = document.getElementById('toolbar-collab');
  if (collab) collab.textContent = (users.length || 1) + ' collaborator' + ((users.length || 1) === 1 ? '' : 's');
  if (!users.length) { el.innerHTML = '<div class="empty-box">Just you so far</div>'; return; }
  el.innerHTML = users.map(u => {
    const cls = u.online ? 'online' : 'offline';
    return '<div class="user-card"><div class="usr-row"><span class="usr-name">'+esc(u.name)+'</span><span class="usr-badge '+cls+'">'+(u.online?'online':'offline')+'</span></div><div class="usr-meta">'+u.cells_run+' cells run</div></div>';
  }).join('');
}

function renderNotebook() {
  const el = document.getElementById('notebook');
  el.innerHTML = cells.map((c, i) => cellHTML(c, i)).join('') + '<div class="add-cell-btn" onclick="addCell()">+ Add Cell</div>';
  cells.forEach((cell, idx) => {
    const ta = document.getElementById('input-' + cell.id);
    if (ta) { ta.value = cell.code; ta.oninput = () => { cell.code = ta.value; syncPreview(idx); autoResize(ta); }; ta.onkeydown = (e) => handleKey(e, idx); autoResize(ta); }
    const mode = document.getElementById('mode-' + cell.id);
    if (mode) mode.onchange = (e) => updateCellMode(idx, e.target.value);
    const lang = document.getElementById('lang-' + cell.id);
    if (lang) lang.onchange = (e) => updateCellLanguage(idx, e.target.value);
    syncPreview(idx);
  });
}

function renderCell(idx) {
  const cell = cells[idx]; if (!cell) return;
  const ex = document.getElementById('cell-' + cell.id);
  if (!ex) { renderNotebook(); return; }
  ex.outerHTML = cellHTML(cell, idx);
  const ta = document.getElementById('input-' + cell.id);
  if (ta) { ta.value = cell.code; ta.oninput = () => { cell.code = ta.value; syncPreview(idx); autoResize(ta); }; ta.onkeydown = (e) => handleKey(e, idx); autoResize(ta); }
  const mode = document.getElementById('mode-' + cell.id);
  if (mode) mode.onchange = (e) => updateCellMode(idx, e.target.value);
  const lang = document.getElementById('lang-' + cell.id);
  if (lang) lang.onchange = (e) => updateCellLanguage(idx, e.target.value);
  syncPreview(idx);
}

function cellHTML(cell, idx) {
  const sc = cell.status==='running'?' cell-running':cell.status==='error'?' cell-error':'';
  const ac = cell.isAI ? ' cell-ai' : '';
  const mc = cell.cellMode === 'terminal' ? ' cell-terminal' : cell.cellMode === 'markdown' ? ' cell-markdown' : '';
  const el = cell.execCount ? '['+cell.execCount+']' : '[ ]';
  const wl = cell.worker ? 'on '+esc(cell.worker) : '';
  const authorBadge = cell.isAI ? '<span class="cell-ai-badge">🤖 AI</span>' : '<span class="cell-user-badge">👤 '+esc(cell.author)+'</span>';
  const modeOptions = ['python','terminal','markdown'].map(m => '<option value="'+m+'"'+(cell.cellMode===m?' selected':'')+'>'+m+'</option>').join('');
  const langOptions = (LANGUAGE_OPTIONS[cell.cellMode] || ['python']).map(l => '<option value="'+l+'"'+(cell.cellLanguage===l?' selected':'')+'>'+l+'</option>').join('');
  let out = '';
  for (const o of cell.outputs) {
    if (o.type==='stream'&&o.name==='stderr') out += '<span class="out-stderr">'+esc(o.text)+'</span>';
    else if (o.type==='stream') out += '<span class="out-stream">'+esc(o.text)+'</span>';
    else if (o.type==='result') out += '<span class="out-result">'+esc(o.text)+'</span>';
    else if (o.type==='error') out += '<span class="out-error">'+esc(o.text)+'</span>';
    else if (o.type==='display') out += '<span class="out-stream">'+o.text+'</span>';
  }
  if (cell.status==='running'&&!cell.outputs.length) out = '<span class="out-status">⏳ Executing'+(wl?' '+wl:'')+'...</span>';
  const previewClass = cell.cellMode === 'python' ? 'preview-code' : cell.cellMode === 'terminal' ? 'preview-terminal' : 'preview-markdown';
  const previewTitle = cell.cellMode === 'python' ? 'Code Context' : cell.cellMode === 'terminal' ? 'Terminal Preview' : 'Markdown Preview';
  return '<div class="cell'+sc+ac+mc+'" id="cell-'+cell.id+'"><div class="cell-header"><div class="cell-meta"><span class="cell-num">'+el+'</span>'+authorBadge+'<select class="cell-mode-select" id="mode-'+cell.id+'">'+modeOptions+'</select><select class="cell-lang-select" id="lang-'+cell.id+'">'+langOptions+'</select></div><span class="cell-worker">'+wl+'</span><div class="cell-actions"><button onclick="runCell('+idx+')" title="Run">▶</button><button onclick="removeCell('+idx+')" title="Delete">✕</button></div></div><div class="cell-body'+(cell.cellMode === 'python' ? '' : '')+'"><div class="cell-input"><textarea id="input-'+cell.id+'" spellcheck="false" placeholder="# Enter '+esc(cell.cellMode)+'...">'+esc(cell.code)+'</textarea></div><div class="cell-preview" id="preview-'+cell.id+'"><div class="preview-title">'+previewTitle+'</div><div class="'+previewClass+'" id="preview-body-'+cell.id+'"></div></div></div><div class="cell-output">'+out+'</div></div>';
}

function updateCellMode(idx, mode) {
  const cell = cells[idx];
  if (!cell) return;
  cell.cellMode = mode;
  cell.cellLanguage = (LANGUAGE_OPTIONS[mode] || ['python'])[0];
  renderCell(idx);
}

function updateCellLanguage(idx, language) {
  const cell = cells[idx];
  if (!cell) return;
  cell.cellLanguage = language;
}

function syncPreview(idx) {
  const cell = cells[idx];
  if (!cell) return;
  const body = document.getElementById('preview-body-' + cell.id);
  if (!body) return;
  if (cell.cellMode === 'markdown') {
    body.className = 'preview-markdown';
    body.innerHTML = renderMarkdown(cell.code);
  } else if (cell.cellMode === 'terminal') {
    body.className = 'preview-terminal';
    body.textContent = '$ ' + cell.code;
  } else {
    body.className = 'preview-code';
    body.textContent = cell.code;
  }
}

function renderMarkdown(src) {
  return esc(src)
    .replace(/^### (.*)$/gm, '<h3>$1</h3>')
    .replace(/^## (.*)$/gm, '<h2>$1</h2>')
    .replace(/^# (.*)$/gm, '<h1>$1</h1>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>');
}

function looksLikeShellCommand(code) {
  const trimmed = code.trim().toLowerCase();
  const shellPrefixes = [
    'pip install', 'pip3 install', 'pip uninstall', 'pip3 uninstall',
    'npm install', 'npm uninstall', 'npm run',
    'yarn add', 'yarn remove', 'yarn install',
    'git clone', 'git pull', 'git push', 'git checkout',
    'curl', 'wget',
    'ls ', 'cd ', 'mkdir ', 'rm ', 'cp ', 'mv ',
    'chmod ', 'chown ',
    'docker build', 'docker run', 'docker compose',
    'python -m pip', 'python3 -m pip',
  ];
  return shellPrefixes.some(prefix => trimmed.startsWith(prefix));
}

function handleKey(e, idx) {
  if (e.key==='Enter'&&(e.shiftKey||e.ctrlKey)) { e.preventDefault(); runCell(idx); if (e.shiftKey&&idx===cells.length-1) addCell(); }
  if (e.key==='Tab') { e.preventDefault(); const ta=e.target, s=ta.selectionStart; ta.value=ta.value.substring(0,s)+'    '+ta.value.substring(ta.selectionEnd); ta.selectionStart=ta.selectionEnd=s+4; cells[idx].code=ta.value; }
}

function autoResize(ta) { ta.style.height='auto'; ta.style.height=Math.max(60,ta.scrollHeight)+'px'; }

// ── Utils ─────────────────────────────────
function uid() { return Math.random().toString(36).substring(2, 14); }
function esc(s) { if (!s) return ''; const d=document.createElement('div'); d.textContent=String(s); return d.innerHTML; }
function fmtMem(mb) { if (!mb) return '?'; return mb>=1024?(mb/1024).toFixed(1)+'GB':mb+'MB'; }
