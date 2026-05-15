"""
Ollama AI Agent — connects to local Ollama instance, autonomously generates
and executes code cells for MEV research. Humans observe progress.

The agent loop:
  1. Plan: Decide what to research/compute next
  2. Write: Generate a Python code cell
  3. Execute: Send to a worker node for execution
  4. Analyze: Read the output, decide next steps
  5. Recurse: Repeat with accumulated knowledge

Each iteration is visible in the notebook as cells that appear, execute,
and produce results — all while humans watch.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Callable, Coroutine, Dict, List, Optional

import aiohttp

log = logging.getLogger("distkernel.ollama")

OLLAMA_URL = "http://localhost:11434"

MEV_SYSTEM_PROMPT = """\
You are an autonomous MEV (Maximum Extractable Value) research agent running inside a distributed compute notebook.

Your role:
- Write Python code cells that explore, analyze, and extract valuable blockchain/financial knowledge
- Each response should be a SINGLE executable Python code cell
- You have access to: numpy, pandas, scipy, matplotlib, requests, web3 (if installed), json, math, time, asyncio
- After each cell executes, you'll see the output and decide what to research next
- Build on previous results — maintain state across cells via variables
- Focus on: market microstructure, arbitrage detection, mempool analysis patterns, DEX/CEX spread analysis, gas optimization, sandwich attack patterns, liquidation mechanics, flashloan strategies (theoretical)
- Be rigorous: validate data, handle errors, show intermediate results
- Think recursively: each finding should suggest deeper investigation paths

Output ONLY the Python code. No markdown fences. No explanation outside the code.
Use comments in the code to explain your reasoning.
Print results clearly so they can be analyzed in the next iteration.

Current research iteration: {iteration}
Previous findings summary: {findings}
"""

GENERAL_SYSTEM_PROMPT = """\
You are an autonomous AI research agent running inside a distributed compute notebook.

Your role:
- Write Python code cells that explore, analyze, and extract valuable knowledge
- Each response should be a SINGLE executable Python code cell
- You have access to standard Python libraries and any packages installed on worker nodes
- After each cell executes, you'll see the output and decide what to research next
- Build on previous results — maintain state across cells via variables
- Be rigorous: validate data, handle errors, show intermediate results
- Think recursively: each finding should suggest deeper investigation paths

Output ONLY the Python code. No markdown fences. No explanation outside the code.
Use comments in the code to explain your reasoning.

Current research iteration: {iteration}
Goal: {goal}
Previous findings summary: {findings}
"""


class OllamaClient:
    """Async client for local Ollama API."""

    def __init__(self, base_url: str = OLLAMA_URL) -> None:
        self._base_url = base_url.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=300))
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def is_available(self) -> bool:
        """Check if Ollama is running locally."""
        try:
            session = await self._get_session()
            async with session.get(f"{self._base_url}/api/tags") as resp:
                return resp.status == 200
        except Exception:
            return False

    async def list_models(self) -> List[str]:
        """List available models."""
        try:
            session = await self._get_session()
            async with session.get(f"{self._base_url}/api/tags") as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    async def generate(self, model: str, prompt: str,
                       system: str = "", temperature: float = 0.7,
                       stream_callback: Optional[Callable[[str], Coroutine]] = None
                       ) -> str:
        """Generate text from Ollama, optionally streaming tokens."""
        session = await self._get_session()
        payload = {
            "model": model,
            "prompt": prompt,
            "system": system,
            "stream": stream_callback is not None,
            "options": {
                "temperature": temperature,
                "num_predict": 4096,
            },
        }

        async with session.post(
            f"{self._base_url}/api/generate",
            json=payload,
        ) as resp:
            if resp.status != 200:
                error = await resp.text()
                raise RuntimeError(f"Ollama error {resp.status}: {error}")

            if stream_callback:
                full_response = []
                async for line in resp.content:
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("response", "")
                        if token:
                            full_response.append(token)
                            await stream_callback(token)
                        if chunk.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue
                return "".join(full_response)
            else:
                data = await resp.json()
                return data.get("response", "")

    async def chat(self, model: str, messages: List[Dict[str, str]],
                   temperature: float = 0.7,
                   stream_callback: Optional[Callable[[str], Coroutine]] = None
                   ) -> str:
        """Chat completion with Ollama."""
        session = await self._get_session()
        payload = {
            "model": model,
            "messages": messages,
            "stream": stream_callback is not None,
            "options": {
                "temperature": temperature,
                "num_predict": 4096,
            },
        }

        async with session.post(
            f"{self._base_url}/api/chat",
            json=payload,
        ) as resp:
            if resp.status != 200:
                error = await resp.text()
                raise RuntimeError(f"Ollama chat error {resp.status}: {error}")

            if stream_callback:
                full_response = []
                async for line in resp.content:
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            full_response.append(token)
                            await stream_callback(token)
                        if chunk.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue
                return "".join(full_response)
            else:
                data = await resp.json()
                return data.get("message", {}).get("content", "")


class ResearchAgent:
    """
    Autonomous AI agent that generates code, executes it on workers,
    analyzes output, and recursively deepens research.

    The agent is observable — every action appears as a cell in the notebook.
    Humans can pause, resume, redirect, or inject cells.
    """

    def __init__(self, ollama: OllamaClient, model: str = "llama3.2",
                 mode: str = "mev", memory_storage=None, agent_id: str = None) -> None:
        self._ollama = ollama
        self._model = model
        self._mode = mode  # "mev" or "general"
        self._iteration = 0
        self._max_iterations = 50
        self._findings: List[str] = []
        self._history: List[Dict[str, str]] = []  # chat history
        self._paused = False
        self._stopped = False
        self._goal = "Explore MEV strategies and extract valuable research"
        self._cell_callback: Optional[Callable] = None  # called to create+execute a cell
        self._status_callback: Optional[Callable] = None  # called to push status updates
        self._memory_storage = memory_storage
        self._agent_id = agent_id or f"agent_{uuid.uuid4().hex[:12]}"
        self._memory = None
        self._current_cell_start_time = None

    @property
    def is_running(self) -> bool:
        return not self._paused and not self._stopped

    def pause(self) -> None:
        self._paused = True
        log.info("Agent paused at iteration %d", self._iteration)

    def resume(self) -> None:
        self._paused = False
        log.info("Agent resumed at iteration %d", self._iteration)

    def stop(self) -> None:
        self._stopped = True
        log.info("Agent stopped at iteration %d", self._iteration)

    async def load_memory(self) -> None:
        """Load agent memory from storage."""
        if self._memory_storage:
            from .agent_memory import AgentMemory
            self._memory = await self._memory_storage.load_memory(self._agent_id)
            if self._memory:
                self._findings = self._memory.execution_history[-10:]  # Recent findings
                log.info("Loaded memory for agent %s: %d executions, %.1f%% success rate",
                         self._agent_id, self._memory.total_cells_executed,
                         self._memory.get_success_rate() * 100)
            else:
                # Create new memory
                self._memory = AgentMemory(
                    agent_id=self._agent_id,
                    session_id=self._agent_id,  # Use agent_id as session_id for now
                    created_at=time.time(),
                    last_updated=time.time(),
                )
        else:
            self._memory = None

    async def save_memory(self) -> None:
        """Save agent memory to storage."""
        if self._memory_storage and self._memory:
            self._memory.last_updated = time.time()
            await self._memory_storage.save_memory(self._memory)
            log.info("Saved memory for agent %s", self._agent_id)

    async def record_execution(self, cell_id: str, code: str, output: str,
                               outcome: str, execution_time: float,
                               worker_id: str, cell_mode: str = "python",
                               cell_language: str = "python") -> None:
        """Record a cell execution in memory."""
        if not self._memory:
            return
        
        from .agent_memory import CellExecutionRecord, Outcome
        
        outcome_enum = Outcome.SUCCESS if outcome == "ok" else Outcome.ERROR if outcome == "error" else Outcome.TIMEOUT
        
        record = CellExecutionRecord(
            timestamp=time.time(),
            cell_id=cell_id,
            cell_mode=cell_mode,
            cell_language=cell_language,
            code=code,
            output=output[:5000],  # Limit output size
            outcome=outcome_enum,
            execution_time=execution_time,
            worker_id=worker_id,
            tags=[self._mode, f"iter_{self._iteration}"]
        )
        
        self._memory.add_execution(record)
        
        # Auto-save every 5 executions
        if self._memory.total_cells_executed % 5 == 0:
            await self.save_memory()

    def get_memory_summary(self) -> Dict[str, Any]:
        """Get a summary of agent memory for display."""
        if not self._memory:
            return {
                "agent_id": self._agent_id,
                "total_executions": 0,
                "success_rate": 0.0,
                "recent_failures": [],
                "learned_patterns": [],
            }
        
        recent_failures = [
            {"code": r.code[:100], "error": r.output[:200]}
            for r in self._memory.execution_history[-10:]
            if r.outcome != Outcome.SUCCESS
        ]
        
        top_patterns = sorted(
            self._memory.learned_patterns,
            key=lambda p: p.confidence,
            reverse=True
        )[:5]
        
        return {
            "agent_id": self._agent_id,
            "total_executions": self._memory.total_cells_executed,
            "success_rate": self._memory.get_success_rate(),
            "recent_failures": recent_failures,
            "learned_patterns": [
                {"pattern": p.pattern, "confidence": p.confidence, "uses": p.success_count + p.failure_count}
                for p in top_patterns
            ],
        }

    def set_goal(self, goal: str) -> None:
        self._goal = goal
        log.info("Agent goal updated: %s", goal[:100])

    def set_model(self, model: str) -> None:
        self._model = model
        log.info("Agent model changed to: %s", model)

    def get_state(self) -> Dict[str, Any]:
        return {
            "iteration": self._iteration,
            "max_iterations": self._max_iterations,
            "paused": self._paused,
            "stopped": self._stopped,
            "model": self._model,
            "mode": self._mode,
            "goal": self._goal,
            "findings_count": len(self._findings),
            "last_findings": self._findings[-3:] if self._findings else [],
        }

    async def run(self, cell_callback: Callable, status_callback: Callable) -> None:
        """
        Main agent loop. Generates code cells, executes them, analyzes results.

        cell_callback(code: str) -> Dict with outputs/status
        status_callback(status: Dict) -> None (push UI updates)
        """
        self._cell_callback = cell_callback
        self._status_callback = status_callback
        self._stopped = False
        self._paused = False

        log.info("Agent starting: model=%s, mode=%s, goal=%s",
                 self._model, self._mode, self._goal[:80])

        # Load memory at start
        await self.load_memory()

        await self._push_status("starting")

        try:
            while not self._stopped and self._iteration < self._max_iterations:
                # Check pause
                while self._paused and not self._stopped:
                    await asyncio.sleep(0.5)

                if self._stopped:
                    break

                self._iteration += 1
                await self._push_status("thinking")

                try:
                    # Generate code
                    code = await self._generate_cell()
                    if not code or not code.strip():
                        log.warning("Agent produced empty code at iteration %d",
                                    self._iteration)
                        await asyncio.sleep(2)
                        continue

                    # Clean code (remove markdown fences if model adds them)
                    code = self._clean_code(code)

                    await self._push_status("executing")

                    # Execute via callback
                    self._current_cell_start_time = time.time()
                    result = await cell_callback(code)
                    execution_time = time.time() - self._current_cell_start_time

                    # Analyze output
                    output_text = result.get("output", "")
                    status = result.get("status", "ok")
                    worker_id = result.get("worker_id", "unknown")

                    # Record execution in memory
                    await self.record_execution(
                        cell_id=f"iter_{self._iteration}",
                        code=code,
                        output=output_text,
                        outcome=status,
                        execution_time=execution_time,
                        worker_id=worker_id,
                        cell_mode="python",
                        cell_language="python"
                    )

                    # Record findings
                    finding = f"Iteration {self._iteration}: {output_text[:500]}"
                    self._findings.append(finding)

                    # Add to chat history for context
                    self._history.append({"role": "assistant", "content": code})
                    self._history.append({
                        "role": "user",
                        "content": f"Cell output (status={status}):\n{output_text[:2000]}\n\nBased on this output, what should we investigate next? Write the next Python code cell."
                    })

                    # Trim history to avoid context overflow
                    if len(self._history) > 20:
                        self._history = self._history[-16:]

                    await self._push_status("analyzing")
                    log.info("Agent iteration %d complete (status=%s, output=%d chars)",
                             self._iteration, status, len(output_text))

                    # Brief pause between iterations
                    await asyncio.sleep(2)

                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    log.exception("Agent error at iteration %d", self._iteration)
                    self._findings.append(
                        f"Iteration {self._iteration}: ERROR — {exc}")
                    await asyncio.sleep(5)

        except Exception as exc:
            log.exception("Agent fatal error: %s", exc)

        finally:
            # Save memory on completion
            await self.save_memory()

        await self._push_status("stopped")
        log.info("Agent finished after %d iterations", self._iteration)

    async def _generate_cell(self) -> str:
        """Ask the LLM to generate the next code cell."""
        findings_summary = "\n".join(self._findings[-5:]) if self._findings else "No previous findings yet. Start with initial exploration."

        if self._mode == "mev":
            system = MEV_SYSTEM_PROMPT.format(
                iteration=self._iteration,
                findings=findings_summary,
            )
        else:
            system = GENERAL_SYSTEM_PROMPT.format(
                iteration=self._iteration,
                goal=self._goal,
                findings=findings_summary,
            )

        if self._history:
            # Use chat for context continuity
            messages = [{"role": "system", "content": system}] + self._history
            return await self._ollama.chat(
                model=self._model,
                messages=messages,
                temperature=0.7,
            )
        else:
            # First iteration
            prompt = (
                f"Write the first Python code cell for iteration 1.\n"
                f"Goal: {self._goal}\n"
                f"Start with foundational exploration and data gathering."
            )
            return await self._ollama.generate(
                model=self._model,
                prompt=prompt,
                system=system,
                temperature=0.7,
            )

    def _clean_code(self, code: str) -> str:
        """Remove markdown fences if the model wraps code in them."""
        code = code.strip()
        if code.startswith("```python"):
            code = code[len("```python"):].strip()
        elif code.startswith("```"):
            code = code[3:].strip()
        if code.endswith("```"):
            code = code[:-3].strip()
        return code

    async def _push_status(self, state: str) -> None:
        if self._status_callback:
            try:
                await self._status_callback({
                    "agent_state": state,
                    **self.get_state(),
                })
            except Exception:
                pass
