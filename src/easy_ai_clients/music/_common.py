import base64
import json
import math
import os
import re
import threading
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import requests

from ._errors import MusicInputLimitError
from ._model_registry import model_key_for

DEFAULT_TIMEOUT = 180
URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+")

_LOCAL_JOBS = {}
_LOCAL_JOBS_LOCK = threading.Lock()


class ApiRequestError(RuntimeError):
    pass


class LocalJobError(RuntimeError):
    pass


def load_env(env_path=None):
    """Load local environment variables from a dotenv-style file.

    Args:
        env_path: Optional. Path to the dotenv file. When omitted, `.env` from
            the current working directory is used.

    Returns:
        A set with variable names loaded or already present.
    """
    loaded = set()
    path = Path(env_path) if env_path is not None else Path.cwd() / ".env"
    if not path.exists():
        return loaded

    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$", line)
        if not match:
            continue
        name, value = match.groups()
        value = _unquote_env_value(value)
        if not value or value.startswith("#"):
            continue
        os.environ.setdefault(name, value)
        loaded.add(name)
    return loaded


def _unquote_env_value(value):
    text = str(value).strip()
    if len(text) >= 2 and (
        (text.startswith('"') and text.endswith('"'))
        or (text.startswith("'") and text.endswith("'"))
    ):
        return text[1:-1]
    return text


def require_env(name):
    """Return a required environment variable.

    Args:
        name: Required. Environment variable name.

    Returns:
        The variable value.

    Raises:
        RuntimeError: If the variable is missing.
    """
    load_env()
    value = os.environ.get(name)
    if value:
        value = _unquote_env_value(value)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def api_timeout(default=DEFAULT_TIMEOUT):
    """Return the effective music HTTP timeout.

    Args:
        default: Optional. Default timeout in seconds when
            `MUSIC_API_TIMEOUT` is not set.

    Returns:
        The timeout in seconds.

    Raises:
        ValueError: If `MUSIC_API_TIMEOUT` is not a positive integer.
    """
    load_env()
    value = os.environ.get("MUSIC_API_TIMEOUT")
    if value is None or not value.strip():
        return default
    try:
        timeout = int(value)
    except ValueError:
        raise ValueError("MUSIC_API_TIMEOUT must be a positive integer") from None
    if timeout <= 0:
        raise ValueError("MUSIC_API_TIMEOUT must be a positive integer")
    return timeout


def auth_header(env_name, scheme="bearer"):
    """Build one authentication header.

    Args:
        env_name: Required. Environment variable containing the credential.
        scheme: Optional. Header scheme. Accepted values:
            - "bearer": Authorization: Bearer <token>.
            - "xi-api-key": xi-api-key: <token>.
            - "x-goog-api-key": x-goog-api-key: <token>.

    Returns:
        A header dictionary.
    """
    token = require_env(env_name)
    if scheme == "bearer":
        return {"Authorization": f"Bearer {token}"}
    if scheme in {"xi-api-key", "x-goog-api-key"}:
        return {scheme: token}
    raise ValueError(f"Unknown auth scheme: {scheme}")


def request_json(
    method,
    url,
    headers=None,
    params=None,
    json_payload=None,
    data=None,
    files=None,
    timeout=None,
):
    """Send an HTTP request and parse a JSON response.

    Args:
        method: Required. HTTP method.
        url: Required. Request URL.
        headers: Optional. HTTP headers.
        params: Optional. Query parameters.
        json_payload: Optional. JSON body.
        data: Optional. Form body.
        files: Optional. Multipart files.
        timeout: Optional. Timeout in seconds.

    Returns:
        Parsed JSON data.
    """
    response = requests.request(
        method,
        url,
        headers=headers,
        params=params,
        json=json_payload,
        data=data,
        files=files,
        timeout=api_timeout() if timeout is None else timeout,
    )
    parsed = _parse_json(response)
    if response.status_code >= 400:
        raise ApiRequestError(format_response_error(response, parsed))
    return parsed


def download_url(url, output_path, timeout=None):
    """Download an audio URL to disk.

    Args:
        url: Required. Download URL.
        output_path: Required. Destination path.
        timeout: Optional. Timeout in seconds.

    Returns:
        The saved path string.
    """
    response = requests.get(url, timeout=api_timeout() if timeout is None else timeout)
    if response.status_code >= 400:
        parsed = _parse_json(response)
        raise ApiRequestError(format_response_error(response, parsed))
    return save_bytes(response.content, output_path)


def download_generation_audio(generation, provider, audio_url, extension="mp3"):
    """Download one audio URL and update the standardized generation object.

    Args:
        generation: Required. Normalized generation dictionary.
        provider: Required. Provider file name.
        audio_url: Required. URL returned by the provider.
        extension: Optional. Output file extension. Defaults to "mp3".

    Returns:
        The updated generation dictionary.
    """
    if generation.get("output_path"):
        return generation
    if not audio_url:
        raise RuntimeError("Provider response did not include an audio URL")
    output_path = make_temp_output_path(provider, generation["model"], extension)
    generation["output_path"] = download_url(audio_url, output_path)
    generation["status"] = "completed"
    return generation


def save_bytes(data, output_path):
    """Save bytes to disk.

    Args:
        data: Required. Bytes-like value.
        output_path: Required. Destination path.

    Returns:
        The saved path string.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(data))
    return str(path)


def make_temp_output_path(provider, model, extension="mp3"):
    """Return a collision-resistant temporary output path.

    Args:
        provider: Required. Provider file name.
        model: Required. Model identifier.
        extension: Optional. File extension. Defaults to "mp3".

    Returns:
        A path string under `outputs/temp/`.
    """
    file_id = uuid.uuid4().hex
    return str(
        _output_root()
        / "temp"
        / slug(provider)
        / slug(model)
        / f"{file_id}.{extension.lstrip('.')}"
    )


def standard_generation(
    provider,
    model,
    request_id,
    status="submitted",
    model_key=None,
    output_path=None,
    cost_usd=None,
    cost_currency="USD",
    cost_source=None,
    cost_is_estimated=False,
    cost_details=None,
    metadata=None,
):
    """Build the public generation dictionary returned by all providers.

    Args:
        provider: Required. Provider file name.
        model: Required. Model identifier.
        request_id: Required. Provider request ID or local job ID.
        status: Optional. Standard local status.
        model_key: Optional. Standardized model key.
        output_path: Optional. Local downloaded file path.
        cost_usd: Optional. Known or estimated USD cost.
        cost_currency: Optional. Currency code. Defaults to `"USD"`.
        cost_source: Optional. Cost source label. Defaults to `"unavailable"`
            when `cost_usd` is not known.
        cost_is_estimated: Optional. Whether the cost is estimated.
        cost_details: Optional. Provider-neutral cost details.
        metadata: Optional. Provider-neutral metadata.

    Returns:
        A normalized public generation dictionary.
    """
    if model_key is None:
        model_key = model_key_for(provider, model)
    cost = cost_metadata(
        cost_usd,
        currency=cost_currency,
        source=cost_source,
        is_estimated=cost_is_estimated,
        details=cost_details,
    )
    return {
        "provider": provider,
        "model": model,
        "model_key": model_key,
        "status": status,
        "request_id": request_id,
        "output_path": output_path,
        **cost,
        "metadata": dict(metadata or {}),
    }


def cost_metadata(
    cost_usd=None,
    currency="USD",
    source=None,
    is_estimated=False,
    details=None,
):
    """Build normalized public cost metadata.

    Args:
        cost_usd: Optional. Numeric USD cost. Unknown cost is normalized to
            `0.0` with `cost_source="unavailable"`.
        currency: Optional. Currency code. Defaults to `"USD"`.
        source: Optional. Cost source label.
        is_estimated: Optional. Whether the cost is estimated.
        details: Optional. Provider-neutral details about the cost basis.

    Returns:
        A dictionary with the public cost metadata fields.
    """
    normalized_cost = normalize_cost(cost_usd)
    if normalized_cost is None:
        normalized_cost = 0.0
        source = "unavailable"
        is_estimated = False
    elif source is None:
        source = "provider_response"

    return {
        "cost_usd": normalized_cost,
        "cost_currency": str(currency or "USD"),
        "cost_source": source,
        "cost_is_estimated": bool(is_estimated),
        "cost_details": dict(details or {}),
    }


def apply_cost_metadata(
    generation,
    cost_usd,
    source=None,
    is_estimated=False,
    details=None,
):
    """Update a generation dictionary with known cost metadata.

    Args:
        generation: Required. Normalized generation dictionary.
        cost_usd: Required. Known or estimated cost value.
        source: Optional. Cost source label.
        is_estimated: Optional. Whether the cost is estimated.
        details: Optional. Provider-neutral details.

    Returns:
        The updated generation dictionary.
    """
    if normalize_cost(cost_usd) is None:
        return generation
    generation.update(
        cost_metadata(
            cost_usd,
            source=source,
            is_estimated=is_estimated,
            details=details,
        )
    )
    return generation


def reject_unknown_kwargs(kwargs, allowed):
    """Raise `ValueError` when kwargs include unsupported keys.

    Args:
        kwargs: Required. Keyword argument dictionary.
        allowed: Required. Iterable with accepted key names.

    Raises:
        ValueError: If any kwarg is not accepted.
    """
    unknown = sorted(set(kwargs) - set(allowed))
    if unknown:
        raise ValueError(f"Unsupported kwargs: {', '.join(unknown)}")


def reject_parameter_present(kwargs, parameter, provider):
    """Raise `ValueError` when an unsupported parameter is present.

    Args:
        kwargs: Required. Keyword argument dictionary.
        parameter: Required. Parameter name.
        provider: Required. Provider file name.
    """
    if parameter in kwargs:
        raise ValueError(f"{parameter} is not supported for {provider}")


def normalize_duration(value, minimum, maximum, default=None):
    """Return a clamped integer duration or the provider default.

    Args:
        value: Optional. Public duration value.
        minimum: Required. Minimum meaningful duration in seconds.
        maximum: Required. Maximum meaningful duration in seconds.
        default: Optional. Value returned when `value` is absent or invalid.

    Returns:
        The normalized duration in seconds, or `default` when absent/invalid.
    """
    duration = _parse_duration(value)
    if duration is None:
        return default
    return max(minimum, min(maximum, duration))


def duration_phrase(duration):
    """Return a natural English approximate duration phrase."""
    minutes, seconds = divmod(int(duration), 60)
    if minutes and seconds:
        minute_word = "minute" if minutes == 1 else "minutes"
        second_word = "second" if seconds == 1 else "seconds"
        return f"about {minutes} {minute_word} and {seconds} {second_word}"
    if minutes:
        minute_word = "minute" if minutes == 1 else "minutes"
        return f"about {minutes} {minute_word}"
    second_word = "second" if seconds == 1 else "seconds"
    return f"about {seconds} {second_word}"


def raise_input_limit_error(provider, model, fields):
    """Raise a public music input-limit exception."""
    raise MusicInputLimitError(
        provider=provider,
        model=model,
        model_key=model_key_for(provider, model),
        fields=fields,
    )


def text_limit_field(text, maximum, unit="characters"):
    """Return limit metadata when text exceeds a maximum length."""
    observed = len(text or "")
    if observed <= maximum:
        return None
    return {
        "unit": unit,
        "maximum": maximum,
        "observed": observed,
    }


def validate_range(name, value, minimum, maximum, suffix=""):
    """Raise `ValueError` when a numeric value is outside an inclusive range.

    Args:
        name: Required. Public parameter name used in the error message.
        value: Required. Value to validate.
        minimum: Required. Minimum accepted value.
        maximum: Required. Maximum accepted value.
        suffix: Optional. Text appended after the maximum value.
    """
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}{suffix}")


def _parse_duration(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        if not math.isfinite(float(value)):
            return None
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            number = float(text)
        except ValueError:
            return None
        if not math.isfinite(number):
            return None
        return int(number)
    return None


def start_local_job(
    provider,
    model,
    worker,
    extension="mp3",
    cost_usd=None,
    cost_source=None,
    cost_is_estimated=False,
    cost_details=None,
    metadata=None,
):
    """Start a local background job for synchronous provider endpoints.

    Args:
        provider: Required. Provider file name.
        model: Required. Model identifier.
        worker: Required. Callable receiving `output_path`.
        extension: Optional. Output file extension. Defaults to "mp3".
        cost_usd: Optional. Known or estimated cost.
        cost_source: Optional. Cost source label.
        cost_is_estimated: Optional. Whether the cost is estimated.
        cost_details: Optional. Provider-neutral cost details.
        metadata: Optional. Provider-neutral metadata.

    Returns:
        A normalized generation dictionary.
    """
    request_id = uuid.uuid4().hex
    output_path = make_temp_output_path(provider, model, extension)
    job = {
        "status": "running",
        "provider": provider,
        "model": model,
        "request_id": request_id,
        "output_path": output_path,
        "error": None,
        "error_type": None,
        "error_message": None,
    }
    with _LOCAL_JOBS_LOCK:
        _LOCAL_JOBS[request_id] = job

    def run_worker():
        try:
            worker(output_path)
            with _LOCAL_JOBS_LOCK:
                job["status"] = "completed"
        except Exception as exc:
            with _LOCAL_JOBS_LOCK:
                job["status"] = "failed"
                job["error_type"] = type(exc).__name__
                job["error_message"] = str(sanitize(str(exc)))
                job["error"] = _format_local_job_error(job)

    thread = threading.Thread(target=run_worker, daemon=True)
    thread.start()
    return standard_generation(
        provider=provider,
        model=model,
        request_id=request_id,
        status="submitted",
        cost_usd=cost_usd,
        cost_source=cost_source,
        cost_is_estimated=cost_is_estimated,
        cost_details=cost_details,
        metadata=metadata,
    )


def normalize_cost(value):
    """Return a simple numeric cost value or `None`."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, 8)


def get_local_job(request_id):
    """Return a local job snapshot.

    Args:
        request_id: Required. Local job ID.

    Returns:
        A copy of the local job dictionary.

    Raises:
        KeyError: If the local job is unknown.
    """
    with _LOCAL_JOBS_LOCK:
        return dict(_LOCAL_JOBS[request_id])


def _clear_local_job(request_id):
    """Remove one local job from the in-memory registry.

    Args:
        request_id: Required. Local job ID.
    """
    with _LOCAL_JOBS_LOCK:
        _LOCAL_JOBS.pop(request_id, None)


def _local_job_ready(request_id):
    """Return whether a local job finished successfully.

    Args:
        request_id: Required. Local job ID.

    Returns:
        `True` when completed, otherwise `False`.

    Raises:
        LocalJobError: If the local job failed.
    """
    job = get_local_job(request_id)
    if job["status"] == "failed":
        raise LocalJobError(job["error"])
    return job["status"] == "completed"


def _format_local_job_error(job):
    """Build a sanitized local worker error message.

    Args:
        job: Required. Local job snapshot with provider, model, request ID, and
            stored exception fields.

    Returns:
        A compact message safe to expose at the caller boundary.
    """
    provider = str(sanitize(job.get("provider") or "unknown"))
    model = str(sanitize(job.get("model") or "unknown"))
    request_id = str(sanitize(job.get("request_id") or "unknown"))
    error_type = str(sanitize(job.get("error_type") or "RuntimeError"))
    error_message = str(sanitize(job.get("error_message") or "worker failed"))
    return (
        "Local music job failed "
        f"provider={provider} model={model} request_id={request_id}: "
        f"{error_type}: {error_message}"
    )


def update_local_job_generation(generation):
    """Update a generation dictionary from an in-memory local job.

    Args:
        generation: Required. Dictionary returned by `start_local_job()`.

    Returns:
        The updated generation dictionary.

    Raises:
        LocalJobError: If the local worker failed.
    """
    try:
        ready = _local_job_ready(generation["request_id"])
    except LocalJobError:
        generation["status"] = "failed"
        raise
    if not ready:
        generation["status"] = "running"
        return generation
    job = get_local_job(generation["request_id"])
    generation["status"] = "completed"
    generation["output_path"] = job["output_path"]
    return generation


def complete_local_job_generation(generation):
    """Update and clear a completed in-memory local job.

    Args:
        generation: Required. Dictionary returned by `start_local_job()`.

    Returns:
        The updated generation dictionary.

    Raises:
        LocalJobError: If the local worker failed.
    """
    update_local_job_generation(generation)
    if generation["status"] == "completed":
        _clear_local_job(generation["request_id"])
    return generation


def slug(value):
    """Return a safe filesystem slug.

    Args:
        value: Required. Raw label.

    Returns:
        A safe slug string.
    """
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9._-]+", "_", text)
    return text.strip("_") or "unknown"


def _output_root():
    """Return the caller working-directory output root for generated music."""
    return Path.cwd() / "outputs" / "music"


def sanitize(value):
    """Redact secrets and large audio payloads from report data.

    Args:
        value: Required. Nested value.

    Returns:
        A sanitized copy.
    """
    secrets = _secret_values()
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(part in lowered for part in ("authorization", "api_key", "token", "secret")):
                clean[key] = "<redacted>"
            elif _is_url_key(lowered) and item:
                clean[key] = "<redacted-url>"
            elif lowered in {
                "audiobase64data",
                "audio_base64",
                "base64_audio",
                "audio_data",
                "data",
            } and _looks_like_large_audio_payload(item):
                clean[key] = f"<omitted {len(str(item))} chars>"
            else:
                clean[key] = sanitize(item)
        return clean
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize(item) for item in value]
    if isinstance(value, bytes):
        return f"<bytes {len(value)}>"
    if isinstance(value, str):
        text = value
        for secret in secrets:
            if secret and secret in text:
                text = text.replace(secret, "<redacted>")
        text = _redact_urls_in_text(text)
        if _looks_like_base64(text) and len(text) > 500:
            return f"<base64 {len(text)} chars>"
        if _looks_like_hex(text) and len(text) > 500:
            return f"<hex {len(text)} chars>"
        return text
    return value


def _parse_json(response):
    try:
        parsed = response.json()
    except ValueError:
        text = response.text[:2000] if response.text else ""
        return {"raw_text": text}
    return parsed


def format_response_error(response, parsed=None):
    """Return a sanitized HTTP error message for a `requests.Response`.

    Args:
        response: Required. HTTP response object.
        parsed: Optional. Parsed response body. If omitted, JSON is parsed or
            raw text is used.

    Returns:
        A sanitized error message with HTTP status, URL, and response details.
    """
    if parsed is None:
        parsed = _parse_json(response)
    safe = json.dumps(sanitize(parsed), ensure_ascii=False)[:2000]
    return f"HTTP {response.status_code} from {_safe_response_url(response.url)}: {safe}"


def _safe_response_url(url):
    text = _redact_url(str(url))
    try:
        parsed = urlsplit(text)
    except ValueError:
        return "<redacted-url>"
    if not parsed.scheme or not parsed.netloc:
        return "<redacted-url>"
    return text


def _redact_urls_in_text(text):
    return URL_PATTERN.sub(lambda match: _redact_url(match.group(0), hide_sensitive=True), text)


def _redact_url(url, hide_sensitive=False):
    trailing = ""
    while url and url[-1] in ".,);]":
        trailing = url[-1] + trailing
        url = url[:-1]
    try:
        parsed = urlsplit(url)
    except ValueError:
        return "<redacted-url>"
    if not parsed.scheme or not parsed.netloc:
        return "<redacted-url>"
    if hide_sensitive and (parsed.query or parsed.fragment or _looks_like_media_path(parsed.path)):
        return "<redacted-url>" + trailing
    query = "<redacted>" if parsed.query or parsed.fragment else ""
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, "")) + trailing


def _looks_like_media_path(path):
    suffix = Path(str(path or "")).suffix.lower()
    return suffix in {
        ".aac",
        ".aiff",
        ".flac",
        ".m4a",
        ".mp3",
        ".mp4",
        ".ogg",
        ".opus",
        ".wav",
        ".webm",
    }


def _looks_like_large_audio_payload(value):
    if isinstance(value, bytes):
        return True
    if not isinstance(value, str):
        return False
    return value.startswith("data:audio") or _looks_like_base64(value) or _looks_like_hex(value)


def _is_url_key(key):
    return key == "url" or key.endswith("_url") or key.endswith("url")


def _looks_like_base64(value):
    if not isinstance(value, str) or len(value.strip()) < 200:
        return False
    text = value.strip()
    if text.startswith("http") or text.startswith("data:"):
        return False
    try:
        base64.b64decode(text, validate=True)
    except (ValueError, TypeError):
        return False
    return True


def _looks_like_hex(value):
    if not isinstance(value, str) or len(value.strip()) < 200:
        return False
    text = value.strip()
    if len(text) % 2:
        return False
    try:
        bytes.fromhex(text)
    except ValueError:
        return False
    return True


def _secret_values():
    values = []
    for name, value in os.environ.items():
        lowered = name.lower()
        if value and any(part in lowered for part in ("key", "token", "secret")):
            values.append(value)
    return values


