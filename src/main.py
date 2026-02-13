"""
MCP-Mem0 Server with Per-User Memory Isolation
Modified from coleam00/mcp-mem0 to support multi-user environments.

User identification priority:
1. X-User-ID HTTP header (set automatically by LibreChat via {{LIBRECHAT_USER_ID}})
2. user_id tool parameter (optional, for direct API/testing use)
3. DEFAULT_USER_ID env var fallback
"""

from mcp.server.fastmcp import FastMCP, Context
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass
from dotenv import load_dotenv
from mem0 import Memory
import contextvars
import asyncio
import json
import os
import logging

from utils import get_mem0_client

load_dotenv()

# Configure logging
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
logger = logging.getLogger("mcp-mem0")

# Default user ID fallback (env var or hardcoded)
DEFAULT_USER_ID = os.getenv("DEFAULT_USER_ID", "default")

# Context variable to store user_id extracted from HTTP headers per-request
current_user_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    'current_user_id', default=None
)


def _resolve_user_id(user_id: str | None = None) -> str:
    """Resolve user_id with priority: explicit param > header context var > env default."""
    if user_id and user_id.strip():
        resolved = user_id.strip()
        logger.debug(f"User ID from tool parameter: {resolved}")
        return resolved
    
    ctx_user = current_user_id.get()
    if ctx_user and ctx_user.strip():
        resolved = ctx_user.strip()
        logger.debug(f"User ID from HTTP header: {resolved}")
        return resolved
    
    logger.debug(f"User ID falling back to default: {DEFAULT_USER_ID}")
    return DEFAULT_USER_ID


# Create a dataclass for our application context
@dataclass
class Mem0Context:
    """Context for the Mem0 MCP server."""
    mem0_client: Memory


@asynccontextmanager
async def mem0_lifespan(server: FastMCP) -> AsyncIterator[Mem0Context]:
    """Manages the Mem0 client lifecycle."""
    mem0_client = get_mem0_client()
    try:
        yield Mem0Context(mem0_client=mem0_client)
    finally:
        pass


# Initialize FastMCP server
mcp = FastMCP(
    "mcp-mem0",
    description="MCP server for per-user long term memory storage and retrieval with Mem0",
    lifespan=mem0_lifespan,
    host=os.getenv("HOST", "0.0.0.0"),
    port=int(os.getenv("PORT", "8050"))
)


@mcp.tool()
async def save_memory(ctx: Context, text: str, user_id: str = "") -> str:
    """Save information to long-term memory for the current user.

    Stores any type of information with semantic indexing for later retrieval.
    User identification is automatic via HTTP headers in multi-user environments.

    Args:
        ctx: The MCP server provided context which includes the Mem0 client
        text: The content to store in memory, including any relevant details and context
        user_id: Optional explicit user identifier. Leave empty to use automatic detection.
    """
    resolved_uid = _resolve_user_id(user_id)
    try:
        mem0_client = ctx.request_context.lifespan_context.mem0_client
        messages = [{"role": "user", "content": text}]
        mem0_client.add(messages, user_id=resolved_uid)
        preview = f"{text[:100]}..." if len(text) > 100 else text
        logger.info(f"Memory saved for user '{resolved_uid}': {preview}")
        return f"Successfully saved memory for user '{resolved_uid}': {preview}"
    except Exception as e:
        logger.error(f"Error saving memory for user '{resolved_uid}': {e}")
        return f"Error saving memory: {str(e)}"


@mcp.tool()
async def get_all_memories(ctx: Context, user_id: str = "") -> str:
    """Get all stored memories for the current user.

    Retrieves complete memory context. User identification is automatic via HTTP headers.

    Args:
        ctx: The MCP server provided context which includes the Mem0 client
        user_id: Optional explicit user identifier. Leave empty to use automatic detection.

    Returns a JSON formatted list of all stored memories.
    """
    resolved_uid = _resolve_user_id(user_id)
    try:
        mem0_client = ctx.request_context.lifespan_context.mem0_client
        memories = mem0_client.get_all(user_id=resolved_uid)

        if isinstance(memories, dict) and "results" in memories:
            flattened_memories = [memory["memory"] for memory in memories["results"]]
        else:
            flattened_memories = memories

        logger.info(f"Retrieved {len(flattened_memories)} memories for user '{resolved_uid}'")
        return json.dumps(flattened_memories, indent=2)
    except Exception as e:
        logger.error(f"Error retrieving memories for user '{resolved_uid}': {e}")
        return f"Error retrieving memories: {str(e)}"


@mcp.tool()
async def search_memories(ctx: Context, query: str, limit: int = 3, user_id: str = "") -> str:
    """Search memories using semantic search for the current user.

    Finds relevant information from memory ranked by relevance.
    User identification is automatic via HTTP headers.

    Args:
        ctx: The MCP server provided context which includes the Mem0 client
        query: Search query string describing what you're looking for. Can be natural language.
        limit: Maximum number of results to return (default: 3)
        user_id: Optional explicit user identifier. Leave empty to use automatic detection.
    """
    resolved_uid = _resolve_user_id(user_id)
    try:
        mem0_client = ctx.request_context.lifespan_context.mem0_client
        memories = mem0_client.search(query, user_id=resolved_uid, limit=limit)

        if isinstance(memories, dict) and "results" in memories:
            flattened_memories = [memory["memory"] for memory in memories["results"]]
        else:
            flattened_memories = memories

        logger.info(
            f"Search for '{query}' returned {len(flattened_memories)} results "
            f"for user '{resolved_uid}'"
        )
        return json.dumps(flattened_memories, indent=2)
    except Exception as e:
        logger.error(f"Error searching memories for user '{resolved_uid}': {e}")
        return f"Error searching memories: {str(e)}"


@mcp.tool()
async def delete_all_memories(ctx: Context, confirm: bool = False, user_id: str = "") -> str:
    """Delete all stored memories for the current user. Requires explicit confirmation.

    Args:
        ctx: The MCP server provided context which includes the Mem0 client
        confirm: Must be set to true to confirm deletion. Safety guard against accidental deletion.
        user_id: Optional explicit user identifier. Leave empty to use automatic detection.
    """
    if not confirm:
        return "Deletion not confirmed. Set confirm=true to delete all memories. This action cannot be undone."

    resolved_uid = _resolve_user_id(user_id)
    try:
        mem0_client = ctx.request_context.lifespan_context.mem0_client
        mem0_client.delete_all(user_id=resolved_uid)
        logger.info(f"All memories deleted for user '{resolved_uid}'")
        return f"Successfully deleted all memories for user '{resolved_uid}'."
    except Exception as e:
        logger.error(f"Error deleting memories for user '{resolved_uid}': {e}")
        return f"Error deleting memories: {str(e)}"


def _create_user_id_middleware():
    """Create Starlette middleware class for X-User-ID header extraction."""
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request

    class UserIDMiddleware(BaseHTTPMiddleware):
        """Extract X-User-ID from request headers and set context variable.

        Checks headers in priority order:
        1. x-user-id (standard, set by LibreChat {{LIBRECHAT_USER_ID}})
        2. x-user-email (alternative, set by LibreChat {{LIBRECHAT_USER_EMAIL}})
        3. x-librechat-user-id (explicit LibreChat header)
        """
        async def dispatch(self, request: Request, call_next):
            user_id = (
                request.headers.get("x-user-id")
                or request.headers.get("x-user-email")
                or request.headers.get("x-librechat-user-id")
            )
            if user_id:
                current_user_id.set(user_id)
                logger.debug(f"Header X-User-ID set: {user_id}")
            else:
                logger.debug("No user ID header found in request")

            response = await call_next(request)
            return response

    return UserIDMiddleware


async def run_sse_with_middleware():
    """Run SSE transport with middleware for X-User-ID header extraction.

    Uses add_middleware() directly on the FastMCP SSE app to avoid
    lifespan issues with wrapping in a new Starlette app.
    """
    import uvicorn

    # Get the SSE Starlette app from FastMCP (includes lifespan management)
    app = mcp.sse_app()

    # Add middleware directly to the existing app (preserves lifespan)
    app.add_middleware(_create_user_id_middleware())

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8050"))

    logger.info(f"Starting MCP-Mem0 SSE server on {host}:{port} (multi-user mode)")
    logger.info(f"Default user ID: {DEFAULT_USER_ID}")

    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def run_streamable_http_with_middleware():
    """Run Streamable HTTP transport with middleware for X-User-ID header extraction."""
    import uvicorn

    # Get the streamable HTTP Starlette app from FastMCP
    app = mcp.streamable_http_app()

    # Add middleware directly
    app.add_middleware(_create_user_id_middleware())

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8050"))

    logger.info(f"Starting MCP-Mem0 Streamable HTTP server on {host}:{port} (multi-user mode)")
    logger.info(f"Default user ID: {DEFAULT_USER_ID}")

    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    transport = os.getenv("TRANSPORT", "sse").lower()

    if transport == "sse":
        await run_sse_with_middleware()
    elif transport == "streamable-http":
        await run_streamable_http_with_middleware()
    else:
        # stdio transport - no HTTP headers available, uses DEFAULT_USER_ID or tool param
        logger.info(f"Starting MCP-Mem0 stdio server (single-user mode, user={DEFAULT_USER_ID})")
        await mcp.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(main())
