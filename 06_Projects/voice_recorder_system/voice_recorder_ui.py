#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, request, send_from_directory, abort

APP_HOST = "127.0.0.1"
APP_PORT = 8101

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "voice_recorder_data"
AUDIO_DIR = DATA_DIR / "audio"
DB_PATH = DATA_DIR / "recordings.db"

AUDIO_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)


def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def db_init() -> None:
    with db_connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS recordings (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                filename TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                duration_ms INTEGER,
                note TEXT
            )
            """
        )
        conn.commit()


@app.get("/")
def index():
    return """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\"/>
  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"/>
  <title>Local Voice Recorder</title>
  <script src=\"https://cdn.tailwindcss.com\"></script>
</head>
<body class=\"bg-slate-950 text-slate-100\">
  <div class=\"max-w-5xl mx-auto p-6\">
    <div class=\"flex items-center justify-between gap-4\">
      <div>
        <h1 class=\"text-2xl font-semibold\">Local Voice Recorder</h1>
        <p class=\"text-slate-300 mt-1\">Press record. Your microphone audio is saved locally and listed in History.</p>
      </div>
      <div class=\"text-xs text-slate-400\">
        <div>Server: <span id=\"serverInfo\"></span></div>
      </div>
    </div>

    <div class=\"mt-6 grid grid-cols-1 lg:grid-cols-3 gap-6\">
      <div class=\"lg:col-span-2 bg-slate-900/60 border border-slate-800 rounded-xl p-4\">
        <div class=\"flex flex-wrap items-center gap-3\">
          <button id=\"btnRecord\" class=\"px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 font-medium\">Record</button>
          <button id=\"btnStop\" disabled class=\"px-4 py-2 rounded-lg bg-rose-600/70 hover:bg-rose-600 disabled:opacity-40 disabled:hover:bg-rose-600/70 font-medium\">Stop</button>
          <button id=\"btnAlwaysOn\" class=\"px-4 py-2 rounded-lg bg-indigo-600/70 hover:bg-indigo-600 font-medium\">Always-on: Off</button>

          <div class=\"ml-auto text-sm\">
            <span class=\"text-slate-400\">Status:</span>
            <span id=\"status\" class=\"font-medium\">Idle</span>
          </div>
        </div>

        <div class=\"mt-4\">
          <label class=\"block text-sm text-slate-300\">Chunk length (seconds)</label>
          <input id=\"chunkSec\" type=\"number\" min=\"1\" max=\"60\" value=\"10\" class=\"mt-1 w-40 bg-slate-950 border border-slate-800 rounded-lg px-3 py-2\"/>
          <p class=\"text-xs text-slate-400 mt-1\">Always-on mode records continuously and uploads segments of this size.</p>
        </div>

        <div class=\"mt-6\">
          <div class=\"text-sm text-slate-300\">Live monitor</div>
          <pre id=\"log\" class=\"mt-2 bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-slate-200 h-48 overflow-auto\"></pre>
        </div>
      </div>

      <div class=\"bg-slate-900/60 border border-slate-800 rounded-xl p-4\">
        <div class=\"flex items-center justify-between\">
          <div class=\"font-medium\">History</div>
          <button id=\"btnRefresh\" class=\"text-sm px-3 py-1 rounded-lg bg-slate-800 hover:bg-slate-700\">Refresh</button>
        </div>
        <div class=\"mt-3\">
          <input id=\"search\" placeholder=\"Search notes...\" class=\"w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm\"/>
        </div>
        <div id=\"history\" class=\"mt-4 space-y-3\"></div>
      </div>
    </div>
  </div>

<script>
const serverInfo = document.getElementById('serverInfo');
serverInfo.textContent = window.location.origin;

const btnRecord = document.getElementById('btnRecord');
const btnStop = document.getElementById('btnStop');
const btnAlwaysOn = document.getElementById('btnAlwaysOn');
const btnRefresh = document.getElementById('btnRefresh');

const statusEl = document.getElementById('status');
const logEl = document.getElementById('log');
const historyEl = document.getElementById('history');
const searchEl = document.getElementById('search');
const chunkSecEl = document.getElementById('chunkSec');

let mediaStream = null;
let recorder = null;
let isAlwaysOn = false;
let alwaysOnTimer = null;
let currentSegmentBlobs = [];
let lastSegmentStart = null;

function log(line) {
  const ts = new Date().toISOString();
  logEl.textContent += `[${ts}] ${line}\n`;
  logEl.scrollTop = logEl.scrollHeight;
}

function setStatus(s) {
  statusEl.textContent = s;
}

async function ensureMic() {
  if (mediaStream) return mediaStream;
  mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  return mediaStream;
}

function mimePick() {
  const candidates = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/ogg'
  ];
  for (const c of candidates) {
    if (MediaRecorder.isTypeSupported(c)) return c;
  }
  return '';
}

async function uploadBlob(blob, durationMs, note) {
  const fd = new FormData();
  fd.append('audio', blob, 'recording.webm');
  fd.append('duration_ms', String(durationMs || ''));
  fd.append('note', note || '');

  const res = await fetch('/api/upload', { method: 'POST', body: fd });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(txt || `upload failed: ${res.status}`);
  }
  return await res.json();
}

async function startManualRecord() {
  await ensureMic();

  currentSegmentBlobs = [];
  lastSegmentStart = Date.now();

  const options = {};
  const mime = mimePick();
  if (mime) options.mimeType = mime;

  recorder = new MediaRecorder(mediaStream, options);
  recorder.ondataavailable = (e) => {
    if (e.data && e.data.size > 0) currentSegmentBlobs.push(e.data);
  };
  recorder.onstart = () => log('Recording started');
  recorder.onerror = (e) => log(`Recorder error: ${e.error?.message || e.message}`);

  recorder.start(1000);
  btnRecord.disabled = true;
  btnStop.disabled = false;
  setStatus('Recording');
}

async function stopManualRecord() {
  if (!recorder) return;

  const startedAt = lastSegmentStart;

  const done = new Promise((resolve) => {
    recorder.onstop = () => resolve(true);
  });
  recorder.stop();
  await done;

  const durationMs = Math.max(0, Date.now() - startedAt);
  const blob = new Blob(currentSegmentBlobs, { type: recorder.mimeType || 'audio/webm' });

  recorder = null;
  currentSegmentBlobs = [];
  lastSegmentStart = null;

  btnRecord.disabled = false;
  btnStop.disabled = true;
  setStatus('Uploading');

  try {
    const result = await uploadBlob(blob, durationMs, 'manual');
    log(`Uploaded: ${result.id} (${result.size_bytes} bytes)`);
    await refreshHistory();
  } catch (e) {
    log(`Upload failed: ${e.message}`);
  } finally {
    setStatus('Idle');
  }
}

async function startAlwaysOn() {
  await ensureMic();

  isAlwaysOn = true;
  btnAlwaysOn.textContent = 'Always-on: On';
  btnAlwaysOn.classList.remove('bg-indigo-600/70');
  btnAlwaysOn.classList.add('bg-indigo-600');

  btnRecord.disabled = true;
  btnStop.disabled = true;
  setStatus('Always-on');

  const chunkSec = Math.max(1, Math.min(60, parseInt(chunkSecEl.value || '10', 10)));

  async function recordOneSegment() {
    if (!isAlwaysOn) return;

    currentSegmentBlobs = [];
    lastSegmentStart = Date.now();

    const options = {};
    const mime = mimePick();
    if (mime) options.mimeType = mime;

    recorder = new MediaRecorder(mediaStream, options);
    recorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) currentSegmentBlobs.push(e.data);
    };

    const startedAt = lastSegmentStart;

    recorder.start(1000);
    log(`Always-on segment started (${chunkSec}s)`);

    await new Promise((r) => setTimeout(r, chunkSec * 1000));

    const done = new Promise((resolve) => {
      recorder.onstop = () => resolve(true);
    });
    recorder.stop();
    await done;

    const durationMs = Math.max(0, Date.now() - startedAt);
    const blob = new Blob(currentSegmentBlobs, { type: recorder.mimeType || 'audio/webm' });

    recorder = null;
    currentSegmentBlobs = [];
    lastSegmentStart = null;

    try {
      const result = await uploadBlob(blob, durationMs, `always_on_${chunkSec}s`);
      log(`Uploaded segment: ${result.id} (${result.size_bytes} bytes)`);
    } catch (e) {
      log(`Upload failed: ${e.message}`);
    }

    await refreshHistory();

    if (isAlwaysOn) {
      alwaysOnTimer = setTimeout(recordOneSegment, 10);
    }
  }

  recordOneSegment();
}

function stopAlwaysOn() {
  isAlwaysOn = false;
  if (alwaysOnTimer) {
    clearTimeout(alwaysOnTimer);
    alwaysOnTimer = null;
  }

  if (recorder && recorder.state !== 'inactive') {
    try { recorder.stop(); } catch (_) {}
  }
  recorder = null;

  btnAlwaysOn.textContent = 'Always-on: Off';
  btnAlwaysOn.classList.remove('bg-indigo-600');
  btnAlwaysOn.classList.add('bg-indigo-600/70');

  btnRecord.disabled = false;
  btnStop.disabled = true;
  setStatus('Idle');
  log('Always-on stopped');
}

async function refreshHistory() {
  const q = encodeURIComponent(searchEl.value || '');
  const res = await fetch(`/api/recordings?q=${q}`);
  const data = await res.json();

  historyEl.innerHTML = '';
  for (const item of data.items) {
    const div = document.createElement('div');
    div.className = 'bg-slate-950 border border-slate-800 rounded-xl p-3';

    const created = new Date(item.created_at).toLocaleString();
    div.innerHTML = `
      <div class="flex items-start justify-between gap-3">
        <div>
          <div class="text-sm font-medium">${created}</div>
          <div class="text-xs text-slate-400 mt-1">${item.note || ''}</div>
          <div class="text-xs text-slate-500 mt-1">${item.mime_type} • ${(item.size_bytes/1024).toFixed(1)} KB • ${item.duration_ms ? (item.duration_ms/1000).toFixed(1)+'s' : ''}</div>
        </div>
        <div class="flex gap-2">
          <a class="text-xs px-2 py-1 rounded bg-slate-800 hover:bg-slate-700" href="/audio/${item.filename}" download>Download</a>
        </div>
      </div>
      <audio class="w-full mt-2" controls src="/audio/${item.filename}"></audio>
    `;

    historyEl.appendChild(div);
  }
}

btnRecord.addEventListener('click', () => startManualRecord().catch(e => log(e.message)));
btnStop.addEventListener('click', () => stopManualRecord().catch(e => log(e.message)));
btnAlwaysOn.addEventListener('click', () => {
  if (!isAlwaysOn) startAlwaysOn().catch(e => log(e.message));
  else stopAlwaysOn();
});
btnRefresh.addEventListener('click', () => refreshHistory().catch(e => log(e.message)));
searchEl.addEventListener('input', () => {
  refreshHistory().catch(() => {});
});

refreshHistory().catch(() => {});
log('Ready');
</script>
</body>
</html>"""


@app.post("/api/upload")
def api_upload():
    if "audio" not in request.files:
        return jsonify({"error": "missing audio file"}), 400

    f = request.files["audio"]
    if not f.filename:
        return jsonify({"error": "empty filename"}), 400

    duration_ms: Optional[int] = None
    raw_duration = request.form.get("duration_ms")
    if raw_duration:
        try:
            duration_ms = int(float(raw_duration))
        except Exception:
            duration_ms = None

    note = (request.form.get("note") or "").strip()[:500]

    content = f.read()
    if not content:
        return jsonify({"error": "empty upload"}), 400

    recording_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat() + "Z"

    mime_type = f.mimetype or "application/octet-stream"

    ext = ".webm"
    if "ogg" in mime_type:
        ext = ".ogg"

    filename = f"rec_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{recording_id[:8]}{ext}"
    out_path = AUDIO_DIR / filename

    with open(out_path, "wb") as out:
        out.write(content)

    size_bytes = out_path.stat().st_size

    with db_connect() as conn:
        conn.execute(
            """
            INSERT INTO recordings (id, created_at, filename, mime_type, size_bytes, duration_ms, note)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (recording_id, created_at, filename, mime_type, int(size_bytes), duration_ms, note),
        )
        conn.commit()

    return jsonify(
        {
            "id": recording_id,
            "created_at": created_at,
            "filename": filename,
            "mime_type": mime_type,
            "size_bytes": int(size_bytes),
            "duration_ms": duration_ms,
            "note": note,
        }
    )


@app.get("/api/recordings")
def api_recordings():
    q = (request.args.get("q") or "").strip()

    with db_connect() as conn:
        if q:
            rows = conn.execute(
                """
                SELECT * FROM recordings
                WHERE note LIKE ?
                ORDER BY created_at DESC
                LIMIT 200
                """,
                (f"%{q}%",),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM recordings
                ORDER BY created_at DESC
                LIMIT 200
                """
            ).fetchall()

    items = [dict(r) for r in rows]
    return jsonify({"items": items})


@app.get("/audio/<path:filename>")
def audio(filename: str):
    full = AUDIO_DIR / filename
    if not full.exists():
        abort(404)
    return send_from_directory(AUDIO_DIR, filename, as_attachment=False)


def main() -> int:
    db_init()
    app.run(host=APP_HOST, port=APP_PORT, debug=False, threaded=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
