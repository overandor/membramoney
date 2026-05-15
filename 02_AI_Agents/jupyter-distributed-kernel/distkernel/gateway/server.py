"""
Gateway Server — WebSocket coordination hub for distributed kernel execution.

Manages:
- Worker registration and health monitoring
- Notebook session lifecycle
- Cell execution routing and load balancing
- Output relay from workers back to JupyterLab clients
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
import uuid
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Set

import websockets
from websockets.server import WebSocketServerProtocol

from ..protocol import (
    MsgType, OutputType, WorkerCapabilities, WorkerInfo, SessionInfo,
    CellExecution, make_msg, make_execute, make_output, make_complete,
)

log = logging.getLogger("distkernel.gateway")


# ─── Router Strategies ───────────────────────────────────────────────────────

class Router:
    """Selects a worker for cell execution based on routing strategy."""

    def __init__(self, workers: Dict[str, _ConnectedWorker]) -> None:
        self._workers = workers
        self._rr_index = 0

    def pick(self, strategy: str = "least_loaded",
             exclude: Optional[Set[str]] = None) -> Optional[str]:
        """Return worker_id of best candidate, or None if none available."""
        exclude = exclude or set()
        available = [
            w for w in self._workers.values()
            if w.info.status in ("idle", "busy")
            and w.info.worker_id not in exclude
            and w.info.running_cells < w.info.capabilities.max_concurrent
        ]
        if not available:
            return None

        if strategy == "round_robin":
            self._rr_index = (self._rr_index + 1) % len(available)
            return available[self._rr_index].info.worker_id

        elif strategy == "least_loaded":
            best = min(available, key=lambda w: (
                w.info.running_cells,
                -w.info.capabilities.memory_mb,
            ))
            return best.info.worker_id

        elif strategy == "random":
            import random
            return random.choice(available).info.worker_id

        # Default: first available
        return available[0].info.worker_id


# ─── Internal Connection Wrappers ────────────────────────────────────────────

class _ConnectedWorker:
    __slots__ = ("ws", "info")
    def __init__(self, ws: WebSocketServerProtocol, info: WorkerInfo) -> None:
        self.ws = ws
        self.info = info


class _ConnectedClient:
    __slots__ = ("ws", "client_id", "session_ids")
    def __init__(self, ws: WebSocketServerProtocol) -> None:
        self.ws = ws
        self.client_id = uuid.uuid4().hex[:12]
        self.session_ids: Set[str] = set()


# ─── Gateway Server ─────────────────────────────────────────────────────────

class GatewayServer:
    """Central coordination server for distributed kernel execution."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8555) -> None:
        self._host = host
        self._port = port
        # State
        self._workers: Dict[str, _ConnectedWorker] = {}       # worker_id → conn
        self._clients: Dict[str, _ConnectedClient] = {}       # client_id → conn
        self._sessions: Dict[str, SessionInfo] = {}            # session_id → info
        self._executions: Dict[str, CellExecution] = {}        # cell_id → exec
        self._execution_count: Dict[str, int] = {}             # session_id → count
        self._router = Router(self._workers)
        # Map ws objects to their role for cleanup
        self._ws_to_worker: Dict[WebSocketServerProtocol, str] = {}
        self._ws_to_client: Dict[WebSocketServerProtocol, str] = {}

    async def start(self) -> None:
        log.info("Gateway starting on ws://%s:%d", self._host, self._port)
        self._health_task = asyncio.create_task(self._health_loop())
        async with websockets.serve(
            self._handler, self._host, self._port,
            ping_interval=20, ping_timeout=10,
            max_size=50 * 1024 * 1024,  # 50MB max message for large outputs
        ):
            log.info("Gateway listening on ws://%s:%d", self._host, self._port)
            await asyncio.Future()  # run forever

    async def _handler(self, ws: WebSocketServerProtocol) -> None:
        """Main WebSocket handler — routes based on first message role."""
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                    await self._dispatch(ws, msg)
                except json.JSONDecodeError:
                    await ws.send(json.dumps(make_msg(
                        MsgType.ERROR, error="invalid JSON")))
                except Exception:
                    log.exception("Dispatch error")
        finally:
            await self._cleanup(ws)

    async def _dispatch(self, ws: WebSocketServerProtocol,
                        msg: Dict[str, Any]) -> None:
        """Route message to appropriate handler."""
        msg_type = msg.get("type", "")

        # ── Worker messages ──────────────────────────────────────────────
        if msg_type == MsgType.WORKER_REGISTER.value:
            await self._handle_worker_register(ws, msg)

        elif msg_type == MsgType.WORKER_HEARTBEAT.value:
            await self._handle_worker_heartbeat(msg)

        elif msg_type == MsgType.WORKER_DEREGISTER.value:
            await self._handle_worker_deregister(msg)

        elif msg_type == MsgType.CELL_OUTPUT.value:
            await self._handle_cell_output(msg)

        elif msg_type == MsgType.CELL_COMPLETE.value:
            await self._handle_cell_complete(msg)

        elif msg_type == MsgType.CELL_ERROR.value:
            await self._handle_cell_error(msg)

        # ── Client messages ──────────────────────────────────────────────
        elif msg_type == MsgType.SESSION_CREATE.value:
            await self._handle_session_create(ws, msg)

        elif msg_type == MsgType.SESSION_JOIN.value:
            await self._handle_session_join(ws, msg)

        elif msg_type == MsgType.EXECUTE_REQUEST.value:
            await self._handle_execute_request(ws, msg)

        elif msg_type == MsgType.INTERRUPT_REQUEST.value:
            await self._handle_interrupt_request(ws, msg)

        elif msg_type == "worker.list.request":
            await self._handle_worker_list_request(ws, msg)

        else:
            await ws.send(json.dumps(make_msg(
                MsgType.ERROR, error=f"unknown message type: {msg_type}")))

    # ── Worker Handlers ──────────────────────────────────────────────────

    async def _handle_worker_register(self, ws: WebSocketServerProtocol,
                                      msg: Dict[str, Any]) -> None:
        worker_id = msg.get("worker_id", uuid.uuid4().hex[:12])
        name = msg.get("name", f"worker-{worker_id[:6]}")
        caps_data = msg.get("capabilities", {})
        caps = WorkerCapabilities(**{
            k: v for k, v in caps_data.items()
            if k in WorkerCapabilities.__dataclass_fields__
        })
        info = WorkerInfo(
            worker_id=worker_id, name=name, capabilities=caps,
            connected_at=time.time(), last_heartbeat=time.time(),
        )
        self._workers[worker_id] = _ConnectedWorker(ws, info)
        self._ws_to_worker[ws] = worker_id

        log.info("Worker registered: %s (%s) — %d CPU, %d MB RAM, platform=%s",
                 name, worker_id, caps.cpu_count, caps.memory_mb, caps.platform)

        # Acknowledge
        await ws.send(json.dumps(make_msg(
            MsgType.WORKER_STATUS,
            worker_id=worker_id, status="registered",
            message=f"Registered as {name}",
        )))

        # Notify all clients
        await self._broadcast_worker_list()

    async def _handle_worker_heartbeat(self, msg: Dict[str, Any]) -> None:
        wid = msg.get("worker_id", "")
        w = self._workers.get(wid)
        if w:
            w.info.last_heartbeat = time.time()
            w.info.running_cells = msg.get("running_cells", 0)
            w.info.status = "busy" if w.info.running_cells > 0 else "idle"

    async def _handle_worker_deregister(self, msg: Dict[str, Any]) -> None:
        wid = msg.get("worker_id", "")
        if wid in self._workers:
            del self._workers[wid]
            log.info("Worker deregistered: %s", wid)
            await self._broadcast_worker_list()

    # ── Cell Output / Completion (Worker → Client relay) ─────────────────

    async def _handle_cell_output(self, msg: Dict[str, Any]) -> None:
        """Relay output from worker to all clients in the session."""
        session_id = msg.get("session_id", "")
        await self._relay_to_session(session_id, msg)

    async def _handle_cell_complete(self, msg: Dict[str, Any]) -> None:
        cell_id = msg.get("cell_id", "")
        session_id = msg.get("session_id", "")
        status = msg.get("status", "ok")

        exe = self._executions.get(cell_id)
        if exe:
            exe.completed_at = time.time()
            exe.status = "complete" if status == "ok" else "error"
            # Update worker running count
            if exe.worker_id and exe.worker_id in self._workers:
                w = self._workers[exe.worker_id]
                w.info.running_cells = max(0, w.info.running_cells - 1)
                w.info.total_executed += 1
                w.info.status = "busy" if w.info.running_cells > 0 else "idle"
            elapsed = (exe.completed_at - exe.submitted_at) if exe.submitted_at else 0
            log.info("Cell %s complete (%s) on %s in %.2fs",
                     cell_id[:8], status, exe.worker_id or "?", elapsed)

        await self._relay_to_session(session_id, msg)

    async def _handle_cell_error(self, msg: Dict[str, Any]) -> None:
        cell_id = msg.get("cell_id", "")
        session_id = msg.get("session_id", "")
        exe = self._executions.get(cell_id)
        if exe:
            exe.completed_at = time.time()
            exe.status = "error"
            if exe.worker_id and exe.worker_id in self._workers:
                w = self._workers[exe.worker_id]
                w.info.running_cells = max(0, w.info.running_cells - 1)
                w.info.status = "busy" if w.info.running_cells > 0 else "idle"
        await self._relay_to_session(session_id, msg)

    # ── Session / Execution Handlers ─────────────────────────────────────

    async def _handle_session_create(self, ws: WebSocketServerProtocol,
                                     msg: Dict[str, Any]) -> None:
        client = self._ensure_client(ws)
        name = msg.get("name", "Untitled")
        routing = msg.get("routing", "least_loaded")
        session = SessionInfo(name=name, routing=routing)
        session.participants.append(client.client_id)
        self._sessions[session.session_id] = session
        self._execution_count[session.session_id] = 0
        client.session_ids.add(session.session_id)

        log.info("Session created: %s (%s) by client %s",
                 name, session.session_id, client.client_id)

        await ws.send(json.dumps(make_msg(
            MsgType.SESSION_INFO,
            session=asdict(session),
            workers=[asdict(w.info) for w in self._workers.values()],
        )))

    async def _handle_session_join(self, ws: WebSocketServerProtocol,
                                   msg: Dict[str, Any]) -> None:
        client = self._ensure_client(ws)
        session_id = msg.get("session_id", "")
        session = self._sessions.get(session_id)
        if not session:
            await ws.send(json.dumps(make_msg(
                MsgType.ERROR, error=f"Session {session_id} not found")))
            return
        if client.client_id not in session.participants:
            session.participants.append(client.client_id)
        client.session_ids.add(session_id)

        log.info("Client %s joined session %s", client.client_id, session_id)

        await ws.send(json.dumps(make_msg(
            MsgType.SESSION_INFO,
            session=asdict(session),
            workers=[asdict(w.info) for w in self._workers.values()],
        )))

    async def _handle_execute_request(self, ws: WebSocketServerProtocol,
                                      msg: Dict[str, Any]) -> None:
        """Route a cell execution to an available worker."""
        session_id = msg.get("session_id", "")
        code = msg.get("code", "")
        cell_id = msg.get("cell_id", uuid.uuid4().hex[:16])

        session = self._sessions.get(session_id)
        if not session:
            await ws.send(json.dumps(make_msg(
                MsgType.ERROR, error="Session not found",
                cell_id=cell_id)))
            return

        # Pick a worker
        worker_id = self._router.pick(
            strategy=session.routing)
        if not worker_id:
            await ws.send(json.dumps(make_msg(
                MsgType.CELL_ERROR,
                cell_id=cell_id, session_id=session_id,
                ename="NoWorkerAvailable",
                evalue="No compute workers are connected. Start a worker with: distkernel-worker --gateway ws://HOST:8555/ws",
                traceback=[],
            )))
            return

        # Track execution
        self._execution_count[session_id] = self._execution_count.get(session_id, 0) + 1
        exe = CellExecution(
            cell_id=cell_id, session_id=session_id, code=code,
            worker_id=worker_id, submitted_at=time.time(),
            execution_count=self._execution_count[session_id],
        )
        self._executions[cell_id] = exe

        # Update worker state
        w = self._workers[worker_id]
        w.info.running_cells += 1
        w.info.status = "busy"

        # Send to worker
        execute_msg = make_execute(
            cell_id=cell_id, session_id=session_id, code=code,
            execution_count=exe.execution_count,
        )
        execute_msg["worker_id"] = worker_id

        log.info("Routing cell %s to worker %s (%s)",
                 cell_id[:8], w.info.name, worker_id[:8])

        try:
            await w.ws.send(json.dumps(execute_msg))
            exe.status = "running"
            exe.started_at = time.time()

            # Notify client that execution started
            await self._relay_to_session(session_id, make_msg(
                MsgType.CELL_OUTPUT,
                cell_id=cell_id, session_id=session_id,
                output_type=OutputType.STATUS.value,
                data={"execution_state": "busy", "worker": w.info.name},
                worker_id=worker_id,
            ))
        except Exception as exc:
            log.error("Failed to send to worker %s: %s", worker_id, exc)
            exe.status = "error"
            w.info.running_cells = max(0, w.info.running_cells - 1)
            await ws.send(json.dumps(make_msg(
                MsgType.CELL_ERROR,
                cell_id=cell_id, session_id=session_id,
                ename="WorkerError",
                evalue=f"Failed to reach worker {w.info.name}: {exc}",
                traceback=[],
            )))

    async def _handle_interrupt_request(self, ws: WebSocketServerProtocol,
                                        msg: Dict[str, Any]) -> None:
        cell_id = msg.get("cell_id", "")
        exe = self._executions.get(cell_id)
        if not exe or not exe.worker_id:
            return
        w = self._workers.get(exe.worker_id)
        if w:
            try:
                await w.ws.send(json.dumps(make_msg(
                    MsgType.CELL_INTERRUPT,
                    cell_id=cell_id,
                    session_id=exe.session_id,
                )))
            except Exception:
                pass

    async def _handle_worker_list_request(self, ws: WebSocketServerProtocol,
                                          msg: Dict[str, Any]) -> None:
        await ws.send(json.dumps(make_msg(
            MsgType.WORKER_LIST,
            workers=[asdict(w.info) for w in self._workers.values()],
        )))

    # ── Helpers ──────────────────────────────────────────────────────────

    def _ensure_client(self, ws: WebSocketServerProtocol) -> _ConnectedClient:
        cid = self._ws_to_client.get(ws)
        if cid and cid in self._clients:
            return self._clients[cid]
        client = _ConnectedClient(ws)
        self._clients[client.client_id] = client
        self._ws_to_client[ws] = client.client_id
        return client

    async def _relay_to_session(self, session_id: str,
                                msg: Dict[str, Any]) -> None:
        """Send a message to all clients in a session."""
        session = self._sessions.get(session_id)
        if not session:
            return
        raw = json.dumps(msg)
        for pid in session.participants:
            client = self._clients.get(pid)
            if client:
                try:
                    await client.ws.send(raw)
                except Exception:
                    pass

    async def _broadcast_worker_list(self) -> None:
        """Notify all clients of updated worker list."""
        msg = json.dumps(make_msg(
            MsgType.WORKER_LIST,
            workers=[asdict(w.info) for w in self._workers.values()],
        ))
        for client in self._clients.values():
            try:
                await client.ws.send(msg)
            except Exception:
                pass

    async def _cleanup(self, ws: WebSocketServerProtocol) -> None:
        """Clean up when a WebSocket disconnects."""
        # Worker cleanup
        wid = self._ws_to_worker.pop(ws, None)
        if wid and wid in self._workers:
            del self._workers[wid]
            log.info("Worker disconnected: %s", wid)
            await self._broadcast_worker_list()

        # Client cleanup
        cid = self._ws_to_client.pop(ws, None)
        if cid and cid in self._clients:
            client = self._clients.pop(cid)
            for sid in client.session_ids:
                session = self._sessions.get(sid)
                if session and cid in session.participants:
                    session.participants.remove(cid)
            log.info("Client disconnected: %s", cid)

    async def _health_loop(self) -> None:
        """Periodic health check — mark stale workers as offline."""
        while True:
            await asyncio.sleep(30)
            now = time.time()
            stale = []
            for wid, w in self._workers.items():
                if now - w.info.last_heartbeat > 60:
                    w.info.status = "offline"
                    stale.append(wid)
            for wid in stale:
                log.warning("Worker %s timed out — removing", wid)
                w = self._workers.pop(wid, None)
                if w:
                    self._ws_to_worker.pop(w.ws, None)
                    try:
                        await w.ws.close()
                    except Exception:
                        pass
            if stale:
                await self._broadcast_worker_list()


# ─── Entry Point ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Distributed Kernel Gateway")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8555, help="Bind port")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    server = GatewayServer(host=args.host, port=args.port)
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        log.info("Gateway stopped")


if __name__ == "__main__":
    main()
