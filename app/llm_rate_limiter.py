"""
Client-side token budget for LLM calls.

Groq's free tier allows a fixed number of tokens per minute per model
(8,000 for openai/gpt-oss-120b at the time of writing). Retrying after a
429 response wastes time and still fails when many calls run together.
This limiter instead waits *before* a call until the request fits in the
rolling one-minute window, shared by every agent in the process.

Configure with GROQ_TOKENS_PER_MINUTE (default 7000, a margin under the
free-tier limit). Set it higher on a paid tier.
"""

import os
import re
import threading
import time
from collections import deque


class LLMUnavailableError(RuntimeError):
    """The LLM cannot be used for a while (e.g. daily quota reached)."""


def parse_retry_after(message: str) -> float | None:
    """
    Seconds from Groq's "Please try again in 1h2m3.5s / 3m37.296s /
    194.9ms" hint, or None when there is no hint.
    """

    match = re.search(r"try again in\s+((?:[\d.]+\s*(?:h|ms|m|s)\s*)+)", message)

    if not match:
        return None

    seconds = 0.0

    for amount, unit in re.findall(r"([\d.]+)\s*(ms|h|m|s)", match.group(1)):
        value = float(amount)
        seconds += {"h": 3600.0, "m": 60.0, "s": 1.0, "ms": 0.001}[unit] * value

    return seconds


class TokenRateLimiter:
    def __init__(self, tokens_per_minute: int, window_seconds: float = 60.0) -> None:
        self.tokens_per_minute = max(1, tokens_per_minute)
        self.window = window_seconds
        self._events: deque[list[float]] = deque()  # [timestamp, tokens]
        self._lock = threading.Lock()
        self._blocked_until = 0.0
        self._blocked_reason = ""

    def _used(self, now: float) -> float:
        while self._events and now - self._events[0][0] >= self.window:
            self._events.popleft()

        return sum(tokens for _, tokens in self._events)

    def acquire(self, estimated_tokens: int, max_wait: float = 90.0) -> list[float]:
        """
        Block until `estimated_tokens` fits in the window, then reserve it.
        Returns a reservation to pass to record().
        """

        estimated = min(max(1, estimated_tokens), self.tokens_per_minute)
        deadline = time.monotonic() + max_wait

        while True:
            with self._lock:
                now = time.monotonic()

                if now < self._blocked_until:
                    raise LLMUnavailableError(self._blocked_reason)

                if self._used(now) + estimated <= self.tokens_per_minute or now >= deadline:
                    event = [now, float(estimated)]
                    self._events.append(event)
                    return event

                wait = self.window - (now - self._events[0][0]) + 0.05

            time.sleep(min(max(wait, 0.05), 2.0))

    def record(self, reservation: list[float], actual_tokens: int | None) -> None:
        """Replace the estimate with the real usage reported by the API."""

        if actual_tokens:
            with self._lock:
                reservation[1] = float(actual_tokens)

    def reset(self, tokens_per_minute: int | None = None) -> None:
        """Forget all usage (and optionally change the budget)."""

        with self._lock:
            self._events.clear()
            self._blocked_until = 0.0
            self._blocked_reason = ""

            if tokens_per_minute is not None:
                self.tokens_per_minute = max(1, tokens_per_minute)

    def block(self, seconds: float, reason: str) -> None:
        """Stop all LLM calls for `seconds` (quota that cannot be waited out)."""

        with self._lock:
            self._blocked_until = max(self._blocked_until, time.monotonic() + seconds)
            self._blocked_reason = reason

    @property
    def blocked_reason(self) -> str | None:
        with self._lock:
            return self._blocked_reason if time.monotonic() < self._blocked_until else None

    def penalise(self, seconds: float) -> None:
        """After a 429, treat the window as full for `seconds`."""

        with self._lock:
            now = time.monotonic()
            self._events.append([now - self.window + seconds, float(self.tokens_per_minute)])


def estimate_tokens(*texts: str, completion: int = 400) -> int:
    """Rough token estimate (~3.5 characters per token) plus the reply."""

    return int(sum(len(text) for text in texts) / 3.5) + completion


RATE_LIMITER = TokenRateLimiter(
    int(os.getenv("GROQ_TOKENS_PER_MINUTE", "7000"))
)
