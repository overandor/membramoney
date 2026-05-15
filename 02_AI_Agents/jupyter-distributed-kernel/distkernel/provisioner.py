"""
Jupyter Kernel Provisioner — bridges JupyterLab's kernel system to the
distributed gateway. When a user selects "Distributed Kernel", this
provisioner connects to the gateway instead of launching a local process.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional

from jupyter_client.provisioning import KernelProvisionerBase

try:
    import websockets
except ImportError:
    raise SystemExit("pip install websockets")

from .protocol import MsgType, OutputType, make_msg

log = logging.getLogger("distkernel.provisioner")


class DistributedProvisioner(KernelProvisionerBase):
    """
    Kernel provisioner that routes execution to the distributed gateway.

    Instead of launching a local kernel process, it connects to the gateway
    via WebSocket and routes execute_request messages to remote workers.
    """

    # Provisioner metadata
    kernel_id: str = ""
    gateway_url: str = ""
    session_id: str = ""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._ws: Optional[Any] = None
        self._connected = False
        self._session_id = ""
        self._gateway_url = os.environ.get(
            "DISTKERNEL_GATEWAY_URL", "ws://localhost:8555")
        self._recv_task: Optional[asyncio.Task] = None
        self._pending: Dict[str, asyncio.Future] = {}
        self._output_handlers: Dict[str, List] = {}

    async def pre_launch(self, **kwargs: Any) -> Dict[str, Any]:
        """Called before kernel launch — connect to gateway."""
        kwargs = await super().pre_launch(**kwargs)
        self._gateway_url = os.environ.get(
            "DISTKERNEL_GATEWAY_URL", self._gateway_url)
        log.info("Distributed provisioner connecting to %s", self._gateway_url)
        return kwargs

    async def launch_kernel(self, cmd: List[str], **kwargs: Any) -> Dict[str, Any]:
        """
        Instead of launching a process, connect to the gateway and create a session.
        """
        try:
            self._ws = await websockets.connect(
                self._gateway_url,
                ping_interval=15, ping_timeout=10,
                max_size=50 * 1024 * 1024,
            )
            self._connected = True

            # Create a session on the gateway
            session_name = kwargs.get("kernel_name", "distributed")
            create_msg = make_msg(
                MsgType.SESSION_CREATE,
                name=session_name,
                routing="least_loaded",
            )
            await self._ws.send(json.dumps(create_msg))

            # Wait for session info response
            raw = await asyncio.wait_for(self._ws.recv(), timeout=10)
            resp = json.loads(raw)
            if resp.get("type") == MsgType.SESSION_INFO.value:
                session_data = resp.get("session", {})
                self._session_id = session_data.get("session_id", "")
                log.info("Session created: %s", self._session_id)
            else:
                log.warning("Unexpected response: %s", resp.get("type"))

            # Start background receiver
            self._recv_task = asyncio.create_task(self._receive_loop())

        except Exception as exc:
            log.error("Failed to connect to gateway: %s", exc)
            raise

        # Return connection info that JupyterLab needs
        return {
            "ip": "127.0.0.1",
            "shell_port": 0,
            "iopub_port": 0,
            "stdin_port": 0,
            "control_port": 0,
            "hb_port": 0,
            "key": uuid.uuid4().hex,
            "transport": "tcp",
            "signature_scheme": "hmac-sha256",
            "kernel_name": "distributed",
        }

    async def _receive_loop(self) -> None:
        """Background task to receive messages from the gateway."""
        if not self._ws:
            return
        try:
            async for raw in self._ws:
                try:
                    msg = json.loads(raw)
                    await self._handle_gateway_msg(msg)
                except json.JSONDecodeError:
                    pass
                except Exception:
                    log.exception("Error handling gateway message")
        except asyncio.CancelledError:
            return
        except Exception as exc:
            log.warning("Gateway connection lost: %s", exc)
            self._connected = False

    async def _handle_gateway_msg(self, msg: Dict[str, Any]) -> None:
        """Process messages from the gateway."""
        msg_type = msg.get("type", "")
        cell_id = msg.get("cell_id", "")

        if msg_type == MsgType.CELL_OUTPUT.value:
            handlers = self._output_handlers.get(cell_id, [])
            for handler in handlers:
                try:
                    await handler(msg)
                except Exception:
                    pass

        elif msg_type in (MsgType.CELL_COMPLETE.value, MsgType.CELL_ERROR.value):
            future = self._pending.pop(cell_id, None)
            if future and not future.done():
                future.set_result(msg)
            # Clean up handlers
            self._output_handlers.pop(cell_id, None)

        elif msg_type == MsgType.WORKER_LIST.value:
            workers = msg.get("workers", [])
            log.info("Workers available: %d", len(workers))

    async def execute(self, code: str, output_handler=None) -> Dict[str, Any]:
        """
        Execute code on a remote worker via the gateway.
        This is called by the Jupyter kernel client.
        """
        if not self._ws or not self._connected:
            return {"status": "error", "ename": "NotConnected",
                    "evalue": "Not connected to gateway"}

        cell_id = uuid.uuid4().hex[:16]
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[cell_id] = future

        if output_handler:
            self._output_handlers[cell_id] = [output_handler]

        execute_msg = make_msg(
            MsgType.EXECUTE_REQUEST,
            cell_id=cell_id,
            session_id=self._session_id,
            code=code,
        )
        await self._ws.send(json.dumps(execute_msg))

        try:
            result = await asyncio.wait_for(future, timeout=300)
            return result
        except asyncio.TimeoutError:
            self._pending.pop(cell_id, None)
            self._output_handlers.pop(cell_id, None)
            return {"status": "error", "ename": "Timeout",
                    "evalue": "Cell execution timed out (300s)"}

    async def poll(self) -> Optional[int]:
        """Check if the 'kernel' is still alive (gateway connected)."""
        if self._connected and self._ws:
            return None  # still alive
        return 1  # dead

    async def wait(self) -> Optional[int]:
        """Wait for the kernel to finish."""
        if self._recv_task:
            await self._recv_task
        return 0

    async def send_signal(self, signum: int) -> None:
        """Send a signal — for interrupt, send interrupt request to gateway."""
        import signal as _signal
        if signum == _signal.SIGINT:
            # Interrupt all pending cells
            for cell_id in list(self._pending.keys()):
                if self._ws:
                    interrupt_msg = make_msg(
                        MsgType.INTERRUPT_REQUEST,
                        cell_id=cell_id,
                        session_id=self._session_id,
                    )
                    try:
                        await self._ws.send(json.dumps(interrupt_msg))
                    except Exception:
                        pass

    async def kill(self, restart: bool = False) -> None:
        """Kill the kernel — disconnect from gateway."""
        await self.cleanup(restart=restart)

    async def cleanup(self, restart: bool = False) -> None:
        """Clean up resources."""
        if self._recv_task:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except (asyncio.CancelledError, Exception):
                pass
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
        self._connected = False
        self._pending.clear()
        self._output_handlers.clear()
        log.info("Distributed provisioner cleaned up (restart=%s)", restart)
