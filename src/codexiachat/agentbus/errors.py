class AgentBusError(Exception):
    """Base AgentBus error."""


class ConfigError(AgentBusError):
    """Configuration is invalid or incomplete."""


class AuthError(AgentBusError):
    """Authentication or authorization failed."""


class ValidationError(AgentBusError):
    """Task, result, or path validation failed."""


class ConflictError(AgentBusError):
    """Requested state transition conflicts with current state."""
