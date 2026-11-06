"""HeyGen v3 video translation adapter."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .... import _heygen
from ...._submission_hooks import run_on_submitted
from ..._heygen_common import (
    TRANSLATE_MODEL,
    build_video_result,
    cost_metadata,
    media_union,
    passthrough_payload,
)
from ..._shared import merge_async_refs, safe_provider_url


def _translation_url(video_translation_id):
    return _heygen.api_base_url() + f"/v3/video-translations/{_heygen.quote_path(video_translation_id)}"


def translate_video(video=None, output_languages=None, output_path=None, sync=True, **kwargs: Any):
    submission = kwargs.get("submission")
    if submission is not None:
        if not isinstance(submission, Mapping):
            raise TypeError("submission must be a dictionary when provided.")
        raw = dict(submission)
    else:
        local_kwargs = dict(kwargs)
        languages = output_languages if output_languages is not None else local_kwargs.pop("output_languages", None)
        if isinstance(languages, str):
            languages = [languages]
        callback_url = str(local_kwargs.get("callback_url") or "").strip()
        webhook = str(local_kwargs.get("webhook_url") or "").strip()
        if webhook and not callback_url:
            local_kwargs["callback_url"] = webhook
        payload = passthrough_payload(
            {
                "video": media_union(
                    local_kwargs.pop("video_path", None) or video,
                    local_kwargs.pop("video_url", None),
                    local_kwargs.pop("video_asset_id", None),
                    field_name="video",
                ),
                "output_languages": languages,
            },
            local_kwargs,
        )
        if not payload.get("video"):
            raise ValueError("video is required.")
        if not payload.get("output_languages"):
            raise ValueError("output_languages is required.")
        raw = _heygen.request_json(
            "POST",
            "/v3/video-translations",
            payload=payload,
            timeout_seconds=kwargs.get("timeout_seconds"),
        )
        run_on_submitted(kwargs.get("on_submitted"), raw)
    ids = []
    item = _heygen.data(raw)
    if isinstance(item, dict) and isinstance(item.get("video_translation_ids"), list):
        ids = [str(value) for value in item["video_translation_ids"]]
    request_id = ids[0] if ids else _heygen.response_id(raw, "video_translation_id", "id")
    refs = merge_async_refs(None, raw, task_url=_translation_url(request_id) if request_id else None)
    final_raw = raw
    if sync and request_id:
        final_raw = _heygen.wait_for_result(
            lambda: get_translation(
                request_id,
                timeout_seconds=60,
                status_url=refs.get("status_url"),
                result_url=refs.get("result_url"),
                task_url=refs.get("task_url"),
                poll_url=refs.get("poll_url"),
            ),
            timeout_seconds=kwargs.get("timeout_seconds"),
            poll_interval_seconds=kwargs.get("poll_interval_seconds"),
        )
    raw_response = {"submission": raw, "result": final_raw} if sync and request_id else raw
    return build_video_result(
        model=kwargs.get("model") or TRANSLATE_MODEL,
        raw_response=raw_response,
        request_id=request_id,
        output_path=output_path,
        cost=cost_metadata(kwargs),
        extra={**refs, **({"video_translation_ids": ids} if ids else {})},
    )


def get_translation(video_translation_id, *, timeout_seconds=None, **kwargs):
    explicit_url = (
        safe_provider_url(kwargs.pop("status_url", None))
        or safe_provider_url(kwargs.pop("result_url", None))
        or safe_provider_url(kwargs.pop("task_url", None))
        or safe_provider_url(kwargs.pop("poll_url", None))
    )
    url = explicit_url or _translation_url(video_translation_id)
    raw = _heygen.request_json(
        "GET",
        url,
        params=kwargs,
        timeout_seconds=timeout_seconds,
    )
    raw.update(merge_async_refs(None, raw, task_url=url))
    return raw


def get_generation_status(request_id, **kwargs):
    return get_translation(request_id, **kwargs)


def get_generation_result(request_id, output_path=None, **kwargs):
    raw = get_translation(
        request_id,
        timeout_seconds=kwargs.get("timeout_seconds"),
        status_url=kwargs.get("status_url"),
        result_url=kwargs.get("result_url"),
        task_url=kwargs.get("task_url"),
        poll_url=kwargs.get("poll_url"),
    )
    return build_video_result(
        model=kwargs.get("model") or TRANSLATE_MODEL,
        raw_response=raw,
        request_id=request_id,
        output_path=output_path,
        cost=cost_metadata(kwargs),
    )


def download_generation(request_id=None, video_url=None, output_path=None, **kwargs):
    if video_url:
        from ..._shared import download_file, normalize_output_path

        return download_file(video_url, normalize_output_path(output_path))
    if not request_id:
        raise ValueError("request_id or video_url is required.")
    return get_generation_result(request_id, output_path=output_path, **kwargs)
