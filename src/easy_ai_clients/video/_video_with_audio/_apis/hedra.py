"""Hedra video-with-audio wrapper."""

from ..._hedra_common import (
    ENV_NAME,
    PROVIDER,
    fetch_generation_status,
    hedra_extract_video_url,
    submit_generation,
)
from ..._shared import (
    download_file,
    hedra_upload_local_asset,
    normalize_hedra_status,
    normalize_output_path,
    require_env,
)
from ..post_processing import build_result
from ..pre_processing import prepare_video_with_audio

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
    model = kwargs.get("model") or kwargs.get("video_generation_model_id")
    if not model:
        raise ValueError(
            "Hedra video_with_audio requires model or video_generation_model_id because "
            "the public catalog does not expose a safe default for this flow."
        )
    return str(model).strip(), {"id": str(model).strip(), "name": str(model).strip(), "operation": "video_with_audio"}


def _video_id(video_path, video_url, kwargs, api_key):
    explicit_id = kwargs.get("video_id") or kwargs.get("video_asset_id")
    if video_path and explicit_id:
        raise ValueError("Provide either video_path or video_id/video_asset_id, not both.")
    if video_url:
        raise ValueError("Hedra video_with_audio requires video_id/video_asset_id or a local video_path; remote video_url is not accepted.")
    if explicit_id:
        return str(explicit_id).strip()
    if video_path:
        return hedra_upload_local_asset(video_path, "video", api_key, kwargs.get("timeout_seconds"))
    return None


def _cost(model_data):
    return {
        "cost_usd": 0.0,
        "cost_is_estimated": True,
        "cost_source": "unavailable",
        "cost_credits": 0.0,
        "credit_source": "unavailable",
        "cost_reason": f"No Hedra catalog pricing metadata is available for `{model_data['name']}` video_with_audio.",
    }


def _build_payload(model_data, prepared, kwargs):
    api_key = require_env(ENV_NAME, "Hedra")
    video_id = _video_id(prepared["video_path"], prepared["video_url"], kwargs, api_key)
    if not video_id:
        raise ValueError("Hedra video_with_audio requires video_id, video_asset_id, or a local video_path.")
    payload = {
        "type": "video_with_audio",
        "video_generation_model_id": model_data["id"],
        "video_id": video_id,
    }
    if prepared["prompt"]:
        payload["prompt"] = prepared["prompt"]
    for name, value in kwargs.items():
        if name not in COMMON_OPTIONS and name not in {"video_id", "video_asset_id", "video_generation_model_id"} and name not in payload and value is not None:
            payload[name] = value
    if "extra_payload" in kwargs:
        from ..._shared import merge_extra_payload

        payload = merge_extra_payload(payload, kwargs)
    return payload


def generate_video_with_audio(
    video_path=None,
    video_url=None,
    prompt=None,
    output_path=None,
    sync=True,
    **kwargs,
):
    _, model_data = _selected_model(kwargs)
    prepared = prepare_video_with_audio(prompt, video_path, video_url, output_path)
    payload = _build_payload(model_data, prepared, kwargs)
    cost = _cost(model_data)
    model_name, request_id, status, video_url_value, normalized_output_path, raw, extra = submit_generation(
        payload,
        sync,
        prepared["output_path"],
        model_data,
        cost,
        kwargs,
    )
    return build_result(
        PROVIDER,
        model_name,
        status,
        request_id,
        video_url_value,
        normalized_output_path,
        cost["cost_usd"],
        cost["cost_is_estimated"],
        cost["cost_source"],
        raw,
        extra,
    )


def get_generation_status(request_id, **kwargs):
    _, model_data = _selected_model(kwargs)
    raw, refs = fetch_generation_status(request_id, kwargs)
    return {
        "provider": PROVIDER,
        "model": model_data["name"],
        "request_id": request_id,
        "status": normalize_hedra_status(raw.get("status")),
        "raw_response": raw,
        **refs,
    }


def get_generation_result(request_id, output_path=None, **kwargs):
    _, model_data = _selected_model(kwargs)
    cost = _cost(model_data)
    raw, refs = fetch_generation_status(request_id, kwargs)
    video_url = hedra_extract_video_url(raw)
    if not video_url:
        raise RuntimeError(f"Hedra generation {request_id} did not include a downloadable video URL.")
    extra = {**refs, "cost_reason": cost["cost_reason"], "cost_credits": cost["cost_credits"], "credit_source": cost["credit_source"]}
    return build_result(PROVIDER, model_data["name"], "completed", request_id, video_url, normalize_output_path(output_path), cost["cost_usd"], cost["cost_is_estimated"], cost["cost_source"], raw, extra)


def download_generation(request_id=None, video_url=None, output_path=None, **kwargs):
    if video_url:
        return download_file(video_url, normalize_output_path(output_path))
    if not request_id:
        raise ValueError("request_id or video_url is required.")
    return get_generation_result(request_id, output_path=output_path, **kwargs)
