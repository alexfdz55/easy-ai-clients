"""Shared helpers for provider wrappers.

The public SDK intentionally keeps provider modules small and explicit. Shared
helpers here cover only transport, environment, media preparation, validation,
polling, downloads, and result normalization.
"""

import base64
import json
import mimetypes
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from pathlib import Path

import requests

FAL_QUEUE_BASE_URL = "https://queue.fal.run"
FAL_API_BASE_URL = "https://api.fal.ai/v1"
RUNWAY_BASE_URL = "https://api.dev.runwayml.com"
RUNWAY_API_VERSION = "2024-11-06"
GOOGLE_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
HEDRA_BASE_URL = "https://api.hedra.com/web-app/public"

_REQUESTS_PATH = re.compile(r"/requests/([^/?#]+)")


class ProviderJobError(RuntimeError):
    """A provider job or request failed.

    Same message as the plain ``RuntimeError`` it replaces (callers classify retries by
    the text), plus the provider ``request_id`` and HTTP ``status_code`` when known.
    """

    def __init__(self, message, *, request_id=None, status_code=None):
        super().__init__(message)
        self.request_id = str(request_id or "")
        self.status_code = status_code


class ProviderJobTimeout(TimeoutError):
    """A provider job did not finish in time. Carries the provider ``request_id``."""

    def __init__(self, message, *, request_id=None):
        super().__init__(message)
        self.request_id = str(request_id or "")


def _request_id_from_http_error(exc, url):
    headers = getattr(exc, "headers", None) or {}
    for key in ("x-fal-request-id", "x-request-id", "request-id"):
        try:
            value = headers.get(key)
        except Exception:
            value = None
        if value:
            return str(value)
    match = _REQUESTS_PATH.search(str(url or ""))
    return match.group(1) if match else ""


def require_env(name, provider):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required for {provider} API requests.")
    return value


def clean_text(value, field_name):
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required.")
    return text


def normalize_output_path(output_path):
    if output_path is None:
        return None
    value = str(output_path).strip()
    if not value:
        return None
    path = Path(value)
    if not path.suffix:
        path = path.with_suffix(".mp4")
    return str(path)


def resolve_existing_file(path, field_name):
    value = str(path or "").strip()
    if not value:
        raise ValueError(f"{field_name} is required.")
    resolved = Path(value).expanduser().resolve()
    if not resolved.exists() or not resolved.is_file():
        raise FileNotFoundError(f"{field_name} does not exist: {resolved}")
    return str(resolved)


def local_file_to_data_url(path):
    resolved = resolve_existing_file(path, "media_path")
    mime_type = mimetypes.guess_type(resolved)[0] or "application/octet-stream"
    with open(resolved, "rb") as handle:
        encoded = base64.b64encode(handle.read()).decode("ascii")
    return "data:" + mime_type + ";base64," + encoded


def local_file_to_base64_object(path):
    resolved = resolve_existing_file(path, "image_path")
    mime_type = mimetypes.guess_type(resolved)[0] or "image/png"
    with open(resolved, "rb") as handle:
        encoded = base64.b64encode(handle.read()).decode("ascii")
    return {"mimeType": mime_type, "bytesBase64Encoded": encoded}


def media_reference(path, url, path_name, url_name, allow_data_url=True):
    if path and url:
        raise ValueError(f"Provide either {path_name} or {url_name}, not both.")
    if url:
        value = str(url).strip()
        if not value:
            raise ValueError(f"{url_name} cannot be empty.")
        if not allow_data_url and value.startswith("data:"):
            raise ValueError(f"{url_name} cannot be a data URL for this provider.")
        return value
    if path:
        return local_file_to_data_url(path)
    return None


def http_json(method, url, headers=None, payload=None, timeout_seconds=None):
    request_headers = dict(headers or {})
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(
        url,
        data=data,
        headers=request_headers,
        method=str(method).upper(),
    )
    timeout = float(timeout_seconds or 60)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            if not body:
                return {}
            return json.loads(body.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        message = compact_whitespace(body[:1200]) or str(exc)
        raise ProviderJobError(
            f"HTTP {exc.code} from {url}: {message}",
            request_id=_request_id_from_http_error(exc, url),
            status_code=exc.code,
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Request failed for {url}: {exc.reason}") from exc


def download_file(url, output_path, headers=None, timeout_seconds=None):
    if not output_path:
        raise ValueError("output_path is required when downloading a video_url.")
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(str(url), headers=dict(headers or {}), method="GET")
    timeout = float(timeout_seconds or 120)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            with target.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        message = compact_whitespace(body[:1200]) or str(exc)
        raise RuntimeError(f"Download failed with HTTP {exc.code}: {message}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Download failed for {url}: {exc.reason}") from exc
    return str(target)


_ASYNC_REF_KEY_ALIASES = {
    "status_url": "status_url",
    "statusUrl": "status_url",
    "response_url": "response_url",
    "responseUrl": "response_url",
    "result_url": "result_url",
    "resultUrl": "result_url",
    "poll_url": "poll_url",
    "pollUrl": "poll_url",
    "polling_url": "poll_url",
    "pollingUrl": "poll_url",
    "task_url": "task_url",
    "taskUrl": "task_url",
    "operation_url": "operation_url",
    "operationUrl": "operation_url",
    "cancel_url": "cancel_url",
    "cancelUrl": "cancel_url",
    "download_url": "download_url",
    "downloadUrl": "download_url",
    "video_url": "video_url",
    "videoUrl": "video_url",
    "generation_id": "generation_id",
    "generationId": "generation_id",
    "task_id": "task_id",
    "taskId": "task_id",
    "job_id": "job_id",
    "jobId": "job_id",
    "operation_name": "operation_name",
    "operationName": "operation_name",
    "video_id": "video_id",
    "videoId": "video_id",
    "session_id": "session_id",
    "sessionId": "session_id",
    "lipsync_id": "lipsync_id",
    "lipsyncId": "lipsync_id",
    "video_translation_id": "video_translation_id",
    "videoTranslationId": "video_translation_id",
    "translation_id": "translation_id",
    "translationId": "translation_id",
}

_ASYNC_URL_REF_KEYS = {
    key for key in set(_ASYNC_REF_KEY_ALIASES.values()) if key.endswith("_url")
}
_ASYNC_CONTAINER_KEYS = ("data", "submission", "result", "response", "task", "operation")
_SENSITIVE_QUERY_FRAGMENTS = (
    "token",
    "secret",
    "signature",
    "credential",
    "policy",
    "x-amz",
    "x-goog",
    "authorization",
    "apikey",
    "api_key",
    "access_key",
)
_SENSITIVE_RAW_KEY_FRAGMENTS = (
    "authorization",
    "api_key",
    "apikey",
    "access_key",
    "secret",
    "token",
    "signature",
    "credential",
    "password",
    "bearer",
    "uploadurl",
    "upload_url",
    "signed",
    "policy",
)
_SENSITIVE_RAW_KEYS = {"fields", "form", "form_fields", "headers"}


def safe_provider_url(value):
    """Return a provider operation URL only when it does not look credential-bearing."""

    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    parsed = urllib.parse.urlsplit(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    if parsed.username or parsed.password:
        return None
    for key, _ in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
        normalized = key.lower()
        if any(fragment in normalized for fragment in _SENSITIVE_QUERY_FRAGMENTS):
            return None
    return text


def _looks_like_url(value):
    if not isinstance(value, str):
        return False
    parsed = urllib.parse.urlsplit(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def sanitize_public_response(value, key_name=""):
    normalized_key = str(key_name or "").replace("-", "_").lower()
    if normalized_key in _SENSITIVE_RAW_KEYS or any(
        fragment in normalized_key for fragment in _SENSITIVE_RAW_KEY_FRAGMENTS
    ):
        return "[redacted]"
    if isinstance(value, Mapping):
        return {str(key): sanitize_public_response(item, str(key)) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_public_response(item, key_name) for item in value]
    if _looks_like_url(value) and safe_provider_url(value) is None:
        return "[redacted]"
    return value


def _safe_async_scalar(value):
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, int | float):
        return str(value)
    return None


def _collect_async_refs(source, refs):
    if not isinstance(source, Mapping):
        return
    for provider_key, public_key in _ASYNC_REF_KEY_ALIASES.items():
        if provider_key not in source or source.get(provider_key) is None:
            continue
        value = source.get(provider_key)
        if public_key in _ASYNC_URL_REF_KEYS:
            safe_url = safe_provider_url(value)
            if safe_url:
                refs.setdefault(public_key, safe_url)
        else:
            scalar = _safe_async_scalar(value)
            if scalar is not None:
                refs.setdefault(public_key, scalar)
    for key in _ASYNC_CONTAINER_KEYS:
        nested = source.get(key)
        if isinstance(nested, Mapping):
            _collect_async_refs(nested, refs)


def safe_async_refs(*sources, **defaults):
    refs = {}
    for source in sources:
        _collect_async_refs(source, refs)
    for key, value in defaults.items():
        public_key = _ASYNC_REF_KEY_ALIASES.get(key, key)
        if value is None or public_key in refs:
            continue
        if public_key in _ASYNC_URL_REF_KEYS:
            safe_url = safe_provider_url(value)
            if safe_url:
                refs[public_key] = safe_url
        else:
            scalar = _safe_async_scalar(value)
            if scalar is not None:
                refs[public_key] = scalar
    return refs


def async_ref_kwargs(kwargs):
    return safe_async_refs({key: kwargs.get(key) for key in _ASYNC_REF_KEY_ALIASES})


def merge_async_refs(extra=None, *sources, **defaults):
    merged = safe_async_refs(*sources, **defaults)
    if extra:
        merged.update(dict(extra))
    return merged


def normalize_result(provider, model, status=None, request_id=None, video_url=None, output_path=None, cost_usd=None, cost_is_estimated=True, cost_source=None, raw_response=None, extra=None):
    warnings = []
    if cost_usd is None:
        cost_usd = 0.0
        warnings.append(f"No documented pricing metadata is available for {provider} {model}.")
    if cost_source is None:
        cost_source = "unavailable"
    result = {
        "provider": provider,
        "model": model,
        "status": status or "completed",
        "request_id": request_id,
        "video_url": video_url,
        "output_path": output_path,
        "cost_usd": float(cost_usd),
        "cost_currency": "USD",
        "cost_is_estimated": bool(cost_is_estimated),
        "cost_source": cost_source,
        "cost_details": {},
        "raw_response": sanitize_public_response(raw_response or {}),
    }
    async_refs = safe_async_refs(raw_response or {})
    if async_refs:
        result.update(async_refs)
    if extra:
        result.update(dict(extra))
        result.setdefault("cost_currency", "USD")
        result.setdefault("cost_details", {})
    if warnings:
        existing = str(result.get("warnings") or "").strip()
        joined = "; ".join([existing, *warnings] if existing else warnings)
        result["warnings"] = joined
    return result


def validate_allowed_kwargs(kwargs, allowed_names, model, provider, context, common_names=None):
    return None


def validate_enum(name, value, allowed_values, provider, model):
    return value


def validate_number(name, value, minimum, maximum, provider, model):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def merge_extra_payload(payload, kwargs):
    extra_payload = kwargs.get("extra_payload")
    if extra_payload is None:
        return payload
    if not isinstance(extra_payload, dict):
        raise ValueError("extra_payload must be a dictionary when provided.")
    merged = dict(payload)
    merged.update(extra_payload)
    return merged


def compact_whitespace(value):
    return " ".join(str(value or "").split())


def fal_headers(api_key):
    return {"Authorization": "Key " + api_key, "Content-Type": "application/json"}


def fal_submit(model, payload, api_key, timeout_seconds=None):
    return http_json(
        "POST",
        FAL_QUEUE_BASE_URL + "/" + model,
        headers=fal_headers(api_key),
        payload=payload,
        timeout_seconds=timeout_seconds,
    )


def fal_estimate_unit_price(model, unit_quantity, api_key, timeout_seconds=None):
    quantity = float(unit_quantity)
    payload = {
        "estimate_type": "unit_price",
        "endpoints": {model: {"unit_quantity": quantity}},
    }
    raw = http_json(
        "POST",
        FAL_API_BASE_URL + "/models/pricing/estimate",
        headers=fal_headers(api_key),
        payload=payload,
        timeout_seconds=timeout_seconds,
    )
    if "total_cost" not in raw:
        raise RuntimeError("fal.ai pricing estimate did not return total_cost.")
    return {
        "cost_usd": float(raw["total_cost"]),
        "cost_is_estimated": True,
        "cost_source": "fal_pricing_estimate_api",
        "cost_reason": (
            "fal.ai pricing estimate API was used with caller-supplied unit_quantity; "
            "live generation usage reconciliation is not performed."
        ),
        "pricing_estimate": raw,
    }


def fal_status_url(model, request_id):
    return FAL_QUEUE_BASE_URL + "/" + model + "/requests/" + urllib.parse.quote(str(request_id), safe="") + "/status"


def fal_response_url(model, request_id):
    return FAL_QUEUE_BASE_URL + "/" + model + "/requests/" + urllib.parse.quote(str(request_id), safe="") + "/response"


def fal_async_refs(submission, model, request_id):
    refs = safe_async_refs(submission or {})
    defaults = {}
    if request_id and not any(refs.get(key) for key in ("status_url", "poll_url")):
        defaults["status_url"] = fal_status_url(model, request_id) + "?logs=1"
    if request_id and not any(refs.get(key) for key in ("response_url", "result_url")):
        defaults["response_url"] = fal_response_url(model, request_id)
    return safe_async_refs(refs, **defaults)


def fal_get_status(model, request_id, api_key, timeout_seconds=None, status_url=None, poll_url=None):
    explicit_url = safe_provider_url(status_url) or safe_provider_url(poll_url)
    url = explicit_url or (fal_status_url(model, request_id) + "?logs=1")
    return http_json("GET", url, headers=fal_headers(api_key), timeout_seconds=timeout_seconds)


def fal_get_result(
    model,
    request_id,
    api_key,
    timeout_seconds=None,
    response_url=None,
    result_url=None,
):
    explicit_url = safe_provider_url(response_url) or safe_provider_url(result_url)
    url = explicit_url or fal_response_url(model, request_id)
    return http_json("GET", url, headers=fal_headers(api_key), timeout_seconds=timeout_seconds)


def normalize_fal_status(value):
    status = str(value or "").upper()
    if status in ("COMPLETED", "OK"):
        return "completed"
    if status in ("IN_PROGRESS", "PROCESSING", "RUNNING"):
        return "running"
    if status in ("IN_QUEUE", "QUEUED"):
        return "queued"
    if status in ("CANCELED", "CANCELLED"):
        return "canceled"
    if status in ("FAILED", "ERROR", "REJECTED"):
        return "failed"
    return "submitted"


def fal_wait_for_result(
    model,
    request_id,
    api_key,
    timeout_seconds=None,
    poll_interval_seconds=None,
    status_url=None,
    poll_url=None,
    response_url=None,
    result_url=None,
):
    deadline = time.monotonic() + float(timeout_seconds or 900)
    interval = float(poll_interval_seconds or 5)
    last_status = {}
    while time.monotonic() < deadline:
        last_status = fal_get_status(
            model,
            request_id,
            api_key,
            timeout_seconds=60,
            status_url=status_url,
            poll_url=poll_url,
        )
        normalized = normalize_fal_status(last_status.get("status"))
        if normalized == "completed":
            result = fal_get_result(
                model,
                request_id,
                api_key,
                timeout_seconds=60,
                response_url=response_url,
                result_url=result_url,
            )
            return {"status": last_status, "response": result}
        if normalized in ("failed", "canceled"):
            raise ProviderJobError(
                f"fal.ai generation {request_id} ended with status {last_status}.",
                request_id=request_id,
            )
        time.sleep(max(0.5, interval))
    raise ProviderJobTimeout(
        f"fal.ai generation {request_id} timed out. Last status: {last_status}",
        request_id=request_id,
    )


def extract_video_url(response):
    if not isinstance(response, dict):
        return None
    video = response.get("video")
    if isinstance(video, str):
        return video
    if isinstance(video, dict) and video.get("url"):
        return video.get("url")
    videos = response.get("videos") or response.get("generated_videos")
    if isinstance(videos, list) and videos:
        first = videos[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            nested = first.get("video")
            if isinstance(nested, dict) and nested.get("url"):
                return nested.get("url")
            if first.get("url"):
                return first.get("url")
    output = response.get("output")
    if isinstance(output, list) and output:
        first = output[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            nested = first.get("video")
            if isinstance(nested, str):
                return nested
            if isinstance(nested, dict) and nested.get("url"):
                return nested.get("url")
            return first.get("url") or first.get("uri")
    if isinstance(output, str):
        return output
    if isinstance(output, dict):
        nested = output.get("video")
        if isinstance(nested, str):
            return nested
        if isinstance(nested, dict) and nested.get("url"):
            return nested.get("url")
        return output.get("url") or output.get("uri")
    for key in ("data", "result", "response"):
        nested = response.get(key)
        if isinstance(nested, dict):
            nested_url = extract_video_url(nested)
            if nested_url:
                return nested_url
    return response.get("video_url") or response.get("url")


def runway_headers(api_key):
    return {
        "Authorization": "Bearer " + api_key,
        "Content-Type": "application/json",
        "X-Runway-Version": RUNWAY_API_VERSION,
    }


def runway_submit(endpoint, payload, api_key, timeout_seconds=None):
    return http_json(
        "POST",
        RUNWAY_BASE_URL + endpoint,
        headers=runway_headers(api_key),
        payload=payload,
        timeout_seconds=timeout_seconds,
    )


def runway_upload_file(path, api_key, timeout_seconds=None):
    resolved = resolve_existing_file(path, "upload_path")
    filename = Path(resolved).name
    create_response = runway_submit(
        "/v1/uploads",
        {"filename": filename, "type": "ephemeral"},
        api_key,
        timeout_seconds=timeout_seconds,
    )
    upload_url = create_response.get("uploadUrl")
    fields = create_response.get("fields")
    runway_uri = create_response.get("runwayUri") or create_response.get("uri")
    if not upload_url or not isinstance(fields, dict) or not runway_uri:
        raise RuntimeError("Runway upload creation did not return uploadUrl, fields, and runwayUri.")
    mime_type = mimetypes.guess_type(resolved)[0] or "application/octet-stream"
    timeout = float(timeout_seconds or 120)
    with open(resolved, "rb") as handle:
        response = requests.post(
            upload_url,
            data=fields,
            files={"file": (filename, handle, mime_type)},
            timeout=timeout,
        )
    if response.status_code >= 400:
        message = compact_whitespace(response.text[:1200]) or response.reason
        raise RuntimeError(f"Runway file upload failed with HTTP {response.status_code}: {message}")
    return runway_uri


def runway_media_uri(path, url, path_name, url_name, api_key, timeout_seconds=None):
    if path and url:
        raise ValueError(f"Provide either {path_name} or {url_name}, not both.")
    if url:
        value = str(url).strip()
        if not value:
            raise ValueError(f"{url_name} cannot be empty.")
        return value
    if path:
        return runway_upload_file(path, api_key, timeout_seconds=timeout_seconds)
    return None


def runway_task_url(task_id):
    return RUNWAY_BASE_URL + "/v1/tasks/" + urllib.parse.quote(str(task_id), safe="")


def runway_async_refs(submission, task_id):
    refs = safe_async_refs(submission or {})
    if task_id and not any(
        refs.get(key) for key in ("status_url", "poll_url", "task_url", "result_url")
    ):
        return safe_async_refs(refs, task_url=runway_task_url(task_id))
    return refs


def runway_get_task(
    task_id,
    api_key,
    timeout_seconds=None,
    task_url=None,
    status_url=None,
    result_url=None,
    poll_url=None,
):
    explicit_url = (
        safe_provider_url(status_url)
        or safe_provider_url(task_url)
        or safe_provider_url(result_url)
        or safe_provider_url(poll_url)
    )
    url = explicit_url or runway_task_url(task_id)
    return http_json(
        "GET",
        url,
        headers=runway_headers(api_key),
        timeout_seconds=timeout_seconds,
    )


def normalize_runway_status(value):
    status = str(value or "").upper()
    if status == "SUCCEEDED":
        return "completed"
    if status in ("RUNNING", "THROTTLED"):
        return "running"
    if status in ("PENDING", "QUEUED"):
        return "queued"
    if status == "FAILED":
        return "failed"
    if status == "CANCELED":
        return "canceled"
    return "submitted"


def runway_wait_for_task(
    task_id,
    api_key,
    timeout_seconds=None,
    poll_interval_seconds=None,
    task_url=None,
    status_url=None,
    result_url=None,
    poll_url=None,
):
    deadline = time.monotonic() + float(timeout_seconds or 900)
    interval = float(poll_interval_seconds or 5)
    last_status = {}
    while time.monotonic() < deadline:
        last_status = runway_get_task(
            task_id,
            api_key,
            timeout_seconds=60,
            task_url=task_url,
            status_url=status_url,
            result_url=result_url,
            poll_url=poll_url,
        )
        normalized = normalize_runway_status(last_status.get("status"))
        if normalized == "completed":
            return last_status
        if normalized in ("failed", "canceled"):
            raise RuntimeError(f"Runway task {task_id} ended with status {last_status}.")
        time.sleep(max(1, interval))
    raise TimeoutError(f"Runway task {task_id} timed out. Last status: {last_status}")


def google_headers(api_key):
    return {"x-goog-api-key": api_key, "Content-Type": "application/json"}


def google_operation_url(operation_name):
    name = str(operation_name or "").lstrip("/")
    if name.startswith("https://"):
        return name
    return GOOGLE_GEMINI_BASE_URL + "/" + name


def google_async_refs(submission, operation_name):
    refs = safe_async_refs(submission or {}, operation_name=operation_name)
    if operation_name and not refs.get("operation_url"):
        return safe_async_refs(refs, operation_url=google_operation_url(operation_name))
    return refs


def google_get_operation(operation_name, api_key, timeout_seconds=None, operation_url=None):
    url = safe_provider_url(operation_url) or google_operation_url(operation_name)
    return http_json(
        "GET",
        url,
        headers=google_headers(api_key),
        timeout_seconds=timeout_seconds,
    )


def google_extract_video_url(operation):
    response = operation.get("response") if isinstance(operation, dict) else None
    if not isinstance(response, dict):
        return None
    video_response = response.get("generateVideoResponse") or response.get("generate_video_response")
    if not isinstance(video_response, dict):
        return None
    samples = video_response.get("generatedSamples") or video_response.get("generated_samples") or []
    if not samples:
        return None
    first = samples[0]
    if not isinstance(first, dict):
        return None
    video = first.get("video") or {}
    if isinstance(video, dict):
        return video.get("uri") or video.get("url")
    return None


def google_wait_for_operation(
    operation_name,
    api_key,
    timeout_seconds=None,
    poll_interval_seconds=None,
    operation_url=None,
):
    deadline = time.monotonic() + float(timeout_seconds or 900)
    interval = float(poll_interval_seconds or 10)
    last_status = {}
    while time.monotonic() < deadline:
        last_status = google_get_operation(
            operation_name,
            api_key,
            timeout_seconds=60,
            operation_url=operation_url,
        )
        if last_status.get("done") is True:
            if last_status.get("error"):
                raise RuntimeError(f"Google Veo operation failed: {last_status.get('error')}")
            return last_status
        time.sleep(max(1, interval))
    raise TimeoutError(f"Google Veo operation {operation_name} timed out. Last status: {last_status}")


def hedra_headers(api_key, content_type="application/json"):
    headers = {"X-API-Key": api_key}
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def hedra_json(method, path, api_key, payload=None, timeout_seconds=None):
    return http_json(
        method,
        HEDRA_BASE_URL + path,
        headers=hedra_headers(api_key),
        payload=payload,
        timeout_seconds=timeout_seconds,
    )


def hedra_create_asset(name, asset_type, api_key, timeout_seconds=None):
    payload = {"name": name, "type": asset_type}
    raw = hedra_json("POST", "/assets", api_key, payload=payload, timeout_seconds=timeout_seconds)
    asset_id = raw.get("id")
    if not asset_id:
        raise RuntimeError(f"Hedra asset creation for {name} did not return an asset id.")
    return asset_id


def hedra_upload_asset(asset_id, path, api_key, timeout_seconds=None):
    resolved = resolve_existing_file(path, "asset_path")
    timeout = float(timeout_seconds or 120)
    url = HEDRA_BASE_URL + "/assets/" + urllib.parse.quote(str(asset_id), safe="") + "/upload"
    with open(resolved, "rb") as handle:
        response = requests.post(
            url,
            headers={"X-API-Key": api_key},
            files={"file": (Path(resolved).name, handle)},
            timeout=timeout,
        )
    if response.status_code >= 400:
        message = compact_whitespace(response.text[:1200]) or response.reason
        raise RuntimeError(f"Hedra asset upload failed with HTTP {response.status_code}: {message}")
    if not response.content:
        return {}
    return response.json()


def hedra_upload_local_asset(path, asset_type, api_key, timeout_seconds=None):
    resolved = resolve_existing_file(path, "asset_path")
    asset_id = hedra_create_asset(Path(resolved).name, asset_type, api_key, timeout_seconds)
    hedra_upload_asset(asset_id, resolved, api_key, timeout_seconds)
    return asset_id


def normalize_hedra_status(value):
    status = str(value or "").lower()
    if status == "complete":
        return "completed"
    if status in ("processing", "finalizing"):
        return "running"
    if status == "queued":
        return "queued"
    if status == "error":
        return "failed"
    if status in ("canceled", "cancelled"):
        return "canceled"
    return "submitted"


def hedra_generation_status_url(generation_id):
    return HEDRA_BASE_URL + "/generations/" + urllib.parse.quote(str(generation_id), safe="") + "/status"


def hedra_async_refs(submission, generation_id):
    refs = safe_async_refs(submission or {}, generation_id=generation_id)
    if generation_id and not any(refs.get(key) for key in ("status_url", "poll_url", "result_url")):
        return safe_async_refs(refs, status_url=hedra_generation_status_url(generation_id))
    return refs


def hedra_get_generation_status(
    generation_id,
    api_key,
    timeout_seconds=None,
    status_url=None,
    result_url=None,
    poll_url=None,
):
    explicit_url = (
        safe_provider_url(status_url)
        or safe_provider_url(result_url)
        or safe_provider_url(poll_url)
    )
    if explicit_url:
        return http_json(
            "GET",
            explicit_url,
            headers=hedra_headers(api_key),
            timeout_seconds=timeout_seconds,
        )
    return hedra_json(
        "GET",
        "/generations/" + urllib.parse.quote(str(generation_id), safe="") + "/status",
        api_key,
        timeout_seconds=timeout_seconds,
    )


def hedra_wait_for_result(
    generation_id,
    api_key,
    timeout_seconds=None,
    poll_interval_seconds=None,
    status_url=None,
    result_url=None,
    poll_url=None,
):
    deadline = time.monotonic() + float(timeout_seconds or 1800)
    interval = float(poll_interval_seconds or 10)
    last_status = {}
    while time.monotonic() < deadline:
        last_status = hedra_get_generation_status(
            generation_id,
            api_key,
            timeout_seconds=60,
            status_url=status_url,
            result_url=result_url,
            poll_url=poll_url,
        )
        normalized = normalize_hedra_status(last_status.get("status"))
        if normalized == "completed":
            return last_status
        if normalized in ("failed", "canceled"):
            raise RuntimeError(f"Hedra generation {generation_id} ended with status {last_status}.")
        time.sleep(max(1, interval))
    raise TimeoutError(f"Hedra generation {generation_id} timed out. Last status: {last_status}")


def hedra_extract_video_url(response):
    if not isinstance(response, dict):
        return None
    return (
        response.get("download_url")
        or response.get("url")
        or response.get("streaming_url")
        or extract_video_url(response)
    )
