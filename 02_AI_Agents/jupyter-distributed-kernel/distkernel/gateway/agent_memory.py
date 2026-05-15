"""
Agent Memory System for MEV Research Agents
Tracks execution history, learns from mistakes, stores strategy results.
Teleportable - persists to Google Drive.
"""

import json
import time
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Any
from enum import Enum
import hashlib

class Outcome(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"
    TIMEOUT = "timeout"

@dataclass
class CellExecutionRecord:
    """Record of a single cell execution."""
    timestamp: float
    cell_id: str
    cell_mode: str
    cell_language: str
    code: str
    output: str
    outcome: Outcome
    execution_time: float
    worker_id: str
    tags: List[str] = field(default_factory=list)

@dataclass
class StrategyResult:
    """Result of a MEV strategy test."""
    timestamp: float
    strategy_name: str
    parameters: Dict[str, Any]
    profit: float
    trades: int
    success_rate: float
    notes: str

@dataclass
class LearnedPattern:
    """A pattern the agent has learned (what works/doesn't work)."""
    pattern: str
    success_count: int
    failure_count: int
    last_used: float
    confidence: float  # 0-1

@dataclass
class AgentMemory:
    """Complete agent memory state."""
    agent_id: str
    session_id: str
    created_at: float
    last_updated: float
    execution_history: List[CellExecutionRecord] = field(default_factory=list)
    strategy_results: List[StrategyResult] = field(default_factory=list)
    learned_patterns: List[LearnedPattern] = field(default_factory=list)
    total_cells_executed: int = 0
    total_successes: int = 0
    total_failures: int = 0

    def add_execution(self, record: CellExecutionRecord) -> None:
        """Add a cell execution record."""
        self.execution_history.append(record)
        self.total_cells_executed += 1
        if record.outcome == Outcome.SUCCESS:
            self.total_successes += 1
        else:
            self.total_failures += 1
        self.last_updated = time.time()
        
        # Learn from this execution
        self._learn_from_execution(record)

    def add_strategy_result(self, result: StrategyResult) -> None:
        """Add a strategy test result."""
        self.strategy_results.append(result)
        self.last_updated = time.time()

    def get_success_rate(self) -> float:
        """Calculate overall success rate."""
        if self.total_cells_executed == 0:
            return 0.0
        return self.total_successes / self.total_cells_executed

    def get_recent_history(self, limit: int = 50) -> List[CellExecutionRecord]:
        """Get recent execution history."""
        return self.execution_history[-limit:]

    def get_pattern_confidence(self, pattern: str) -> float:
        """Get confidence level for a learned pattern."""
        for p in self.learned_patterns:
            if p.pattern == pattern:
                return p.confidence
        return 0.0

    def _learn_from_execution(self, record: CellExecutionRecord) -> None:
        """Extract and store patterns from execution."""
        # Extract code patterns (first line, imports, function definitions)
        lines = record.code.strip().split('\n')
        if lines:
            first_line = lines[0].strip()
            if first_line and not first_line.startswith('#'):
                self._update_pattern(first_line, record.outcome)
        
        # Track import patterns
        for line in lines:
            if line.strip().startswith('import ') or line.strip().startswith('from '):
                self._update_pattern(line.strip(), record.outcome)

    def _update_pattern(self, pattern: str, outcome: Outcome) -> None:
        """Update pattern statistics based on outcome."""
        # Find existing pattern or create new
        for p in self.learned_patterns:
            if p.pattern == pattern:
                if outcome == Outcome.SUCCESS:
                    p.success_count += 1
                else:
                    p.failure_count += 1
                p.last_used = time.time()
                total = p.success_count + p.failure_count
                p.confidence = p.success_count / total if total > 0 else 0
                return
        
        # Create new pattern
        success = 1 if outcome == Outcome.SUCCESS else 0
        failure = 0 if outcome == Outcome.SUCCESS else 1
        self.learned_patterns.append(LearnedPattern(
            pattern=pattern,
            success_count=success,
            failure_count=failure,
            last_used=time.time(),
            confidence=success / (success + failure) if (success + failure) > 0 else 0
        ))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "execution_history": [asdict(r) for r in self.execution_history],
            "strategy_results": [asdict(r) for r in self.strategy_results],
            "learned_patterns": [asdict(p) for p in self.learned_patterns],
            "total_cells_executed": self.total_cells_executed,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMemory":
        """Create from dictionary."""
        execution_history = [
            CellExecutionRecord(**r) for r in data.get("execution_history", [])
        ]
        strategy_results = [
            StrategyResult(**r) for r in data.get("strategy_results", [])
        ]
        learned_patterns = [
            LearnedPattern(**p) for p in data.get("learned_patterns", [])
        ]
        return cls(
            agent_id=data["agent_id"],
            session_id=data["session_id"],
            created_at=data["created_at"],
            last_updated=data["last_updated"],
            execution_history=execution_history,
            strategy_results=strategy_results,
            learned_patterns=learned_patterns,
            total_cells_executed=data.get("total_cells_executed", 0),
            total_successes=data.get("total_successes", 0),
            total_failures=data.get("total_failures", 0),
        )

# ─── Memory Storage Interface ─────────────────────────────────────────────────

class MemoryStorage:
    """Interface for storing agent memory (Google Drive or local)."""
    
    def __init__(self, google_user=None):
        self.google_user = google_user
        self._local_cache: Dict[str, AgentMemory] = {}
    
    async def save_memory(self, memory: AgentMemory) -> bool:
        """Save agent memory to storage."""
        self._local_cache[memory.agent_id] = memory
        
        if self.google_user:
            from .google_auth import DriveStorage
            storage = DriveStorage(self.google_user)
            data = memory.to_dict()
            return await storage.save_notebook(
                f"agent_memory_{memory.agent_id}",
                [{"type": "agent_memory", "data": data}]
            )
        
        # Local fallback
        import os
        cache_dir = os.path.expanduser("~/.distkernel/agent_memory")
        os.makedirs(cache_dir, exist_ok=True)
        path = os.path.join(cache_dir, f"{memory.agent_id}.json")
        with open(path, 'w') as f:
            json.dump(memory.to_dict(), f, indent=2)
        return True
    
    async def load_memory(self, agent_id: str) -> Optional[AgentMemory]:
        """Load agent memory from storage."""
        # Check cache first
        if agent_id in self._local_cache:
            return self._local_cache[agent_id]
        
        if self.google_user:
            from .google_auth import DriveStorage
            storage = DriveStorage(self.google_user)
            notebook = await storage.load_notebook()
            if notebook and notebook.get("cells"):
                for cell in notebook["cells"]:
                    if cell.get("type") == "agent_memory":
                        data = cell.get("data", {})
                        if data.get("agent_id") == agent_id:
                            memory = AgentMemory.from_dict(data)
                            self._local_cache[agent_id] = memory
                            return memory
        
        # Local fallback
        import os
        path = os.path.expanduser(f"~/.distkernel/agent_memory/{agent_id}.json")
        if os.path.exists(path):
            with open(path, 'r') as f:
                data = json.load(f)
                memory = AgentMemory.from_dict(data)
                self._local_cache[agent_id] = memory
                return memory
        
        return None
    
    async def list_memories(self) -> List[str]:
        """List all available agent memory IDs."""
        if self.google_user:
            from .google_auth import DriveStorage
            storage = DriveStorage(self.google_user)
            notebook = await storage.load_notebook()
            if notebook and notebook.get("cells"):
                return [
                    cell.get("data", {}).get("agent_id")
                    for cell in notebook["cells"]
                    if cell.get("type") == "agent_memory"
                ]
        
        # Local fallback
        import os
        cache_dir = os.path.expanduser("~/.distkernel/agent_memory")
        if os.path.exists(cache_dir):
            return [
                f.replace(".json", "")
                for f in os.listdir(cache_dir)
                if f.endswith(".json")
            ]
        return []
