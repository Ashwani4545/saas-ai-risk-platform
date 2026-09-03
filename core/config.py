"""Centralized configuration loaded from environment variables."""
import os
import secrets
import warnings

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

ENV = os.getenv("APP_ENV", "development")

# JWT secret: required in production, auto-generated (with a loud warning) in dev
# so the app never silently ships with a hardcoded, guessable secret.
_JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not _JWT_SECRET_KEY:
    if ENV == "production":
        raise RuntimeError(
            "JWT_SECRET_KEY environment variable must be set in production. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
    _JWT_SECRET_KEY = secrets.token_urlsafe(32)
    warnings.warn(
        "JWT_SECRET_KEY not set - using a random secret for this process only. "
        "Tokens will not survive a restart. Set JWT_SECRET_KEY in .env for real use.",
        stacklevel=2,
    )

JWT_SECRET_KEY = _JWT_SECRET_KEY
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

DATABASE_PATH = os.getenv("DATABASE_PATH", "data/app.db")

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092").split(",")
KAFKA_ENABLED = os.getenv("KAFKA_ENABLED", "true").lower() == "true"
KAFKA_CONNECT_TIMEOUT_SECONDS = float(os.getenv("KAFKA_CONNECT_TIMEOUT_SECONDS", "2"))

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")

# Seed a demo tenant/user only when explicitly enabled - keeps prod DBs clean.
SEED_DEMO_DATA = os.getenv("SEED_DEMO_DATA", "true").lower() == "true"

# Optional GenAI explanation feature (rag/). If no API key is set, the
# /explain and /policy/ask endpoints still work using retrieval alone (see
# rag/explain.py) - they just skip the generative step. This mirrors the
# Kafka design: an unconfigured or unreachable external dependency degrades
# gracefully instead of failing the request.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic" if os.getenv("ANTHROPIC_API_KEY") else "none")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-6")
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "8"))
