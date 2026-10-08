"""Task 1.3.3 — LLM client with structured output and audit log."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ValidationError

if TYPE_CHECKING:
    from app.company_ingest.run_context import RunContext

logger = logging.getLogger(__name__)

# Module-level semaphore — allows up to 16 concurrent LLM calls.
_semaphore: asyncio.Semaphore | None = None

# Module-level Anthropic async client (created lazily).
_anthropic_client: Any = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(16)
    return _semaphore


def _get_anthropic_client() -> Any:
    """Return a cached AsyncAnthropic client with SDK-level retries disabled."""
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic
        from app.config import settings  # lazy — avoids missing .env at import time

        _anthropic_client = anthropic.AsyncAnthropic(
            api_key=settings.LLM_API_KEY,
            max_retries=0,  # we handle retries ourselves
        )
    return _anthropic_client


# Patchable sleep — tests replace this without touching asyncio globally.
_sleep = asyncio.sleep

# ---------------------------------------------------------------------------
# Provider layer
# ---------------------------------------------------------------------------


async def _call_provider(system: str, user: str, model: str) -> str:
    """Call the configured LLM provider and return the raw text response."""
    from app.config import settings  # lazy — avoids missing .env at import time

    provider = settings.LLM_PROVIDER.lower()
    if provider == "anthropic":
        client = _get_anthropic_client()
        response = await client.messages.create(
            model=model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        # Extract text from the first content block.
        for block in response.content:
            if hasattr(block, "text"):
                return block.text
        return ""
    else:
        raise NotImplementedError(f"LLM provider not supported: {provider!r}")


async def _call_with_backoff(system: str, user: str, model: str) -> str:
    """Acquire semaphore, call provider with exponential backoff on rate limits."""
    import anthropic

    max_retries = 3
    async with _get_semaphore():
        for attempt in range(max_retries + 1):
            try:
                return await _call_provider(system, user, model)
            except anthropic.RateLimitError:
                if attempt >= max_retries:
                    raise
                wait = min(2 ** attempt, 60)
                logger.warning(
                    "Rate limit hit (attempt %d/%d); sleeping %ds",
                    attempt + 1,
                    max_retries,
                    wait,
                )
                await _sleep(wait)
    # unreachable, but satisfies the type checker
    raise RuntimeError("backoff loop exited unexpectedly")


# ---------------------------------------------------------------------------
# Audit writer
# ---------------------------------------------------------------------------


async def _write_audit(
    ctx: RunContext,
    stage: str,
    unit_id: str,
    record: dict[str, Any],
) -> None:
    """Write the audit record to R2. Failure is logged but not propagated."""
    try:
        from app.company_ingest.store.r2 import _get_client
        from app.config import settings
        from app.company_ingest.store.r2_keys import llm_key

        key = llm_key(ctx.company_id, str(ctx.run_id), stage, unit_id)
        body = json.dumps(record, default=str).encode()
        bucket = settings.R2_BUCKET_NAME

        def _put() -> None:
            client = _get_client()
            client.put_object(Bucket=bucket, Key=key, Body=body,
                              ContentType="application/json")

        await asyncio.to_thread(_put)
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM audit write failed for %s/%s: %s", stage, unit_id, exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _strip_fences(text: str) -> str:
    """Remove ```json … ``` fences that the model may add."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        lines = lines[1:]  # drop opening fence line (e.g. ```json)
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]  # drop closing fence
        return "\n".join(lines).strip()
    return stripped


async def call_structured(
    stage: str,
    unit_id: str,
    system: str,
    user: str,
    schema: type[BaseModel],
    ctx: "RunContext",
    model: str | None = None,
) -> BaseModel | None:
    """Call the LLM and return a validated *schema* instance, or None on failure.

    Steps:
    1. Compute prompt_sha256 from the raw system+user strings.
    2. Check replay cache (when ctx.rebuild is True).
    3. Build a schema-augmented system prompt.
    4. Call the LLM; retry once on a pydantic/JSON validation error,
       sending the error back to the model.
    5. On double failure, record a warning issue and return None.
    6. Write an audit record to R2 (optional — failure is ignored).
    7. Populate the replay cache.
    """
    from app.config import settings

    model = model or settings.LLM_MODEL

    # Compute the prompt hash from the raw (non-augmented) system+user strings.
    prompt_sha256 = hashlib.sha256((system + user).encode()).hexdigest()
    cache_key = (stage, unit_id, prompt_sha256)

    # --- Replay cache ---
    if ctx.rebuild and cache_key in ctx.llm_cache:
        logger.debug("LLM cache hit for %s/%s", stage, unit_id)
        return ctx.llm_cache[cache_key]

    # Augment the system prompt with the JSON schema.
    schema_json = json.dumps(schema.model_json_schema(), indent=2)
    augmented_system = (
        f"{system}\n\n"
        "Respond with a single JSON object that matches the following JSON Schema "
        "exactly. Do not include any prose outside the JSON.\n\n"
        f"```json\n{schema_json}\n```"
    )

    raw: str | None = None
    result: BaseModel | None = None
    last_error: str | None = None
    attempts = 0

    for attempt in range(2):
        current_user = user
        if attempt == 1 and last_error is not None:
            current_user = (
                f"{user}\n\n"
                f"Your previous response was:\n{raw}\n\n"
                f"Your previous response had this error: {last_error}. "
                "Please correct it."
            )

        raw = await _call_with_backoff(augmented_system, current_user, model)
        attempts += 1
        cleaned = _strip_fences(raw)

        try:
            result = schema.model_validate_json(cleaned)
            break  # success
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            last_error = str(exc)
            result = None

    # --- Audit record ---
    audit: dict[str, Any] = {
        "run_id": str(ctx.run_id),
        "stage": stage,
        "unit_id": unit_id,
        "prompt_sha256": prompt_sha256,
        "model": model,
        "attempts": attempts,
        "valid": result is not None,
        "output": result.model_dump(mode="json") if result is not None else None,
        "error": last_error,
        "raw": raw,
    }
    await _write_audit(ctx, stage, unit_id, audit)

    if result is None:
        ctx.issue(
            "warning",
            stage,
            "llm_validation_failed",
            f"LLM output failed validation for {unit_id}",
            clause_id=unit_id,
        )
        return None

    # Populate the cache regardless of ctx.rebuild so future calls can hit it.
    ctx.llm_cache[cache_key] = result
    return result
