"""In-memory sliding-window rate limiter for login attempts.

Per-process (the compose deployment runs a single api replica), so a module
level dict is sufficient. Only failed attempts count, keyed by email + client
IP; a successful login clears the key. Limits come from Settings
(LOGIN_RATE_LIMIT_ATTEMPTS / LOGIN_RATE_LIMIT_WINDOW_SECONDS).
"""

import threading
import time

_lock = threading.Lock()
_failures: dict[str, list[float]] = {}


def _now() -> float:
    return time.time()


def reset() -> None:
    with _lock:
        _failures.clear()


def retry_after(key: str, *, limit: int, window: float, now: float | None = None) -> int:
    """Seconds until the next attempt is allowed; 0 means allowed right now."""
    now = _now() if now is None else now
    with _lock:
        recent = [t for t in _failures.get(key, []) if now - t < window]
        _failures[key] = recent
        if len(recent) < limit:
            return 0
        return max(1, int(window - (now - recent[0])) + 1)


def register_failure(key: str, *, now: float | None = None) -> None:
    now = _now() if now is None else now
    with _lock:
        _failures.setdefault(key, []).append(now)


def clear(key: str) -> None:
    with _lock:
        _failures.pop(key, None)
