"""Shared normalized error helpers for public dispatchers."""

from __future__ import annotations

import json
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


#: HTTP statuses where the provider turns the ACCOUNT away, not the request: an unpaid
#: invoice, exhausted credits, a revoked key, a locked workspace. Repeating the same call
#: cannot succeed, so callers should not retry it and may switch to another provider.
ACCOUNT_STATUS_CODES = (401, 402, 403)
ERROR_CATEGORY_ACCOUNT = "account"


def _provider_code_and_message(body: Any) -> tuple[str, str]:
    """Read the provider's own error code and message out of a response body.

    Providers nest them differently: ElevenLabs under ``detail`` (a mapping with ``status``
    and ``message``), fal under ``detail`` too (a list of ``{type, msg}``), OpenAI-style
    APIs under ``error``. A body that is not JSON is returned whole as the message.
    """

    text = str(body or "").strip()
    if not text:
        return "", ""
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        return "", text
    node = parsed
    if isinstance(parsed, Mapping):
        node = parsed.get("detail", parsed.get("error", parsed))
    if isinstance(node, list):
        node = node[0] if node else ""
    if isinstance(node, Mapping):
        code = next(
            (
                str(node[key]).strip()
                for key in ("status", "code", "type")
                if isinstance(node.get(key), str) and node[key].strip()
            ),
            "",
        )
        message = next(
            (
                str(node[key]).strip()
                for key in ("message", "msg")
                if isinstance(node.get(key), str) and node[key].strip()
            ),
            "",
        )
        return code, message
    return "", str(node or "").strip()


def http_failure_of(error: Any) -> dict[str, Any]:
    """Return what the HTTP failure behind an exception says, or ``{}``.

    Walks the ``__cause__``/``__context__`` chain like :func:`request_id_of`, because the
    status and the body live on the low-level HTTP error that a friendlier exception
    wraps. Keys, each present only when known: ``http_status``, ``provider_code``,
    ``provider_message`` and ``category`` (``"account"`` for :data:`ACCOUNT_STATUS_CODES`).
    """

    current = error
    for _ in range(5):
        if current is None:
            break
        response = getattr(current, "response", None)
        status = getattr(current, "status_code", None)
        if status is None:
            status = getattr(response, "status_code", None)
        try:
            status = int(status)
        except (TypeError, ValueError):
            status = 0
        if status >= 400:
            failure: dict[str, Any] = {"http_status": status}
            body = getattr(current, "response_text", None)
            if body is None:
                try:
                    body = getattr(response, "text", None)
                except Exception:
                    body = None
            code, message = _provider_code_and_message(body)
            if code:
                failure["provider_code"] = code[:80]
            if message:
                failure["provider_message"] = sanitize_error_message(message)[:500]
            if status in ACCOUNT_STATUS_CODES:
                failure["category"] = ERROR_CATEGORY_ACCOUNT
            return failure
        current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)
    return {}


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

    ``request_id`` is added only when known (explicitly or from the exception), and so
    are the HTTP status, the provider's own code and message and the failure category
    (see :func:`http_failure_of`): an error without them keeps exactly the keys it
    always had.
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
    payload.update(http_failure_of(error))
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
