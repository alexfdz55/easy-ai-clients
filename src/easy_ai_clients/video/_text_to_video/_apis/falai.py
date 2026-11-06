"""fal.ai text-to-video wrapper."""

import math

from ..._falai_pricing import FAL_ESTIMATE_OPTIONS, fal_pricing_estimate
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
from ..pre_processing import prepare_text_to_video

PROVIDER = "falai"
ENV_NAME = "FAL_KEY"
DEFAULT_MODEL = "fal-ai/wan/v2.2-5b/text-to-video/distill"
COST_SOURCE = "fal_model_pricing_snapshot_2026-05-14"

DOCUMENTED_MODEL_PRICING = {
    "fal-ai/ltx-2-19b/distilled/text-to-video": {"price_usd": 0.0008, "unit": "megapixels"},
    "fal-ai/ltx-2-19b/distilled/text-to-video/lora": {"price_usd": 0.001, "unit": "megapixels"},
    "fal-ai/ltx-2.3-22b/distilled/text-to-video": {"price_usd": 0.001205, "unit": "megapixels"},
    "fal-ai/animatediff-sparsectrl-lcm": {"price_usd": 0.00125, "unit": "compute_seconds"},
    "fal-ai/fast-animatediff/text-to-video": {"price_usd": 0.00125, "unit": "compute_seconds"},
    "fal-ai/kandinsky5/text-to-video": {"price_usd": 0.08, "unit": "video"},
    DEFAULT_MODEL: {"price_usd": 0.08, "unit": "video"},
    "fal-ai/minimax/hailuo-02/pro/text-to-video": {"price_usd": 0.08, "unit": "seconds"},
    "fal-ai/wan/v2.2-a14b/text-to-video": {"price_usd": 0.08, "unit": "seconds"},
    "fal-ai/kling-video/v2.6/pro/text-to-video": {"price_usd": 0.07, "unit": "seconds"},
    "fal-ai/veo3.1": {"price_usd": 0.4, "unit": "seconds"},
    "fal-ai/bytedance/seedance/v1/pro/fast/text-to-video": {"price_usd": 1.0, "unit": "1m_tokens"},
    "fal-ai/bytedance/seedance/v1.5/pro/text-to-video": {"price_usd": 1.2, "unit": "1m_tokens"},
    "moonvalley/marey/t2v": {"price_usd": 1.5, "unit": "5_seconds"},
    "fal-ai/bytedance/seedance/v1/pro/text-to-video": {"price_usd": 2.5, "unit": "1m_tokens"},
}

COMMON_FAL_VIDEO_OPTIONS = {
    "negative_prompt",
    "num_frames",
    "frames_per_second",
    "seed",
    "resolution",
    "aspect_ratio",
    "duration",
    "duration_seconds",
    "billing_duration_seconds",
    "num_videos",
    "number_of_videos",
    "compute_seconds",
    "billing_compute_seconds",
    "megapixels",
    "billing_megapixels",
    "tokens",
    "billing_tokens",
    "billing_million_tokens",
    "num_inference_steps",
    "enable_safety_checker",
    "enable_output_safety_checker",
    "enable_prompt_expansion",
    "guidance_scale",
    "shift",
    "interpolator_model",
    "num_interpolated_frames",
    "adjust_fps_for_interpolation",
    "video_quality",
    "video_write_mode",
    "video_size",
    "generate_audio",
    "acceleration",
}

DOCUMENTED_MODEL_OPTIONS = {
    model: set(COMMON_FAL_VIDEO_OPTIONS) for model in DOCUMENTED_MODEL_PRICING
}

COMMON_OPTIONS = {
    "model",
    "timeout_seconds",
    "poll_interval_seconds",
    "extra_payload",
    "webhook_url",
    "on_submitted",
    "submission",
    *FAL_ESTIMATE_OPTIONS,
}


def _selected_model(kwargs):
    return kwargs.get("model", DEFAULT_MODEL)


def _build_payload(model, prepared, kwargs):
    documented_options = DOCUMENTED_MODEL_OPTIONS.get(model, set())
    validate_allowed_kwargs(kwargs, documented_options, model, PROVIDER, "text_to_video", COMMON_OPTIONS)
    validate_enum("resolution", kwargs.get("resolution"), ["580p", "720p"], PROVIDER, model)
    validate_enum("aspect_ratio", kwargs.get("aspect_ratio"), ["16:9", "9:16", "1:1"], PROVIDER, model)
    validate_enum("interpolator_model", kwargs.get("interpolator_model"), ["none", "film", "rife"], PROVIDER, model)
    validate_enum("video_quality", kwargs.get("video_quality"), ["low", "medium", "high", "maximum"], PROVIDER, model)
    validate_enum("video_write_mode", kwargs.get("video_write_mode"), ["fast", "balanced", "small"], PROVIDER, model)
    validate_number("num_frames", kwargs.get("num_frames"), 17, 161, PROVIDER, model)
    validate_number("frames_per_second", kwargs.get("frames_per_second"), 4, 60, PROVIDER, model)
    validate_number("seed", kwargs.get("seed"), 0, 4294967295, PROVIDER, model)
    validate_number("num_inference_steps", kwargs.get("num_inference_steps"), 2, 50, PROVIDER, model)
    validate_number("guidance_scale", kwargs.get("guidance_scale"), 1, 10, PROVIDER, model)
    validate_number("shift", kwargs.get("shift"), 1, 10, PROVIDER, model)
    validate_number("num_interpolated_frames", kwargs.get("num_interpolated_frames"), 0, 4, PROVIDER, model)

    payload = {"prompt": prepared["prompt"]}
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


def _quantity_for_unit(unit, kwargs):
    if unit == "video":
        return float(kwargs.get("number_of_videos", kwargs.get("num_videos", 1)))
    if unit == "seconds":
        value = kwargs.get("billing_duration_seconds", kwargs.get("duration_seconds", kwargs.get("duration")))
        return float(value) if value is not None else None
    if unit == "5_seconds":
        value = kwargs.get("billing_duration_seconds", kwargs.get("duration_seconds", kwargs.get("duration")))
        return math.ceil(float(value) / 5.0) if value is not None else None
    if unit == "compute_seconds":
        value = kwargs.get("billing_compute_seconds", kwargs.get("compute_seconds"))
        return float(value) if value is not None else None
    if unit == "megapixels":
        value = kwargs.get("billing_megapixels", kwargs.get("megapixels"))
        return float(value) if value is not None else None
    if unit == "1m_tokens":
        if kwargs.get("billing_million_tokens") is not None:
            return float(kwargs.get("billing_million_tokens"))
        value = kwargs.get("billing_tokens", kwargs.get("tokens"))
        return float(value) / 1_000_000 if value is not None else None
    return None


def _cost(model, kwargs):
    estimate = fal_pricing_estimate(model, kwargs, ENV_NAME)
    if estimate is not None:
        return estimate
    if model not in DOCUMENTED_MODEL_PRICING:
        return {
            "cost_usd": 0.0,
            "cost_is_estimated": True,
            "cost_source": "unavailable",
            "cost_reason": f"No documented pricing metadata is available for fal.ai model `{model}`.",
        }
    pricing = DOCUMENTED_MODEL_PRICING[model]
    quantity = _quantity_for_unit(pricing["unit"], kwargs)
    if quantity is None:
        return {
            "cost_usd": 0.0,
            "cost_is_estimated": True,
            "cost_source": "unavailable",
            "cost_reason": (
                f"fal.ai pricing for `{model}` is documented per {pricing['unit']}, "
                "but this wrapper cannot infer the billable quantity without an explicit billing kwarg."
            ),
        }
    price = pricing["price_usd"] * quantity
    return {
        "cost_usd": price,
        "cost_is_estimated": True,
        "cost_source": COST_SOURCE,
        "cost_reason": f"fal.ai pricing is estimated from documented {pricing['unit']} pricing; usage reconciliation is not performed during safe wrapper execution.",
    }


def _request_id(submission):
    request_id = submission.get("request_id") or submission.get("requestId")
    if not request_id:
        raise RuntimeError("fal.ai submission did not return a request_id.")
    return request_id


def generate_text_to_video(prompt, output_path=None, sync=True, **kwargs):
    model = _selected_model(kwargs)
    prepared = prepare_text_to_video(prompt, output_path)
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
    video_url = extract_video_url(response)
    if not video_url:
        raise RuntimeError(f"fal.ai text-to-video result for {request_id} did not include a video URL.")
    extra = {**async_refs, "cost_reason": cost["cost_reason"]}
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
        raise RuntimeError(f"fal.ai text-to-video result for {request_id} did not include a video URL.")
    prepared_output = prepare_text_to_video("placeholder", output_path)["output_path"]
    extra = {**refs, "cost_reason": cost["cost_reason"]}
    return build_result(PROVIDER, model, "completed", request_id, video_url, prepared_output, cost["cost_usd"], cost["cost_is_estimated"], cost["cost_source"], raw, extra)


def download_generation(request_id=None, video_url=None, output_path=None, **kwargs):
    if video_url:
        from ..._shared import download_file, normalize_output_path

        return download_file(video_url, normalize_output_path(output_path))
    if not request_id:
        raise ValueError("request_id or video_url is required.")
    return get_generation_result(request_id, output_path=output_path, **kwargs)
