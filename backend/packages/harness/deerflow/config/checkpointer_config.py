"""Configuration for LangGraph checkpointer."""

from typing import Literal

from pydantic import BaseModel, Field

CheckpointerType = Literal["memory", "sqlite", "postgres"]


class CheckpointerConfig(BaseModel):
    """Configuration for LangGraph state persistence checkpointer."""

    type: CheckpointerType = Field(
        description="Checkpointer backend type. "
        "'memory' is in-process only (lost on restart). "
        "'sqlite' persists to a local file (requires langgraph-checkpoint-sqlite). "
        "'postgres' persists to PostgreSQL (requires langgraph-checkpoint-postgres)."
    )
    connection_string: str | None = Field(
        default=None,
        description="Connection string for sqlite (file path) or postgres (DSN). "
        "Required for sqlite and postgres types. "
        "For sqlite, use a file path like '.deer-flow/checkpoints.db' or ':memory:' for in-memory. "
        "For postgres, use a DSN like 'postgresql://user:pass@localhost:5432/db'.",
    )


# Sentinel: distinguishes "never set" from "explicitly set to None".
# get_checkpointer() only triggers app-config loading when the state is _UNSET.
_UNSET: object = object()

# Global configuration instance.
# _UNSET  → never initialised (app config should be consulted).
# None    → explicitly set to "no checkpointer" (e.g. by a test fixture).
# config  → a real CheckpointerConfig chosen by set_checkpointer_config / YAML load.
_checkpointer_config: object = _UNSET


def get_checkpointer_config() -> CheckpointerConfig | None:
    """Get the current checkpointer configuration, or None if not configured."""
    if _checkpointer_config is _UNSET:
        return None
    return _checkpointer_config  # type: ignore[return-value]


def is_checkpointer_config_set() -> bool:
    """Return True if the config was explicitly set (even to None), False if never initialised."""
    return _checkpointer_config is not _UNSET


def set_checkpointer_config(config: CheckpointerConfig | None) -> None:
    """Set the checkpointer configuration."""
    global _checkpointer_config
    _checkpointer_config = config


def reset_checkpointer_config() -> None:
    """Reset checkpointer config back to the uninitialised sentinel.

    Use this (instead of ``set_checkpointer_config(None)``) when you want
    ``get_checkpointer()`` to re-consult the app config on the next call.
    In tests, ``set_checkpointer_config(None)`` is the right call to say
    "no checkpointer" — the sentinel is an internal implementation detail.
    """
    global _checkpointer_config
    _checkpointer_config = _UNSET


def load_checkpointer_config_from_dict(config_dict: dict) -> None:
    """Load checkpointer configuration from a dictionary."""
    global _checkpointer_config
    _checkpointer_config = CheckpointerConfig(**config_dict)
