"""
Shared protocol definitions for gateway ↔ worker ↔ client communication.
All messages are JSON over WebSocket.
"""
from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


# ─── Message Types ───────────────────────────────────────────────────────────

class MsgType(str, enum.Enum):
    # Worker → Gateway
    WORKER_REGISTER   = "worker.register"
    WORKER_HEARTBEAT  = "worker.heartbeat"
    WORKER_DEREGISTER = "worker.deregister"

    # Gateway → Worker
    CELL_EXECUTE      = "cell.execute"
    CELL_INTERRUPT    = "cell.interrupt"
    ENV_SYNC          = "env.sync"

    # Worker → Gateway → Client
    CELL_OUTPUT       = "cell.output"
    CELL_COMPLETE     = "cell.complete"
    CELL_ERROR        = "cell.error"

    # Client → Gateway
    SESSION_CREATE    = "session.create"
    SESSION_JOIN      = "session.join"
    SESSION_LEAVE     = "session.leave"
    EXECUTE_REQUEST   = "execute.request"
    INTERRUPT_REQUEST = "interrupt.request"

    # Gateway → Client
    SESSION_INFO      = "session.info"
    WORKER_STATUS     = "worker.status"
    WORKER_LIST       = "worker.list"
    ERROR             = "error"


# ─── Output Types (mirrors Jupyter messaging) ───────────────────────────────

class OutputType(str, enum.Enum):
    STREAM       = "stream"          # stdout / stderr
    EXECUTE_RESULT = "execute_result"
    DISPLAY_DATA = "display_data"
    ERROR        = "error"
    STATUS       = "status"


# ─── Data Classes ────────────────────────────────────────────────────────────

@dataclass
class WorkerCapabilities:
    """Advertised capabilities of a compute worker."""
    cpu_count: int = 1
    memory_mb: int = 512
    gpu: bool = False
    gpu_name: str = ""
    platform: str = "unknown"       # linux, darwin, ios, android
    python_version: str = ""
    packages: List[str] = field(default_factory=list)
    max_concurrent: int = 1         # max cells to run concurrently
    tags: List[str] = field(default_factory=list)  # user labels


@dataclass
class WorkerInfo:
    """Gateway's view of a connected worker."""
    worker_id: str
    name: str = ""
    capabilities: WorkerCapabilities = field(default_factory=WorkerCapabilities)
    connected_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    running_cells: int = 0
    total_executed: int = 0
    status: str = "idle"            # idle, busy, draining, offline


@dataclass
class SessionInfo:
    """A collaborative notebook session."""
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = "Untitled"
    created_at: float = field(default_factory=time.time)
    participants: List[str] = field(default_factory=list)
    kernel_state: Dict[str, Any] = field(default_factory=dict)
    # Execution routing strategy
    routing: str = "round_robin"    # round_robin, least_loaded, pinned, random
    # Google auth for teleportable memory
    google_user_id: Optional[str] = None


@dataclass
class CellExecution:
    """A cell execution request in flight."""
    cell_id: str
    session_id: str
    code: str
    worker_id: Optional[str] = None
    submitted_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    status: str = "queued"          # queued, running, complete, error, interrupted
    execution_count: int = 0


# ─── Message Construction Helpers ────────────────────────────────────────────

def make_msg(msg_type: MsgType, **kwargs: Any) -> Dict[str, Any]:
    """Build a protocol message dict."""
    return {
        "type": msg_type.value,
        "ts": time.time(),
        "id": uuid.uuid4().hex[:16],
        **kwargs,
    }


def make_register(worker_id: str, name: str,
                  capabilities: WorkerCapabilities) -> Dict[str, Any]:
    return make_msg(
        MsgType.WORKER_REGISTER,
        worker_id=worker_id,
        name=name,
        capabilities=asdict(capabilities),
    )


def make_heartbeat(worker_id: str, running_cells: int = 0,
                   cpu_pct: float = 0, mem_pct: float = 0) -> Dict[str, Any]:
    return make_msg(
        MsgType.WORKER_HEARTBEAT,
        worker_id=worker_id,
        running_cells=running_cells,
        cpu_pct=cpu_pct,
        mem_pct=mem_pct,
    )


def make_execute(cell_id: str, session_id: str, code: str,
                 execution_count: int = 0,
                 cell_mode: str = "python",
                 cell_language: str = "python") -> Dict[str, Any]:
    return make_msg(
        MsgType.CELL_EXECUTE,
        cell_id=cell_id,
        session_id=session_id,
        code=code,
        execution_count=execution_count,
        cell_mode=cell_mode,
        cell_language=cell_language,
    )


def make_output(cell_id: str, session_id: str,
                output_type: OutputType, data: Dict[str, Any],
                worker_id: str = "") -> Dict[str, Any]:
    return make_msg(
        MsgType.CELL_OUTPUT,
        cell_id=cell_id,
        session_id=session_id,
        output_type=output_type.value,
        data=data,
        worker_id=worker_id,
    )


def make_complete(cell_id: str, session_id: str, status: str = "ok",
                  execution_count: int = 0,
                  worker_id: str = "") -> Dict[str, Any]:
    return make_msg(
        MsgType.CELL_COMPLETE,
        cell_id=cell_id,
        session_id=session_id,
        status=status,
        execution_count=execution_count,
        worker_id=worker_id,
    )


def make_error(cell_id: str, session_id: str,
               ename: str, evalue: str, traceback: List[str],
               worker_id: str = "") -> Dict[str, Any]:
    return make_msg(
        MsgType.CELL_ERROR,
        cell_id=cell_id,
        session_id=session_id,
        ename=ename,
        evalue=evalue,
        traceback=traceback,
        worker_id=worker_id,
    )
