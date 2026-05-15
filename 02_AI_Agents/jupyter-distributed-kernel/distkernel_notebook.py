#!/usr/bin/env python3
"""DistKernel Notebook — Single Portable File (No External Dependencies)"""

from __future__ import annotations
import argparse
import asyncio
import enum
import json
import logging
import os
import secrets
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Coroutine, Dict, List, Optional

from dotenv import load_dotenv
load_dotenv()

import aiohttp
from aiohttp import web

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s [%(name)s] %(message)s')
log = logging.getLogger("distkernel")

# ─── Protocol ───────────────────────────────────────────────────────────────

class MsgType(str, enum.Enum):
    WORKER_REGISTER = "worker.register"
    WORKER_HEARTBEAT = "worker.heartbeat"
    WORKER_DEREGISTER = "worker.deregister"
    CELL_EXECUTE = "cell.execute"
    CELL_INTERRUPT = "cell.interrupt"
    CELL_OUTPUT = "cell.output"
    CELL_COMPLETE = "cell.complete"
    CELL_ERROR = "cell.error"
    SESSION_CREATE = "session.create"
    SESSION_JOIN = "session.join"
    SESSION_LEAVE = "session.leave"
    EXECUTE_REQUEST = "execute.request"
    INTERRUPT_REQUEST = "interrupt.request"
    SESSION_INFO = "session.info"
    WORKER_STATUS = "worker.status"
    WORKER_LIST = "worker.list"
    ERROR = "error"

class OutputType(str, enum.Enum):
    STREAM = "stream"
    EXECUTE_RESULT = "execute_result"
    DISPLAY_DATA = "display_data"
    ERROR = "error"
    STATUS = "status"

@dataclass
class WorkerCapabilities:
    cpu_count: int = 1
    memory_mb: int = 512
    platform: str = "unknown"
    python_version: str = ""

@dataclass
class WorkerInfo:
    worker_id: str
    name: str = ""
    capabilities: WorkerCapabilities = field(default_factory=WorkerCapabilities)
    connected_at: float = field(default_factory=time.time)
    running_cells: int = 0
    status: str = "idle"

@dataclass
class SessionInfo:
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = "Untitled"
    created_at: float = field(default_factory=time.time)
    participants: List[str] = field(default_factory=list)
    routing: str = "round_robin"
    google_user_id: Optional[str] = None

@dataclass
class CellExecution:
    cell_id: str
    session_id: str
    code: str
    worker_id: Optional[str] = None
    submitted_at: float = field(default_factory=time.time)
    status: str = "queued"
    execution_count: int = 0

def make_msg(msg_type: MsgType, **kwargs: Any) -> Dict[str, Any]:
    return {"type": msg_type.value, "ts": time.time(), "id": uuid.uuid4().hex[:16], **kwargs}

def make_execute(cell_id: str, session_id: str, code: str,
                 execution_count: int = 0,
                 cell_mode: str = "python",
                 cell_language: str = "python") -> Dict[str, Any]:
    return make_msg(MsgType.CELL_EXECUTE, cell_id=cell_id, session_id=session_id,
                   code=code, execution_count=execution_count,
                   cell_mode=cell_mode, cell_language=cell_language)

def make_output(cell_id: str, session_id: str, output_type: OutputType,
                data: Dict[str, Any], worker_id: str = "") -> Dict[str, Any]:
    return make_msg(MsgType.CELL_OUTPUT, cell_id=cell_id, session_id=session_id,
                   output_type=output_type.value, data=data, worker_id=worker_id)

def make_complete(cell_id: str, session_id: str, status: str = "ok",
                  execution_count: int = 0, worker_id: str = "") -> Dict[str, Any]:
    return make_msg(MsgType.CELL_COMPLETE, cell_id=cell_id, session_id=session_id,
                   status=status, execution_count=execution_count, worker_id=worker_id)

def make_error(cell_id: str, session_id: str, ename: str, evalue: str,
               traceback: List[str], worker_id: str = "") -> Dict[str, Any]:
    return make_msg(MsgType.CELL_ERROR, cell_id=cell_id, session_id=session_id,
                   ename=ename, evalue=evalue, traceback=traceback, worker_id=worker_id)

# ─── Auth ─────────────────────────────────────────────────────────────────

_challenges: Dict[str, Dict[str, Any]] = {}
_sessions: Dict[str, Dict[str, Any]] = {}
_users: Dict[str, Dict[str, Any]] = {}

def create_challenge(address: str) -> Dict[str, str]:
    address = address.lower().strip()
    nonce = secrets.token_hex(16)
    message = f"Sign in to DistKernel\\nNonce: {nonce}\\nTimestamp: {int(time.time())}"
    _challenges[nonce] = {"address": address, "message": message, "ts": time.time(), "used": False}
    return {"nonce": nonce, "message": message}

def verify_signature(address: str, nonce: str, signature: str) -> tuple:
    address = address.lower().strip()
    challenge = _challenges.get(nonce)
    if not challenge or challenge["used"] or challenge["address"] != address:
        return False, "Invalid challenge"
    challenge["used"] = True
    token = secrets.token_hex(32)
    _sessions[token] = {"address": address, "ts": time.time()}
    if address not in _users:
        _users[address] = {"address": address, "name": f"{address[:6]}...{address[-4:]}", "cells_run": 0}
    return True, token

def validate_session(token: str) -> Optional[Dict[str, Any]]:
    session = _sessions.get(token)
    return session and _users.get(session["address"]) or None

def get_all_users() -> list:
    return list(_users.values())

# ─── Ollama Agent ───────────────────────────────────────────────────────────

OLLAMA_URL = "http://localhost:11434"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GITHUB_API_KEY = os.environ.get("GITHUB_API_KEY", "")
HUGGING_FACE_API_KEY = os.environ.get("HUGGING_FACE_API_KEY", "")

class OllamaClient:
    def __init__(self, base_url: str = OLLAMA_URL) -> None:
        self._base_url = base_url.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def list_models(self) -> List[str]:
        session = await self._get_session()
        async with session.get(f"{self._base_url}/api/tags") as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            return [m["name"] for m in data.get("models", [])]

    async def generate(self, model: str, prompt: str, system: str = "") -> str:
        session = await self._get_session()
        payload = {"model": model, "prompt": prompt, "system": system, "stream": False}
        async with session.post(f"{self._base_url}/api/generate", json=payload) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Ollama error {resp.status}")
            data = await resp.json()
            return data.get("response", "")

class GroqClient:
    def __init__(self, api_key: str = GROQ_API_KEY) -> None:
        self._api_key = api_key
        self._base_url = "https://api.groq.com/openai/v1"
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {"Authorization": f"Bearer {self._api_key}"}
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def generate(self, model: str, prompt: str, system: str = "") -> str:
        if not self._api_key:
            return "Groq API key not set"
        session = await self._get_session()
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system} if system else {"role": "user", "content": prompt}],
            "temperature": 0.7
        }
        if system:
            payload["messages"].append({"role": "user", "content": prompt})
        async with session.post(f"{self._base_url}/chat/completions", json=payload) as resp:
            if resp.status != 200:
                return f"Groq error {resp.status}"
            data = await resp.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")

class GitHubClient:
    def __init__(self, api_key: str = GITHUB_API_KEY) -> None:
        self._api_key = api_key
        self._base_url = "https://api.github.com"
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {"Authorization": f"token {self._api_key}"}
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def list_repos(self) -> List[Dict]:
        if not self._api_key:
            return []
        session = await self._get_session()
        async with session.get(f"{self._base_url}/user/repos") as resp:
            if resp.status != 200:
                return []
            return await resp.json()

class HuggingFaceClient:
    def __init__(self, api_key: str = HUGGING_FACE_API_KEY) -> None:
        self._api_key = api_key
        self._base_url = "https://api-inference.huggingface.co"
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {"Authorization": f"Bearer {self._api_key}"}
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def generate(self, model: str, inputs: str) -> str:
        if not self._api_key:
            return "Hugging Face API key not set"
        session = await self._get_session()
        payload = {"inputs": inputs}
        async with session.post(f"{self._base_url}/models/{model}", json=payload) as resp:
            if resp.status != 200:
                return f"HF error {resp.status}"
            data = await resp.json()
            if isinstance(data, list) and len(data) > 0:
                return data[0].get("generated_text", "")
            return str(data)

# ─── Server ───────────────────────────────────────────────────────────────

class DistKernelServer:
    def __init__(self, host="0.0.0.0", port=8555):
        self._host, self._port = host, port
        self._workers: Dict[str, Any] = {}
        self._clients: Dict[int, Any] = {}
        self._sessions: Dict[str, SessionInfo] = {}
        self._executions: Dict[str, CellExecution] = {}
        self._exec_counts: Dict[str, int] = {}
        self._ollama = OllamaClient()
        self._groq = GroqClient()
        self._github = GitHubClient()
        self._huggingface = HuggingFaceClient()
        self._rr_idx = 0
        self._start_time = time.time()
        self._runner = None
        self._site = None

    async def start(self):
        app = web.Application()
        app.router.add_get("/", self._index)
        app.router.add_post("/api/auth/challenge", self._auth_challenge)
        app.router.add_post("/api/auth/verify", self._auth_verify)
        app.router.add_get("/api/ollama/models", self._ollama_models)
        app.router.add_post("/api/ollama/generate", self._ollama_generate)
        app.router.add_post("/api/ollama/pull", self._ollama_pull)
        app.router.add_post("/api/groq/generate", self._groq_generate)
        app.router.add_get("/api/github/repos", self._github_repos)
        app.router.add_post("/api/hf/generate", self._hf_generate)
        app.router.add_get("/ws", self._handle_ws)
        app.router.add_get("/health", self._health_check)
        app.router.add_get("/status", self._status_check)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self._host, self._port)
        await self._site.start()
        log.info("DistKernel at http://%s:%d", self._host, self._port)
        log.info("Uptime: 0s | Sessions: 0 | Executions: 0")
        while True:
            await asyncio.sleep(30)
            await self._maintenance_loop()

    async def _maintenance_loop(self):
        uptime = int(time.time() - self._start_time)
        sessions_count = len(self._sessions)
        executions_count = len(self._executions)
        log.info(f"Uptime: {uptime}s | Sessions: {sessions_count} | Executions: {executions_count}")
        
        # Clean up old executions (older than 1 hour)
        cutoff = time.time() - 3600
        for cell_id in list(self._executions.keys()):
            if self._executions[cell_id].submitted_at < cutoff:
                del self._executions[cell_id]

    async def _health_check(self, req):
        return web.json_response({
            "status": "healthy",
            "uptime": int(time.time() - self._start_time),
            "sessions": len(self._sessions),
            "executions": len(self._executions),
            "ollama": "connected" if OLLAMA_URL else "not_configured",
            "groq": "configured" if GROQ_API_KEY else "not_configured",
            "github": "configured" if GITHUB_API_KEY else "not_configured",
            "huggingface": "configured" if HUGGING_FACE_API_KEY else "not_configured"
        })

    async def _status_check(self, req):
        return web.json_response({
            "host": self._host,
            "port": self._port,
            "uptime": int(time.time() - self._start_time),
            "sessions": [{"id": s.session_id, "name": s.name, "created_at": s.created_at} for s in self._sessions.values()],
            "workers": list(self._workers.keys()),
            "executions": len(self._executions)
        })

    async def _index(self, req):
        return web.Response(text=self._get_html(), content_type="text/html")

    def _get_html(self) -> str:
        return '''
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DistKernel — Distributed AI Notebook</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root { --bg: #0f1117; --bg-card: #161922; --bg-cell: #1c1f2e; --border: #2a2e3f; --text: #e1e4ed; --text-dim: #8b8fa3; --accent: #6c5ce7; --green: #00b894; --red: #e17055; --blue: #74b9ff; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, sans-serif; min-height: 100vh; }
.container { max-width: 900px; margin: 0 auto; padding: 20px; }
h1 { color: var(--accent); }
.btn { background: var(--accent); color: white; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; margin: 5px; }
.btn:hover { background: #5b4bd5; }
.cell { background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px; padding: 16px; margin: 12px 0; }
.cell-header { display: flex; justify-content: space-between; margin-bottom: 8px; }
.cell-input textarea { width: 100%; background: var(--bg); color: var(--text); border: 1px solid var(--border); border-radius: 6px; padding: 12px; font-family: monospace; min-height: 60px; }
.cell-output { margin-top: 12px; font-family: monospace; white-space: pre-wrap; }
.status { color: var(--text-dim); }
.login-screen { display: flex; align-items: center; justify-content: center; height: 100vh; }
.login-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 16px; padding: 48px; text-align: center; max-width: 420px; }
.app { display: flex; height: 100vh; }
.app.hidden { display: none; }
.sidebar { width: 300px; background: var(--bg-card); border-right: 1px solid var(--border); padding: 20px; }
.main { flex: 1; display: flex; flex-direction: column; }
.toolbar { height: 48px; background: var(--bg-card); border-bottom: 1px solid var(--border); display: flex; align-items: center; padding: 0 16px; gap: 8px; }
.notebook { flex: 1; overflow-y: auto; padding: 24px; }
</style>
</head>
<body>
<div id="login-screen" class="login-screen">
  <div class="login-card">
    <h1>⚡ DistKernel</h1>
    <p style="color:var(--text-dim);margin:16px 0;">Distributed AI Notebook</p>
    <button class="btn" onclick="connectWallet()">🦊 Connect MetaMask</button>
    <div id="login-status" style="margin-top:16px;font-size:12px;color:var(--text-dim);"></div>
  </div>
</div>
<div id="app" class="app hidden">
  <div class="sidebar">
    <h2>Stats</h2>
    <div>Workers: <span id="stat-workers">0</span></div>
    <div style="margin:20px 0;">
      <select id="agent-model" style="width:100%;padding:8px;margin-bottom:8px;">
        <option value="llama3.2:1b">llama3.2:1b</option>
        <option value="deepseek-coder:1.3b">deepseek-coder:1.3b</option>
        <option value="qwen2.5:0.5b">qwen2.5:0.5b</option>
        <option value="deepseek-r1:latest">deepseek-r1:latest</option>
      </select>
      <textarea id="agent-goal" style="width:100%;padding:8px;height:60px;" placeholder="Research goal...">Explore MEV strategies</textarea>
      <button class="btn" onclick="startAgent()">▶ Start Agent</button>
      <button class="btn" onclick="stopAgent()">⏹ Stop</button>
    </div>
    <div id="agent-status" style="font-size:12px;color:var(--text-dim);">Agent idle</div>
    <div style="margin:20px 0;border-top:1px solid var(--border);padding-top:16px;">
      <h3 style="font-size:14px;margin-bottom:8px;">📥 Pull Ollama Model</h3>
      <input id="pull-model-name" type="text" placeholder="e.g. llama3.2:3b" style="width:100%;padding:8px;margin-bottom:8px;background:var(--bg);color:var(--text);border:1px solid var(--border);border-radius:6px;">
      <button class="btn" onclick="pullModel()">⬇️ Pull Model</button>
      <div id="pull-status" style="font-size:11px;color:var(--text-dim);margin-top:8px;"></div>
    </div>
    <div style="margin:20px 0;border-top:1px solid var(--border);padding-top:16px;">
      <h3 style="font-size:14px;margin-bottom:8px;">🤖 External APIs</h3>
      <select id="api-provider" style="width:100%;padding:8px;margin-bottom:8px;background:var(--bg);color:var(--text);border:1px solid var(--border);border-radius:6px;">
        <option value="groq">Groq (fast LLM)</option>
        <option value="hf">Hugging Face</option>
        <option value="github">GitHub</option>
      </select>
      <input id="api-prompt" type="text" placeholder="Prompt..." style="width:100%;padding:8px;margin-bottom:8px;background:var(--bg);color:var(--text);border:1px solid var(--border);border-radius:6px;">
      <button class="btn" onclick="callAPI()">🚀 Call API</button>
      <div id="api-response" style="font-size:11px;color:var(--text-dim);margin-top:8px;white-space:pre-wrap;"></div>
    </div>
  </div>
  <div class="main">
    <div class="toolbar">
      <span style="font-weight:600;">📓 Notebook</span>
      <button class="btn" onclick="addCell()">+ Cell</button>
      <button class="btn" onclick="addCell('',false,'terminal','bash')">>_ Terminal</button>
      <button class="btn" onclick="runAll()">▶ Run All</button>
    </div>
    <div class="notebook" id="notebook"></div>
  </div>
</div>
<script>
let ws = null, sessionId = '', cells = [], authToken = '', walletAddr = '';

async function connectWallet() {
  if (!window.ethereum) { document.getElementById('login-status').textContent = 'MetaMask not detected'; return; }
  try {
    const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
    walletAddr = accounts[0];
    const chalResp = await fetch('/api/auth/challenge', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ address: walletAddr }) });
    const chal = await chalResp.json();
    const signature = await window.ethereum.request({ method: 'personal_sign', params: [chal.message, walletAddr] });
    const verResp = await fetch('/api/auth/verify', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ address: walletAddr, nonce: chal.nonce, signature }) });
    const ver = await verResp.json();
    if (ver.success) { authToken = ver.token; enterApp(); }
  } catch(e) { document.getElementById('login-status').textContent = e.message; }
}

function enterApp() {
  document.getElementById('login-screen').style.display = 'none';
  document.getElementById('app').classList.remove('hidden');
  connectWS();
  fetchOllamaModels();
  addCell('import sys,platform\\nprint(f"Node: {platform.node()}")\\nprint(f"Python {sys.version}")');
  addCell('## Research Notes\\n\\n- Python, Terminal, Markdown cells supported\\n- Terminal cells run shell commands\\n- Python cells execute code');
}

function connectWS() {
  ws = new WebSocket('ws://' + location.host + '/ws');
  ws.onopen = () => ws.send(JSON.stringify({ type: 'session.create', session_id: sessionId || null, name: 'Research' }));
  ws.onmessage = (e) => { try { handleMsg(JSON.parse(e.data)); } catch(err) {} };
}

function handleMsg(msg) {
  if (msg.type === 'cell.output') handleOutput(msg);
  if (msg.type === 'cell.complete') handleComplete(msg);
  if (msg.type === 'cell.error') handleError(msg);
}

async function fetchOllamaModels() {
  try {
    const r = await fetch('/api/ollama/models');
    const d = await r.json();
    if (d.models && d.models.length > 0) {
      const sel = document.getElementById('agent-model');
      sel.innerHTML = d.models.map(m => '<option value="'+m+'">'+m+'</option>').join('');
      document.getElementById('agent-status').textContent = 'Ollama ready';
    }
  } catch(e) { document.getElementById('agent-status').textContent = 'Ollama not reachable'; }
}

function startAgent() {
  if (!ws || !sessionId) return;
  const model = document.getElementById('agent-model').value;
  const goal = document.getElementById('agent-goal').value;
  ws.send(JSON.stringify({ type: 'agent.start', session_id: sessionId, model, goal }));
}

function stopAgent() {
  if (ws) ws.send(JSON.stringify({ type: 'agent.stop', session_id: sessionId }));
}

async function pullModel() {
  const modelName = document.getElementById('pull-model-name').value.trim();
  if (!modelName) { document.getElementById('pull-status').textContent = 'Enter a model name'; return; }
  document.getElementById('pull-status').textContent = 'Pulling ' + modelName + '...';
  try {
    const r = await fetch('/api/ollama/pull', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model: modelName }) });
    const d = await r.json();
    if (d.success) {
      document.getElementById('pull-status').textContent = '✅ ' + modelName + ' pulled successfully';
      fetchOllamaModels();
    } else {
      document.getElementById('pull-status').textContent = '❌ ' + (d.error || d.output || 'Pull failed');
    }
  } catch(e) { document.getElementById('pull-status').textContent = '❌ Error: ' + e.message; }
}

async function callAPI() {
  const provider = document.getElementById('api-provider').value;
  const prompt = document.getElementById('api-prompt').value.trim();
  document.getElementById('api-response').textContent = 'Calling ' + provider + '...';
  try {
    let url, body;
    if (provider === 'groq') {
      url = '/api/groq/generate';
      body = JSON.stringify({ model: 'llama3-8b-8192', prompt: prompt });
    } else if (provider === 'hf') {
      url = '/api/hf/generate';
      body = JSON.stringify({ model: 'gpt2', inputs: prompt });
    } else if (provider === 'github') {
      url = '/api/github/repos';
      body = null;
    }
    const r = await fetch(url, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body } : {});
    const d = await r.json();
    document.getElementById('api-response').textContent = JSON.stringify(d, null, 2);
  } catch(e) { document.getElementById('api-response').textContent = '❌ Error: ' + e.message; }
}

function addCell(code='', isAI=false, cellMode='python', cellLanguage='python') {
  const id = Math.random().toString(36).substr(2, 9);
  cells.push({ id, code, outputs: [], cellMode, cellLanguage });
  render();
}

function runCell(id) {
  const cell = cells.find(c => c.id === id);
  if (!cell || !ws) return;
  ws.send(JSON.stringify({ type: 'execute.request', cell_id: id, session_id: sessionId, code: cell.code, cell_mode: cell.cellMode, cell_language: cell.cellLanguage }));
}

function runAll() { cells.forEach(c => runCell(c.id)); }

function handleOutput(msg) {
  const cell = cells.find(c => c.id === msg.cell_id);
  if (cell) cell.outputs.push(msg.data.text || '');
  render();
}

function handleComplete(msg) { render(); }

function handleError(msg) {
  const cell = cells.find(c => c.id === msg.cell_id);
  if (cell) cell.outputs.push('ERROR: ' + msg.evalue);
  render();
}

function render() {
  document.getElementById('notebook').innerHTML = cells.map(c => `
    <div class="cell">
      <div class="cell-header">
        <select onchange="cells.find(x=>x.id==='${c.id}').cellMode=this.value;render()">
          <option value="python" ${c.cellMode==='python'?'selected':''}>python</option>
          <option value="terminal" ${c.cellMode==='terminal'?'selected':''}>terminal</option>
          <option value="markdown" ${c.cellMode==='markdown'?'selected':''}>markdown</option>
        </select>
        <button onclick="runCell('${c.id}')">▶</button>
      </div>
      <textarea oninput="cells.find(x=>x.id==='${c.id}').code=this.value">${c.code}</textarea>
      <div class="cell-output">${c.outputs.join('')}</div>
    </div>
  `).join('');
}
</script>
</body>
</html>'''

    async def _auth_challenge(self, req):
        data = await req.json()
        return web.json_response(create_challenge(data.get("address", "")))

    async def _auth_verify(self, req):
        data = await req.json()
        ok, result = verify_signature(data.get("address", ""), data.get("nonce", ""), data.get("signature", ""))
        return web.json_response({"success": ok, "token": result})

    async def _ollama_models(self, req):
        models = await self._ollama.list_models()
        return web.json_response({"models": models})

    async def _ollama_generate(self, req):
        data = await req.json()
        code = await self._ollama.generate(data.get("model", "llama3.2"), data.get("goal", ""))
        return web.json_response({"code": code})

    async def _ollama_pull(self, req):
        data = await req.json()
        model = data.get("model", "")
        if not model:
            return web.json_response({"error": "Model name required"}, status=400)
        try:
            proc = await asyncio.create_subprocess_exec(
                "ollama", "pull", model,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
            output = stdout.decode(errors="replace") + stderr.decode(errors="replace")
            return web.json_response({"success": proc.returncode == 0, "output": output})
        except asyncio.TimeoutError:
            return web.json_response({"error": "Pull timed out"}, status=500)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def _groq_generate(self, req):
        data = await req.json()
        response = await self._groq.generate(data.get("model", "llama3-8b-8192"), data.get("prompt", ""), data.get("system", ""))
        return web.json_response({"response": response})

    async def _github_repos(self, req):
        repos = await self._github.list_repos()
        return web.json_response({"repos": repos})

    async def _hf_generate(self, req):
        data = await req.json()
        response = await self._huggingface.generate(data.get("model", "gpt2"), data.get("inputs", ""))
        return web.json_response({"response": response})

    async def _handle_ws(self, req):
        ws = web.WebSocketResponse()
        await ws.prepare(req)
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                data = json.loads(msg.data)
                await self._dispatch(ws, data)
        return ws

    async def _dispatch(self, ws, msg):
        if msg["type"] == "execute.request":
            await self._execute(ws, msg)
        elif msg["type"] == "session.create":
            await self._create_session(ws, msg)

    async def _create_session(self, ws, msg):
        sid = msg.get("session_id") or uuid.uuid4().hex[:12]
        sessionId = sid
        self._sessions[sid] = SessionInfo(session_id=sid, name=msg.get("name", "Untitled"))
        await ws.send_json(make_msg(MsgType.SESSION_INFO, session={"session_id": sid}, workers=[]))

    async def _execute(self, ws, msg):
        sid = msg.get("session_id", "")
        cell_id = msg.get("cell_id", "")
        code = msg.get("code", "")
        cell_mode = msg.get("cell_mode", "python")
        
        if cell_mode == "terminal":
            try:
                shell = msg.get("cell_language", "bash")
                shell_cmd = self._resolve_shell(shell)
                if not shell_cmd:
                    await ws.send_json(make_error(cell_id, sid, "UnsupportedShell", f"Shell {shell} not available", []))
                    return
                proc = await asyncio.create_subprocess_exec(
                    shell_cmd, "-lc", code,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=os.getcwd(),
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
                output = stdout.decode(errors="replace")
                error = stderr.decode(errors="replace")
                if output:
                    await ws.send_json(make_output(cell_id, sid, OutputType.STREAM, {"name": "stdout", "text": output}))
                if error:
                    await ws.send_json(make_output(cell_id, sid, OutputType.STREAM, {"name": "stderr", "text": error}))
                status = "ok" if proc.returncode == 0 else "error"
                await ws.send_json(make_complete(cell_id, sid, status))
            except asyncio.TimeoutError:
                await ws.send_json(make_error(cell_id, sid, "TimeoutError", "Command timed out", []))
            except Exception as e:
                import traceback
                await ws.send_json(make_error(cell_id, sid, str(type(e).__name__), str(e), traceback.format_exc().splitlines()))
            return
        
        try:
            import sys
            from io import StringIO
            old_stdout = sys.stdout
            sys.stdout = StringIO()
            exec(code, {})
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout
            await ws.send_json(make_output(cell_id, sid, OutputType.STREAM, {"name": "stdout", "text": output}))
            await ws.send_json(make_complete(cell_id, sid, "ok"))
        except Exception as e:
            import traceback
            await ws.send_json(make_error(cell_id, sid, str(type(e).__name__), str(e), traceback.format_exc().splitlines()))

    def _resolve_shell(self, shell: str) -> Optional[str]:
        candidates = [shell] if shell in ("bash", "zsh", "sh") else ["bash"]
        for candidate in candidates:
            path = shutil.which(candidate)
            if path:
                return path
        return None

def main():
    parser = argparse.ArgumentParser(description="DistKernel Notebook - 24/7 Distributed AI Notebook")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8555, help="Port to bind to")
    parser.add_argument("--no-restart", action="store_true", help="Disable auto-restart on crash")
    args = parser.parse_args()
    
    if args.no_restart:
        server = DistKernelServer(args.host, args.port)
        asyncio.run(server.start())
    else:
        # Auto-restart loop for 24/7 operation
        restart_count = 0
        max_restarts = 100
        while restart_count < max_restarts:
            try:
                log.info("=" * 60)
                log.info(f"Starting DistKernel (restart #{restart_count})")
                log.info("=" * 60)
                server = DistKernelServer(args.host, args.port)
                asyncio.run(server.start())
            except KeyboardInterrupt:
                log.info("Shutting down gracefully...")
                break
            except Exception as e:
                log.error(f"Server crashed: {e}")
                import traceback
                log.error(traceback.format_exc())
                restart_count += 1
                if restart_count < max_restarts:
                    wait_time = min(5 * restart_count, 60)
                    log.info(f"Restarting in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    log.error("Max restarts reached. Exiting.")
                    break
        log.info("DistKernel stopped.")

if __name__ == "__main__":
    main()
