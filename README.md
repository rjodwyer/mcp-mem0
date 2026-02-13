# MCP-Mem0 (Multi-User Fork)

Fork of [coleam00/mcp-mem0](https://github.com/coleam00/mcp-mem0) with **per-user memory isolation** for multi-user environments like LibreChat.

## What Changed

The original MCP-Mem0 uses a hardcoded `DEFAULT_USER_ID = "user"` for all memory operations — meaning every user shares the same memory pool. This fork adds automatic per-user scoping.

### User Identification Priority

1. **`X-User-ID` HTTP header** — Set automatically by LibreChat via `{{LIBRECHAT_USER_ID}}` placeholder. Zero LLM involvement, fully automatic.
2. **`X-User-Email` HTTP header** — Alternative header if email is preferred as user key.
3. **`user_id` tool parameter** — Optional explicit parameter on each tool. Useful for testing or non-LibreChat clients.
4. **`DEFAULT_USER_ID` env var** — Fallback for stdio transport or when no header/param is provided.

### New Tool: `delete_all_memories`

Added a `delete_all_memories` tool with a `confirm` safety guard for GDPR/privacy compliance.

### Technical Implementation

- **`contextvars`** — Bridges HTTP request headers into async MCP tool handlers without modifying the MCP protocol.
- **Starlette middleware** — Intercepts every SSE/streamable-http request, extracts user identity from headers, sets the context variable before the tool handler runs.
- **Custom server startup** — Wraps FastMCP's SSE/streamable-http app with the middleware layer, using `uvicorn` directly.

## LibreChat Configuration

```yaml
# librechat.yaml
mcpServers:
  mem0:
    type: sse
    url: "http://mem0-mcp:8050/sse"
    headers:
      X-User-ID: "{{LIBRECHAT_USER_ID}}"
    serverInstructions: |
      You have access to persistent memory tools. Use them to remember user preferences,
      project context, and important details across conversations.
      - Call search_memories before answering questions that might benefit from past context.
      - Call save_memory when the user shares preferences, project details, or asks you to remember something.
      - User identification is automatic — do NOT pass user_id parameter unless testing.
```

## Docker Compose

```yaml
services:
  mem0-mcp:
    build:
      context: ./mcp-mem0
      dockerfile: Dockerfile
    container_name: mem0-mcp
    ports:
      - "8050:8050"
    environment:
      - TRANSPORT=sse
      - LLM_PROVIDER=openai
      - LLM_BASE_URL=http://litellm:4000/v1
      - LLM_API_KEY=${LITELLM_MASTER_KEY}
      - LLM_CHOICE=gpt-4.1-mini
      - EMBEDDING_MODEL_CHOICE=text-embedding-3-small
      - DATABASE_URL=postgresql://mem0user:mem0password@mem0-db:5432/mem0
      - DEFAULT_USER_ID=default
      - LOG_LEVEL=INFO
      - OPENAI_API_KEY=${LITELLM_MASTER_KEY}
      - OPENAI_BASE_URL=http://litellm:4000/v1
    depends_on:
      mem0-db:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - librechat_default

  mem0-db:
    image: pgvector/pgvector:pg16
    container_name: mem0-db
    environment:
      - POSTGRES_USER=mem0user
      - POSTGRES_PASSWORD=mem0password
      - POSTGRES_DB=mem0
    ports:
      - "5433:5432"
    volumes:
      - mem0_pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mem0user -d mem0"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - librechat_default

volumes:
  mem0_pgdata:
```

## Testing

### Verify per-user isolation

```bash
# Save memory as user "alice"
curl -X POST http://localhost:8050/messages \
  -H "X-User-ID: alice" \
  -H "Content-Type: application/json" \
  -d '{"method": "tools/call", "params": {"name": "save_memory", "arguments": {"text": "Alice likes Python"}}}'

# Search as user "bob" — should return empty
curl -X POST http://localhost:8050/messages \
  -H "X-User-ID: bob" \
  -H "Content-Type: application/json" \
  -d '{"method": "tools/call", "params": {"name": "search_memories", "arguments": {"query": "Python"}}}'

# Search as user "alice" — should return the memory
curl -X POST http://localhost:8050/messages \
  -H "X-User-ID: alice" \
  -H "Content-Type: application/json" \
  -d '{"method": "tools/call", "params": {"name": "search_memories", "arguments": {"query": "Python"}}}'
```

### Check logs for user resolution

```bash
docker logs mem0-mcp 2>&1 | grep "User ID"
# Should show: "Header X-User-ID set: alice"
# Should show: "User ID from HTTP header: alice"
```

## Compatibility

- **LibreChat** — Full automatic per-user isolation via headers
- **Claude Desktop / Cursor / Windsurf** — Use `user_id` tool parameter or `DEFAULT_USER_ID` env var
- **n8n** — Use `DEFAULT_USER_ID` env var (single-user per instance) or pass `user_id` parameter
- **stdio transport** — Falls back to `DEFAULT_USER_ID` (no HTTP headers available)

## Original

Based on [coleam00/mcp-mem0](https://github.com/coleam00/mcp-mem0) — MIT License.
