"""
Distributed Kernel — a Jupyter kernel that routes execution to remote workers
via the gateway. This is the kernel entry point launched by JupyterLab.

It implements the Jupyter messaging protocol over ZMQ, translating
execute_request messages into gateway WebSocket calls and relaying
outputs back.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional

from ipykernel.kernelbase import Kernel

try:
    import websockets
except ImportError:
    raise SystemExit("pip install websockets")

from .protocol import (
    MsgType, OutputType, make_msg,
)

log = logging.getLogger("distkernel.kernel")


class DistributedKernel(Kernel):
    """
    IPython kernel that delegates execution to distributed workers
    via the gateway server.
    """

    implementation = "distributed"
    implementation_version = "0.1.0"
    language = "python"
    language_version = "3.10+"
    language_info = {
        "name": "python",
        "mimetype": "text/x-python",
        "file_extension": ".py",
        "codemirror_mode": {"name": "ipython", "version": 3},
        "pygments_lexer": "ipython3",
    }
    banner = "Distributed Kernel — compute backed by participant devices"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._gateway_url = os.environ.get(
            "DISTKERNEL_GATEWAY_URL", "ws://localhost:8555")
        self._ws: Optional[Any] = None
        self._session_id = ""
        self._connected = False
        self._pending: Dict[str, asyncio.Future] = {}
        self._recv_task: Optional[asyncio.Task] = None
        self._execution_count = 0

    async def _ensure_connected(self) -> bool:
        """Ensure we're connected to the gateway."""
        if self._connected and self._ws:
            return True
        try:
            self._ws = await websockets.connect(
                self._gateway_url,
                ping_interval=15, ping_timeout=10,
                max_size=50 * 1024 * 1024,
            )
            # Create session
            await self._ws.send(json.dumps(make_msg(
                MsgType.SESSION_CREATE,
                name="distributed-kernel",
                routing="least_loaded",
            )))
            raw = await asyncio.wait_for(self._ws.recv(), timeout=10)
            resp = json.loads(raw)
            if resp.get("type") == MsgType.SESSION_INFO.value:
                self._session_id = resp.get("session", {}).get("session_id", "")
                self._connected = True
                log.info("Connected to gateway, session: %s", self._session_id)
            # Start receiver
            self._recv_task = asyncio.create_task(self._receive_loop())
            return True
        except Exception as exc:
            log.error("Gateway connection failed: %s", exc)
            return False

    async def _receive_loop(self) -> None:
        """Background: receive messages from gateway, resolve pending futures."""
        if not self._ws:
            return
        try:
            async for raw in self._ws:
                try:
                    msg = json.loads(raw)
                    cell_id = msg.get("cell_id", "")
                    msg_type = msg.get("type", "")

                    if msg_type == MsgType.CELL_OUTPUT.value:
                        self._handle_output(msg)
                    elif msg_type in (MsgType.CELL_COMPLETE.value,
                                      MsgType.CELL_ERROR.value):
                        future = self._pending.pop(cell_id, None)
                        if future and not future.done():
                            future.set_result(msg)
                except Exception:
                    log.exception("Receive error")
        except asyncio.CancelledError:
            return
        except Exception:
            self._connected = False

    def _handle_output(self, msg: Dict[str, Any]) -> None:
        """Translate gateway output messages into Jupyter IOPub messages."""
        output_type = msg.get("output_type", "")
        data = msg.get("data", {})

        if output_type == OutputType.STREAM.value:
            stream_name = data.get("name", "stdout")
            text = data.get("text", "")
            self.send_response(self.iopub_socket, "stream", {
                "name": stream_name,
                "text": text,
            })

        elif output_type == OutputType.EXECUTE_RESULT.value:
            self.send_response(self.iopub_socket, "execute_result", {
                "execution_count": self._execution_count,
                "data": data.get("data", {"text/plain": ""}),
                "metadata": data.get("metadata", {}),
            })

        elif output_type == OutputType.DISPLAY_DATA.value:
            self.send_response(self.iopub_socket, "display_data", {
                "data": data.get("data", {}),
                "metadata": data.get("metadata", {}),
            })

        elif output_type == OutputType.STATUS.value:
            worker_name = data.get("worker", "unknown")
            self.send_response(self.iopub_socket, "stream", {
                "name": "stderr",
                "text": f"[executing on {worker_name}]\n",
            })

    async def do_execute(self, code: str, silent: bool,
                         store_history: bool = True,
                         user_expressions: Optional[Dict] = None,
                         allow_stdin: bool = False) -> Dict[str, Any]:
        """Execute code by routing to a remote worker via the gateway."""
        if not code.strip():
            return {
                "status": "ok",
                "execution_count": self._execution_count,
                "payload": [],
                "user_expressions": {},
            }

        self._execution_count += 1

        # Connect if needed
        if not await self._ensure_connected():
            self.send_response(self.iopub_socket, "stream", {
                "name": "stderr",
                "text": (
                    "⚠ Not connected to gateway. Start one with:\n"
                    "  distkernel-gateway --port 8555\n\n"
                    "Then connect a worker:\n"
                    "  distkernel-worker --gateway ws://localhost:8555\n"
                ),
            })
            return {
                "status": "error",
                "execution_count": self._execution_count,
                "ename": "ConnectionError",
                "evalue": "Not connected to distributed gateway",
                "traceback": [],
            }

        # Create pending future
        cell_id = uuid.uuid4().hex[:16]
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        self._pending[cell_id] = future

        # Send execute request
        execute_msg = make_msg(
            MsgType.EXECUTE_REQUEST,
            cell_id=cell_id,
            session_id=self._session_id,
            code=code,
        )
        try:
            await self._ws.send(json.dumps(execute_msg))
        except Exception as exc:
            self._pending.pop(cell_id, None)
            return {
                "status": "error",
                "execution_count": self._execution_count,
                "ename": "SendError",
                "evalue": str(exc),
                "traceback": [],
            }

        # Wait for completion
        try:
            result = await asyncio.wait_for(future, timeout=600)
        except asyncio.TimeoutError:
            self._pending.pop(cell_id, None)
            return {
                "status": "error",
                "execution_count": self._execution_count,
                "ename": "TimeoutError",
                "evalue": "Cell execution timed out (600s)",
                "traceback": [],
            }

        # Translate result
        if result.get("status") == "ok" or result.get("type") == MsgType.CELL_COMPLETE.value:
            return {
                "status": "ok",
                "execution_count": self._execution_count,
                "payload": [],
                "user_expressions": {},
            }
        else:
            ename = result.get("ename", "Error")
            evalue = result.get("evalue", "Unknown error")
            tb = result.get("traceback", [])
            # Send error to iopub
            self.send_response(self.iopub_socket, "error", {
                "ename": ename,
                "evalue": evalue,
                "traceback": tb,
            })
            return {
                "status": "error",
                "execution_count": self._execution_count,
                "ename": ename,
                "evalue": evalue,
                "traceback": tb,
            }

    async def do_complete(self, code: str, cursor_pos: int) -> Dict[str, Any]:
        """Tab completion — basic for now."""
        return {
            "status": "ok",
            "matches": [],
            "cursor_start": cursor_pos,
            "cursor_end": cursor_pos,
            "metadata": {},
        }

    async def do_inspect(self, code: str, cursor_pos: int,
                         detail_level: int = 0,
                         omit_sections: tuple = ()) -> Dict[str, Any]:
        return {"status": "ok", "found": False, "data": {}, "metadata": {}}

    def do_shutdown(self, restart: bool) -> Dict[str, Any]:
        if self._recv_task:
            self._recv_task.cancel()
        if self._ws:
            asyncio.get_event_loop().run_until_complete(self._ws.close())
        return {"status": "ok", "restart": restart}


if __name__ == "__main__":
    from ipykernel.kernelapp import IPKernelApp
    IPKernelApp.launch_instance(kernel_class=DistributedKernel)
