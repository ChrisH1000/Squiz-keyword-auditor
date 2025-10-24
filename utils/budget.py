"""Budget manager to track and limit LLM API calls."""

from typing import Optional
import logging

logger = logging.getLogger(__name__)


class BudgetManager:
    """Manages and enforces LLM call budget limits."""
    
    def __init__(self, max_calls: int = 10):
        """Initialize budget manager.
        
        Args:
            max_calls: Maximum number of LLM calls allowed
        """
        self.max_calls = max_calls
        self.calls_made = 0
        self.calls_by_type = {}
        
    def can_call(self, call_type: str = "general") -> bool:
        """Check if another LLM call is within budget.
        
        Args:
            call_type: Type of call (e.g., 'summarize', 'extract', 'general')
            
        Returns:
            True if call is within budget, False otherwise
        """
        if self.calls_made >= self.max_calls:
            logger.warning(
                f"Budget exceeded: {self.calls_made}/{self.max_calls} calls made"
            )
            return False
        return True
    
    def record_call(self, call_type: str = "general", tokens_used: Optional[int] = None):
        """Record an LLM call.
        
        Args:
            call_type: Type of call made
            tokens_used: Optional token count
        """
        self.calls_made += 1
        if call_type not in self.calls_by_type:
            self.calls_by_type[call_type] = []
        self.calls_by_type[call_type].append({
            "call_number": self.calls_made,
            "tokens": tokens_used
        })
        logger.info(
            f"LLM call recorded: {call_type} ({self.calls_made}/{self.max_calls})"
        )
    
    def get_remaining(self) -> int:
        """Get remaining call budget.
        
        Returns:
            Number of calls remaining
        """
        return max(0, self.max_calls - self.calls_made)
    
    def get_stats(self) -> dict:
        """Get budget statistics.
        
        Returns:
            Dictionary with budget stats
        """
        return {
            "max_calls": self.max_calls,
            "calls_made": self.calls_made,
            "calls_remaining": self.get_remaining(),
            "calls_by_type": self.calls_by_type
        }
    
    def reset(self):
        """Reset the budget counter."""
        self.calls_made = 0
        self.calls_by_type = {}
        logger.info("Budget reset")
