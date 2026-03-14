"""Core package.

Keep this import-light so offline experiment modules can import `core.prompts`
without pulling in unfinished DB/API dependencies.
"""

__all__ = []

try:
    from core.context import AgentContext, AgentDecision, ExecutionResult

    __all__ = ["AgentContext", "AgentDecision", "ExecutionResult"]
except Exception:
    # Offline experiment tooling should still be importable even if the
    # product-serving stack is not installed or wired correctly.
    pass
