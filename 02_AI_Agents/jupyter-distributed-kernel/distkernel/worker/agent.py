"""
Compute Worker Agent — runs on each participant's device.

Connects to the gateway, registers capabilities, and executes notebook cells
in an isolated namespace with real-time output streaming.
"""
from __future__ import annotations

import argparse
import ast
import asyncio
import contextlib
import io
import json
import logging
import os
import platform
import shutil
import signal
import sys
import time
import traceback
import uuid
from typing import Any, Dict, Optional

import psutil

try:
    import websockets
except ImportError:
    raise SystemExit("pip install websockets")

from ..protocol import (
    MsgType, OutputType,
    WorkerCapabilities, make_register, make_heartbeat,
    make_output, make_complete, make_error, make_msg,
)

log = logging.getLogger("distkernel.worker")


# ─── Sandboxed Cell Executor ────────────────────────────────────────────────

class CellExecutor:
    """
    Executes Python code in a persistent namespace with captured I/O.
    Each session gets its own namespace to maintain state across cells.
    """

    def __init__(self) -> None:
        # session_id → namespace dict
        self._namespaces: Dict[str, Dict[str, Any]] = {}
        self._running: Dict[str, asyncio.Task] = {}  # cell_id → task

    def _get_ns(self, session_id: str) -> Dict[str, Any]:
        if session_id not in self._namespaces:
            ns: Dict[str, Any] = {"__builtins__": __builtins__}
            # Pre-import common packages
            for mod_name in ("os", "sys", "math", "json", "time", "datetime"):
                try:
                    ns[mod_name] = __import__(mod_name)
                except ImportError:
                    pass
            self._namespaces[session_id] = ns
        return self._namespaces[session_id]

    async def execute(self, cell_id: str, session_id: str, code: str,
                      output_callback) -> Dict[str, Any]:
        """
        Execute code in the session namespace.
        Streams output via output_callback(output_type, data).
        Returns {"status": "ok"} or {"status": "error", ...}.
        """
        ns = self._get_ns(session_id)
        loop = asyncio.get_event_loop()

        # Run in thread to avoid blocking the event loop
        result = await loop.run_in_executor(
            None, self._execute_sync, cell_id, session_id, code, ns,
            output_callback, loop,
        )
        return result

    def _execute_sync(self, cell_id: str, session_id: str, code: str,
                      ns: Dict[str, Any], output_callback, loop) -> Dict[str, Any]:
        """Synchronous cell execution with captured stdout/stderr."""
        stdout_capture = _StreamCapture("stdout", cell_id, session_id,
                                        output_callback, loop)
        stderr_capture = _StreamCapture("stderr", cell_id, session_id,
                                        output_callback, loop)

        old_stdout, old_stderr = sys.stdout, sys.stderr
        sys.stdout = stdout_capture  # type: ignore
        sys.stderr = stderr_capture  # type: ignore

        result_value = None
        try:
            # Parse code to detect if last statement is an expression
            tree = ast.parse(code, mode="exec")
            if tree.body and isinstance(tree.body[-1], ast.Expr):
                # Last statement is an expression — capture its value
                last_expr = tree.body.pop()
                if tree.body:
                    exec(compile(ast.Module(body=tree.body, type_ignores=[]),
                                 "<cell>", "exec"), ns)
                result_value = eval(compile(ast.Expression(body=last_expr.value),
                                            "<cell>", "eval"), ns)
            else:
                exec(compile(tree, "<cell>", "exec"), ns)
        except KeyboardInterrupt:
            return {"status": "error", "ename": "KeyboardInterrupt",
                    "evalue": "Interrupted", "traceback": []}
        except Exception:
            etype, evalue, tb = sys.exc_info()
            tb_lines = traceback.format_exception(etype, evalue, tb)
            return {
                "status": "error",
                "ename": etype.__name__ if etype else "Error",
                "evalue": str(evalue),
                "traceback": tb_lines,
            }
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            # Flush any remaining buffered output
            stdout_capture.flush()
            stderr_capture.flush()

        # Send expression result as execute_result
        if result_value is not None:
            ns["_"] = result_value
            data = {}
            # Try rich repr first
            for mime, method in [
                ("text/html", "_repr_html_"),
                ("image/png", "_repr_png_"),
                ("text/latex", "_repr_latex_"),
                ("application/json", "_repr_json_"),
            ]:
                if hasattr(result_value, method):
                    try:
                        r = getattr(result_value, method)()
                        if r is not None:
                            data[mime] = r
                    except Exception:
                        pass
            if not data:
                data["text/plain"] = repr(result_value)

            asyncio.run_coroutine_threadsafe(
                output_callback(
                    OutputType.EXECUTE_RESULT,
                    {"data": data, "metadata": {}},
                ),
                loop,
            ).result(timeout=5)

        return {"status": "ok"}

    def interrupt(self, cell_id: str) -> bool:
        """Attempt to interrupt a running cell."""
        task = self._running.get(cell_id)
        if task and not task.done():
            task.cancel()
            return True
        return False


class _StreamCapture(io.TextIOBase):
    """Captures writes to stdout/stderr and sends them as output messages."""

    def __init__(self, stream_name: str, cell_id: str, session_id: str,
                 callback, loop) -> None:
        self._name = stream_name
        self._cell_id = cell_id
        self._session_id = session_id
        self._callback = callback
        self._loop = loop
        self._buffer = ""
        self._last_flush = time.time()

    def write(self, text: str) -> int:
        if not text:
            return 0
        self._buffer += text
        # Flush on newline or buffer size
        if "\n" in text or len(self._buffer) > 1024:
            self.flush()
        return len(text)

    def flush(self) -> None:
        if not self._buffer:
            return
        text = self._buffer
        self._buffer = ""
        try:
            asyncio.run_coroutine_threadsafe(
                self._callback(
                    OutputType.STREAM,
                    {"name": self._name, "text": text},
                ),
                self._loop,
            ).result(timeout=5)
        except Exception:
            pass
        self._last_flush = time.time()

    def writable(self) -> bool:
        return True


# ─── Worker Agent ────────────────────────────────────────────────────────────

class WorkerAgent:
    """
    Connects to the gateway, registers, and processes cell execution requests.
    """

    def __init__(self, gateway_url: str, name: str = "",
                 tags: Optional[list] = None) -> None:
        self._gateway_url = gateway_url
        self._worker_id = uuid.uuid4().hex[:12]
        self._name = name or f"{platform.node()}-{self._worker_id[:4]}"
        self._tags = tags or []
        self._executor = CellExecutor()
        self._ws = None
        self._shutdown = False
        self._running_count = 0

    def _detect_capabilities(self) -> WorkerCapabilities:
        """Auto-detect device capabilities."""
        try:
            mem = psutil.virtual_memory()
            mem_mb = mem.total // (1024 * 1024)
        except Exception:
            mem_mb = 512

        gpu = False
        gpu_name = ""
        try:
            import torch
            if torch.cuda.is_available():
                gpu = True
                gpu_name = torch.cuda.get_device_name(0)
        except ImportError:
            pass

        packages = []
        for pkg in ("numpy", "pandas", "scipy", "matplotlib",
                    "sklearn", "torch", "tensorflow", "PIL"):
            try:
                __import__(pkg)
                packages.append(pkg)
            except ImportError:
                pass

        return WorkerCapabilities(
            cpu_count=os.cpu_count() or 1,
            memory_mb=mem_mb,
            gpu=gpu,
            gpu_name=gpu_name,
            platform=sys.platform,
            python_version=platform.python_version(),
            packages=packages,
            max_concurrent=max(1, (os.cpu_count() or 1) // 2),
            tags=self._tags,
        )

    async def start(self) -> None:
        """Connect to gateway and start processing."""
        log.info("Worker %s (%s) starting — connecting to %s",
                 self._name, self._worker_id, self._gateway_url)

        backoff = 1.0
        while not self._shutdown:
            try:
                async with websockets.connect(
                    self._gateway_url,
                    ping_interval=15, ping_timeout=10,
                    max_size=50 * 1024 * 1024,
                ) as ws:
                    self._ws = ws
                    backoff = 1.0

                    # Register
                    caps = self._detect_capabilities()
                    reg_msg = make_register(self._worker_id, self._name, caps)
                    await ws.send(json.dumps(reg_msg))
                    log.info("Connected and registered with gateway")
                    log.info("  Platform: %s | Python: %s | CPU: %d | RAM: %dMB",
                             caps.platform, caps.python_version,
                             caps.cpu_count, caps.memory_mb)
                    if caps.packages:
                        log.info("  Packages: %s", ", ".join(caps.packages))

                    # Start heartbeat
                    hb_task = asyncio.create_task(self._heartbeat_loop())

                    try:
                        async for raw in ws:
                            if self._shutdown:
                                return
                            try:
                                msg = json.loads(raw)
                                await self._handle(msg)
                            except json.JSONDecodeError:
                                log.warning("Invalid JSON from gateway")
                            except Exception:
                                log.exception("Handler error")
                    finally:
                        hb_task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await hb_task

            except asyncio.CancelledError:
                return
            except Exception as exc:
                if self._shutdown:
                    return
                log.warning("Disconnected from gateway: %s — retry in %.0fs",
                            exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    async def stop(self) -> None:
        self._shutdown = True
        if self._ws:
            try:
                await self._ws.send(json.dumps(make_msg(
                    MsgType.WORKER_DEREGISTER,
                    worker_id=self._worker_id,
                )))
                await self._ws.close()
            except Exception:
                pass

    async def _heartbeat_loop(self) -> None:
        while not self._shutdown and self._ws:
            try:
                cpu_pct = psutil.cpu_percent(interval=None)
                mem_pct = psutil.virtual_memory().percent
            except Exception:
                cpu_pct, mem_pct = 0, 0

            msg = make_heartbeat(
                self._worker_id,
                running_cells=self._running_count,
                cpu_pct=cpu_pct,
                mem_pct=mem_pct,
            )
            try:
                await self._ws.send(json.dumps(msg))
            except Exception:
                break
            await asyncio.sleep(10)

    async def _handle(self, msg: Dict[str, Any]) -> None:
        msg_type = msg.get("type", "")

        if msg_type == MsgType.CELL_EXECUTE.value:
            # Run in background so we can handle more messages
            asyncio.create_task(self._execute_cell(msg))

        elif msg_type == MsgType.CELL_INTERRUPT.value:
            cell_id = msg.get("cell_id", "")
            self._executor.interrupt(cell_id)

        elif msg_type == MsgType.WORKER_STATUS.value:
            log.info("Gateway: %s", msg.get("message", ""))

    async def _execute_cell(self, msg: Dict[str, Any]) -> None:
        cell_id = msg.get("cell_id", "")
        session_id = msg.get("session_id", "")
        code = msg.get("code", "")
        execution_count = msg.get("execution_count", 0)
        cell_mode = msg.get("cell_mode", "python")
        cell_language = msg.get("cell_language", "python")

        log.info("Executing %s/%s cell %s (session %s, exec #%d): %s",
                 cell_mode, cell_language,
                 cell_id[:8], session_id[:8], execution_count,
                 code[:80].replace("\n", "\\n"))

        self._running_count += 1

        async def output_callback(output_type: OutputType,
                                  data: Dict[str, Any]) -> None:
            out_msg = make_output(
                cell_id=cell_id, session_id=session_id,
                output_type=output_type, data=data,
                worker_id=self._worker_id,
            )
            if self._ws:
                try:
                    await self._ws.send(json.dumps(out_msg))
                except Exception:
                    pass

        try:
            if cell_mode == "terminal":
                result = await self._execute_terminal(
                    cell_id=cell_id,
                    session_id=session_id,
                    code=code,
                    shell=cell_language,
                    output_callback=output_callback,
                )
            else:
                result = await self._executor.execute(
                    cell_id, session_id, code, output_callback)

            if result["status"] == "ok":
                complete_msg = make_complete(
                    cell_id=cell_id, session_id=session_id, status="ok",
                    execution_count=execution_count,
                    worker_id=self._worker_id,
                )
                if self._ws:
                    await self._ws.send(json.dumps(complete_msg))
            else:
                error_msg = make_error(
                    cell_id=cell_id, session_id=session_id,
                    ename=result.get("ename", "Error"),
                    evalue=result.get("evalue", ""),
                    traceback=result.get("traceback", []),
                    worker_id=self._worker_id,
                )
                if self._ws:
                    await self._ws.send(json.dumps(error_msg))

        except Exception:
            log.exception("Cell execution failed: %s", cell_id[:8])
            if self._ws:
                await self._ws.send(json.dumps(make_error(
                    cell_id=cell_id, session_id=session_id,
                    ename="InternalError",
                    evalue="Worker internal error during execution",
                    traceback=traceback.format_exc().splitlines(),
                    worker_id=self._worker_id,
                )))
        finally:
            self._running_count = max(0, self._running_count - 1)

    async def _execute_terminal(self, cell_id: str, session_id: str, code: str,
                                shell: str, output_callback) -> Dict[str, Any]:
        shell_cmd = self._resolve_shell(shell)
        if not shell_cmd:
            return {
                "status": "error",
                "ename": "UnsupportedShell",
                "evalue": f"Shell {shell!r} is not available on this node",
                "traceback": [],
            }

        proc = await asyncio.create_subprocess_exec(
            shell_cmd,
            "-lc",
            code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=os.getcwd(),
        )

        async def _pump(stream, name: str) -> None:
            while True:
                chunk = await stream.readline()
                if not chunk:
                    break
                await output_callback(
                    OutputType.STREAM,
                    {"name": name, "text": chunk.decode(errors="replace")},
                )

        try:
            await asyncio.gather(
                _pump(proc.stdout, "stdout"),
                _pump(proc.stderr, "stderr"),
            )
            rc = await asyncio.wait_for(proc.wait(), timeout=120)
        except asyncio.CancelledError:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            raise
        except Exception:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            raise

        if rc == 0:
            return {"status": "ok"}
        return {
            "status": "error",
            "ename": "TerminalCommandError",
            "evalue": f"Command exited with status {rc}",
            "traceback": [],
        }

    def _resolve_shell(self, shell: str) -> Optional[str]:
        candidates = []
        if shell in ("bash", "zsh", "sh"):
            candidates.append(shell)
        else:
            candidates.append("bash")
        for candidate in candidates:
            path = shutil.which(candidate)
            if path:
                return path
        return None


# ─── Entry Point ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Distributed Kernel Worker")
    parser.add_argument("--gateway", required=True,
                        help="Gateway WebSocket URL (e.g. ws://localhost:8555)")
    parser.add_argument("--name", default="",
                        help="Display name for this worker")
    parser.add_argument("--tags", nargs="*", default=[],
                        help="Tags for this worker (e.g. gpu fast)")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    agent = WorkerAgent(
        gateway_url=args.gateway,
        name=args.name,
        tags=args.tags,
    )

    loop = asyncio.new_event_loop()

    def _sig(*_):
        log.info("Shutting down worker...")
        loop.create_task(agent.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _sig)
        except NotImplementedError:
            pass

    try:
        loop.run_until_complete(agent.start())
    except KeyboardInterrupt:
        loop.run_until_complete(agent.stop())
    finally:
        loop.close()
        log.info("Worker stopped")


if __name__ == "__main__":
    main()
