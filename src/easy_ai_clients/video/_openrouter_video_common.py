"""Shared OpenRouter Video API helpers for Seedance generation."""

from __future__ import annotations

import os
import time
import urllib.parse
from collections.abc import Mapping, Sequence
from typing import Any

from ._shared import (
    clean_text,
    download_file,
    http_json,
    media_reference,
    merge_async_refs,
    merge_extra_payload,
    normalize_output_path,
    normalize_result,
    require_env,
    safe_provider_url,
)

PROVIDER = "openrouter"
ENV_NAME = "OPENROUTER_API_KEY"
BASE_URL_ENV = "OPENROUTER_BASE_URL"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "bytedance/seedance-2.0-mini"

MODEL_2_0_MINI = "bytedance/seedance-2.0-mini"
MODEL_2_0_FAST = "bytedance/seedance-2.0-fast"
MODEL_2_0 = "bytedance/seedance-2.0"
MODEL_2_5 = "bytedance/seedance-2.5"
MODEL_1_5_PRO = "bytedance/seedance-1-5-pro"

DOCUMENTED_MODELS: dict[str, dict[str, Any]] = {
    MODEL_2_0_MINI: {
        "family": "2.0-mini",
        "duration_min": 4,
        "duration_max": 15,
        "resolutions": ("480p", "720p"),
        "aspect_ratios": ("1:1", "3:4", "9:16", "4:3", "16:9", "21:9", "9:21"),
        "default_resolution": "720p",
    },
    MODEL_2_0_FAST: {
        "family": "2.0-fast",
        "duration_min": 4,
        "duration_max": 15,
        "resolutions": ("480p", "720p"),
        "aspect_ratios": ("1:1", "3:4", "9:16", "4:3", "16:9", "21:9", "9:21"),
        "default_resolution": "720p",
    },
    MODEL_2_0: {
        "family": "2.0",
        "duration_min": 4,
        "duration_max": 15,
        "resolutions": ("480p", "720p", "1080p", "4K"),
        "aspect_ratios": ("1:1", "3:4", "9:16", "4:3", "16:9", "21:9", "9:21"),
        "default_resolution": "720p",
    },
    MODEL_2_5: {
        "family": "2.5",
        "duration_min": 4,
        "duration_max": 30,
        "resolutions": ("480p", "720p"),
        "aspect_ratios": ("16:9", "4:3", "1:1", "3:4", "9:16", "21:9"),
        "default_resolution": "720p",
    },
    MODEL_1_5_PRO: {
        "family": "1.5-pro",
        "duration_min": 4,
        "duration_max": 12,
        "resolutions": ("480p", "720p", "1080p"),
        "aspect_ratios": ("1:1", "3:4", "9:16", "9:21", "4:3", "16:9", "21:9"),
        "default_resolution": "720p",
    },
}

RESERVED_KWARGS = {
    "sync",
    "timeout_seconds",
    "poll_interval_seconds",
    "output_path",
    "model",
    "extra_payload",
    "image_urls",
    "video_urls",
    "audio_urls",
    "end_image_url",
    "last_image_url",
    "last_frame",
    "first_frame",
    "duration",
    "duration_seconds",
    "resolution",
    "size",
    "aspect_ratio",
    "ratio",
    "generate_audio",
    "image_path",
    "image_url",
    "video_path",
    "video_url",
    "reference_path",
    "reference_url",
    "frame_images",
    "input_references",
}

NATIVE_OPTIONAL = (
    "seed",
    "callback_url",
    "watermark",
    "req_key",
    "return_last_frame",
    "output_format",
)


def base_url() -> str:
    return str(os.getenv(BASE_URL_ENV) or DEFAULT_BASE_URL).rstrip("/")


def headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def videos_url() -> str:
    return f"{base_url()}/videos"


def video_job_url(job_id: str) -> str:
    return f"{videos_url()}/{urllib.parse.quote(str(job_id), safe='')}"


def video_content_url(job_id: str, *, index: int = 0) -> str:
    return f"{video_job_url(job_id)}/content?index={int(index)}"


def _absolute_url(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.startswith("/"):
        parsed = urllib.parse.urlsplit(base_url())
        origin = f"{parsed.scheme}://{parsed.netloc}"
        return origin + text
    return text


def _needs_auth(url: str | None) -> bool:
    if not url:
        return False
    host = urllib.parse.urlsplit(url).netloc.lower()
    return host == "openrouter.ai" or host.endswith(".openrouter.ai")


def download_headers_for_url(url: str | None, api_key: str | None = None) -> dict[str, str]:
    if not _needs_auth(url):
        return {}
    key = api_key or require_env(ENV_NAME, "OpenRouter")
    return {"Authorization": f"Bearer {key}"}


def create_job(payload: Mapping[str, Any], *, timeout_seconds: float | None = None) -> dict[str, Any]:
    api_key = require_env(ENV_NAME, "OpenRouter")
    return http_json(
        "POST",
        videos_url(),
        headers=headers(api_key),
        payload=dict(payload),
        timeout_seconds=timeout_seconds,
    )


def get_job(
    job_id: str,
    *,
    timeout_seconds: float | None = None,
    status_url: str | None = None,
    result_url: str | None = None,
    poll_url: str | None = None,
) -> dict[str, Any]:
    api_key = require_env(ENV_NAME, "OpenRouter")
    url = (
        safe_provider_url(status_url)
        or safe_provider_url(result_url)
        or safe_provider_url(poll_url)
        or _absolute_url(status_url)
        or _absolute_url(poll_url)
        or video_job_url(job_id)
    )
    return http_json(
        "GET",
        url,
        headers=headers(api_key),
        timeout_seconds=timeout_seconds,
    )


def async_refs(raw: Mapping[str, Any] | None, job_id: str | None) -> dict[str, Any]:
    refs = merge_async_refs(None, raw or {})
    polling = _absolute_url((raw or {}).get("polling_url"))
    if polling and not refs.get("poll_url"):
        refs = merge_async_refs(refs, poll_url=polling)
    if job_id and not any(refs.get(key) for key in ("status_url", "poll_url", "result_url")):
        refs = merge_async_refs(refs, status_url=video_job_url(job_id), poll_url=video_job_url(job_id))
    return refs


def normalize_status(value: Any) -> str:
    status = str(value or "").strip().lower()
    if status in {"succeeded", "success", "completed", "complete"}:
        return "completed"
    if status in {"running", "processing", "in_progress"}:
        return "running"
    if status in {"queued", "pending", "submitted"}:
        return "queued"
    if status in {"failed", "error"}:
        return "failed"
    if status in {"cancelled", "canceled"}:
        return "canceled"
    if status in {"expired"}:
        return "failed"
    return "submitted"


def request_id(raw: Mapping[str, Any]) -> str | None:
    for key in ("id", "job_id", "request_id"):
        if raw.get(key):
            return str(raw[key])
    data = raw.get("data")
    if isinstance(data, Mapping):
        return request_id(data)
    return None


def extract_video_url(response: Mapping[str, Any] | None, *, job_id: str | None = None) -> str | None:
    if not isinstance(response, dict):
        return None
    for candidate in (response, response.get("result"), response.get("data"), response.get("submission")):
        if not isinstance(candidate, dict):
            continue
        unsigned = candidate.get("unsigned_urls")
        if isinstance(unsigned, Sequence) and not isinstance(unsigned, (str, bytes)):
            for item in unsigned:
                url = str(item or "").strip()
                if url:
                    return url
        for key in ("video_url", "url"):
            if candidate.get(key):
                return str(candidate[key])
    if job_id:
        return video_content_url(job_id)
    return None


def _job_error_message(raw: Mapping[str, Any]) -> str:
    error = raw.get("error")
    if isinstance(error, Mapping):
        code = error.get("code") or error.get("type")
        message = error.get("message") or error.get("msg") or error
        if code:
            return f"{code}: {message}"
        return str(message)
    if error:
        return str(error)
    return str(raw)


def wait_for_job(
    job_id: str,
    *,
    timeout_seconds: float | None = None,
    poll_interval_seconds: float | None = None,
    status_url: str | None = None,
    result_url: str | None = None,
    poll_url: str | None = None,
) -> dict[str, Any]:
    deadline = time.monotonic() + float(timeout_seconds or 900)
    interval = float(poll_interval_seconds or 10)
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last = get_job(
            job_id,
            timeout_seconds=60,
            status_url=status_url,
            result_url=result_url,
            poll_url=poll_url,
        )
        status = normalize_status(last.get("status"))
        if status == "completed":
            return last
        if status in {"failed", "canceled"}:
            raise RuntimeError(
                f"OpenRouter video job {job_id} ended with status "
                f"{last.get('status')}: {_job_error_message(last)}"
            )
        time.sleep(max(1, interval))
    raise TimeoutError(f"OpenRouter video job {job_id} timed out. Last status: {last}")


def cost_from_job(raw: Mapping[str, Any] | None, model: str) -> dict[str, Any]:
    usage = None
    if isinstance(raw, Mapping):
        usage = raw.get("usage")
        if usage is None:
            result = raw.get("result")
            if isinstance(result, Mapping):
                usage = result.get("usage")
    if isinstance(usage, Mapping) and usage.get("cost") is not None:
        return {
            "cost_usd": float(usage["cost"]),
            "cost_is_estimated": False,
            "cost_source": "openrouter_video_usage",
            "cost_details": {"model": model, "usage": dict(usage)},
            "cost_reason": "OpenRouter reported usage.cost on the completed video job.",
        }
    return {
        "cost_usd": 0.0,
        "cost_is_estimated": True,
        "cost_source": "unavailable",
        "cost_details": {"model": model},
        "cost_reason": (
            "OpenRouter video cost is taken from usage.cost on a completed job; "
            "it is not available until the job finishes."
        ),
    }


def _normalize_resolution(value: Any) -> str:
    text = str(value or "").strip()
    if text.upper() == "4K":
        return "4K"
    if text.lower().endswith("p"):
        return text.lower()
    return text


def _validate_duration(model: str, duration: int) -> None:
    meta = DOCUMENTED_MODELS.get(model)
    if meta is None:
        return
    minimum = int(meta["duration_min"])
    maximum = int(meta["duration_max"])
    if duration < minimum or duration > maximum:
        raise ValueError(
            f"OpenRouter Seedance model `{model}` duration must be {minimum}-{maximum} "
            f"seconds; got {duration}."
        )


def _validate_resolution(model: str, resolution: str) -> None:
    meta = DOCUMENTED_MODELS.get(model)
    if meta is None:
        return
    allowed = meta["resolutions"]
    if resolution not in allowed:
        raise ValueError(
            f"OpenRouter Seedance model `{model}` does not support resolution `{resolution}`. "
            f"Documented resolutions: {', '.join(allowed)}."
        )


def _validate_aspect_ratio(model: str, aspect_ratio: str) -> None:
    meta = DOCUMENTED_MODELS.get(model)
    if meta is None:
        return
    allowed = meta["aspect_ratios"]
    if aspect_ratio not in allowed:
        raise ValueError(
            f"OpenRouter Seedance model `{model}` does not support aspect_ratio `{aspect_ratio}`. "
            f"Documented aspect ratios: {', '.join(allowed)}."
        )


def _frame_image(url: str, frame_type: str) -> dict[str, Any]:
    return {
        "type": "image_url",
        "image_url": {"url": url},
        "frame_type": frame_type,
    }


def _reference_item(url: str, kind: str) -> dict[str, Any]:
    if kind == "image_url":
        return {"type": "image_url", "image_url": {"url": url}}
    if kind == "video_url":
        return {"type": "video_url", "video_url": {"url": url}}
    if kind == "audio_url":
        return {"type": "audio_url", "audio_url": {"url": url}}
    raise ValueError(f"Unsupported OpenRouter reference kind `{kind}`.")


def _scalar_media(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, Mapping):
        nested_url = value.get("url")
        if nested_url:
            return str(nested_url)
        for key in ("image_url", "video_url", "audio_url"):
            nested = value.get(key)
            if isinstance(nested, Mapping) and nested.get("url"):
                return str(nested["url"])
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
    raise ValueError("Media reference must be a URL string or a dictionary with a url.")


def _ref_urls(value: Any) -> list[str]:
    if value is None:
        return []
    items = value if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) else [value]
    urls: list[str] = []
    for item in items:
        url = _scalar_media(item)
        if url:
            urls.append(url)
    return urls


def _content_prompt(prompt: Any, *, required: bool) -> str | None:
    if prompt is None:
        if required:
            raise ValueError("prompt is required.")
        return None
    text = str(prompt).strip()
    if required:
        return clean_text(text, "prompt")
    return text or None


def build_generation_payload(
    *,
    model: str,
    prompt: Any,
    mode: str,
    kwargs: Mapping[str, Any],
    first_image: str | None = None,
) -> dict[str, Any]:
    prompt_required = mode != "image_to_video" or not first_image
    prompt_text = _content_prompt(prompt, required=prompt_required)
    payload: dict[str, Any] = {"model": model}
    if prompt_text:
        payload["prompt"] = prompt_text

    frame_images: list[dict[str, Any]] = []
    if mode == "image_to_video":
        if not first_image:
            raise ValueError("OpenRouter image_to_video requires image_path or image_url.")
        frame_images.append(_frame_image(first_image, "first_frame"))
        last_image = _scalar_media(
            kwargs.get("end_image_url")
            or kwargs.get("last_image_url")
            or kwargs.get("last_frame")
        )
        if last_image:
            frame_images.append(_frame_image(last_image, "last_frame"))
    if frame_images:
        payload["frame_images"] = frame_images

    input_references: list[dict[str, Any]] = []
    for url in _ref_urls(kwargs.get("image_urls")):
        input_references.append(_reference_item(url, "image_url"))
    for url in _ref_urls(kwargs.get("video_urls")):
        input_references.append(_reference_item(url, "video_url"))
    for url in _ref_urls(kwargs.get("audio_urls")):
        input_references.append(_reference_item(url, "audio_url"))
    if input_references:
        payload["input_references"] = input_references

    duration = kwargs.get("duration", kwargs.get("duration_seconds"))
    if duration is not None:
        duration_value = int(duration)
        _validate_duration(model, duration_value)
        payload["duration"] = duration_value

    if kwargs.get("resolution") is not None:
        resolution = _normalize_resolution(kwargs.get("resolution"))
        _validate_resolution(model, resolution)
        payload["resolution"] = resolution
    if kwargs.get("size") is not None:
        payload["size"] = str(kwargs.get("size")).strip()

    aspect = kwargs.get("aspect_ratio", kwargs.get("ratio"))
    if aspect is not None:
        aspect_text = str(aspect).strip()
        if aspect_text.lower() not in {"", "auto", "adaptive"}:
            _validate_aspect_ratio(model, aspect_text)
            payload["aspect_ratio"] = aspect_text

    if kwargs.get("generate_audio") is not None:
        payload["generate_audio"] = bool(kwargs.get("generate_audio"))

    for key in NATIVE_OPTIONAL:
        if key in kwargs and kwargs[key] is not None:
            payload[key] = kwargs[key]

    for key, value in kwargs.items():
        if key in RESERVED_KWARGS or key in payload or value is None:
            continue
        payload[key] = value

    return merge_extra_payload(payload, kwargs)


def build_result(
    *,
    model: str,
    status: str,
    request_id_value: str | None,
    video_url: str | None,
    output_path: str | None,
    raw: Mapping[str, Any],
    cost_metadata: Mapping[str, Any],
    extra: Mapping[str, Any] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    saved_path = normalize_output_path(output_path)
    if video_url and saved_path and status == "completed":
        saved_path = download_file(
            video_url,
            saved_path,
            headers=download_headers_for_url(video_url, api_key),
        )
    return normalize_result(
        PROVIDER,
        model,
        status,
        request_id_value,
        video_url,
        saved_path,
        cost_metadata["cost_usd"],
        cost_metadata["cost_is_estimated"],
        cost_metadata["cost_source"],
        raw,
        {
            "cost_reason": cost_metadata["cost_reason"],
            "cost_details": cost_metadata["cost_details"],
            **dict(extra or {}),
        },
    )


def finalize_or_submit(
    *,
    model: str,
    payload: Mapping[str, Any],
    output_path: str | None,
    sync: bool,
    timeout_seconds: float | None,
    poll_interval_seconds: float | None,
) -> dict[str, Any]:
    raw = create_job(payload, timeout_seconds=timeout_seconds)
    video_id = request_id(raw)
    if not video_id:
        raise RuntimeError("OpenRouter video submission did not return a job id.")
    refs = async_refs(raw, video_id)
    if not sync:
        return build_result(
            model=model,
            status="submitted",
            request_id_value=video_id,
            video_url=None,
            output_path=output_path,
            raw=raw,
            cost_metadata=cost_from_job(raw, model),
            extra=refs,
        )
    final = wait_for_job(
        video_id,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        status_url=refs.get("status_url"),
        result_url=refs.get("result_url"),
        poll_url=refs.get("poll_url"),
    )
    video_url = extract_video_url(final, job_id=video_id)
    if not video_url:
        raise RuntimeError(
            f"OpenRouter video job {video_id} completed without a downloadable video URL."
        )
    refs = merge_async_refs(refs, final, **async_refs(final, video_id))
    return build_result(
        model=model,
        status="completed",
        request_id_value=video_id,
        video_url=video_url,
        output_path=output_path,
        raw={"submission": raw, "result": final},
        cost_metadata=cost_from_job(final, model),
        extra=refs,
    )


def media(path: str | None, url: str | None, path_name: str, url_name: str) -> str | None:
    return media_reference(path, url, path_name, url_name)


def selected_model(kwargs: Mapping[str, Any], default: str = DEFAULT_MODEL) -> str:
    value = kwargs.get("model", default)
    return str(value or default)


def status_payload(request_id_value: str, raw: Mapping[str, Any], model: str, refs: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "provider": PROVIDER,
        "model": model,
        "request_id": request_id_value,
        "status": normalize_status(raw.get("status")),
        "raw_response": raw,
        **dict(refs),
    }


def get_generation_status(request_id_value: str, **kwargs: Any) -> dict[str, Any]:
    model = selected_model(kwargs)
    refs = merge_async_refs(None, kwargs, **async_refs({}, request_id_value))
    raw = get_job(
        request_id_value,
        timeout_seconds=kwargs.get("timeout_seconds"),
        status_url=refs.get("status_url"),
        result_url=refs.get("result_url"),
        poll_url=refs.get("poll_url"),
    )
    refs = merge_async_refs(refs, raw, **async_refs(raw, request_id_value))
    return status_payload(request_id_value, raw, model, refs)


def get_generation_result(request_id_value: str, output_path: str | None = None, **kwargs: Any) -> dict[str, Any]:
    model = selected_model(kwargs)
    refs = merge_async_refs(None, kwargs, **async_refs({}, request_id_value))
    raw = get_job(
        request_id_value,
        timeout_seconds=kwargs.get("timeout_seconds"),
        status_url=refs.get("status_url"),
        result_url=refs.get("result_url"),
        poll_url=refs.get("poll_url"),
    )
    status = normalize_status(raw.get("status"))
    if status in {"failed", "canceled"}:
        raise RuntimeError(
            f"OpenRouter video job {request_id_value} ended with status "
            f"{raw.get('status')}: {_job_error_message(raw)}"
        )
    refs = merge_async_refs(refs, raw, **async_refs(raw, request_id_value))
    video_url = extract_video_url(raw, job_id=request_id_value) if status == "completed" else None
    return build_result(
        model=model,
        status=status,
        request_id_value=request_id_value,
        video_url=video_url,
        output_path=output_path,
        raw=raw,
        cost_metadata=cost_from_job(raw, model),
        extra=refs,
    )


def download_generation(
    request_id_value: str | None = None,
    video_url: str | None = None,
    output_path: str | None = None,
    **kwargs: Any,
) -> Any:
    target = normalize_output_path(output_path)
    if video_url:
        return download_file(
            video_url,
            target,
            headers=download_headers_for_url(video_url),
        )
    if not request_id_value:
        raise ValueError("request_id or video_url is required.")
    return get_generation_result(request_id_value, output_path=output_path, **kwargs)


__all__ = [
    "DEFAULT_MODEL",
    "ENV_NAME",
    "PROVIDER",
    "async_refs",
    "build_generation_payload",
    "build_result",
    "create_job",
    "download_generation",
    "extract_video_url",
    "finalize_or_submit",
    "get_generation_result",
    "get_generation_status",
    "get_job",
    "media",
    "normalize_status",
    "request_id",
    "selected_model",
]
