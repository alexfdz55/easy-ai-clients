"""Shared normalized error helpers for public dispatchers."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from typing import Any

_SECRET_PATTERNS = (
    (
        re.compile(r"(?i)(authorization\s*[:=]\s*(?:bearer|key|token)?\s*)[^\s,;]+"),
        r"\1[redacted]",
    ),
    (
        re.compile(r"(?i)\b(bearer|key|token)\s+[A-Za-z0-9._~+/=-]{8,}"),
        r"\1 [redacted]",
    ),
    (
        re.compile(r"(?i)\b(api[_-]?key|token|secret)(\s*[:=]\s*)[^\s,;]+"),
        r"\1\2[redacted]",
    ),
)


#: Headers where providers report the id of the request that failed. fal uses its own.
_REQUEST_ID_HEADERS = ("x-fal-request-id", "x-request-id", "request-id", "x-generation-id")


def _header_value(headers: Any, key: str) -> str:
    try:
        value = headers.get(key)
    except Exception:
        return ""
    return str(value or "").strip()


def request_id_of(error: Any) -> str:
    """Return the provider request id carried by an exception, or ``""``.

    Looks at a ``request_id`` attribute and at the response headers, walking the
    ``__cause__``/``__context__`` chain, because the id usually lives on the low-level
    HTTP error that a friendlier exception wraps.
    """

    current = error
    for _ in range(5):
        if current is None:
            break
        value = getattr(current, "request_id", None)
        if value:
            return str(value)
        for headers in (
            getattr(current, "headers", None),
            getattr(getattr(current, "response", None), "headers", None),
        ):
            if headers:
                for key in _REQUEST_ID_HEADERS:
                    found = _header_value(headers, key)
                    if found:
                        return found
        current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)
    return ""


def sanitize_error_message(error: Any) -> str:
    """Return a compact provider/runtime error message with secrets redacted."""

    message = " ".join(str(error or "").split())
    for value in os.environ.values():
        secret = str(value or "").strip()
        if len(secret) >= 8 and secret in message:
            message = message.replace(secret, "[redacted]")
    for pattern, replacement in _SECRET_PATTERNS:
        message = pattern.sub(replacement, message)
    return message[:1500]


def build_error(
    error: Any,
    *,
    provider: str | None = None,
    operation: str | None = None,
    model: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Build the public `error` object used by normalized failure results.

    ``request_id`` is added only when known (explicitly or from the exception), so an
    error without an id keeps exactly the keys it always had.
    """

    payload = {
        "type": type(error).__name__ if error is not None else "Error",
        "message": sanitize_error_message(error),
        "provider": provider,
        "operation": operation,
        "model": model,
    }
    known_id = str(request_id or "").strip() or request_id_of(error)
    if known_id:
        payload["request_id"] = known_id
    return payload


def error_message(error: Any) -> str:
    """Return only the redacted message portion of a public error."""

    return sanitize_error_message(error)


def attach_error(
    result: Mapping[str, Any],
    error: Any,
    *,
    provider: str | None = None,
    operation: str | None = None,
    model: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Return a copy of `result` with a normalized `error` object attached.

    The request id comes from ``request_id``, the exception, or the result itself; when
    one is known it also fills an empty top-level ``request_id``.
    """

    output = dict(result)
    existing = output.get("request_id")
    known_id = (
        str(request_id or "").strip()
        or request_id_of(error)
        or (existing.strip() if isinstance(existing, str) else "")
    )
    output["error"] = build_error(
        error,
        provider=provider,
        operation=operation,
        model=model,
        request_id=known_id or None,
    )
    if known_id and not output.get("request_id"):
        output["request_id"] = known_id
    return output
