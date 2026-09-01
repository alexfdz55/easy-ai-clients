"""Shared BytePlus ModelArk helpers for Seedance 2.x video generation."""

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
from ._shared import (
    extract_video_url as generic_extract_video_url,
)

PROVIDER = "byteplus"
ENV_NAME = "ARK_API_KEY"
BASE_URL_ENV = "ARK_BASE_URL"
DEFAULT_BASE_URL = "https://ark.ap-southeast.bytepluses.com/api/v3"
DEFAULT_MODEL = "dreamina-seedance-2-5-260628"

MODEL_2_5 = "dreamina-seedance-2-5-260628"
MODEL_2_0 = "dreamina-seedance-2-0-260128"
MODEL_2_0_FAST = "dreamina-seedance-2-0-fast-260128"
MODEL_2_0_MINI = "dreamina-seedance-2-0-mini-260615"

DOCUMENTED_MODELS: dict[str, dict[str, Any]] = {
    MODEL_2_5: {
        "family": "2.5",
        "duration_min": 4,
        "duration_max": 30,
        "resolutions": ("480p", "720p", "1080p"),
        "default_resolution": "720p",
    },
    MODEL_2_0: {
        "family": "2.0",
        "duration_min": 4,
        "duration_max": 15,
        "resolutions": ("480p", "720p", "1080p", "4k"),
        "default_resolution": "720p",
    },
    MODEL_2_0_FAST: {
        "family": "2.0-fast",
        "duration_min": 4,
        "duration_max": 15,
        "resolutions": ("480p", "720p"),
        "default_resolution": "720p",
    },
    MODEL_2_0_MINI: {
        "family": "2.0-mini",
        "duration_min": 4,
        "duration_max": 15,
        "resolutions": ("480p", "720p"),
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
    "task_type",
    "extend",
    "omni_reference_task_type",
    "duration",
    "duration_seconds",
    "resolution",
    "ratio",
    "aspect_ratio",
    "generate_audio",
    "image_path",
    "image_url",
    "video_path",
    "video_url",
    "reference_path",
    "reference_url",
}

NATIVE_OPTIONAL = (
    "watermark",
    "seed",
    "camera_fixed",
    "return_last_frame",
    "output_format",
    "draft",
    "service_tier",
    "callback_url",
    "execution_expires_after",
    "priority",
    "safety_identifier",
    "frames",
)


def base_url() -> str:
    return str(os.getenv(BASE_URL_ENV) or DEFAULT_BASE_URL).rstrip("/")


def headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept-Encoding": "identity",
    }


def tasks_url() -> str:
    return f"{base_url()}/contents/generations/tasks"


def task_endpoint_url(task_id: str) -> str:
    return f"{tasks_url()}/{urllib.parse.quote(str(task_id), safe='')}"


def create_task(payload: Mapping[str, Any], *, timeout_seconds: float | None = None) -> dict[str, Any]:
    api_key = require_env(ENV_NAME, "BytePlus ModelArk")
    return http_json(
        "POST",
        tasks_url(),
        headers=headers(api_key),
        payload=dict(payload),
        timeout_seconds=timeout_seconds,
    )


def get_task(
    task_id: str,
    *,
    timeout_seconds: float | None = None,
    status_url: str | None = None,
    result_url: str | None = None,
    task_url: str | None = None,
    poll_url: str | None = None,
) -> dict[str, Any]:
    api_key = require_env(ENV_NAME, "BytePlus ModelArk")
    url = (
        safe_provider_url(status_url)
        or safe_provider_url(result_url)
        or safe_provider_url(task_url)
        or safe_provider_url(poll_url)
        or task_endpoint_url(task_id)
    )
    return http_json(
        "GET",
        url,
        headers=headers(api_key),
        timeout_seconds=timeout_seconds,
    )


def async_refs(raw: Mapping[str, Any] | None, task_id: str | None) -> dict[str, Any]:
    refs = merge_async_refs(None, raw or {})
    if task_id and not any(
        refs.get(key) for key in ("status_url", "poll_url", "task_url", "result_url")
    ):
        return merge_async_refs(refs, task_url=task_endpoint_url(task_id))
    return refs


def normalize_status(value: Any) -> str:
    status = str(value or "").strip().lower()
    if status in {"succeeded", "success", "completed", "complete"}:
        return "completed"
    if status in {"running", "processing", "in_progress"}:
        return "running"
    if status in {"queued", "pending", "submitted"}:
        return "queued"
    if status in {"failed", "error", "expired"}:
        return "failed"
    if status in {"cancelled", "canceled"}:
        return "canceled"
    return "submitted"


def request_id(raw: Mapping[str, Any]) -> str | None:
    for key in ("id", "task_id", "request_id"):
        if raw.get(key):
            return str(raw[key])
    data = raw.get("data")
    if isinstance(data, Mapping):
        return request_id(data)
    return None


def extract_video_url(response: Mapping[str, Any] | None) -> str | None:
    if not isinstance(response, dict):
        return None
    for candidate in (
        response,
        response.get("result"),
        response.get("data"),
        response.get("submission"),
    ):
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content")
        if isinstance(content, dict) and content.get("video_url"):
            return str(content["video_url"])
        if candidate.get("video_url"):
            return str(candidate["video_url"])
        nested = generic_extract_video_url(candidate)
        if nested:
            return nested
    return None


def _task_error_message(raw: Mapping[str, Any]) -> str:
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


def wait_for_task(
    task_id: str,
    *,
    timeout_seconds: float | None = None,
    poll_interval_seconds: float | None = None,
    status_url: str | None = None,
    result_url: str | None = None,
    task_url: str | None = None,
    poll_url: str | None = None,
) -> dict[str, Any]:
    deadline = time.monotonic() + float(timeout_seconds or 900)
    interval = float(poll_interval_seconds or 10)
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last = get_task(
            task_id,
            timeout_seconds=60,
            status_url=status_url,
            result_url=result_url,
            task_url=task_url,
            poll_url=poll_url,
        )
        status = normalize_status(last.get("status"))
        if status == "completed":
            return last
        if status in {"failed", "canceled"}:
            raise RuntimeError(
                f"BytePlus ModelArk task {task_id} ended with status "
                f"{last.get('status')}: {_task_error_message(last)}"
            )
        time.sleep(max(1, interval))
    raise TimeoutError(f"BytePlus ModelArk task {task_id} timed out. Last status: {last}")


def cost(model: str, kwargs: Mapping[str, Any] | None = None) -> dict[str, Any]:
    del kwargs
    return {
        "cost_usd": 0.0,
        "cost_is_estimated": False,
        "cost_source": "unavailable",
        "cost_details": {"model": model},
        "cost_reason": (
            "BytePlus ModelArk Seedance billing is token-based and is not exposed "
            "as a stable USD amount on the video task response."
        ),
    }


def _normalize_resolution(value: Any) -> str:
    text = str(value or "").strip()
    if text.upper() == "4K":
        return "4k"
    return text.lower() if text.lower().endswith("p") or text.lower() == "4k" else text


def _validate_duration(model: str, duration: int) -> None:
    meta = DOCUMENTED_MODELS.get(model)
    if meta is None or duration == -1:
        return
    minimum = int(meta["duration_min"])
    maximum = int(meta["duration_max"])
    if duration < minimum or duration > maximum:
        raise ValueError(
            f"BytePlus Seedance model `{model}` duration must be -1 or {minimum}-{maximum} "
            f"seconds; got {duration}."
        )


def _validate_resolution(model: str, resolution: str) -> None:
    meta = DOCUMENTED_MODELS.get(model)
    if meta is None:
        return
    allowed = meta["resolutions"]
    if resolution not in allowed:
        raise ValueError(
            f"BytePlus Seedance model `{model}` does not support resolution `{resolution}`. "
            f"Documented resolutions: {', '.join(allowed)}."
        )


def _media_item(kind: str, url: str, role: str | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"type": kind, kind: {"url": url}}
    if role:
        item["role"] = role
    return item


def _ref_url_and_role(item: Any, default_role: str, nested_key: str) -> tuple[str, str | None]:
    if isinstance(item, str):
        value = item.strip()
        if not value:
            raise ValueError("Reference media URL cannot be empty.")
        return value, default_role
    if not isinstance(item, Mapping):
        raise ValueError("Reference media items must be URL strings or dictionaries.")
    nested = item.get(nested_key)
    if isinstance(nested, Mapping):
        url = nested.get("url")
    else:
        url = item.get("url") or nested
    if not url:
        raise ValueError(f"Reference {nested_key} item is missing a url.")
    role = item.get("role", default_role)
    return str(url), str(role) if role else default_role


def _ref_items(value: Any, kind: str, default_role: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    items = value if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) else [value]
    result = []
    for item in items:
        url, role = _ref_url_and_role(item, default_role, kind)
        result.append(_media_item(kind, url, role))
    return result


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


def _task_type(mode: str, kwargs: Mapping[str, Any]) -> str | None:
    explicit = kwargs.get("omni_reference_task_type") or kwargs.get("task_type")
    if explicit:
        return str(explicit).strip()
    if mode != "video_to_video":
        return None
    if kwargs.get("extend") is True:
        return "extend"
    return "edit"


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
    source_video: str | None = None,
    extra_image: str | None = None,
) -> dict[str, Any]:
    content: list[dict[str, Any]] = []
    prompt_text = _content_prompt(prompt, required=mode != "video_to_video")
    if prompt_text:
        content.append({"type": "text", "text": prompt_text})

    if mode == "image_to_video":
        if not first_image:
            raise ValueError("BytePlus image_to_video requires image_path or image_url.")
        content.append(_media_item("image_url", first_image, "first_frame"))
        last_image = _scalar_media(
            kwargs.get("end_image_url")
            or kwargs.get("last_image_url")
            or kwargs.get("last_frame")
        )
        if last_image:
            content.append(_media_item("image_url", last_image, "last_frame"))

    if mode == "video_to_video":
        if not source_video:
            raise ValueError("BytePlus video_to_video requires video_path or video_url.")
        content.append(_media_item("video_url", source_video, "reference_video"))
        if extra_image:
            content.append(_media_item("image_url", extra_image, "reference_image"))

    content.extend(_ref_items(kwargs.get("image_urls"), "image_url", "reference_image"))
    content.extend(_ref_items(kwargs.get("video_urls"), "video_url", "reference_video"))
    content.extend(_ref_items(kwargs.get("audio_urls"), "audio_url", "reference_audio"))

    payload: dict[str, Any] = {"model": model, "content": content}
    if kwargs.get("generate_audio") is None:
        payload["generate_audio"] = True
    else:
        payload["generate_audio"] = bool(kwargs.get("generate_audio"))

    task_type = _task_type(mode, kwargs)
    if task_type:
        payload["omni_reference_task_type"] = task_type

    duration = kwargs.get("duration", kwargs.get("duration_seconds"))
    if duration is None and task_type == "edit":
        duration = -1
    if duration is not None:
        duration_value = int(duration)
        _validate_duration(model, duration_value)
        payload["duration"] = duration_value

    if kwargs.get("resolution") is not None:
        resolution = _normalize_resolution(kwargs.get("resolution"))
        _validate_resolution(model, resolution)
        payload["resolution"] = resolution

    ratio = kwargs.get("ratio", kwargs.get("aspect_ratio"))
    family = (DOCUMENTED_MODELS.get(model) or {}).get("family")
    if ratio is None and mode in {"image_to_video", "video_to_video"} and family == "2.5":
        ratio = "adaptive"
    if ratio is not None:
        payload["ratio"] = str(ratio)

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
) -> dict[str, Any]:
    saved_path = normalize_output_path(output_path)
    if video_url and saved_path and status == "completed":
        saved_path = download_file(video_url, saved_path)
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
    cost_metadata = cost(model, payload)
    raw = create_task(payload, timeout_seconds=timeout_seconds)
    video_id = request_id(raw)
    if not video_id:
        raise RuntimeError("BytePlus ModelArk submission did not return a task id.")
    refs = async_refs(raw, video_id)
    if not sync:
        return build_result(
            model=model,
            status="submitted",
            request_id_value=video_id,
            video_url=None,
            output_path=output_path,
            raw=raw,
            cost_metadata=cost_metadata,
            extra=refs,
        )
    final = wait_for_task(
        video_id,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        status_url=refs.get("status_url"),
        result_url=refs.get("result_url"),
        task_url=refs.get("task_url"),
        poll_url=refs.get("poll_url"),
    )
    video_url = extract_video_url(final)
    if not video_url:
        raise RuntimeError(
            f"BytePlus ModelArk task {video_id} completed without a downloadable video_url."
        )
    refs = merge_async_refs(refs, final)
    return build_result(
        model=model,
        status="completed",
        request_id_value=video_id,
        video_url=video_url,
        output_path=output_path,
        raw={"submission": raw, "result": final},
        cost_metadata=cost_metadata,
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
    raw = get_task(
        request_id_value,
        timeout_seconds=kwargs.get("timeout_seconds"),
        status_url=refs.get("status_url"),
        result_url=refs.get("result_url"),
        task_url=refs.get("task_url"),
        poll_url=refs.get("poll_url"),
    )
    refs = merge_async_refs(refs, raw)
    return status_payload(request_id_value, raw, model, refs)


def get_generation_result(request_id_value: str, output_path: str | None = None, **kwargs: Any) -> dict[str, Any]:
    model = selected_model(kwargs)
    refs = merge_async_refs(None, kwargs, **async_refs({}, request_id_value))
    raw = get_task(
        request_id_value,
        timeout_seconds=kwargs.get("timeout_seconds"),
        status_url=refs.get("status_url"),
        result_url=refs.get("result_url"),
        task_url=refs.get("task_url"),
        poll_url=refs.get("poll_url"),
    )
    status = normalize_status(raw.get("status"))
    if status in {"failed", "canceled"}:
        raise RuntimeError(
            f"BytePlus ModelArk task {request_id_value} ended with status "
            f"{raw.get('status')}: {_task_error_message(raw)}"
        )
    refs = merge_async_refs(refs, raw)
    video_url = extract_video_url(raw) if status == "completed" else None
    return build_result(
        model=model,
        status=status,
        request_id_value=request_id_value,
        video_url=video_url,
        output_path=output_path,
        raw=raw,
        cost_metadata=cost(model, kwargs),
        extra=refs,
    )


def download_generation(
    request_id_value: str | None = None,
    video_url: str | None = None,
    output_path: str | None = None,
    **kwargs: Any,
) -> Any:
    if video_url:
        return download_file(video_url, normalize_output_path(output_path))
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
    "create_task",
    "download_generation",
    "extract_video_url",
    "finalize_or_submit",
    "get_generation_result",
    "get_generation_status",
    "get_task",
    "media",
    "normalize_status",
    "request_id",
    "selected_model",
]
