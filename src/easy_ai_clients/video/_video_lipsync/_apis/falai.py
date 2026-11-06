"""fal.ai video lip-sync wrapper."""

from ..._shared import (
    extract_video_url,
    fal_async_refs,
    fal_get_result,
    fal_get_status,
    fal_submission_receipt,
    fal_submit,
    fal_wait_for_result,
    merge_async_refs,
    normalize_fal_status,
    require_env,
    validate_allowed_kwargs,
    validate_enum,
    validate_number,
)
from ..post_processing import build_result
from ..pre_processing import prepare_video_lipsync

PROVIDER = "falai"
ENV_NAME = "FAL_KEY"
DEFAULT_MODEL = "fal-ai/infinitalk/video-to-video"
COST_SOURCE = "fal_model_pricing_seconds_snapshot_2026-05-13"

DOCUMENTED_MODEL_OPTIONS = {
    DEFAULT_MODEL: {
        "prompt",
        "num_frames",
        "resolution",
        "seed",
        "acceleration",
        "duration_seconds",
        "billing_duration_seconds",
    },
}

COMMON_OPTIONS = {
    "model",
    "timeout_seconds",
    "poll_interval_seconds",
    "extra_payload",
    "webhook_url",
    "on_submitted",
    "submission",
}


def _selected_model(kwargs):
    return kwargs.get("model", DEFAULT_MODEL)


def _build_payload(model, prepared, kwargs):
    documented_options = DOCUMENTED_MODEL_OPTIONS.get(model, set())
    validate_allowed_kwargs(kwargs, documented_options, model, PROVIDER, "video_lipsync", COMMON_OPTIONS)
    validate_enum("resolution", kwargs.get("resolution"), ["480p", "720p"], PROVIDER, model)
    validate_enum("acceleration", kwargs.get("acceleration"), ["none", "regular", "high"], PROVIDER, model)
    validate_number("num_frames", kwargs.get("num_frames"), 41, 241, PROVIDER, model)
    validate_number("seed", kwargs.get("seed"), 0, 4294967295, PROVIDER, model)
    payload = {
        "video_url": prepared["video"],
        "audio_url": prepared["audio"],
        "prompt": kwargs.get("prompt", "A person speaking naturally in sync with the provided audio."),
    }
    for name in ("num_frames", "resolution", "seed", "acceleration"):
        if name in kwargs and kwargs[name] is not None:
            payload[name] = kwargs[name]
    for name, value in kwargs.items():
        if name not in COMMON_OPTIONS and name not in payload and value is not None:
            payload[name] = value
    if "extra_payload" in kwargs:
        from ..._shared import merge_extra_payload

        payload = merge_extra_payload(payload, kwargs)
    return payload


def _cost(model, kwargs):
    if model not in DOCUMENTED_MODEL_OPTIONS:
        return {
            "cost_usd": 0.0,
            "cost_is_estimated": True,
            "cost_source": "unavailable",
            "cost_reason": f"No documented pricing metadata is available for fal.ai model `{model}`.",
        }
    if kwargs.get("billing_duration_seconds") is not None:
        duration_seconds = float(kwargs.get("billing_duration_seconds"))
    elif kwargs.get("duration_seconds") is not None:
        duration_seconds = float(kwargs.get("duration_seconds"))
    else:
        frames = float(kwargs.get("num_frames", 145))
        duration_seconds = frames / 25.0
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be greater than zero for fal.ai video lip-sync cost calculation.")
    return {
        "cost_usd": duration_seconds * 0.3,
        "cost_is_estimated": True,
        "cost_source": COST_SOURCE,
        "cost_reason": "fal.ai InfiniteTalk pricing is documented per generated second; wrapper estimates duration from explicit duration fields or num_frames.",
    }


def _request_id(submission):
    request_id = submission.get("request_id") or submission.get("requestId")
    if not request_id:
        raise RuntimeError("fal.ai submission did not return a request_id.")
    return request_id


def generate_video_lipsync(video_path=None, video_url=None, audio_path=None, audio_url=None, text=None, output_path=None, sync=True, **kwargs):
    if text is not None:
        raise ValueError("fal.ai InfiniteTalk video lip-sync requires audio_path or audio_url; text-to-speech is not exposed by this wrapper.")
    model = _selected_model(kwargs)
    prepared = prepare_video_lipsync(video_path, video_url, audio_path, audio_url, text, output_path)
    payload = _build_payload(model, prepared, kwargs)
    cost = _cost(model, kwargs)
    api_key = require_env(ENV_NAME, "fal.ai")
    submission = fal_submission_receipt(
        model,
        payload,
        api_key,
        timeout_seconds=kwargs.get("timeout_seconds"),
        webhook_url=kwargs.get("webhook_url"),
        on_submitted=kwargs.get("on_submitted"),
        submission=kwargs.get("submission"),
        submit_fn=fal_submit,
    )
    request_id = _request_id(submission)
    async_refs = fal_async_refs(submission, model, request_id)

    if not sync:
        extra = {**async_refs, "cost_reason": cost["cost_reason"]}
        return build_result(PROVIDER, model, "submitted", request_id, None, prepared["output_path"], cost["cost_usd"], cost["cost_is_estimated"], cost["cost_source"], submission, extra)

    raw = fal_wait_for_result(
        model,
        request_id,
        api_key,
        timeout_seconds=kwargs.get("timeout_seconds"),
        poll_interval_seconds=kwargs.get("poll_interval_seconds"),
        status_url=async_refs.get("status_url"),
        poll_url=async_refs.get("poll_url"),
        response_url=async_refs.get("response_url"),
    )
    response = raw.get("response") or {}
    video_url_value = extract_video_url(response)
    if not video_url_value:
        raise RuntimeError(f"fal.ai video lip-sync result for {request_id} did not include a video URL.")
    extra = {**async_refs, "cost_reason": cost["cost_reason"]}
    raw_response = {"submission": submission, "status": raw.get("status") or {}, "response": response}
    return build_result(PROVIDER, model, "completed", request_id, video_url_value, prepared["output_path"], cost["cost_usd"], cost["cost_is_estimated"], cost["cost_source"], raw_response, extra)


def get_generation_status(request_id, **kwargs):
    model = kwargs.get("model", DEFAULT_MODEL)
    api_key = require_env(ENV_NAME, "fal.ai")
    refs = merge_async_refs(None, kwargs, **fal_async_refs({}, model, request_id))
    raw = fal_get_status(
        model,
        request_id,
        api_key,
        timeout_seconds=kwargs.get("timeout_seconds"),
        status_url=refs.get("status_url"),
        poll_url=refs.get("poll_url"),
    )
    return {"provider": PROVIDER, "model": model, "request_id": request_id, "status": normalize_fal_status(raw.get("status")), "raw_response": raw, **refs}


def get_generation_result(request_id, output_path=None, **kwargs):
    model = kwargs.get("model", DEFAULT_MODEL)
    cost = _cost(model, kwargs)
    api_key = require_env(ENV_NAME, "fal.ai")
    refs = merge_async_refs(None, kwargs, **fal_async_refs({}, model, request_id))
    raw = fal_get_result(
        model,
        request_id,
        api_key,
        timeout_seconds=kwargs.get("timeout_seconds"),
        response_url=refs.get("response_url"),
        result_url=refs.get("result_url"),
    )
    video_url_value = extract_video_url(raw)
    if not video_url_value:
        raise RuntimeError(f"fal.ai video lip-sync result for {request_id} did not include a video URL.")
    from ..._shared import normalize_output_path

    extra = {**refs, "cost_reason": cost["cost_reason"]}
    return build_result(PROVIDER, model, "completed", request_id, video_url_value, normalize_output_path(output_path), cost["cost_usd"], cost["cost_is_estimated"], cost["cost_source"], raw, extra)


def download_generation(request_id=None, video_url=None, output_path=None, **kwargs):
    if video_url:
        from ..._shared import download_file, normalize_output_path

        return download_file(video_url, normalize_output_path(output_path))
    if not request_id:
        raise ValueError("request_id or video_url is required.")
    return get_generation_result(request_id, output_path=output_path, **kwargs)
