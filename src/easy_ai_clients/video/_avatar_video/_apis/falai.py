"""fal.ai avatar-video wrapper."""

from ..._falai_pricing import FAL_ESTIMATE_OPTIONS, fal_pricing_estimate
from ..._shared import (
    extract_video_url,
    fal_async_refs,
    fal_get_result,
    fal_get_status,
    fal_submit,
    fal_wait_for_result,
    merge_async_refs,
    normalize_fal_status,
    require_env,
)
from ..post_processing import build_result
from ..pre_processing import prepare_avatar_video

PROVIDER = "falai"
ENV_NAME = "FAL_KEY"
DEFAULT_MODEL = "fal-ai/longcat-single-avatar/image-audio-to-video"
COST_SOURCE = "fal_model_pricing_snapshot_2026-06-24"

MODEL_ALIASES = {
    "fal_omnihuman_v1_5": "fal-ai/bytedance/omnihuman/v1.5",
    "fal_veed_fabric_1_0": "veed/fabric-1.0",
}

LTX_AUDIO_TO_VIDEO = "fal-ai/ltx-2.3-22b/audio-to-video"
# fal factura LTX por megapíxel-frame ($0.001605/MP a 24 fps): 720p = 0.92 MP → 0,0355 $/s.
_LTX_RES_SHORT = {"480p": 480, "720p": 720, "1080p": 1080}
_LTX_ASPECT = {"9:16": (9, 16), "16:9": (16, 9), "1:1": (1, 1), "portrait_16_9": (9, 16), "landscape_16_9": (16, 9), "square_hd": (1, 1)}

DOCUMENTED_MODEL_PRICING = {
    LTX_AUDIO_TO_VIDEO: {
        "unit": "resolution_seconds",
        "prices_usd": {"480p": 0.016, "720p": 0.036, "1080p": 0.08},
    },
    "fal-ai/bytedance/omnihuman/v1.5": {"price_usd": 0.16, "unit": "seconds"},
    "veed/fabric-1.0": {
        "unit": "resolution_seconds",
        "prices_usd": {"480p": 0.08, "720p": 0.15},
    },
    "veed/fabric-1.0/fast": {"price_usd": 0.00017, "unit": "compute_seconds"},
    "fal-ai/flashtalk": {"price_usd": 0.02, "unit": "seconds"},
    DEFAULT_MODEL: {"price_usd": 0.15, "unit": "longcat_units"},
    "fal-ai/longcat-multi-avatar/image-audio-to-video": {"price_usd": 0.15, "unit": "longcat_units"},
    "fal-ai/ai-avatar": {"price_usd": 0.2, "unit": "seconds"},
    "fal-ai/infinitalk": {"price_usd": 0.2, "unit": "seconds"},
    "fal-ai/echomimic-v3": {"price_usd": 0.2, "unit": "seconds"},
    "fal-ai/wan/v2.2-14b/speech-to-video": {"price_usd": 0.2, "unit": "seconds"},
    "fal-ai/creatify/aurora": {"price_usd": 1.0, "unit": "units"},
}

COMMON_OPTIONS = {
    "model",
    "aspect_ratio",
    "timeout_seconds",
    "poll_interval_seconds",
    "extra_payload",
    "billing_duration_seconds",
    "duration_seconds",
    "duration",
    "prompt",
    *FAL_ESTIMATE_OPTIONS,
}


def _selected_model(kwargs):
    selected = kwargs.get("model", DEFAULT_MODEL)
    return MODEL_ALIASES.get(str(selected).strip(), selected)


def _ltx_video_size(resolution, aspect_ratio):
    """Dims explícitas para LTX: la «p» es el lado corto (720p vertical = 720×1280)."""
    short = _LTX_RES_SHORT.get(str(resolution or "").strip())
    if not short:
        return None
    aw, ah = _LTX_ASPECT.get(str(aspect_ratio or "").strip() or "9:16", (9, 16))
    if aw >= ah:
        height, width = short, round(short * aw / ah)
    else:
        width, height = short, round(short * ah / aw)
    return {"width": width - width % 2, "height": height - height % 2}


def _build_payload(model, prepared, kwargs):
    if model == LTX_AUDIO_TO_VIDEO:
        # Imagen + audio → video completo con movimiento y lip-sync (hasta 20 s). El
        # prompt es el del plano; la duración sigue al audio.
        payload = {
            "image_url": prepared["image"],
            "audio_url": prepared["audio"],
            "prompt": kwargs.get("prompt") or prepared["text"] or "Natural performance synchronized with the provided audio.",
            "match_audio_length": True,
        }
        size = kwargs.get("video_size") or _ltx_video_size(kwargs.get("resolution", "720p"), kwargs.get("aspect_ratio"))
        if size:
            payload["video_size"] = size
        if kwargs.get("video_quality"):
            payload["video_quality"] = kwargs["video_quality"]
        return _forward_extra_payload(payload, {k: v for k, v in kwargs.items() if k not in ("video_size", "resolution", "video_quality")})

    if model == "fal-ai/bytedance/omnihuman/v1.5":
        payload = {
            "image_url": prepared["image"],
            "audio_url": prepared["audio"],
            "resolution": kwargs.get("resolution", "720p"),
            "turbo_mode": kwargs.get("turbo_mode", True),
        }
        prompt = kwargs.get("prompt") or prepared["text"]
        if prompt:
            payload["prompt"] = prompt
        return _forward_extra_payload(payload, kwargs)

    if model == "veed/fabric-1.0":
        payload = {
            "image_url": prepared["image"],
            "audio_url": prepared["audio"],
            "resolution": kwargs.get("resolution", "480p"),
        }
        return _forward_extra_payload(payload, kwargs)

    payload = {}
    if prepared["image"]:
        payload["image_url"] = prepared["image"]
    if prepared["audio"]:
        payload["audio_url"] = prepared["audio"]
    if prepared["text"]:
        payload["text"] = prepared["text"]
    for name, value in kwargs.items():
        if name not in COMMON_OPTIONS and name not in payload and value is not None:
            payload[name] = value
    if "extra_payload" in kwargs:
        payload = _forward_extra_payload(payload, kwargs)
    return payload


def _forward_extra_payload(payload, kwargs):
    from ..._shared import merge_extra_payload

    payload = merge_extra_payload(payload, kwargs)
    for name, value in kwargs.items():
        if name not in COMMON_OPTIONS and name not in payload and value is not None:
            payload[name] = value
    return payload


def _quantity_for_unit(unit, kwargs):
    if unit == "seconds":
        value = kwargs.get("billing_duration_seconds", kwargs.get("duration_seconds", kwargs.get("duration")))
        return float(value) if value is not None else None
    if unit == "compute_seconds":
        value = kwargs.get("billing_compute_seconds", kwargs.get("compute_seconds"))
        return float(value) if value is not None else None
    if unit == "units":
        value = kwargs.get("billing_units", kwargs.get("units"))
        return float(value) if value is not None else None
    if unit == "resolution_seconds":
        value = kwargs.get("billing_duration_seconds", kwargs.get("duration_seconds", kwargs.get("duration")))
        return float(value) if value is not None else None
    if unit == "longcat_units":
        if kwargs.get("billing_units") is not None:
            return float(kwargs.get("billing_units"))
        resolution = kwargs.get("resolution", "480p")
        segments = int(kwargs.get("num_segments", 1))
        billed_seconds = 5.8 + max(0, segments - 1) * 5
        units_per_second = 4 if resolution == "720p" else 1
        return billed_seconds * units_per_second
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
    if pricing["unit"] == "resolution_seconds":
        quantity = _quantity_for_unit(pricing["unit"], kwargs)
        resolution = kwargs.get("resolution", "480p")
        price = pricing["prices_usd"].get(resolution)
        if quantity is None or price is None:
            return {
                "cost_usd": 0.0,
                "cost_is_estimated": True,
                "cost_source": "unavailable",
                "cost_reason": (
                    f"fal.ai pricing for `{model}` requires duration and a supported "
                    f"resolution. Supported resolutions: {', '.join(sorted(pricing['prices_usd']))}."
                ),
            }
        return {
            "cost_usd": price * quantity,
            "cost_is_estimated": True,
            "cost_source": COST_SOURCE,
            "cost_reason": (
                "fal.ai pricing is estimated from documented per-second pricing by "
                "resolution; usage reconciliation is not performed during safe wrapper execution."
            ),
        }
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


def generate_avatar_video(
    image_path=None,
    image_url=None,
    audio_path=None,
    audio_url=None,
    text=None,
    output_path=None,
    sync=True,
    **kwargs,
):
    model = _selected_model(kwargs)
    prepared = prepare_avatar_video(image_path, image_url, audio_path, audio_url, text, output_path)
    payload = _build_payload(model, prepared, kwargs)
    cost = _cost(model, kwargs)
    api_key = require_env(ENV_NAME, "fal.ai")
    submission = fal_submit(model, payload, api_key, timeout_seconds=kwargs.get("timeout_seconds"))
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
    video_url = extract_video_url(response)
    if not video_url:
        raise RuntimeError(f"fal.ai avatar-video result for {request_id} did not include a video URL.")
    extra = {**async_refs, "cost_reason": cost["cost_reason"]}
    raw_response = {"submission": submission, "status": raw.get("status") or {}, "response": response}
    return build_result(
        PROVIDER,
        model,
        "completed",
        request_id,
        video_url,
        prepared["output_path"],
        cost["cost_usd"],
        cost["cost_is_estimated"],
        cost["cost_source"],
        raw_response,
        extra,
    )


def get_generation_status(request_id, **kwargs):
    model = _selected_model(kwargs)
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
    model = _selected_model(kwargs)
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
        raise RuntimeError(f"fal.ai avatar-video result for {request_id} did not include a video URL.")
    from ..._shared import normalize_output_path

    extra = {**refs, "cost_reason": cost["cost_reason"]}
    return build_result(
        PROVIDER,
        model,
        "completed",
        request_id,
        video_url,
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
