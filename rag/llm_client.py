"""Thin LLM client for the generative half of the RAG explanation feature.

Calling out the failure mode explicitly, because this repo already had one
bug from an external dependency blocking a request path (see
messaging/kafka_service.py): `generate()` returns None - never raises - if
no API key is configured, the request times out, or the call otherwise
fails. Callers (rag/explain.py) are written to always have a sensible
fallback for a None response, so a missing or misbehaving LLM provider
degrades the feature rather than breaking it.
"""
from typing import Optional

import httpx
from loguru import logger

from core.config import LLM_PROVIDER, ANTHROPIC_API_KEY, LLM_MODEL, LLM_TIMEOUT_SECONDS

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"


def is_configured() -> bool:
    return LLM_PROVIDER == "anthropic" and bool(ANTHROPIC_API_KEY)


async def generate(system_prompt: str, user_prompt: str, max_tokens: int = 400) -> Optional[str]:
    if not is_configured():
        return None

    try:
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT_SECONDS) as client:
            response = await client.post(
                ANTHROPIC_MESSAGES_URL,
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": LLM_MODEL,
                    "max_tokens": max_tokens,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                },
            )
            response.raise_for_status()
            data = response.json()
            text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
            return "\n".join(text_blocks) if text_blocks else None
    except Exception as e:
        logger.warning(f"LLM call failed or timed out, falling back to retrieval-only output: {e}")
        return None
