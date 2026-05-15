import argparse
import base64
import json
import os
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timezone

import requests
from flask import Flask, Response, jsonify, request


DEFAULT_LOG_FILES = ["llama_agent.log", "market_maker.log", "marinade_deploy.log"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class OverseerDB:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS agents (
                    agent_id TEXT PRIMARY KEY,
                    display_name TEXT,
                    kind TEXT,
                    status TEXT,
                    last_seen_utc TEXT,
                    details_json TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS heartbeats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    ts_utc TEXT NOT NULL,
                    status TEXT,
                    details_json TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS commands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    created_utc TEXT NOT NULL,
                    command TEXT NOT NULL,
                    args_json TEXT,
                    status TEXT NOT NULL DEFAULT 'queued',
                    processed_utc TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS voice_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    ts_utc TEXT NOT NULL,
                    is_final INTEGER NOT NULL,
                    transcript TEXT NOT NULL,
                    meta_json TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS screen_frames (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    ts_utc TEXT NOT NULL,
                    width INTEGER,
                    height INTEGER,
                    mime TEXT,
                    file_path TEXT NOT NULL,
                    sha256 TEXT
                )
                """
            )
            self._conn.commit()

    def upsert_agent(self, agent_id: str, display_name: str, kind: str, status: str, details_json: str | None) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO agents (agent_id, display_name, kind, status, last_seen_utc, details_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(agent_id) DO UPDATE SET
                    display_name=excluded.display_name,
                    kind=excluded.kind,
                    status=excluded.status,
                    last_seen_utc=excluded.last_seen_utc,
                    details_json=excluded.details_json
                """,
                (agent_id, display_name, kind, status, utc_now_iso(), details_json),
            )
            self._conn.commit()

    def insert_heartbeat(self, agent_id: str, status: str, details_json: str | None) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "INSERT INTO heartbeats (agent_id, ts_utc, status, details_json) VALUES (?, ?, ?, ?)",
                (agent_id, utc_now_iso(), status, details_json),
            )
            self._conn.commit()

    def queue_command(self, agent_id: str, command: str, args_json: str | None) -> int:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "INSERT INTO commands (agent_id, created_utc, command, args_json) VALUES (?, ?, ?, ?)",
                (agent_id, utc_now_iso(), command, args_json),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def list_agents(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT agent_id, display_name, kind, status, last_seen_utc, details_json FROM agents ORDER BY agent_id"
            ).fetchall()
        return [dict(r) for r in rows]

    def list_heartbeats(self, limit: int) -> list[dict]:
        limit = max(1, min(int(limit), 500))
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, agent_id, ts_utc, status, details_json FROM heartbeats ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def fetch_commands(self, agent_id: str, limit: int) -> list[dict]:
        limit = max(1, min(int(limit), 200))
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, agent_id, created_utc, command, args_json, status
                FROM commands
                WHERE agent_id=? AND status='queued'
                ORDER BY id ASC
                LIMIT ?
                """,
                (agent_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_command_processed(self, command_id: int, status: str = "processed") -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE commands SET status=?, processed_utc=? WHERE id=?",
                (status, utc_now_iso(), int(command_id)),
            )
            self._conn.commit()

    def insert_voice_event(
        self,
        session_id: str | None,
        is_final: bool,
        transcript: str,
        meta_json: str | None,
    ) -> int:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "INSERT INTO voice_events (session_id, ts_utc, is_final, transcript, meta_json) VALUES (?, ?, ?, ?, ?)",
                (session_id, utc_now_iso(), 1 if is_final else 0, transcript, meta_json),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def list_voice_events(self, limit: int) -> list[dict]:
        limit = max(1, min(int(limit), 500))
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, session_id, ts_utc, is_final, transcript, meta_json
                FROM voice_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def insert_screen_frame(
        self,
        session_id: str | None,
        width: int | None,
        height: int | None,
        mime: str | None,
        file_path: str,
        sha256: str | None,
    ) -> int:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO screen_frames (session_id, ts_utc, width, height, mime, file_path, sha256)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, utc_now_iso(), width, height, mime, file_path, sha256),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def get_latest_frame(self) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT id, session_id, ts_utc, width, height, mime, file_path, sha256
                FROM screen_frames
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
        return dict(row) if row else None

    def delete_frames_older_than_id(self, keep_last_n: int) -> list[str]:
        keep_last_n = max(1, min(int(keep_last_n), 5000))
        with self._lock:
            ids = self._conn.execute(
                "SELECT id FROM screen_frames ORDER BY id DESC LIMIT ?",
                (keep_last_n,),
            ).fetchall()
            keep_ids = {int(r[0]) for r in ids}
            rows = self._conn.execute(
                "SELECT id, file_path FROM screen_frames ORDER BY id ASC"
            ).fetchall()
            delete_paths: list[str] = []
            delete_ids: list[int] = []
            for r in rows:
                fid = int(r[0])
                if fid not in keep_ids:
                    delete_ids.append(fid)
                    delete_paths.append(str(r[1]))
            if delete_ids:
                q = ",".join(["?"] * len(delete_ids))
                self._conn.execute(f"DELETE FROM screen_frames WHERE id IN ({q})", delete_ids)
                self._conn.commit()
        return delete_paths


def tail_file(path: str, max_lines: int = 120) -> str:
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            end = f.tell()
            block = 4096
            data = b""
            pos = end
            while pos > 0 and data.count(b"\n") <= max_lines:
                step = block if pos >= block else pos
                pos -= step
                f.seek(pos)
                data = f.read(step) + data
            text = data.decode("utf-8", errors="replace")
            return "\n".join(text.splitlines()[-max_lines:])
    except FileNotFoundError:
        return ""
    except Exception as e:
        return f"[overseer] tail failed: {e}"


def build_app(db: OverseerDB, llama_url: str, poll_interval_s: int, log_files: list[str]) -> Flask:
    app = Flask(__name__)

    frames_dir = os.path.abspath("overseer_frames")
    os.makedirs(frames_dir, exist_ok=True)
    frames_keep_last = 60

    db.upsert_agent("llama_autonomous_agent", "Llama Autonomous Agent", "poll", "unknown", None)
    for lf in log_files:
        db.upsert_agent(f"log:{lf}", f"Log: {lf}", "log", "unknown", None)

    def poller() -> None:
        while True:
            # Llama poll
            try:
                r = requests.get(f"{llama_url.rstrip('/')}/api/status", timeout=3)
                ok = r.status_code == 200
                payload = r.json() if ok else {"http_status": r.status_code}
                st = "ok" if ok else "error"
                db.upsert_agent("llama_autonomous_agent", "Llama Autonomous Agent", "poll", st, str(payload))
                db.insert_heartbeat("llama_autonomous_agent", st, str(payload))
            except Exception as e:
                details = {"error": str(e)}
                db.upsert_agent("llama_autonomous_agent", "Llama Autonomous Agent", "poll", "error", str(details))
                db.insert_heartbeat("llama_autonomous_agent", "error", str(details))

            # Log presence heartbeat
            for lf in log_files:
                p = os.path.abspath(lf)
                exists = os.path.exists(p)
                st = "ok" if exists else "missing"
                details = {"path": p, "exists": exists}
                db.upsert_agent(f"log:{lf}", f"Log: {lf}", "log", st, str(details))
                db.insert_heartbeat(f"log:{lf}", st, str(details))

            time.sleep(max(1, int(poll_interval_s)))

    threading.Thread(target=poller, daemon=True).start()

    INDEX = """<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Overseer</title>
<style>
body{font-family:ui-sans-serif,system-ui;margin:16px;max-width:1100px}
table{border-collapse:collapse;width:100%}
td,th{border:1px solid #ddd;padding:8px;vertical-align:top}
th{background:#f6f6f6}
pre{background:#0b0b0b;color:#e6e6e6;padding:12px;overflow:auto;max-height:360px}
input,button,select{padding:8px;font-size:14px}
.row{display:flex;gap:12px;flex-wrap:wrap;align-items:center}
.card{border:1px solid #ddd;border-radius:8px;padding:12px;flex:1;min-width:280px}
.muted{opacity:0.75}
img{max-width:100%;height:auto;border:1px solid #ddd;border-radius:8px}
@media (max-width: 640px){body{margin:10px} input{width:100%!important}}
</style>
</head><body>
<h2>Overseer</h2>
<div class='row'>
  <div class='card'>
    <div class='row'>
      <div><b>Speech:</b></div>
      <button id='speakNow'>Speak now</button>
      <button id='toggleMute'>Mute: off</button>
      <span id='speechStatus' class='muted'></span>
    </div>
    <div class='row' style='margin-top:10px'>
      <div><b>Voice (STT):</b></div>
      <button id='toggleListen'>Listening: off</button>
      <span id='sttStatus' class='muted'></span>
    </div>
    <div style='margin-top:10px'>
      <div><b>Command:</b></div>
      <div class='row' style='margin-top:6px'>
        <input id='cmd' style='width:520px' placeholder='pause llama_autonomous_agent'/>
        <button id='send'>Send</button>
      </div>
      <div class='muted' style='margin-top:6px'>Voice commands are stored in SQLite and can also enqueue overseer commands.</div>
    </div>
  </div>
  <div class='card'>
    <div class='row'>
      <div><b>Screen:</b></div>
      <button id='toggleScreen'>Capture: off</button>
      <span id='screenStatus' class='muted'></span>
    </div>
    <div style='margin-top:10px'><img id='screenImg' alt='Latest frame will appear here'/></div>
    <div class='muted' style='margin-top:6px'>Frames are saved on disk with rolling retention.</div>
  </div>
</div>
<br/>
<table><thead><tr><th>agent_id</th><th>status</th><th>last_seen_utc</th><th>kind</th></tr></thead><tbody id='agents'></tbody></table>
<br/>
<div><b>Selected log tail:</b> <select id='logSel'></select> <button id='refreshLog'>Refresh</button></div>
<pre id='log'></pre>
<script>
const SPEAK_INTERVAL_MS = 30000;
let lastSpoken = 0;
let muted = false;
let listening = false;
let recognition = null;
let screenStream = null;
let screenTimer = null;
const VOICE_SESSION_ID = (crypto && crypto.randomUUID) ? crypto.randomUUID() : (String(Date.now()) + Math.random());
function speak(text){
  if(muted) return;
  try{const u=new SpeechSynthesisUtterance(text); u.rate=1; window.speechSynthesis.cancel(); window.speechSynthesis.speak(u); document.getElementById('speechStatus').innerText='speaking'; u.onend=()=>document.getElementById('speechStatus').innerText='';}catch(e){}
}
function summarize(agents){
  const bad=agents.filter(a=>a.status!=='ok');
  if(bad.length===0) return `All agents OK. ${agents.length} agents reporting.`;
  return `${bad.length} agents need attention: ` + bad.map(a=>a.agent_id+': '+a.status).join(', ');
}
function safeText(td, v){ td.textContent = (v===undefined || v===null) ? '' : String(v); }
async function load(){
  const a=await fetch('/api/agents').then(r=>r.json());
  const tb=document.getElementById('agents'); tb.innerHTML='';
  for(const row of a.agents){
    const tr=document.createElement('tr');
    const td1=document.createElement('td'); safeText(td1, row.agent_id);
    const td2=document.createElement('td'); safeText(td2, row.status);
    const td3=document.createElement('td'); safeText(td3, row.last_seen_utc||'');
    const td4=document.createElement('td'); safeText(td4, row.kind||'');
    tr.appendChild(td1); tr.appendChild(td2); tr.appendChild(td3); tr.appendChild(td4);
    tb.appendChild(tr);
  }
  // populate log selector
  const sel=document.getElementById('logSel');
  const logs=a.agents.filter(x=>x.agent_id.startsWith('log:')).map(x=>x.agent_id.substring(4));
  if(sel.options.length===0){
    for(const lf of logs){const opt=document.createElement('option'); opt.value=lf; opt.innerText=lf; sel.appendChild(opt);} 
  }
  const now=Date.now();
  if(now-lastSpoken>SPEAK_INTERVAL_MS){ lastSpoken=now; speak(summarize(a.agents)); }
}
async function refreshLog(){
  const lf=document.getElementById('logSel').value;
  const t=await fetch('/api/log_tail?file='+encodeURIComponent(lf)).then(r=>r.text());
  document.getElementById('log').innerText=t;
}
async function refreshLatestFrame(){
  try{
    const r = await fetch('/api/screen_latest', {cache:'no-store'});
    if(r.status !== 200){ return; }
    const b = await r.blob();
    const url = URL.createObjectURL(b);
    const img = document.getElementById('screenImg');
    img.src = url;
    setTimeout(()=>URL.revokeObjectURL(url), 5000);
  }catch(e){}
}
async function postVoiceEvent(transcript, isFinal){
  try{
    await fetch('/api/voice_event', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({session_id: VOICE_SESSION_ID, transcript, is_final: !!isFinal})});
  }catch(e){}
}
async function postVoiceCommand(transcript){
  try{
    const res = await fetch('/api/voice_command', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({session_id: VOICE_SESSION_ID, transcript})}).then(r=>r.json());
    if(res && res.reply_text){ speak(res.reply_text); }
  }catch(e){}
}
function startListening(){
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if(!SR){ document.getElementById('sttStatus').innerText = 'SpeechRecognition not supported in this browser'; return; }
  recognition = new SR();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = 'en-US';
  recognition.onresult = (ev)=>{
    let interim='';
    for(let i=ev.resultIndex; i<ev.results.length; i++){
      const r = ev.results[i];
      const text = r[0] && r[0].transcript ? r[0].transcript.trim() : '';
      if(!text) continue;
      if(r.isFinal){ postVoiceEvent(text, true); postVoiceCommand(text); }
      else{ interim = text; postVoiceEvent(text, false); }
    }
    document.getElementById('sttStatus').innerText = interim ? ('hearing: ' + interim) : '';
  };
  recognition.onerror = (e)=>{ document.getElementById('sttStatus').innerText = 'stt error: ' + (e && e.error ? e.error : 'unknown'); };
  recognition.onend = ()=>{ if(listening){ try{ recognition.start(); }catch(e){} } };
  try{ recognition.start(); listening = true; document.getElementById('toggleListen').innerText = 'Listening: on'; }catch(e){ document.getElementById('sttStatus').innerText = String(e); }
}
function stopListening(){
  listening = false;
  document.getElementById('toggleListen').innerText = 'Listening: off';
  try{ if(recognition){ recognition.onend = null; recognition.stop(); } }catch(e){}
  recognition = null;
  document.getElementById('sttStatus').innerText = '';
}
async function startScreenCapture(){
  try{
    screenStream = await navigator.mediaDevices.getDisplayMedia({video:true, audio:false});
    const video = document.createElement('video');
    video.srcObject = screenStream;
    await video.play();
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    document.getElementById('screenStatus').innerText = 'capturing';
    document.getElementById('toggleScreen').innerText = 'Capture: on';
    screenTimer = setInterval(async ()=>{
      try{
        const w = video.videoWidth || 1280;
        const h = video.videoHeight || 720;
        const targetW = 960;
        const scale = targetW / w;
        canvas.width = targetW;
        canvas.height = Math.max(1, Math.round(h * scale));
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        const dataUrl = canvas.toDataURL('image/jpeg', 0.65);
        const jpeg_b64 = dataUrl.split(',')[1];
        await fetch('/api/screen_frame', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({session_id: VOICE_SESSION_ID, mime:'image/jpeg', width: canvas.width, height: canvas.height, jpeg_b64})});
        refreshLatestFrame();
      }catch(e){}
    }, 1000);
    const track = screenStream.getVideoTracks()[0];
    if(track){ track.onended = ()=>{ stopScreenCapture(); }; }
  }catch(e){ document.getElementById('screenStatus').innerText = 'capture error: ' + String(e); }
}
function stopScreenCapture(){
  try{ if(screenTimer) clearInterval(screenTimer); }catch(e){}
  screenTimer = null;
  try{ if(screenStream){ for(const t of screenStream.getTracks()){ try{t.stop();}catch(e){} } } }catch(e){}
  screenStream = null;
  document.getElementById('toggleScreen').innerText = 'Capture: off';
  document.getElementById('screenStatus').innerText = '';
}
document.getElementById('send').onclick=async()=>{
  const v=document.getElementById('cmd').value.trim();
  if(!v) return;
  const res=await fetch('/api/command_text',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:v})}).then(r=>r.json());
  if(res.ok){ document.getElementById('cmd').value=''; }
  else{ alert(res.error||'failed'); }
};
document.getElementById('refreshLog').onclick=refreshLog;
document.getElementById('speakNow').onclick=async()=>{const a=await fetch('/api/agents').then(r=>r.json()); speak(summarize(a.agents));};
document.getElementById('toggleMute').onclick=()=>{ muted = !muted; document.getElementById('toggleMute').innerText = muted ? 'Mute: on' : 'Mute: off'; if(muted){ try{ window.speechSynthesis.cancel(); }catch(e){} } };
document.getElementById('toggleListen').onclick=()=>{ if(listening){ stopListening(); } else { startListening(); } };
document.getElementById('toggleScreen').onclick=()=>{ if(screenStream){ stopScreenCapture(); } else { startScreenCapture(); } };
setInterval(load, 2000);
load();
setInterval(refreshLog, 4000);
setInterval(refreshLatestFrame, 3000);
</script>
</body></html>"""

    @app.get("/")
    def index() -> Response:
        return Response(INDEX, mimetype="text/html")

    @app.get("/api/agents")
    def api_agents():
        return jsonify({"ok": True, "agents": db.list_agents()})

    @app.get("/api/heartbeats")
    def api_heartbeats():
        limit = request.args.get("limit", "100")
        try:
            lim = int(limit)
        except Exception:
            lim = 100
        return jsonify({"ok": True, "heartbeats": db.list_heartbeats(lim)})

    @app.post("/api/heartbeat")
    def api_heartbeat_post():
        body = request.get_json(force=True, silent=True) or {}
        agent_id = str(body.get("agent_id") or "").strip()
        if not agent_id:
            return jsonify({"ok": False, "error": "missing agent_id"}), 400
        display_name = str(body.get("display_name") or agent_id)
        kind = str(body.get("kind") or "push")
        status = str(body.get("status") or "ok")
        details = body.get("details")
        details_json = None if details is None else str(details)
        db.upsert_agent(agent_id, display_name, kind, status, details_json)
        db.insert_heartbeat(agent_id, status, details_json)
        return jsonify({"ok": True})

    @app.get("/api/commands")
    def api_commands_get():
        agent_id = request.args.get("agent_id", "")
        if not agent_id:
            return jsonify({"ok": False, "error": "missing agent_id"}), 400
        limit = request.args.get("limit", "25")
        try:
            lim = int(limit)
        except Exception:
            lim = 25
        return jsonify({"ok": True, "commands": db.fetch_commands(agent_id, lim)})

    @app.post("/api/commands/ack")
    def api_commands_ack():
        body = request.get_json(force=True, silent=True) or {}
        cmd_id = body.get("id")
        status = str(body.get("status") or "processed")
        if cmd_id is None:
            return jsonify({"ok": False, "error": "missing id"}), 400
        db.mark_command_processed(int(cmd_id), status=status)
        return jsonify({"ok": True})

    @app.post("/api/command")
    def api_command_queue():
        body = request.get_json(force=True, silent=True) or {}
        agent_id = str(body.get("agent_id") or "").strip()
        command = str(body.get("command") or "").strip()
        args = body.get("args")
        if not agent_id or not command:
            return jsonify({"ok": False, "error": "missing agent_id or command"}), 400
        cmd_id = db.queue_command(agent_id, command, None if args is None else str(args))
        return jsonify({"ok": True, "id": cmd_id})

    @app.post("/api/command_text")
    def api_command_text():
        body = request.get_json(force=True, silent=True) or {}
        text = str(body.get("text") or "").strip()
        if not text:
            return jsonify({"ok": False, "error": "missing text"}), 400
        parts = text.split()
        if len(parts) < 2:
            return jsonify({"ok": False, "error": "format: <command> <agent_id> [args...]"}), 400
        command = parts[0]
        agent_id = parts[1]
        args = " ".join(parts[2:]) if len(parts) > 2 else ""
        cmd_id = db.queue_command(agent_id, command, args or None)
        return jsonify({"ok": True, "id": cmd_id})

    @app.get("/api/log_tail")
    def api_log_tail():
        lf = request.args.get("file", "")
        lf = os.path.basename(lf)
        if lf not in log_files:
            return Response("", mimetype="text/plain")
        return Response(tail_file(os.path.abspath(lf)), mimetype="text/plain")

    @app.post("/api/voice_event")
    def api_voice_event():
        body = request.get_json(force=True, silent=True) or {}
        transcript = str(body.get("transcript") or "").strip()
        if not transcript:
            return jsonify({"ok": False, "error": "missing transcript"}), 400
        session_id = body.get("session_id")
        is_final = bool(body.get("is_final"))
        meta = body.get("meta")
        meta_json = None if meta is None else json.dumps(meta, ensure_ascii=False)
        vid = db.insert_voice_event(None if session_id is None else str(session_id), is_final, transcript, meta_json)
        return jsonify({"ok": True, "id": vid})

    @app.post("/api/voice_command")
    def api_voice_command():
        body = request.get_json(force=True, silent=True) or {}
        transcript = str(body.get("transcript") or "").strip()
        if not transcript:
            return jsonify({"ok": False, "error": "missing transcript"}), 400

        text = transcript.strip()
        parts = text.split()
        reply_text = ""
        queued_id = None

        if len(parts) >= 2 and parts[0].lower() in {"pause", "stop", "priority"}:
            command = parts[0].lower()
            agent_id = parts[1]
            args = " ".join(parts[2:]) if len(parts) > 2 else None
            queued_id = db.queue_command(agent_id, command, args)
            reply_text = f"Queued {command} for {agent_id}."
        else:
            reply_text = "Heard. If you want to control an agent, say: pause <agent_id>, stop <agent_id>, or priority <agent_id> high."

        return jsonify({"ok": True, "reply_text": reply_text, "queued_command_id": queued_id})

    @app.post("/api/screen_frame")
    def api_screen_frame():
        body = request.get_json(force=True, silent=True) or {}
        jpeg_b64 = str(body.get("jpeg_b64") or "").strip()
        if not jpeg_b64:
            return jsonify({"ok": False, "error": "missing jpeg_b64"}), 400

        session_id = body.get("session_id")
        mime = str(body.get("mime") or "image/jpeg")
        width = body.get("width")
        height = body.get("height")

        try:
            raw = base64.b64decode(jpeg_b64)
        except Exception:
            return jsonify({"ok": False, "error": "invalid base64"}), 400

        fname = f"frame_{int(time.time()*1000)}_{secrets.token_hex(6)}.jpg"
        fpath = os.path.join(frames_dir, fname)
        try:
            with open(fpath, "wb") as f:
                f.write(raw)
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

        try:
            wv = int(width) if width is not None else None
        except Exception:
            wv = None
        try:
            hv = int(height) if height is not None else None
        except Exception:
            hv = None

        fid = db.insert_screen_frame(None if session_id is None else str(session_id), wv, hv, mime, fpath, None)
        delete_paths = db.delete_frames_older_than_id(frames_keep_last)
        for p in delete_paths:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass
        return jsonify({"ok": True, "id": fid})

    @app.get("/api/screen_latest")
    def api_screen_latest():
        row = db.get_latest_frame()
        if not row:
            return Response("", status=404)
        path = str(row.get("file_path") or "")
        if not path or not os.path.exists(path):
            return Response("", status=404)
        try:
            with open(path, "rb") as f:
                data = f.read()
        except Exception:
            return Response("", status=404)
        return Response(data, mimetype=str(row.get("mime") or "image/jpeg"))

    @app.get("/api/frames_stats")
    def api_frames_stats():
        latest = db.get_latest_frame()
        return jsonify({"ok": True, "latest": latest, "frames_dir": frames_dir, "keep_last": frames_keep_last})

    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5050)
    parser.add_argument("--db", default="overseer.db")
    parser.add_argument("--llama-url", default="http://localhost:8099")
    parser.add_argument("--poll-interval", type=int, default=5)
    parser.add_argument(
        "--log-files",
        default=",".join(DEFAULT_LOG_FILES),
        help="Comma-separated files in current directory to tail",
    )
    args = parser.parse_args()

    log_files = [x.strip() for x in str(args.log_files).split(",") if x.strip()]

    db = OverseerDB(args.db)
    app = build_app(db, args.llama_url, args.poll_interval, log_files)
    app.run(host="0.0.0.0", port=int(args.port), debug=False)


if __name__ == "__main__":
    main()
