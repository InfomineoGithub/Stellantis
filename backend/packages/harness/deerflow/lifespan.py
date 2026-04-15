"""LangGraph server lifespan hook for DeerFlow.

Eagerly initializes the sandbox provider at server startup when pre_warm_count > 0,
ensuring pre-warmed containers are ready before the first request arrives rather
than waiting for the lazy singleton to be created on the first agent run.
"""

import logging
from contextlib import asynccontextmanager

from starlette.applications import Starlette

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    """Eagerly initialize sandbox provider at startup if pre-warming is configured."""
    try:
        from deerflow.config import get_app_config

        config = get_app_config()
        pre_warm_count = getattr(config.sandbox, "pre_warm_count", 0) or 0
        if pre_warm_count > 0:
            logger.info(f"Eagerly initializing sandbox provider (pre_warm_count={pre_warm_count})")
            from deerflow.sandbox.sandbox_provider import get_sandbox_provider

            get_sandbox_provider()
    except Exception as e:
        logger.warning(f"Failed to eagerly initialize sandbox provider: {e}")
    yield


app = Starlette(lifespan=lifespan)
