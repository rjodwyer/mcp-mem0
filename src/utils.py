"""
Utility functions for MCP-Mem0 server.
Creates the Mem0 Memory client with configuration from environment variables.

For LiteLLM proxy compatibility, set:
  LLM_BASE_URL=http://litellm:4000/v1
  OPENAI_API_KEY=<litellm-master-key>      (used by underlying openai client)
  OPENAI_BASE_URL=http://litellm:4000/v1   (used by underlying openai client)
"""

from mem0 import Memory
from dotenv import load_dotenv
import os
import logging

load_dotenv()
logger = logging.getLogger("mcp-mem0")


def get_mem0_client() -> Memory:
    """Create and configure the Mem0 Memory client from environment variables."""
    
    llm_provider = os.getenv("LLM_PROVIDER", "openai")
    llm_base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    llm_api_key = os.getenv("LLM_API_KEY", "")
    llm_choice = os.getenv("LLM_CHOICE", "gpt-4.1-mini")
    embedding_model = os.getenv("EMBEDDING_MODEL_CHOICE", "text-embedding-3-small")
    database_url = os.getenv("DATABASE_URL", "")

    config = {
        "llm": {
            "provider": llm_provider,
            "config": {
                "model": llm_choice,
                "api_key": llm_api_key,
            }
        },
        "embedder": {
            "provider": llm_provider,
            "config": {
                "model": embedding_model,
                "api_key": llm_api_key,
            }
        },
        "vector_store": {
            "provider": "pgvector",
            "config": {
                "url": database_url,
            }
        }
    }

    # Add base_url if specified (for LiteLLM proxy or OpenRouter)
    if llm_base_url and llm_base_url != "https://api.openai.com/v1":
        config["llm"]["config"]["openai_base_url"] = llm_base_url
        config["embedder"]["config"]["openai_base_url"] = llm_base_url

    logger.info(f"Mem0 config: provider={llm_provider}, model={llm_choice}, "
                f"embedder={embedding_model}, base_url={llm_base_url}")
    
    return Memory.from_config(config)
