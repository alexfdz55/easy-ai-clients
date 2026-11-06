"""Shared HeyGen v3 video helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .. import _heygen
from ._shared import (
    download_file,
    merge_async_refs,
    normalize_output_path,
    normalize_result,
    safe_provider_url,
)

PROVIDER = "heygen"
VIDEO_MODEL = "heygen-v3-video"
AGENT_MODEL = "heygen-v3-video-agent"
AVATAR_MODEL = "heygen-v3-avatar"
LIPSYNC_MODEL = "heygen-v3-lipsync"
TRANSLATE_MODEL = "heygen-v3-video-translation"


def passthrough_payload(base: Mapping[str, Any], kwargs: Mapping[str, Any], exclude: set[str] | None = None) -> dict[str, Any]:
    excluded = set(exclude or set()) | {
        "model",
        "sync",
        "output_path",
        "timeout_seconds",
        "poll_interval_seconds",
        "estimated_cost_usd",
        "billing_cost_usd",
        "extra_payload",
        "webhook_url",
        "on_submitted",
        "submission",
    }
    payload = dict(base)
    for name, value in kwargs.items():
        if name not in excluded and value is not None:
            payload[name] = value
    extra_payload = kwargs.get("extra_payload")
    if isinstance(extra_payload, Mapping):
        payload.update({str(key): value for key, value in extra_payload.items() if value is not None})
    return _heygen.clean_payload(payload)


def cost_metadata(kwargs: Mapping[str, Any]) -> dict[str, Any]:
    value = kwargs.get("billing_cost_usd", kwargs.get("estimated_cost_usd"))
    if value is None:
        return {
            "cost_usd": 0.0,
            "cost_is_estimated": False,
            "cost_source": "unavailable",
        }
    return {
        "cost_usd": float(value),
        "cost_is_estimated": True,
        "cost_source": "caller_estimate",
    }


def video_url(item: Any) -> str | None:
    if not isinstance(item, Mapping):
        return None
    return (
        item.get("video_url")
        or item.get("captioned_video_url")
        or item.get("url")
        or item.get("video_page_url")
    )


def build_video_result(
    *,
    model: str,
    raw_response: Mapping[str, Any],
    request_id: str | None = None,
    output_path: str | None = None,
    cost: Mapping[str, Any] | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    response_for_status = raw_response
    if isinstance(raw_response, Mapping) and isinstance(raw_response.get("result"), Mapping):
        response_for_status = raw_response["result"]
    item = _heygen.data(response_for_status)
    status = _heygen.normalize_status(item.get("status") if isinstance(item, Mapping) else None)
    resolved_id = request_id or _heygen.response_id(
        raw_response,
        "video_id",
        "session_id",
        "lipsync_id",
        "video_translation_id",
        "id",
    )
    resolved_url = video_url(item)
    saved_path = normalize_output_path(output_path)
    if resolved_url and saved_path and status == "completed":
        saved_path = download_file(str(resolved_url), saved_path)
    metadata = dict(cost or {})
    metadata.setdefault("cost_usd", 0.0)
    metadata.setdefault("cost_is_estimated", False)
    metadata.setdefault("cost_source", "unavailable")
    details: dict[str, Any] = merge_async_refs(extra, raw_response)
    if isinstance(item, Mapping):
        for name in (
            "video_id",
            "session_id",
            "lipsync_id",
            "video_translation_id",
            "subtitle_url",
            "caption_url",
            "srt_caption_url",
            "vtt_caption_url",
            "audio_url",
            "thumbnail_url",
            "gif_url",
            "video_page_url",
        ):
            if item.get(name) is not None:
                details[name] = item.get(name)
    return normalize_result(
        PROVIDER,
        model,
        status,
        resolved_id,
        resolved_url,
        saved_path,
        metadata["cost_usd"],
        metadata["cost_is_estimated"],
        metadata["cost_source"],
        dict(raw_response),
        details,
    )


def _video_url(video_id: str) -> str:
    return _heygen.api_base_url() + f"/v3/videos/{_heygen.quote_path(video_id)}"


def _lipsync_url(lipsync_id: str) -> str:
    return _heygen.api_base_url() + f"/v3/lipsyncs/{_heygen.quote_path(lipsync_id)}"


def get_video(
    video_id: str,
    *,
    timeout_seconds: float | None = None,
    status_url: str | None = None,
    result_url: str | None = None,
    task_url: str | None = None,
    poll_url: str | None = None,
    **params: Any,
) -> dict[str, Any]:
    url = (
        safe_provider_url(status_url)
        or safe_provider_url(result_url)
        or safe_provider_url(task_url)
        or safe_provider_url(poll_url)
        or _video_url(video_id)
    )
    raw = _heygen.request_json(
        "GET",
        url,
        params=params,
        timeout_seconds=timeout_seconds,
    )
    raw.update(merge_async_refs(None, raw, task_url=url))
    return raw


def wait_video(
    video_id: str,
    *,
    timeout_seconds: float | None = None,
    poll_interval_seconds: float | None = None,
    status_url: str | None = None,
    result_url: str | None = None,
    task_url: str | None = None,
    poll_url: str | None = None,
) -> dict[str, Any]:
    return _heygen.wait_for_result(
        lambda: get_video(
            video_id,
            timeout_seconds=60,
            status_url=status_url,
            result_url=result_url,
            task_url=task_url,
            poll_url=poll_url,
        ),
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )


def submit_video(payload: Mapping[str, Any], *, output_path: str | None, sync: bool, model: str, kwargs: Mapping[str, Any]) -> dict[str, Any]:
    raw = _heygen.request_json(
        "POST",
        "/v3/videos",
        payload=payload,
        timeout_seconds=kwargs.get("timeout_seconds"),
    )
    video_id = _heygen.response_id(raw, "video_id", "id")
    refs = merge_async_refs(None, raw, task_url=_video_url(video_id) if video_id else None)
    final_raw = wait_video(
        video_id,
        timeout_seconds=kwargs.get("timeout_seconds"),
        poll_interval_seconds=kwargs.get("poll_interval_seconds"),
        status_url=refs.get("status_url"),
        result_url=refs.get("result_url"),
        task_url=refs.get("task_url"),
        poll_url=refs.get("poll_url"),
    ) if sync and video_id else raw
    raw_response = {"submission": raw, "result": final_raw} if sync and video_id else raw
    return build_video_result(
        model=model,
        raw_response=raw_response,
        request_id=video_id,
        output_path=output_path,
        cost=cost_metadata(kwargs),
        extra=refs,
    )


def submit_lipsync(payload: Mapping[str, Any], *, output_path: str | None, sync: bool, kwargs: Mapping[str, Any]) -> dict[str, Any]:
    raw = _heygen.request_json(
        "POST",
        "/v3/lipsyncs",
        payload=payload,
        timeout_seconds=kwargs.get("timeout_seconds"),
    )
    lipsync_id = _heygen.response_id(raw, "lipsync_id", "id")
    refs = merge_async_refs(None, raw, task_url=_lipsync_url(lipsync_id) if lipsync_id else None)
    final_raw = wait_lipsync(
        lipsync_id,
        timeout_seconds=kwargs.get("timeout_seconds"),
        poll_interval_seconds=kwargs.get("poll_interval_seconds"),
        status_url=refs.get("status_url"),
        result_url=refs.get("result_url"),
        task_url=refs.get("task_url"),
        poll_url=refs.get("poll_url"),
    ) if sync and lipsync_id else raw
    raw_response = {"submission": raw, "result": final_raw} if sync and lipsync_id else raw
    return build_video_result(
        model=LIPSYNC_MODEL,
        raw_response=raw_response,
        request_id=lipsync_id,
        output_path=output_path,
        cost=cost_metadata(kwargs),
        extra=refs,
    )


def get_lipsync(
    lipsync_id: str,
    *,
    timeout_seconds: float | None = None,
    status_url: str | None = None,
    result_url: str | None = None,
    task_url: str | None = None,
    poll_url: str | None = None,
    **params: Any,
) -> dict[str, Any]:
    url = (
        safe_provider_url(status_url)
        or safe_provider_url(result_url)
        or safe_provider_url(task_url)
        or safe_provider_url(poll_url)
        or _lipsync_url(lipsync_id)
    )
    raw = _heygen.request_json(
        "GET",
        url,
        params=params,
        timeout_seconds=timeout_seconds,
    )
    raw.update(merge_async_refs(None, raw, task_url=url))
    return raw


def wait_lipsync(
    lipsync_id: str,
    *,
    timeout_seconds: float | None = None,
    poll_interval_seconds: float | None = None,
    status_url: str | None = None,
    result_url: str | None = None,
    task_url: str | None = None,
    poll_url: str | None = None,
) -> dict[str, Any]:
    return _heygen.wait_for_result(
        lambda: get_lipsync(
            lipsync_id,
            timeout_seconds=60,
            status_url=status_url,
            result_url=result_url,
            task_url=task_url,
            poll_url=poll_url,
        ),
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )


def media_union(path: Any = None, url: Any = None, asset_id: Any = None, *, field_name: str, allow_base64: bool = False) -> dict[str, Any]:
    present = [item is not None for item in (path, url, asset_id)].count(True)
    if present > 1:
        raise ValueError(f"Provide only one of {field_name}_path, {field_name}_url, or {field_name}_asset_id.")
    source = asset_id if asset_id is not None else url if url is not None else path
    return _heygen.asset_input(source, field_name=field_name, allow_base64=allow_base64)


def audio_fields(audio_path: Any = None, audio_url: Any = None, audio_asset_id: Any = None, *, timeout_seconds: float | None = None) -> dict[str, Any]:
    return _heygen.media_url_or_asset_fields(
        path=audio_path,
        url=audio_url,
        asset_id=audio_asset_id,
        url_key="audio_url",
        asset_id_key="audio_asset_id",
        timeout_seconds=timeout_seconds,
    )
