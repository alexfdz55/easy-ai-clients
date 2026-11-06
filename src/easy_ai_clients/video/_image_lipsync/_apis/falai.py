"""fal.ai image lip-sync wrapper."""

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
from ..pre_processing import prepare_image_lipsync

PROVIDER = "falai"
ENV_NAME = "FAL_KEY"
DEFAULT_MODEL = "fal-ai/longcat-single-avatar/image-audio-to-video"
COST_SOURCE = "fal_model_pricing_units_snapshot_2026-05-13"

DOCUMENTED_MODEL_OPTIONS = {
    DEFAULT_MODEL: {
        "prompt",
        "negative_prompt",
        "num_inference_steps",
        "text_guidance_scale",
        "audio_guidance_scale",
        "resolution",
        "num_segments",
        "seed",
        "enable_safety_checker",
        "enable_prompt_expansion",
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
    validate_allowed_kwargs(kwargs, documented_options, model, PROVIDER, "image_lipsync", COMMON_OPTIONS)
    validate_enum("resolution", kwargs.get("resolution", "480p"), ["480p", "720p"], PROVIDER, model)
    validate_number("num_segments", kwargs.get("num_segments", 1), 1, 10, PROVIDER, model)
    validate_number("num_inference_steps", kwargs.get("num_inference_steps"), 10, 100, PROVIDER, model)
    validate_number("text_guidance_scale", kwargs.get("text_guidance_scale"), 1, 10, PROVIDER, model)
    validate_number("audio_guidance_scale", kwargs.get("audio_guidance_scale"), 1, 10, PROVIDER, model)
    payload = {
        "image_url": prepared["image"],
        "audio_url": prepared["audio"],
        "resolution": kwargs.get("resolution", "480p"),
    }
    for name in documented_options:
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
            "cost_credits": 0.0,
            "credit_source": "unavailable",
            "cost_reason": f"No documented pricing metadata is available for fal.ai model `{model}`.",
        }
    resolution = kwargs.get("resolution", "480p")
    segments = int(kwargs.get("num_segments", 1))
    billed_seconds = 5.8 + max(0, segments - 1) * 5
    units_per_second = 4 if resolution == "720p" else 1
    units = billed_seconds * units_per_second
    cost_usd = units * 0.15
    return {
        "cost_usd": cost_usd,
        "cost_is_estimated": True,
        "cost_source": COST_SOURCE,
        "cost_credits": units,
        "credit_source": "fal.ai LongCat billing units",
        "cost_reason": "fal.ai LongCat pricing is documented by resolution-weighted generated seconds; duration is estimated from num_segments.",
    }


def _request_id(submission):
    request_id = submission.get("request_id") or submission.get("requestId")
    if not request_id:
        raise RuntimeError("fal.ai submission did not return a request_id.")
    return request_id


def generate_image_lipsync(image_path=None, image_url=None, audio_path=None, audio_url=None, text=None, output_path=None, sync=True, **kwargs):
    if text is not None:
        raise ValueError("fal.ai LongCat image lip-sync requires audio_path or audio_url; text-to-speech is not exposed by this wrapper.")
    model = _selected_model(kwargs)
    prepared = prepare_image_lipsync(image_path, image_url, audio_path, audio_url, text, output_path)
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
        extra = {
            **async_refs,
            "cost_reason": cost["cost_reason"],
            "cost_credits": cost["cost_credits"],
            "credit_source": cost["credit_source"],
        }
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
    video_url = extract_video_url(response)
    if not video_url:
        raise RuntimeError(f"fal.ai image lip-sync result for {request_id} did not include a video URL.")
    extra = {**async_refs, "cost_reason": cost["cost_reason"], "cost_credits": cost["cost_credits"], "credit_source": cost["credit_source"]}
    raw_response = {"submission": submission, "status": raw.get("status") or {}, "response": response}
    return build_result(PROVIDER, model, "completed", request_id, video_url, prepared["output_path"], cost["cost_usd"], cost["cost_is_estimated"], cost["cost_source"], raw_response, extra)


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
    video_url = extract_video_url(raw)
    if not video_url:
        raise RuntimeError(f"fal.ai image lip-sync result for {request_id} did not include a video URL.")
    from ..._shared import normalize_output_path

    extra = {**refs, "cost_reason": cost["cost_reason"], "cost_credits": cost["cost_credits"], "credit_source": cost["credit_source"]}
    return build_result(PROVIDER, model, "completed", request_id, video_url, normalize_output_path(output_path), cost["cost_usd"], cost["cost_is_estimated"], cost["cost_source"], raw, extra)


def download_generation(request_id=None, video_url=None, output_path=None, **kwargs):
    if video_url:
        from ..._shared import download_file, normalize_output_path

        return download_file(video_url, normalize_output_path(output_path))
    if not request_id:
        raise ValueError("request_id or video_url is required.")
    return get_generation_result(request_id, output_path=output_path, **kwargs)
