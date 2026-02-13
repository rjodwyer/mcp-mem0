# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MCP-Mem0 is a Model Context Protocol (MCP) server providing per-user long-term memory for AI agents. It's a multi-user fork of [coleam00/mcp-mem0](https://github.com/coleam00/mcp-mem0) that adds automatic user isolation via HTTP headers (`X-User-ID`, `X-User-Email`, `X-LibreChat-User-ID`).

## Build & Run Commands

```bash
# Run locally (requires Python 3.12+ and uv)
uv run src/main.py

# Build Docker image
docker build -t mem0-mcp:latest .

# Run in Docker (typically via docker-compose with a pgvector database)
# See README.md for full docker-compose example

# Install dependencies
uv pip install -e .
```

There are no tests, linter, or CI/CD configured in this repo.

## Architecture

### Core Files

- **`src/main.py`** — FastMCP server with 4 tools (save_memory, search_memories, get_all_memories, delete_all_memories), HTTP middleware for user ID extraction, and transport handlers (SSE, Streamable HTTP, stdio).
- **`src/utils.py`** — Configures the Mem0 `Memory` client from environment variables (LLM provider, embedder, pgvector connection).

### Per-User Isolation Pattern

The key architectural pattern uses Python `contextvars.ContextVar` for per-request user scoping:

1. `UserIDMiddleware` (Starlette middleware) extracts user ID from HTTP headers and sets `current_user_id` ContextVar
2. `_resolve_user_id()` resolves user with priority: explicit tool param → HTTP header context → `DEFAULT_USER_ID` env var → "default"
3. All tool functions call `_resolve_user_id()` to scope memory operations to the correct user

### External Dependencies

- **Mem0** (`mem0ai`) — Memory management with semantic indexing
- **FastMCP** (`mcp[cli]`) — MCP server framework
- **pgvector/PostgreSQL** — Vector storage backend for semantic search
- **LLM provider** (OpenAI/OpenRouter/Ollama) — Used by Mem0 for semantic analysis and embeddings

### Transport Modes

Set via `TRANSPORT` env var:
- `sse` (default) — Server-Sent Events with HTTP header middleware on port 8050
- `streamable-http` — Streamable HTTP with header middleware
- `stdio` — Standard I/O (no HTTP headers; uses env var or explicit param for user ID)

### Environment Variables

See `.env.example` for the full list. Key variables: `TRANSPORT`, `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_CHOICE`, `EMBEDDING_MODEL_CHOICE`, `DATABASE_URL`, `DEFAULT_USER_ID`.
