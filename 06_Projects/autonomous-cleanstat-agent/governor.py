"""
Governor - Controls autonomous agent execution
Enforces policies and prevents runaway loops
"""

from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class GovernorConfig:
    """Governor configuration"""
    max_iterations: int = 25
    max_cost_usd: float = 1.50
    max_error_rate: float = 0.30
    max_errors: int = 3


@dataclass
class ExecutionResult:
    """Result of action execution"""
    status: str  # "success", "error", "done"
    action: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    cost_usd: float = 0.0
    duration_ms: float = 0.0


class Governor:
    """Governs autonomous agent execution"""
    
    def __init__(self, config: GovernorConfig = None):
        self.config = config or GovernorConfig()
        self.iterations = 0
        self.total_cost = 0.0
        self.total_errors = 0
        self.action_history = []
        
    def allow(self, action: str, input_data: Dict[str, Any]) -> tuple[bool, str]:
        """Check if action is allowed"""
        if self.iterations >= self.config.max_iterations:
            return False, f"Max iterations ({self.config.max_iterations}) reached"
        
        if self.total_cost >= self.config.max_cost_usd:
            return False, f"Max cost (${self.config.max_cost_usd}) reached"
        
        if self.iterations > 0:
            error_rate = self.total_errors / self.iterations
            if error_rate >= self.config.max_error_rate:
                return False, f"Error rate ({error_rate:.2%}) exceeded threshold"
        
        if self.total_errors >= self.config.max_errors:
            return False, f"Max errors ({self.config.max_errors}) reached"
        
        return True, ""
    
    def observe(self, result: ExecutionResult):
        """Observe result of action"""
        self.iterations += 1
        self.total_cost += result.cost_usd
        
        if result.status == "error":
            self.total_errors += 1
        
        self.action_history.append({
            "iteration": self.iterations,
            "action": result.action,
            "status": result.status,
            "cost_usd": result.cost_usd,
            "duration_ms": result.duration_ms,
            "error": result.error if result.error else None
        })
    
    def should_stop(self) -> tuple[bool, str]:
        """Check if execution should stop"""
        if self.iterations >= self.config.max_iterations:
            return True, f"Max iterations ({self.config.max_iterations}) reached"
        
        if self.total_cost >= self.config.max_cost_usd:
            return True, f"Max cost (${self.config.max_cost_usd}) reached"
        
        if self.total_errors >= self.config.max_errors:
            return True, f"Max errors ({self.config.max_errors}) reached"
        
        if self.iterations > 0:
            error_rate = self.total_errors / self.iterations
            if error_rate >= self.config.max_error_rate:
                return True, f"Error rate ({error_rate:.2%}) exceeded threshold"
        
        return False, ""
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics"""
        error_rate = self.total_errors / self.iterations if self.iterations > 0 else 0.0
        
        return {
            "iterations": self.iterations,
            "total_cost_usd": round(self.total_cost, 4),
            "total_errors": self.total_errors,
            "error_rate": round(error_rate, 4),
            "remaining_iterations": self.config.max_iterations - self.iterations,
            "remaining_cost_usd": round(self.config.max_cost_usd - self.total_cost, 4)
        }
