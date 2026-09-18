"""HTTP helpers with small retry logic for transient failures."""

from __future__ import annotations

import re
import time
from typing import Any

import httpx

from .errors import ProviderResponseError

_TRANSIENT_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}


def _should_retry(status_code: int) -> bool:
    return status_code in _TRANSIENT_STATUS_CODES


def request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    json: Any = None,
    data: Any = None,
    files: Any = None,
    content: bytes | None = None,
    timeout_seconds: int = 60,
    max_attempts: int = 3,
) -> httpx.Response:
    """Perform an HTTP request with shared retry, timeout, and error handling.

    This helper is the single network gateway for provider wrappers. It applies
    the project-wide policy of retrying only transient transport and service
    failures while failing fast on auth, billing, moderation, and unsupported
    feature errors.

    Args:
        method: HTTP verb such as `GET` or `POST`.
        url: Absolute request URL.
        headers: Optional request headers.
        params: Optional query-string parameters.
        json: Optional JSON body. Mutually exclusive with `content` in normal
            usage.
        data: Optional form body.
        files: Optional multipart body accepted by `httpx`.
        content: Optional raw request bytes.
        timeout_seconds: End-to-end timeout passed to `httpx.Timeout`.
        max_attempts: Maximum number of attempts, including the first try.

    Returns:
        Successful `httpx.Response` with `2xx` status.

    Raises:
        ProviderResponseError: If the request exhausts retries or receives a
            non-success response that should not be retried safely.

    Notes:
        Retries are limited to network exceptions and status codes in the shared
        transient allowlist (`408`, `409`, `425`, `429`, `5xx`).
    """

    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            with httpx.Client(
                timeout=httpx.Timeout(timeout_seconds),
                follow_redirects=True,
            ) as client:
                response = client.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=json,
                    data=data,
                    files=files,
                    content=content,
                )
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < max_attempts:
                time.sleep(0.6 * attempt)
                continue
            raise ProviderResponseError(
                f"HTTP transport error while calling {url}: {exc}",
                is_transient=True,
            ) from exc

        if response.is_success:
            return response

        if attempt < max_attempts and _should_retry(response.status_code):
            time.sleep(0.6 * attempt)
            continue

        raise ProviderResponseError(
            f"Provider request failed with status {response.status_code}.",
            status_code=response.status_code,
            response_text=response.text,
            is_transient=_should_retry(response.status_code),
            headers=dict(response.headers),
            request_id=_failed_request_id(response, url),
        )

    raise ProviderResponseError(
        f"HTTP request exhausted retries for {url}: {last_error}",
        is_transient=True,
    )


def _failed_request_id(response: Any, url: str) -> str:
    """Id of a failed request: from the provider headers or, for fal queue URLs, the path."""

    headers = getattr(response, "headers", {}) or {}
    for key in ("x-fal-request-id", "x-request-id", "request-id"):
        value = headers.get(key)
        if value:
            return str(value)
    match = _REQUESTS_PATH.search(str(url or ""))
    return match.group(1) if match else ""


_REQUESTS_PATH = re.compile(r"/requests/([^/?#]+)")


def download_bytes(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout_seconds: int = 60,
) -> bytes:
    """Download raw bytes using the shared HTTP retry and timeout policy.

    Args:
        url: Absolute URL to download.
        headers: Optional request headers, typically used for signed or
            temporary provider asset URLs.
        timeout_seconds: Download timeout in seconds.

    Returns:
        Raw response bytes.

    Raises:
        ProviderResponseError: Propagated from :func:`request` when the download
            fails.
    """

    response = request(
        "GET",
        url,
        headers=headers,
        timeout_seconds=timeout_seconds,
    )
    return response.content


def download_response(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout_seconds: int = 60,
) -> httpx.Response:
    """Download a URL and return the full response metadata.

    Args:
        url: Absolute URL to download.
        headers: Optional request headers.
        timeout_seconds: Download timeout in seconds.

    Returns:
        Successful `httpx.Response` with content and response headers.
    """

    return request(
        "GET",
        url,
        headers=headers,
        timeout_seconds=timeout_seconds,
    )
