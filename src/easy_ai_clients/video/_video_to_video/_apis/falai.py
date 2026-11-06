"""fal.ai video-to-video wrapper."""

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
)
from ..post_processing import build_result
from ..pre_processing import prepare_video_to_video

PROVIDER = "falai"
ENV_NAME = "FAL_KEY"
DEFAULT_MODEL = "wan/v2.6/reference-to-video/flash"
COST_SOURCE = "fal_model_pricing_snapshot_2026-05-14"

DOCUMENTED_MODEL_PRICING = {
    DEFAULT_MODEL: {"price_usd": 0.00007, "unit": "compute_seconds"},
    "fal-ai/ltx-2.3-22b/distilled/reference-video-to-video": {"price_usd": 0.001205, "unit": "megapixels"},
    "fal-ai/ltx-2.3-22b/distilled/reference-video-to-video/lora": {"price_usd": 0.001405, "unit": "megapixels"},
    "fal-ai/ltx-2.3-22b/reference-video-to-video": {"price_usd": 0.001605, "unit": "megapixels"},
    "fal-ai/kling-video/o1/standard/video-to-video/reference": {"price_usd": 0.126, "unit": "seconds"},
    "fal-ai/kling-video/o1/video-to-video/reference": {"price_usd": 0.168, "unit": "seconds"},
    "fal-ai/wan-vace-14b/reframe": {"price_usd": 0.08, "unit": "seconds"},
    "fal-ai/wan-vace-apps/long-reframe": {"price_usd": 0.08, "unit": "seconds"},
    "decart/lucy-edit/pro": {"price_usd": 0.1, "unit": "seconds"},
    "fal-ai/wan-vace": {"price_usd": 0.2, "unit": "video"},
    "fal-ai/infinitalk/video-to-video": {"price_usd": 0.3, "unit": "seconds"},
    "fal-ai/pika/v2/pikadditions": {"price_usd": 0.465, "unit": "video"},
    "fal-ai/video-as-prompt": {"price_usd": 1.0, "unit": "video"},
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
    payload = {"video_url": prepared["video"]}
    if prepared["prompt"]:
        payload["prompt"] = prepared["prompt"]
    if prepared["image"]:
        payload["image_url"] = prepared["image"]
    if prepared["reference"]:
        payload["reference_url"] = prepared["reference"]
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
    return {
        "cost_usd": pricing["price_usd"] * quantity,
        "cost_is_estimated": True,
        "cost_source": COST_SOURCE,
        "cost_reason": f"fal.ai pricing is estimated from documented {pricing['unit']} pricing; usage reconciliation is not performed during safe wrapper execution.",
    }


def _request_id(submission):
    request_id = submission.get("request_id") or submission.get("requestId")
    if not request_id:
        raise RuntimeError("fal.ai submission did not return a request_id.")
    return request_id


def generate_video_to_video(
    prompt=None,
    video_path=None,
    video_url=None,
    image_path=None,
    image_url=None,
    reference_path=None,
    reference_url=None,
    output_path=None,
    sync=True,
    **kwargs,
):
    model = _selected_model(kwargs)
    prepared = prepare_video_to_video(
        prompt,
        video_path,
        video_url,
        image_path,
        image_url,
        reference_path,
        reference_url,
        output_path,
    )
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
        return build_result(
            PROVIDER,
            model,
            "submitted",
            request_id,
            None,
            prepared["output_path"],
            cost["cost_usd"],
            cost["cost_is_estimated"],
            cost["cost_source"],
            submission,
            extra,
        )

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
        raise RuntimeError(f"fal.ai video-to-video result for {request_id} did not include a video URL.")
    extra = {**async_refs, "cost_reason": cost["cost_reason"]}
    raw_response = {"submission": submission, "status": raw.get("status") or {}, "response": response}
    return build_result(
        PROVIDER,
        model,
        "completed",
        request_id,
        video_url_value,
        prepared["output_path"],
        cost["cost_usd"],
        cost["cost_is_estimated"],
        cost["cost_source"],
        raw_response,
        extra,
    )


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
    return {
        "provider": PROVIDER,
        "model": model,
        "request_id": request_id,
        "status": normalize_fal_status(raw.get("status")),
        "raw_response": raw,
        **refs,
    }


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
        raise RuntimeError(f"fal.ai video-to-video result for {request_id} did not include a video URL.")
    from ..._shared import normalize_output_path

    extra = {**refs, "cost_reason": cost["cost_reason"]}
    return build_result(
        PROVIDER,
        model,
        "completed",
        request_id,
        video_url_value,
        normalize_output_path(output_path),
        cost["cost_usd"],
        cost["cost_is_estimated"],
        cost["cost_source"],
        raw,
        extra,
    )


def download_generation(request_id=None, video_url=None, output_path=None, **kwargs):
    if video_url:
        from ..._shared import download_file, normalize_output_path

        return download_file(video_url, normalize_output_path(output_path))
    if not request_id:
        raise ValueError("request_id or video_url is required.")
    return get_generation_result(request_id, output_path=output_path, **kwargs)
