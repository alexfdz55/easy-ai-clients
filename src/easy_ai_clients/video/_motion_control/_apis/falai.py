"""fal.ai motion-control wrapper."""

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
)
from ..post_processing import build_result
from ..pre_processing import prepare_motion_control

PROVIDER = "falai"
ENV_NAME = "FAL_KEY"
DEFAULT_MODEL = "fal-ai/kling-video/v2.6/standard/motion-control"
COST_SOURCE = "fal_model_pricing_snapshot_2026-05-14"

DOCUMENTED_MODEL_PRICING = {
    "fal-ai/wan-motion": {"price_usd": 0.00017, "unit": "compute_seconds"},
    "fal-ai/controlnext": {"price_usd": 0.00111, "unit": "compute_seconds"},
    "fal-ai/ltx-2.3-22b/distilled/reference-video-to-video": {"price_usd": 0.001205, "unit": "megapixels"},
    "fal-ai/ltx-2.3-22b/distilled/reference-video-to-video/lora": {"price_usd": 0.001405, "unit": "megapixels"},
    "fal-ai/ltx-2.3-22b/reference-video-to-video": {"price_usd": 0.001605, "unit": "megapixels"},
    DEFAULT_MODEL: {"price_usd": 0.07, "unit": "seconds"},
    "fal-ai/wan/v2.2-14b/animate/move": {"price_usd": 0.08, "unit": "seconds"},
    "fal-ai/wan/v2.2-14b/animate/replace": {"price_usd": 0.08, "unit": "seconds"},
    "fal-ai/kling-video/v2.6/pro/motion-control": {"price_usd": 0.112, "unit": "seconds"},
    "fal-ai/kling-video/o1/standard/video-to-video/reference": {"price_usd": 0.126, "unit": "seconds"},
    "fal-ai/kling-video/o1/video-to-video/reference": {"price_usd": 0.168, "unit": "seconds"},
    "fal-ai/kling-video/v3/pro/motion-control": {"price_usd": 0.168, "unit": "seconds"},
    "fal-ai/wan-move": {"price_usd": 0.2, "unit": "video"},
    "fal-ai/video-as-prompt": {"price_usd": 1.0, "unit": "video"},
    "moonvalley/marey/motion-transfer": {"price_usd": 2.0, "unit": "video"},
}

COMMON_FAL_MOTION_OPTIONS = {
    "character_orientation",
    "keep_original_sound",
    "duration_seconds",
    "billing_duration_seconds",
    "prompt",
    "negative_prompt",
    "seed",
    "resolution",
    "aspect_ratio",
    "num_frames",
    "compute_seconds",
    "billing_compute_seconds",
    "megapixels",
    "billing_megapixels",
    "num_videos",
    "number_of_videos",
    "enhance_identity",
    "billing_unit_quantity",
    "unit_quantity",
}

DOCUMENTED_MODEL_OPTIONS = {
    model: set(COMMON_FAL_MOTION_OPTIONS) for model in DOCUMENTED_MODEL_PRICING
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
    validate_allowed_kwargs(kwargs, documented_options, model, PROVIDER, "motion_control", COMMON_OPTIONS)
    orientation = kwargs.get("character_orientation")
    validate_enum("character_orientation", orientation, ["image", "video"], PROVIDER, model)
    strict_kling_motion = model in {
        DEFAULT_MODEL,
        "fal-ai/kling-video/v2.6/pro/motion-control",
        "fal-ai/kling-video/v3/pro/motion-control",
    }
    if strict_kling_motion and not orientation:
        raise ValueError("fal.ai Kling motion-control requires character_orientation set to image or video.")
    if strict_kling_motion and not prepared["image"]:
        raise ValueError("fal.ai Kling motion-control requires image_path or image_url for the character image.")
    if strict_kling_motion and not prepared["video"]:
        raise ValueError("fal.ai Kling motion-control requires video_path or video_url for the motion reference.")
    payload = {}
    if prepared["image"]:
        payload["image_url"] = prepared["image"]
    if prepared["video"]:
        payload["video_url"] = prepared["video"]
    if prepared["reference"]:
        payload["reference_url"] = prepared["reference"]
    if orientation:
        payload["character_orientation"] = orientation
    if strict_kling_motion or kwargs.get("keep_original_sound") is not None:
        payload["keep_original_sound"] = bool(kwargs.get("keep_original_sound", True))
    if prepared["prompt"]:
        payload["prompt"] = prepared["prompt"]
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
    if unit == "compute_seconds":
        value = kwargs.get("billing_compute_seconds", kwargs.get("compute_seconds"))
        return float(value) if value is not None else None
    if unit == "megapixels":
        value = kwargs.get("billing_megapixels", kwargs.get("megapixels"))
        return float(value) if value is not None else None
    if unit == "5_seconds":
        value = kwargs.get("billing_duration_seconds", kwargs.get("duration_seconds", kwargs.get("duration")))
        return math.ceil(float(value) / 5.0) if value is not None else None
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
    if quantity <= 0:
        raise ValueError("Billable quantity must be greater than zero for fal.ai motion-control cost calculation.")
    return {
        "cost_usd": quantity * pricing["price_usd"],
        "cost_is_estimated": True,
        "cost_source": COST_SOURCE,
        "cost_reason": f"fal.ai pricing is estimated from documented {pricing['unit']} pricing; usage reconciliation is not performed during safe wrapper execution.",
    }


def _request_id(submission):
    request_id = submission.get("request_id") or submission.get("requestId")
    if not request_id:
        raise RuntimeError("fal.ai submission did not return a request_id.")
    return request_id


def generate_motion_control(prompt=None, image_path=None, image_url=None, video_path=None, video_url=None, reference_path=None, reference_url=None, output_path=None, sync=True, **kwargs):
    model = _selected_model(kwargs)
    if model in {DEFAULT_MODEL, "fal-ai/kling-video/v2.6/pro/motion-control", "fal-ai/kling-video/v3/pro/motion-control"} and (reference_path or reference_url):
        raise ValueError("fal.ai Kling motion-control uses video_path or video_url as the motion reference; reference_path and reference_url are not supported.")
    prepared = prepare_motion_control(prompt, image_path, image_url, video_path, video_url, reference_path, reference_url, output_path)
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
        raise RuntimeError(f"fal.ai motion-control result for {request_id} did not include a video URL.")
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
        raise RuntimeError(f"fal.ai motion-control result for {request_id} did not include a video URL.")
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
