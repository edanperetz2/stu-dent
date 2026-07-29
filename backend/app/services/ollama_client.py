import json
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def generate_json(prompt: str) -> dict | None:
    """Best-effort call to the local Ollama model, requesting JSON output.

    Failures (network error, timeout, non-2xx response, unparseable JSON)
    are logged and return None -- callers must degrade gracefully, mirroring
    services/email.py's "best-effort, never raise" contract for other
    dev/local-only infra. This is the only place in the codebase that talks
    to Ollama; it never touches the database and never decides anything --
    callers are responsible for validating and acting on whatever comes back.

    A connect-level failure (container not up yet, brief network blip) or a
    5xx from Ollama itself (e.g. momentarily overloaded) gets one retry --
    a read-timeout (the model was actively generating, just slow) or a 4xx
    (e.g. model not pulled, a permanent condition that retrying can't fix)
    does not, since retrying either would just double the wait for an
    identical failure.
    """
    for attempt in range(2):
        try:
            response = httpx.post(
                f"{settings.ollama_base_url}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": prompt,
                    "format": "json",
                    "stream": False,
                },
                timeout=settings.ollama_timeout_seconds,
            )
            response.raise_for_status()
            parsed = json.loads(response.json()["response"])
            return parsed if isinstance(parsed, dict) else None
        except (httpx.ConnectError, httpx.ConnectTimeout):
            if attempt == 0:
                logger.warning("Ollama connection failed, retrying once", exc_info=True)
                continue
            logger.warning("Ollama call failed", exc_info=True)
            return None
        except httpx.HTTPStatusError as exc:
            if attempt == 0 and exc.response.status_code >= 500:
                logger.warning("Ollama returned a server error, retrying once", exc_info=True)
                continue
            logger.warning("Ollama call failed", exc_info=True)
            return None
        except (httpx.HTTPError, KeyError, ValueError, TypeError):
            logger.warning("Ollama call failed", exc_info=True)
            return None
    return None
