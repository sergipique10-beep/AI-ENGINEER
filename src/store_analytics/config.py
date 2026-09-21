"""Configuration loaded from environment / .env file."""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

# LLM providers
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")

AGENT_MODEL = os.getenv("AGENT_MODEL", "openai/gpt-oss-120b")
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "mistral-small-latest")

# Database — always resolve relative to project root
_db_rel = os.getenv("DATABASE_PATH", "data/store.db")
DATABASE_PATH = Path(_db_rel) if Path(_db_rel).is_absolute() else _PROJECT_ROOT / _db_rel

# Agent limits
MAX_TOOL_CALLS = 10  # safety cap to prevent infinite loops
MAX_TOKENS_AGENT = 2048

# Observability (Langfuse)
LANGFUSE_ENABLED = os.getenv("LANGFUSE_ENABLED", "false").lower() == "true"
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
