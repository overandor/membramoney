"""
Standalone web demo — serves a notebook UI + the gateway on a single port.
No JupyterLab required. Just run:

    python -m distkernel.gateway.demo --port 8555

Then open http://localhost:8555 in your browser and connect workers with:

    distkernel-worker --gateway ws://localhost:8555/ws
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import asdict
from typing import Any, Dict, Optional

from aiohttp import web

from ..protocol import (
    MsgType, OutputType, WorkerCapabilities, WorkerInfo, SessionInfo,
    CellExecution, make_msg, make_execute,
)

log = logging.getLogger("distkernel.demo")

# ─── HTML Notebook UI ────────────────────────────────────────────────────────

NOTEBOOK_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Distributed Notebook</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0f1117;
    --bg-card: #161922;
    --bg-cell: #1c1f2e;
    --bg-hover: #22263a;
    --border: #2a2e3f;
    --text: #e1e4ed;
    --text-dim: #8b8fa3;
    --accent: #6c5ce7;
    --accent-light: #a29bfe;
    --green: #00b894;
    --green-dim: #00b89433;
    --orange: #fdcb6e;
    --red: #e17055;
    --blue: #74b9ff;
    --font: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    --mono: 'JetBrains Mono', 'Menlo', monospace;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--font);
    font-size: 14px;
    line-height: 1.5;
    min-height: 100vh;
  }

  /* ── Layout ─────────────────────────────── */
  .app { display: flex; height: 100vh; }
  .sidebar {
    width: 280px;
    min-width: 280px;
    background: var(--bg-card);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    overflow-y: auto;
  }
  .main {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .toolbar {
    height: 48px;
    background: var(--bg-card);
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    padding: 0 16px;
    gap: 8px;
    flex-shrink: 0;
  }
  .notebook {
    flex: 1;
    overflow-y: auto;
    padding: 24px;
  }

  /* ── Sidebar ────────────────────────────── */
  .sidebar-header {
    padding: 16px;
    border-bottom: 1px solid var(--border);
  }
  .sidebar-header h1 {
    font-size: 16px;
    font-weight: 700;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .sidebar-header h1 span { font-size: 20px; }
  .conn-badge {
    display: inline-block;
    font-size: 11px;
    padding: 1px 8px;
    border-radius: 10px;
    margin-top: 6px;
    font-weight: 500;
  }
  .conn-badge.on { background: var(--green-dim); color: var(--green); }
  .conn-badge.off { background: #e1705533; color: var(--red); }

  .stats-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    padding: 12px 16px;
  }
  .stat-box {
    background: var(--bg);
    padding: 10px;
    border-radius: 8px;
    text-align: center;
  }
  .stat-val { font-size: 22px; font-weight: 700; color: var(--accent-light); }
  .stat-lbl { font-size: 10px; color: var(--text-dim); text-transform: uppercase; letter-spacing: .5px; }

  .section-title {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: .8px;
    color: var(--text-dim);
    padding: 12px 16px 6px;
  }
  .worker-list { padding: 0 12px 12px; }
  .worker-card {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 10px 12px;
    margin-bottom: 6px;
    transition: border-color .15s;
  }
  .worker-card:hover { border-color: var(--accent); }
  .wk-row { display: flex; justify-content: space-between; align-items: center; }
  .wk-name { font-weight: 600; font-size: 13px; }
  .wk-badge {
    font-size: 10px;
    padding: 1px 6px;
    border-radius: 6px;
    font-weight: 500;
  }
  .wk-badge.idle { background: var(--green-dim); color: var(--green); }
  .wk-badge.busy { background: #fdcb6e33; color: var(--orange); }
  .wk-badge.offline { background: #e1705533; color: var(--red); }
  .wk-meta { font-size: 11px; color: var(--text-dim); margin-top: 4px; }

  .empty-workers {
    padding: 20px 16px;
    text-align: center;
    color: var(--text-dim);
    font-size: 12px;
  }
  .empty-workers code {
    display: block;
    background: var(--bg);
    padding: 6px 10px;
    border-radius: 6px;
    margin-top: 8px;
    font-family: var(--mono);
    font-size: 11px;
    color: var(--accent-light);
    word-break: break-all;
  }

  /* ── Toolbar ────────────────────────────── */
  .btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--bg-cell);
    color: var(--text);
    font-size: 12px;
    font-family: var(--font);
    cursor: pointer;
    transition: all .15s;
  }
  .btn:hover { background: var(--bg-hover); border-color: var(--accent); }
  .btn-primary { background: var(--accent); border-color: var(--accent); color: #fff; font-weight: 500; }
  .btn-primary:hover { background: #5b4bd5; }
  .toolbar-title { font-weight: 600; font-size: 14px; flex: 1; }

  /* ── Cells ──────────────────────────────── */
  .cell {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 10px;
    margin-bottom: 12px;
    overflow: hidden;
    transition: border-color .15s;
  }
  .cell:focus-within { border-color: var(--accent); }
  .cell-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 12px;
    background: var(--bg-cell);
    border-bottom: 1px solid var(--border);
    font-size: 11px;
    color: var(--text-dim);
  }
  .cell-num { font-family: var(--mono); }
  .cell-worker { font-family: var(--mono); color: var(--blue); }
  .cell-actions { display: flex; gap: 4px; }
  .cell-actions button {
    background: none;
    border: none;
    color: var(--text-dim);
    cursor: pointer;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 12px;
  }
  .cell-actions button:hover { background: var(--bg-hover); color: var(--text); }

  .cell-input {
    padding: 0;
    position: relative;
  }
  .cell-input textarea {
    width: 100%;
    min-height: 60px;
    padding: 12px 14px;
    background: transparent;
    color: var(--text);
    border: none;
    outline: none;
    font-family: var(--mono);
    font-size: 13px;
    line-height: 1.6;
    resize: vertical;
    tab-size: 4;
  }

  .cell-output {
    border-top: 1px solid var(--border);
    padding: 10px 14px;
    font-family: var(--mono);
    font-size: 12px;
    line-height: 1.5;
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 400px;
    overflow-y: auto;
  }
  .cell-output:empty { display: none; }
  .out-stream { color: var(--text); }
  .out-stderr { color: var(--orange); }
  .out-error { color: var(--red); }
  .out-result { color: var(--green); }
  .out-status { color: var(--text-dim); font-style: italic; font-size: 11px; }
  .cell-running .cell-header { background: #6c5ce722; }
  .cell-error .cell-header { background: #e1705522; }

  .add-cell-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 10px;
    border: 1px dashed var(--border);
    border-radius: 10px;
    color: var(--text-dim);
    cursor: pointer;
    font-size: 13px;
    transition: all .15s;
  }
  .add-cell-btn:hover {
    border-color: var(--accent);
    color: var(--accent-light);
    background: var(--bg-card);
  }

  /* ── Responsive ─────────────────────────── */
  @media (max-width: 768px) {
    .sidebar { display: none; }
    .stats-grid { grid-template-columns: 1fr 1fr; }
  }
</style>
</head>
<body>
<div class="app">
  <!-- Sidebar -->
  <div class="sidebar">
    <div class="sidebar-header">
      <h1><span>⚡</span> Distributed Notebook</h1>
      <div id="conn-badge" class="conn-badge off">● Disconnected</div>
    </div>
    <div class="stats-grid">
      <div class="stat-box">
        <div class="stat-val" id="stat-workers">0</div>
        <div class="stat-lbl">Workers</div>
      </div>
      <div class="stat-box">
        <div class="stat-val" id="stat-busy">0</div>
        <div class="stat-lbl">Busy</div>
      </div>
      <div class="stat-box">
        <div class="stat-val" id="stat-cpus">0</div>
        <div class="stat-lbl">CPUs</div>
      </div>
      <div class="stat-box">
        <div class="stat-val" id="stat-ram">0</div>
        <div class="stat-lbl">RAM (GB)</div>
      </div>
    </div>
    <div class="section-title">Workers</div>
    <div class="worker-list" id="worker-list"></div>
  </div>

  <!-- Main -->
  <div class="main">
    <div class="toolbar">
      <span class="toolbar-title">📓 Untitled Notebook</span>
      <button class="btn" onclick="addCell()">+ Cell</button>
      <button class="btn btn-primary" onclick="runAllCells()">▶ Run All</button>
    </div>
    <div class="notebook" id="notebook"></div>
  </div>
</div>

<script>
// ── State ─────────────────────────────────
let ws = null;
let sessionId = '';
let cells = [];
let workers = [];
let cellCounter = 0;
let pendingCells = {};  // cellId → {resolve, reject, cellIdx}

const WS_URL = `ws://${location.host}/ws`;

// ── WebSocket ─────────────────────────────
function connect() {
  ws = new WebSocket(WS_URL);
  ws.onopen = () => {
    document.getElementById('conn-badge').className = 'conn-badge on';
    document.getElementById('conn-badge').textContent = '● Connected';
    // Create session
    ws.send(JSON.stringify({
      type: 'session.create',
      ts: Date.now()/1000,
      id: uid(),
      name: 'Web Demo',
      routing: 'least_loaded',
    }));
    ws.send(JSON.stringify({ type: 'worker.list.request', ts: Date.now()/1000, id: uid() }));
  };
  ws.onmessage = (e) => {
    try { handleMsg(JSON.parse(e.data)); } catch(err) { console.error(err); }
  };
  ws.onclose = () => {
    document.getElementById('conn-badge').className = 'conn-badge off';
    document.getElementById('conn-badge').textContent = '● Disconnected';
    setTimeout(connect, 3000);
  };
  ws.onerror = () => {};
}

function handleMsg(msg) {
  switch(msg.type) {
    case 'session.info':
      sessionId = msg.session?.session_id || '';
      workers = msg.workers || [];
      renderWorkers();
      break;
    case 'worker.list':
      workers = msg.workers || [];
      renderWorkers();
      break;
    case 'cell.output':
      handleCellOutput(msg);
      break;
    case 'cell.complete':
      handleCellComplete(msg);
      break;
    case 'cell.error':
      handleCellError(msg);
      break;
  }
}

// ── Cell Management ───────────────────────
function addCell(code = '') {
  const idx = cells.length;
  const cell = { id: uid(), code, outputs: [], status: 'idle', execCount: null, worker: '' };
  cells.push(cell);
  renderNotebook();
  // Focus new cell
  setTimeout(() => {
    const ta = document.getElementById('input-' + cell.id);
    if (ta) ta.focus();
  }, 50);
  return idx;
}

function removeCell(idx) {
  if (cells.length <= 1) return;
  cells.splice(idx, 1);
  renderNotebook();
}

function runCell(idx) {
  const cell = cells[idx];
  if (!cell || !ws || ws.readyState !== 1 || !sessionId) return;

  cell.outputs = [];
  cell.status = 'running';
  cell.worker = '';
  cellCounter++;
  cell.execCount = cellCounter;

  const cellId = cell.id + '-' + cellCounter;
  pendingCells[cellId] = idx;

  ws.send(JSON.stringify({
    type: 'execute.request',
    ts: Date.now()/1000,
    id: uid(),
    cell_id: cellId,
    session_id: sessionId,
    code: cell.code,
  }));

  renderCell(idx);
}

function runAllCells() {
  cells.forEach((_, idx) => runCell(idx));
}

function handleCellOutput(msg) {
  const idx = pendingCells[msg.cell_id];
  if (idx === undefined) return;
  const cell = cells[idx];
  if (!cell) return;

  const ot = msg.output_type;
  const data = msg.data || {};

  if (ot === 'stream') {
    cell.outputs.push({ type: 'stream', name: data.name, text: data.text });
  } else if (ot === 'execute_result') {
    const plain = data.data?.['text/plain'] || '';
    const html = data.data?.['text/html'] || '';
    cell.outputs.push({ type: 'result', text: html || plain });
  } else if (ot === 'display_data') {
    const html = data.data?.['text/html'] || data.data?.['text/plain'] || '';
    cell.outputs.push({ type: 'display', text: html });
  } else if (ot === 'status') {
    cell.worker = data.worker || '';
  }
  renderCell(idx);
}

function handleCellComplete(msg) {
  const idx = pendingCells[msg.cell_id];
  delete pendingCells[msg.cell_id];
  if (idx === undefined) return;
  const cell = cells[idx];
  if (cell) {
    cell.status = 'complete';
    cell.worker = msg.worker_id ? (workers.find(w => w.worker_id === msg.worker_id)?.name || msg.worker_id) : cell.worker;
  }
  renderCell(idx);
}

function handleCellError(msg) {
  const idx = pendingCells[msg.cell_id];
  delete pendingCells[msg.cell_id];
  if (idx === undefined) return;
  const cell = cells[idx];
  if (cell) {
    cell.status = 'error';
    const tb = (msg.traceback || []).join('\n');
    cell.outputs.push({ type: 'error', text: `${msg.ename}: ${msg.evalue}\n${tb}` });
  }
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
  document.getElementById('stat-ram').textContent = (ram / 1024).toFixed(1);

  if (workers.length === 0) {
    el.innerHTML = `
      <div class="empty-workers">
        No workers connected.<br>Start one with:
        <code>distkernel-worker --gateway ${WS_URL}</code>
      </div>`;
    return;
  }

  el.innerHTML = workers.map(w => {
    const c = w.capabilities || {};
    const cls = w.status === 'busy' ? 'busy' : w.status === 'offline' ? 'offline' : 'idle';
    return `
      <div class="worker-card">
        <div class="wk-row">
          <span class="wk-name">${esc(w.name || w.worker_id)}</span>
          <span class="wk-badge ${cls}">${w.status}${w.running_cells > 0 ? ' ('+w.running_cells+')' : ''}</span>
        </div>
        <div class="wk-meta">${c.platform || '?'} · ${c.cpu_count || '?'} CPU · ${formatMem(c.memory_mb)} · Py ${c.python_version || '?'}</div>
      </div>`;
  }).join('');
}

function renderNotebook() {
  const el = document.getElementById('notebook');
  el.innerHTML = cells.map((cell, idx) => cellHTML(cell, idx)).join('') +
    '<div class="add-cell-btn" onclick="addCell()">+ Add Cell</div>';
  // Restore textareas
  cells.forEach((cell, idx) => {
    const ta = document.getElementById('input-' + cell.id);
    if (ta) {
      ta.value = cell.code;
      ta.oninput = () => { cell.code = ta.value; autoResize(ta); };
      ta.onkeydown = (e) => handleKey(e, idx);
      autoResize(ta);
    }
  });
}

function renderCell(idx) {
  const cell = cells[idx];
  if (!cell) return;
  const existing = document.getElementById('cell-' + cell.id);
  if (!existing) { renderNotebook(); return; }
  existing.outerHTML = cellHTML(cell, idx);
  // Re-bind
  const ta = document.getElementById('input-' + cell.id);
  if (ta) {
    ta.value = cell.code;
    ta.oninput = () => { cell.code = ta.value; autoResize(ta); };
    ta.onkeydown = (e) => handleKey(e, idx);
    autoResize(ta);
  }
}

function cellHTML(cell, idx) {
  const statusClass = cell.status === 'running' ? ' cell-running' : cell.status === 'error' ? ' cell-error' : '';
  const execLabel = cell.execCount ? `[${cell.execCount}]` : '[ ]';
  const workerLabel = cell.worker ? `on ${esc(cell.worker)}` : '';

  let outputHTML = '';
  for (const o of cell.outputs) {
    if (o.type === 'stream' && o.name === 'stderr') {
      outputHTML += `<span class="out-stderr">${esc(o.text)}</span>`;
    } else if (o.type === 'stream') {
      outputHTML += `<span class="out-stream">${esc(o.text)}</span>`;
    } else if (o.type === 'result') {
      outputHTML += `<span class="out-result">${esc(o.text)}</span>`;
    } else if (o.type === 'error') {
      outputHTML += `<span class="out-error">${esc(o.text)}</span>`;
    } else if (o.type === 'display') {
      outputHTML += `<span class="out-stream">${o.text}</span>`;
    }
  }
  if (cell.status === 'running' && cell.outputs.length === 0) {
    outputHTML = `<span class="out-status">⏳ Executing${workerLabel ? ' ' + workerLabel : ''}...</span>`;
  }

  return `
    <div class="cell${statusClass}" id="cell-${cell.id}">
      <div class="cell-header">
        <span class="cell-num">${execLabel}</span>
        <span class="cell-worker">${workerLabel}</span>
        <div class="cell-actions">
          <button onclick="runCell(${idx})" title="Run">▶</button>
          <button onclick="removeCell(${idx})" title="Delete">✕</button>
        </div>
      </div>
      <div class="cell-input">
        <textarea id="input-${cell.id}" spellcheck="false" placeholder="# Enter Python code...">${esc(cell.code)}</textarea>
      </div>
      <div class="cell-output">${outputHTML}</div>
    </div>`;
}

function handleKey(e, idx) {
  if (e.key === 'Enter' && (e.shiftKey || e.ctrlKey)) {
    e.preventDefault();
    runCell(idx);
    if (e.shiftKey && idx === cells.length - 1) addCell();
  }
  if (e.key === 'Tab') {
    e.preventDefault();
    const ta = e.target;
    const start = ta.selectionStart;
    ta.value = ta.value.substring(0, start) + '    ' + ta.value.substring(ta.selectionEnd);
    ta.selectionStart = ta.selectionEnd = start + 4;
    cells[idx].code = ta.value;
  }
}

function autoResize(ta) {
  ta.style.height = 'auto';
  ta.style.height = Math.max(60, ta.scrollHeight) + 'px';
}

// ── Utils ─────────────────────────────────
function uid() { return Math.random().toString(36).substring(2, 14); }
function esc(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}
function formatMem(mb) {
  if (!mb) return '?';
  return mb >= 1024 ? (mb/1024).toFixed(1)+'GB' : mb+'MB';
}

// ── Init ──────────────────────────────────
addCell('import sys\nprint(f"Hello from {sys.platform}!")\nprint(f"Python {sys.version}")');
addCell('import math\n\n# Distributed compute demo\nresults = [math.factorial(n) for n in range(20)]\nresults');
addCell('# This cell runs on whichever worker is least loaded\nimport time\nfor i in range(5):\n    print(f"Step {i+1}/5")\n    time.sleep(0.5)\nprint("Done!")');
renderNotebook();
connect();
</script>
</body>
</html>"""


# ─── Demo Server (aiohttp serving HTML + proxying WS to gateway logic) ──────

class DemoServer:
    """
    Combines the gateway server with an HTTP server that serves the notebook UI.
    Single port, no CORS issues.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8555) -> None:
        self._host = host
        self._port = port
        # Gateway state (inline, not separate process)
        self._workers: Dict[str, Any] = {}         # worker_id → {ws, info}
        self._clients: Dict[int, Any] = {}          # ws id → {ws, client_id, sessions}
        self._sessions: Dict[str, SessionInfo] = {}
        self._executions: Dict[str, CellExecution] = {}
        self._exec_counts: Dict[str, int] = {}
        self._rr_idx = 0

    async def start(self) -> None:
        app = web.Application()
        app.router.add_get("/", self._handle_index)
        app.router.add_get("/ws", self._handle_ws)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self._host, self._port)
        await site.start()
        log.info("Demo notebook at http://%s:%d", self._host, self._port)
        log.info("Workers connect to ws://%s:%d/ws", self._host, self._port)

        # Health check loop
        while True:
            await asyncio.sleep(30)
            self._check_health()

    async def _handle_index(self, request: web.Request) -> web.Response:
        return web.Response(text=NOTEBOOK_HTML, content_type="text/html")

    async def _handle_ws(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(max_msg_size=50 * 1024 * 1024)
        await ws.prepare(request)
        ws_id = id(ws)
        log.info("WebSocket connected: %s", ws_id)

        try:
            async for raw_msg in ws:
                if raw_msg.type in (web.WSMsgType.TEXT,):
                    try:
                        msg = json.loads(raw_msg.data)
                        await self._dispatch(ws, msg)
                    except json.JSONDecodeError:
                        await ws.send_json(make_msg(MsgType.ERROR, error="invalid JSON"))
                    except Exception:
                        log.exception("Dispatch error")
                elif raw_msg.type == web.WSMsgType.ERROR:
                    log.warning("WS error: %s", ws.exception())
        finally:
            await self._cleanup(ws)

        return ws

    async def _dispatch(self, ws, msg: Dict[str, Any]) -> None:
        t = msg.get("type", "")

        if t == MsgType.WORKER_REGISTER.value:
            await self._on_worker_register(ws, msg)
        elif t == MsgType.WORKER_HEARTBEAT.value:
            self._on_worker_heartbeat(msg)
        elif t == MsgType.WORKER_DEREGISTER.value:
            await self._on_worker_deregister(msg)
        elif t == MsgType.CELL_OUTPUT.value:
            await self._relay_to_session(msg.get("session_id", ""), msg)
        elif t == MsgType.CELL_COMPLETE.value:
            await self._on_cell_complete(msg)
        elif t == MsgType.CELL_ERROR.value:
            await self._on_cell_error(msg)
        elif t == MsgType.SESSION_CREATE.value:
            await self._on_session_create(ws, msg)
        elif t == MsgType.SESSION_JOIN.value:
            await self._on_session_join(ws, msg)
        elif t == MsgType.EXECUTE_REQUEST.value:
            await self._on_execute_request(ws, msg)
        elif t == MsgType.INTERRUPT_REQUEST.value:
            await self._on_interrupt(msg)
        elif t == "worker.list.request":
            await ws.send_json(make_msg(
                MsgType.WORKER_LIST,
                workers=[w["info"] for w in self._workers.values()]))

    # ── Worker handlers ──────────────────────────────────────────────

    async def _on_worker_register(self, ws, msg):
        wid = msg.get("worker_id", uuid.uuid4().hex[:12])
        name = msg.get("name", f"worker-{wid[:6]}")
        caps = msg.get("capabilities", {})
        info = {
            "worker_id": wid, "name": name, "capabilities": caps,
            "connected_at": time.time(), "last_heartbeat": time.time(),
            "running_cells": 0, "total_executed": 0, "status": "idle",
        }
        self._workers[wid] = {"ws": ws, "info": info}
        log.info("Worker registered: %s (%s)", name, wid)
        await ws.send_json(make_msg(MsgType.WORKER_STATUS,
                                     worker_id=wid, status="registered",
                                     message=f"Registered as {name}"))
        await self._broadcast_workers()

    def _on_worker_heartbeat(self, msg):
        wid = msg.get("worker_id", "")
        w = self._workers.get(wid)
        if w:
            w["info"]["last_heartbeat"] = time.time()
            w["info"]["running_cells"] = msg.get("running_cells", 0)
            w["info"]["status"] = "busy" if w["info"]["running_cells"] > 0 else "idle"

    async def _on_worker_deregister(self, msg):
        wid = msg.get("worker_id", "")
        self._workers.pop(wid, None)
        log.info("Worker deregistered: %s", wid)
        await self._broadcast_workers()

    # ── Session handlers ─────────────────────────────────────────────

    async def _on_session_create(self, ws, msg):
        ws_id = id(ws)
        client_id = uuid.uuid4().hex[:12]
        self._clients[ws_id] = {"ws": ws, "client_id": client_id, "sessions": set()}

        session = SessionInfo(
            name=msg.get("name", "Untitled"),
            routing=msg.get("routing", "least_loaded"),
        )
        session.participants.append(client_id)
        self._sessions[session.session_id] = session
        self._exec_counts[session.session_id] = 0
        self._clients[ws_id]["sessions"].add(session.session_id)

        log.info("Session created: %s by client %s", session.session_id, client_id)
        await ws.send_json(make_msg(
            MsgType.SESSION_INFO,
            session=asdict(session),
            workers=[w["info"] for w in self._workers.values()],
        ))

    async def _on_session_join(self, ws, msg):
        sid = msg.get("session_id", "")
        session = self._sessions.get(sid)
        if not session:
            await ws.send_json(make_msg(MsgType.ERROR, error="Session not found"))
            return
        ws_id = id(ws)
        if ws_id not in self._clients:
            cid = uuid.uuid4().hex[:12]
            self._clients[ws_id] = {"ws": ws, "client_id": cid, "sessions": set()}
        self._clients[ws_id]["sessions"].add(sid)
        await ws.send_json(make_msg(
            MsgType.SESSION_INFO,
            session=asdict(session),
            workers=[w["info"] for w in self._workers.values()],
        ))

    # ── Execute handlers ─────────────────────────────────────────────

    async def _on_execute_request(self, ws, msg):
        sid = msg.get("session_id", "")
        code = msg.get("code", "")
        cell_id = msg.get("cell_id", uuid.uuid4().hex[:16])
        session = self._sessions.get(sid)
        if not session:
            await ws.send_json(make_msg(MsgType.CELL_ERROR, cell_id=cell_id,
                                         session_id=sid, ename="NoSession",
                                         evalue="Session not found", traceback=[]))
            return

        wid = self._pick_worker(session.routing)
        if not wid:
            await ws.send_json(make_msg(
                MsgType.CELL_ERROR, cell_id=cell_id, session_id=sid,
                ename="NoWorkerAvailable",
                evalue="No compute workers connected. Run: distkernel-worker --gateway ws://HOST:PORT/ws",
                traceback=[]))
            return

        self._exec_counts[sid] = self._exec_counts.get(sid, 0) + 1
        exe = CellExecution(cell_id=cell_id, session_id=sid, code=code,
                            worker_id=wid, submitted_at=time.time(),
                            execution_count=self._exec_counts[sid])
        self._executions[cell_id] = exe

        w = self._workers[wid]
        w["info"]["running_cells"] += 1
        w["info"]["status"] = "busy"

        exec_msg = make_execute(cell_id=cell_id, session_id=sid, code=code,
                                execution_count=exe.execution_count)
        exec_msg["worker_id"] = wid

        log.info("Route cell %s → worker %s", cell_id[:8], w["info"]["name"])

        try:
            await w["ws"].send_json(exec_msg)
            exe.status = "running"
            await self._relay_to_session(sid, make_msg(
                MsgType.CELL_OUTPUT, cell_id=cell_id, session_id=sid,
                output_type=OutputType.STATUS.value,
                data={"execution_state": "busy", "worker": w["info"]["name"]},
                worker_id=wid))
        except Exception as exc:
            log.error("Failed to send to worker %s: %s", wid, exc)
            w["info"]["running_cells"] = max(0, w["info"]["running_cells"] - 1)
            await ws.send_json(make_msg(
                MsgType.CELL_ERROR, cell_id=cell_id, session_id=sid,
                ename="WorkerError", evalue=str(exc), traceback=[]))

    async def _on_cell_complete(self, msg):
        cell_id = msg.get("cell_id", "")
        exe = self._executions.get(cell_id)
        if exe and exe.worker_id:
            w = self._workers.get(exe.worker_id)
            if w:
                w["info"]["running_cells"] = max(0, w["info"]["running_cells"] - 1)
                w["info"]["total_executed"] += 1
                w["info"]["status"] = "busy" if w["info"]["running_cells"] > 0 else "idle"
        await self._relay_to_session(msg.get("session_id", ""), msg)

    async def _on_cell_error(self, msg):
        cell_id = msg.get("cell_id", "")
        exe = self._executions.get(cell_id)
        if exe and exe.worker_id:
            w = self._workers.get(exe.worker_id)
            if w:
                w["info"]["running_cells"] = max(0, w["info"]["running_cells"] - 1)
                w["info"]["status"] = "busy" if w["info"]["running_cells"] > 0 else "idle"
        await self._relay_to_session(msg.get("session_id", ""), msg)

    async def _on_interrupt(self, msg):
        cell_id = msg.get("cell_id", "")
        exe = self._executions.get(cell_id)
        if exe and exe.worker_id:
            w = self._workers.get(exe.worker_id)
            if w:
                try:
                    await w["ws"].send_json(make_msg(
                        MsgType.CELL_INTERRUPT,
                        cell_id=cell_id, session_id=exe.session_id))
                except Exception:
                    pass

    # ── Routing ──────────────────────────────────────────────────────

    def _pick_worker(self, strategy: str = "least_loaded") -> Optional[str]:
        available = [
            (wid, w) for wid, w in self._workers.items()
            if w["info"]["status"] in ("idle", "busy")
            and w["info"]["running_cells"] < w["info"]["capabilities"].get("max_concurrent", 1)
        ]
        if not available:
            return None

        if strategy == "round_robin":
            self._rr_idx = (self._rr_idx + 1) % len(available)
            return available[self._rr_idx][0]
        elif strategy == "least_loaded":
            best = min(available, key=lambda x: x[1]["info"]["running_cells"])
            return best[0]
        return available[0][0]

    # ── Helpers ──────────────────────────────────────────────────────

    async def _relay_to_session(self, sid: str, msg: Dict[str, Any]):
        for c in self._clients.values():
            if sid in c["sessions"]:
                try:
                    await c["ws"].send_json(msg)
                except Exception:
                    pass

    async def _broadcast_workers(self):
        msg = make_msg(MsgType.WORKER_LIST,
                       workers=[w["info"] for w in self._workers.values()])
        for c in self._clients.values():
            try:
                await c["ws"].send_json(msg)
            except Exception:
                pass

    def _check_health(self):
        now = time.time()
        stale = [wid for wid, w in self._workers.items()
                 if now - w["info"]["last_heartbeat"] > 60]
        for wid in stale:
            log.warning("Worker %s timed out", wid)
            self._workers.pop(wid, None)

    async def _cleanup(self, ws):
        ws_id = id(ws)
        # Worker cleanup
        stale_workers = [wid for wid, w in self._workers.items() if id(w["ws"]) == ws_id]
        for wid in stale_workers:
            self._workers.pop(wid, None)
            log.info("Worker disconnected: %s", wid)
        # Client cleanup
        self._clients.pop(ws_id, None)
        if stale_workers:
            await self._broadcast_workers()


# ─── Entry Point ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Distributed Notebook Demo (gateway + web UI)")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8555)
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    server = DemoServer(host=args.host, port=args.port)
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        log.info("Demo stopped")


if __name__ == "__main__":
    main()
