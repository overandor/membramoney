"""Demo v2 server — wallet auth + Google auth + AI agents + distributed compute."""
from __future__ import annotations
import argparse, asyncio, json, logging, os, time, uuid
from dataclasses import asdict
from typing import Any, Dict, List, Optional
from aiohttp import web
from ..protocol import (MsgType, OutputType, SessionInfo, CellExecution, make_msg, make_execute)
from .auth import create_challenge, verify_signature, validate_session, get_all_users, record_cell_run
from .ollama import OllamaClient, ResearchAgent
from .google_auth import (
    get_auth_url, exchange_code, get_user_info, GoogleUser, DriveStorage,
    store_user, get_user as get_google_user, get_all_google_users, update_last_active,
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI,
)
from .agent_memory import MemoryStorage

log = logging.getLogger("distkernel.demo")
STATIC = os.path.join(os.path.dirname(__file__), "static")

class DemoServerV2:
    def __init__(self, host="0.0.0.0", port=8555):
        self._host, self._port = host, port
        self._workers: Dict[str, Any] = {}
        self._clients: Dict[int, Any] = {}
        self._sessions: Dict[str, SessionInfo] = {}
        self._executions: Dict[str, CellExecution] = {}
        self._execution_meta: Dict[str, Dict[str, Any]] = {}
        self._exec_counts: Dict[str, int] = {}
        self._agents: Dict[str, ResearchAgent] = {}
        self._ollama = OllamaClient()
        self._rr_idx = 0

    async def start(self):
        app = web.Application()
        app.router.add_get("/", self._index)
        app.router.add_static("/static", STATIC)
        # MetaMask auth
        app.router.add_post("/api/auth/challenge", self._auth_challenge)
        app.router.add_post("/api/auth/verify", self._auth_verify)
        # Google OAuth
        app.router.add_get("/auth/google", self._google_auth)
        app.router.add_get("/auth/google/callback", self._google_callback)
        app.router.add_post("/api/drive/save", self._drive_save)
        app.router.add_get("/api/drive/load", self._drive_load)
        # Ollama
        app.router.add_get("/api/ollama/models", self._ollama_models)
        app.router.add_post("/api/ollama/generate", self._ollama_generate)
        # Agent memory
        app.router.add_get("/api/agent/memory", self._agent_memory)
        # WebSocket
        app.router.add_get("/ws", self._handle_ws)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self._host, self._port)
        await site.start()
        log.info("DistKernel v2 at http://%s:%d", self._host, self._port)
        while True:
            await asyncio.sleep(30)
            self._check_health()

    async def _index(self, req):
        return web.FileResponse(os.path.join(STATIC, "notebook.html"))

    # ── Auth Routes ──
    async def _auth_challenge(self, req):
        data = await req.json()
        addr = data.get("address", "")
        if not addr: return web.json_response({"error": "address required"}, status=400)
        return web.json_response(create_challenge(addr))

    async def _auth_verify(self, req):
        data = await req.json()
        ok, result = verify_signature(data.get("address",""), data.get("nonce",""), data.get("signature",""))
        if ok: return web.json_response({"success": True, "token": result})
        return web.json_response({"success": False, "error": result}, status=401)

    # ── Google OAuth Routes ──
    async def _google_auth(self, req):
        """Initiate Google OAuth flow."""
        if not GOOGLE_CLIENT_ID:
            return web.json_response({"error": "Google OAuth not configured"}, status=503)
        state = uuid.uuid4().hex[:16]
        auth_url = get_auth_url(state=state)
        raise web.HTTPFound(auth_url)

    async def _google_callback(self, req):
        """Handle Google OAuth callback."""
        code = req.query.get("code", "")
        error = req.query.get("error", "")
        if error:
            return web.json_response({"error": error}, status=400)
        if not code:
            return web.json_response({"error": "No code provided"}, status=400)

        # Exchange code for tokens
        token_data = await exchange_code(code)
        if not token_data:
            return web.json_response({"error": "Token exchange failed"}, status=400)

        access_token = token_data.get("access_token", "")
        refresh_token = token_data.get("refresh_token", "")
        expires_in = token_data.get("expires_in", 3600)

        # Get user info
        user_info = await get_user_info(access_token)
        if not user_info:
            return web.json_response({"error": "Failed to get user info"}, status=400)

        user_id = user_info.get("id", uuid.uuid4().hex[:12])
        user = GoogleUser(
            user_id=user_id,
            email=user_info.get("email", ""),
            name=user_info.get("name", ""),
            picture=user_info.get("picture", ""),
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=time.time() + expires_in,
        )
        store_user(user)

        # Redirect back to app with token
        return web.HTTPFound(f"/?google_token={user_id}&email={user.email}")

    async def _drive_save(self, req):
        """Save notebook to Google Drive."""
        data = await req.json()
        user_id = data.get("user_id", "")
        session_id = data.get("session_id", "")
        cells = data.get("cells", [])

        user = get_google_user(user_id)
        if not user:
            return web.json_response({"error": "User not authenticated"}, status=401)

        storage = DriveStorage(user)
        success = await storage.save_notebook(session_id, cells)
        update_last_active(user_id)

        return web.json_response({"success": success})

    async def _drive_load(self, req):
        """Load notebook from Google Drive."""
        user_id = req.query.get("user_id", "")
        user = get_google_user(user_id)
        if not user:
            return web.json_response({"error": "User not authenticated"}, status=401)

        storage = DriveStorage(user)
        notebook = await storage.load_notebook()
        update_last_active(user_id)

        return web.json_response({"success": notebook is not None, "notebook": notebook})

    # ── Ollama Routes ──
    async def _ollama_models(self, req):
        models = await self._ollama.list_models()
        return web.json_response({"models": models, "available": len(models) > 0})

    async def _ollama_generate(self, req):
        data = await req.json()
        model = data.get("model", "llama3.2")
        goal = data.get("goal", "")
        ctx = data.get("context", "")
        try:
            prompt = f"Goal: {goal}\n\nPrevious context:\n{ctx}\n\nWrite the next Python code cell."
            code = await self._ollama.generate(model=model, prompt=prompt,
                system="You are a code-writing AI. Output ONLY executable Python code, no markdown fences.",
                temperature=0.7)
            code = code.strip()
            if code.startswith("```"): code = code.split("\n",1)[1] if "\n" in code else code[3:]
            if code.endswith("```"): code = code[:-3]
            return web.json_response({"code": code.strip()})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def _agent_memory(self, req):
        session_id = req.query.get("session_id", "")
        agent = self._agents.get(session_id)
        if not agent:
            return web.json_response({"error": "Agent not found"}, status=404)
        return web.json_response(agent.get_memory_summary())

    # ── WebSocket ──
    async def _handle_ws(self, req):
        ws = web.WebSocketResponse(max_msg_size=50*1024*1024)
        await ws.prepare(req)
        try:
            async for raw in ws:
                if raw.type == web.WSMsgType.TEXT:
                    try:
                        msg = json.loads(raw.data)
                        await self._dispatch(ws, msg)
                    except json.JSONDecodeError:
                        await ws.send_json(make_msg(MsgType.ERROR, error="bad json"))
                    except Exception: log.exception("dispatch error")
        finally:
            await self._cleanup(ws)
        return ws

    async def _dispatch(self, ws, msg):
        t = msg.get("type", "")
        if t == MsgType.WORKER_REGISTER.value: await self._on_worker_reg(ws, msg)
        elif t == MsgType.WORKER_HEARTBEAT.value: self._on_worker_hb(msg)
        elif t == MsgType.CELL_OUTPUT.value: await self._relay(msg.get("session_id",""), msg)
        elif t == MsgType.CELL_COMPLETE.value: await self._on_cell_done(msg)
        elif t == MsgType.CELL_ERROR.value: await self._on_cell_err(msg)
        elif t == MsgType.SESSION_CREATE.value: await self._on_sess_create(ws, msg)
        elif t == MsgType.EXECUTE_REQUEST.value: await self._on_exec(ws, msg)
        elif t == "worker.list.request":
            await ws.send_json(make_msg(MsgType.WORKER_LIST, workers=[w["info"] for w in self._workers.values()]))
        elif t == "agent.start": await self._on_agent_start(ws, msg)
        elif t == "agent.pause": self._on_agent_pause(msg)
        elif t == "agent.stop": self._on_agent_stop(msg)

    async def _on_worker_reg(self, ws, msg):
        wid = msg.get("worker_id", uuid.uuid4().hex[:12])
        name = msg.get("name", f"node-{wid[:6]}")
        info = {"worker_id": wid, "name": name, "capabilities": msg.get("capabilities",{}),
                "connected_at": time.time(), "last_heartbeat": time.time(),
                "running_cells": 0, "total_executed": 0, "status": "idle"}
        self._workers[wid] = {"ws": ws, "info": info}
        log.info("Node registered: %s (%s)", name, wid)
        await ws.send_json(make_msg(MsgType.WORKER_STATUS, worker_id=wid, status="registered", message=f"Registered as {name}"))
        await self._bcast_workers()

    def _on_worker_hb(self, msg):
        w = self._workers.get(msg.get("worker_id",""))
        if w:
            w["info"]["last_heartbeat"] = time.time()
            w["info"]["running_cells"] = msg.get("running_cells", 0)
            w["info"]["status"] = "busy" if w["info"]["running_cells"] > 0 else "idle"

    async def _on_sess_create(self, ws, msg):
        ws_id = id(ws)
        cid = uuid.uuid4().hex[:12]
        self._clients[ws_id] = {"ws": ws, "client_id": cid, "sessions": set()}
        sess = SessionInfo(name=msg.get("name","Untitled"), routing=msg.get("routing","least_loaded"))
        sess.participants.append(cid)
        self._sessions[sess.session_id] = sess
        self._exec_counts[sess.session_id] = 0
        self._clients[ws_id]["sessions"].add(sess.session_id)
        log.info("Session %s by %s", sess.session_id, cid)
        await ws.send_json(make_msg(MsgType.SESSION_INFO, session=asdict(sess),
            workers=[w["info"] for w in self._workers.values()]))
        await ws.send_json({"type": "user.list", "users": get_all_users()})

    async def _on_exec(self, ws, msg):
        sid = msg.get("session_id",""); code = msg.get("code","")
        cell_id = msg.get("cell_id", uuid.uuid4().hex[:16])
        cell_mode = msg.get("cell_mode", "python")
        cell_language = msg.get("cell_language", "python")
        sess = self._sessions.get(sid)
        if not sess:
            await ws.send_json(make_msg(MsgType.CELL_ERROR, cell_id=cell_id, session_id=sid,
                ename="NoSession", evalue="Session not found", traceback=[])); return
        self._execution_meta[cell_id] = {
            "cell_mode": cell_mode,
            "cell_language": cell_language,
        }
        if cell_mode == "markdown":
            self._exec_counts[sid] = self._exec_counts.get(sid, 0) + 1
            await self._relay(sid, make_msg(
                MsgType.CELL_OUTPUT,
                cell_id=cell_id,
                session_id=sid,
                output_type=OutputType.DISPLAY_DATA.value,
                data={"data": {"text/markdown": code, "text/plain": code}},
                worker_id="local-markup",
            ))
            await self._relay(sid, make_msg(
                MsgType.CELL_COMPLETE,
                cell_id=cell_id,
                session_id=sid,
                status="ok",
                execution_count=self._exec_counts[sid],
                worker_id="local-markup",
            ))
            return
        wid = self._pick_worker(sess.routing)
        if not wid:
            await ws.send_json(make_msg(MsgType.CELL_ERROR, cell_id=cell_id, session_id=sid,
                ename="NoWorker", evalue="No compute nodes connected", traceback=[])); return
        self._exec_counts[sid] = self._exec_counts.get(sid,0)+1
        exe = CellExecution(cell_id=cell_id, session_id=sid, code=code, worker_id=wid,
            submitted_at=time.time(), execution_count=self._exec_counts[sid])
        self._executions[cell_id] = exe
        w = self._workers[wid]; w["info"]["running_cells"] += 1; w["info"]["status"] = "busy"
        em = make_execute(
            cell_id=cell_id,
            session_id=sid,
            code=code,
            execution_count=exe.execution_count,
            cell_mode=cell_mode,
            cell_language=cell_language,
        )
        em["worker_id"] = wid
        try:
            await w["ws"].send_json(em); exe.status = "running"
            await self._relay(sid, make_msg(MsgType.CELL_OUTPUT, cell_id=cell_id, session_id=sid,
                output_type=OutputType.STATUS.value,
                data={"execution_state":"busy","worker":w["info"]["name"]}, worker_id=wid))
        except Exception as e:
            w["info"]["running_cells"] = max(0, w["info"]["running_cells"]-1)
            await ws.send_json(make_msg(MsgType.CELL_ERROR, cell_id=cell_id, session_id=sid,
                ename="WorkerError", evalue=str(e), traceback=[]))

    async def _on_cell_done(self, msg):
        cell_id = msg.get("cell_id","")
        exe = self._executions.get(cell_id)
        if exe and exe.worker_id:
            w = self._workers.get(exe.worker_id)
            if w:
                w["info"]["running_cells"] = max(0, w["info"]["running_cells"]-1)
                w["info"]["total_executed"] += 1
                w["info"]["status"] = "busy" if w["info"]["running_cells"]>0 else "idle"
        future = self._executions.pop(cell_id+"_future", None)
        if future and not future.done():
            future.set_result({
                "output": self._collect_execution_output(cell_id),
                "status": msg.get("status", "ok"),
            })
        await self._relay(msg.get("session_id",""), msg)

    async def _on_cell_err(self, msg):
        cell_id = msg.get("cell_id","")
        exe = self._executions.get(cell_id)
        if exe and exe.worker_id:
            w = self._workers.get(exe.worker_id)
            if w:
                w["info"]["running_cells"] = max(0, w["info"]["running_cells"]-1)
                w["info"]["status"] = "busy" if w["info"]["running_cells"]>0 else "idle"
        future = self._executions.pop(cell_id+"_future", None)
        if future and not future.done():
            future.set_result({
                "output": f"{msg.get('ename', 'Error')}: {msg.get('evalue', '')}\n" + "\n".join(msg.get("traceback", [])),
                "status": "error",
            })
        await self._relay(msg.get("session_id",""), msg)

    # ── AI Agent ──
    async def _on_agent_start(self, ws, msg):
        sid = msg.get("session_id","")
        model = msg.get("model","llama3.2")
        goal = msg.get("goal","Explore MEV strategies")
        mode = msg.get("mode","mev")
        if sid in self._agents:
            self._agents[sid].stop()
        
        # Create memory storage with Google user if available
        sess = self._sessions.get(sid)
        google_user_id = sess.google_user_id if sess else None
        google_user = get_google_user(google_user_id) if google_user_id else None
        memory_storage = MemoryStorage(google_user) if google_user else None
        
        agent = ResearchAgent(
            self._ollama,
            model=model,
            mode=mode,
            memory_storage=memory_storage,
            agent_id=f"{sid}_{mode}"
        )
        agent.set_goal(goal)
        self._agents[sid] = agent

        async def cell_cb(code):
            await self._relay(sid, {
                "type":"agent.cell",
                "code":code,
                "session_id":sid,
                "cell_mode":"terminal",
                "cell_language":"bash",
            })
            cell_id = uuid.uuid4().hex[:16]
            wid = self._pick_worker("least_loaded")
            if not wid: return {"output":"No workers available","status":"error"}
            self._exec_counts[sid] = self._exec_counts.get(sid,0)+1
            exe = CellExecution(cell_id=cell_id, session_id=sid, code=code, worker_id=wid,
                submitted_at=time.time(), execution_count=self._exec_counts[sid])
            self._executions[cell_id] = exe
            self._execution_meta[cell_id] = {"cell_mode": "terminal", "cell_language": "bash"}
            w = self._workers[wid]; w["info"]["running_cells"]+=1; w["info"]["status"]="busy"
            em = make_execute(
                cell_id=cell_id,
                session_id=sid,
                code=code,
                execution_count=exe.execution_count,
                cell_mode="terminal",
                cell_language="bash",
            )
            em["worker_id"] = wid
            result_future = asyncio.get_event_loop().create_future()
            self._executions[cell_id+"_future"] = result_future
            try:
                await w["ws"].send_json(em)
                result = await asyncio.wait_for(result_future, timeout=120)
                return result
            except asyncio.TimeoutError:
                return {"output":"Execution timed out","status":"error"}
            except Exception as e:
                return {"output":str(e),"status":"error"}

        async def status_cb(status):
            await self._relay(sid, {"type":"agent.status","session_id":sid,**status})

        asyncio.create_task(agent.run(cell_cb, status_cb))
        log.info("Agent started for session %s (model=%s)", sid, model)

    def _on_agent_pause(self, msg):
        sid = msg.get("session_id","")
        a = self._agents.get(sid)
        if a: a.pause()

    def _on_agent_stop(self, msg):
        sid = msg.get("session_id","")
        a = self._agents.get(sid)
        if a: a.stop()

    # ── Routing ──
    def _pick_worker(self, strategy="least_loaded"):
        avail = [(k,v) for k,v in self._workers.items()
                 if v["info"]["status"] in ("idle","busy")
                 and v["info"]["running_cells"] < v["info"]["capabilities"].get("max_concurrent",1)]
        if not avail: return None
        if strategy == "least_loaded":
            return min(avail, key=lambda x: x[1]["info"]["running_cells"])[0]
        return avail[0][0]

    # ── Helpers ──
    async def _relay(self, sid, msg):
        for c in self._clients.values():
            if sid in c["sessions"]:
                try: await c["ws"].send_json(msg)
                except: pass

    def _collect_execution_output(self, cell_id):
        meta = self._execution_meta.get(cell_id, {})
        mode = meta.get("cell_mode", "python")
        language = meta.get("cell_language", "python")
        return f"Completed {mode} cell ({language})"

    async def _bcast_workers(self):
        m = make_msg(MsgType.WORKER_LIST, workers=[w["info"] for w in self._workers.values()])
        for c in self._clients.values():
            try: await c["ws"].send_json(m)
            except: pass

    def _check_health(self):
        now = time.time()
        for wid in [k for k,v in self._workers.items() if now-v["info"]["last_heartbeat"]>60]:
            self._workers.pop(wid, None)

    async def _cleanup(self, ws):
        ws_id = id(ws)
        for wid in [k for k,v in self._workers.items() if id(v["ws"])==ws_id]:
            self._workers.pop(wid, None); log.info("Node disconnected: %s", wid)
        self._clients.pop(ws_id, None)
        await self._bcast_workers()

def main():
    parser = argparse.ArgumentParser(description="DistKernel v2")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8555)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
    try: asyncio.run(DemoServerV2(args.host, args.port).start())
    except KeyboardInterrupt: log.info("Stopped")

if __name__ == "__main__":
    main()
