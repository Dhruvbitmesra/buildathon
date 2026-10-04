"""
Pool of Groq API keys with automatic failover.

Groq limits tokens per minute and per day *per organisation*. With keys
from several organisations configured, a call that hits one key's quota
is retried immediately on the next key; only when every key is
exhausted do the agents continue without the LLM.

Keys are read from the environment / .env, in this order:
    GROQ_API_KEYS   comma-separated list
    GROQ_API_KEY
    GROQ_API_KEY_1 ... GROQ_API_KEY_9
Duplicates are ignored. Key values are never logged; slots are labelled
"key 1", "key 2", ...
"""

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from app.llm_rate_limiter import (
    LLMUnavailableError,
    TokenRateLimiter,
    estimate_tokens,
    parse_retry_after,
)


from dotenv import load_dotenv

# Read .env once; later calls see the process environment (so tests and
# deployments can override it).
load_dotenv()

MAX_RETRIES = 4
MAX_SHORT_WAIT = 20.0


def configured_keys() -> list[str]:
    raw: list[str] = []

    raw.extend((os.getenv("GROQ_API_KEYS") or "").replace(";", ",").split(","))
    raw.append(os.getenv("GROQ_API_KEY") or "")
    raw.extend(os.getenv(f"GROQ_API_KEY_{i}") or "" for i in range(1, 10))

    keys: list[str] = []

    for key in raw:
        key = key.strip().strip('"').strip("'")

        if key and key not in keys:
            keys.append(key)

    return keys


def is_rate_limit(error: Exception) -> bool:
    status = getattr(error, "status_code", None)
    return status == 429 or "rate limit" in str(error).lower()


def retry_delay(error: Exception, attempt: int, cap: float) -> float:
    """Server's "try again in ..." hint, else exponential backoff."""

    hint = parse_retry_after(str(error))

    if hint is not None:
        return min(hint + 0.5, cap)

    return min(2.0 ** attempt, cap)


def quota_exhausted(error: Exception, max_wait: float) -> float | None:
    """
    Seconds until reset when the limit cannot be waited out inside one
    run (a daily quota, or a reset later than `max_wait`), else None.
    """

    message = str(error).lower()
    hint = parse_retry_after(str(error))
    daily = "per day" in message or "(tpd)" in message or "(rpd)" in message

    if daily or (hint is not None and hint > max_wait):
        return hint if hint is not None else 3600.0

    return None


def rejects_reasoning_effort(error: Exception) -> bool:
    text = str(error).lower()
    return "reasoning_effort" in text and (
        "400" in text or "unsupported" in text or "invalid" in text
    )


def complete_with(
    client: Any,
    limiter: TokenRateLimiter,
    request: dict,
    completion_tokens: int = 400,
    label: str = "key",
) -> Any:
    """
    One chat completion on one client inside its token budget.

    - short 429s: wait (server hint) and retry;
    - quota that cannot be waited out: block this key until it resets and
      raise LLMUnavailableError (the pool then tries the next key);
    - a model that rejects reasoning_effort: retry without it.
    """

    prompt_text = "".join(
        str(message.get("content", "")) for message in request.get("messages", [])
    )
    attempt = 0

    while True:
        reservation = limiter.acquire(
            estimate_tokens(prompt_text, completion=completion_tokens)
        )

        try:
            response = client.chat.completions.create(**request)
        except Exception as error:
            if rejects_reasoning_effort(error) and "reasoning_effort" in request:
                request = {k: v for k, v in request.items() if k != "reasoning_effort"}
                continue

            if not is_rate_limit(error):
                raise

            reset = quota_exhausted(error, MAX_SHORT_WAIT)

            if reset is not None:
                daily = "per day" in str(error).lower() or "(tpd)" in str(error).lower()
                minutes, seconds = divmod(int(reset), 60)
                reason = (
                    f"{label}: {'daily token quota' if daily else 'rate limit'} "
                    f"used up (resets in about {minutes}m {seconds}s)"
                )
                limiter.block(reset, reason)
                raise LLMUnavailableError(reason) from error

            attempt += 1

            if attempt > MAX_RETRIES:
                raise

            delay = retry_delay(error, attempt, MAX_SHORT_WAIT)
            limiter.penalise(delay)
            time.sleep(delay)
            continue

        usage = getattr(response, "usage", None)
        limiter.record(reservation, getattr(usage, "total_tokens", None))
        return response


@dataclass
class KeySlot:
    label: str
    key: str = field(repr=False)
    limiter: TokenRateLimiter
    _client: Any = field(default=None, repr=False)

    @property
    def client(self) -> Any:
        if self._client is None:
            from groq import Groq

            self._client = Groq(api_key=self.key)

        return self._client


class GroqKeyPool:
    def __init__(self, keys: list[str], tokens_per_minute: int | None = None) -> None:
        if not keys:
            raise ValueError("No Groq API key is configured (GROQ_API_KEY).")

        budget = tokens_per_minute or int(os.getenv("GROQ_TOKENS_PER_MINUTE", "7000"))
        self.slots = [
            KeySlot(f"key {index}", key, TokenRateLimiter(budget))
            for index, key in enumerate(keys, start=1)
        ]

    def complete(self, request: dict, completion_tokens: int = 400) -> Any:
        """Run the request on the first key with quota left."""

        reasons: list[str] = []

        for slot in self.slots:
            try:
                return complete_with(
                    slot.client, slot.limiter, request, completion_tokens, slot.label
                )
            except LLMUnavailableError as error:
                reasons.append(str(error))

        raise LLMUnavailableError(
            "Every configured Groq key has used up its quota ("
            + "; ".join(reasons)
            + "); continuing without the LLM."
            if len(self.slots) > 1
            else (reasons[0][0].upper() + reasons[0][1:] + "; continuing without the LLM.")
            if reasons
            else "No Groq key is available; continuing without the LLM."
        )

    def status(self) -> list[tuple[str, str | None]]:
        """[(label, blocked reason or None)] - never exposes key values."""

        return [(slot.label, slot.limiter.blocked_reason) for slot in self.slots]


_POOL: GroqKeyPool | None = None
_POOL_KEYS: tuple[str, ...] = ()
_POOL_LOCK = threading.Lock()


def get_pool() -> GroqKeyPool:
    """Process-wide pool, rebuilt if the configured keys change."""

    global _POOL, _POOL_KEYS

    keys = tuple(configured_keys())

    with _POOL_LOCK:
        if _POOL is None or keys != _POOL_KEYS:
            _POOL = GroqKeyPool(list(keys))
            _POOL_KEYS = keys

        return _POOL


def pool_status() -> list[tuple[str, str | None]]:
    try:
        return get_pool().status()
    except ValueError:
        return []
