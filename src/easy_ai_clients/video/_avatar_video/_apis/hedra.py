"""Hedra avatar-video wrapper."""

from ..._hedra_common import (
    ENV_NAME,
    PROVIDER,
    fetch_generation_status,
    generated_video_inputs,
    hedra_cost,
    hedra_extract_video_url,
    hedra_status_result,
    media_payload_key,
    resolve_model,
    submit_generation,
)
from ..._shared import download_file, merge_extra_payload, normalize_output_path, require_env
from ..post_processing import build_result

DEFAULT_MODEL = "hedra-avatar"
COMMON_OPTIONS = {
    "model",
    "timeout_seconds",
    "poll_interval_seconds",
    "extra_payload",
    "webhook_url",
    "on_submitted",
    "submission",
}
GENERATED_INPUT_OPTIONS = {
    "duration_ms",
    "duration_seconds",
    "duration",
    "billing_duration_seconds",
    "aspect_ratio",
    "resolution",
    "batch_size",
    "number_of_videos",
    "enhance_prompt",
    "bounding_box_target",
    "character_orientation",
    "start_keyframe_id",
    "start_keyframe_url",
    "audio_id",
    "prompt",
    "voice_id",
}


def _selected_model(kwargs):
    return resolve_model(kwargs.get("model"), DEFAULT_MODEL, "avatar_video")


def _build_payload(model_data, image_path, image_url, audio_path, audio_url, text, kwargs):
    api_key = require_env(ENV_NAME, "Hedra")
    prompt = kwargs.get("prompt") or "A person speaking naturally in sync with the provided speech."
    payload = {
        "type": "video",
        "ai_model_id": model_data["id"],
        "generated_video_inputs": generated_video_inputs(prompt, model_data, kwargs),
    }

    start_keyframe_id = kwargs.get("start_keyframe_id")
    start_keyframe_url = kwargs.get("start_keyframe_url")
    if not start_keyframe_id and not start_keyframe_url:
        key, value = media_payload_key(image_path, image_url, "image", api_key, kwargs.get("timeout_seconds"))
        if key == "id":
            start_keyframe_id = value
        elif key == "url":
            start_keyframe_url = value
    if start_keyframe_id:
        payload["start_keyframe_id"] = start_keyframe_id
    if start_keyframe_url:
        payload["start_keyframe_url"] = start_keyframe_url

    audio_id = kwargs.get("audio_id")
    if not audio_id and audio_path:
        audio_id = media_payload_key(audio_path, None, "audio", api_key, kwargs.get("timeout_seconds"))[1]
    if audio_url and not audio_id:
        raise ValueError("Hedra avatar_video does not document direct audio_url ingestion; pass audio_id or a local audio_path.")
    if audio_id:
        payload["audio_id"] = audio_id
    elif text:
        voice_id = kwargs.get("voice_id")
        if not voice_id:
            raise ValueError("Hedra avatar_video text-to-speech requires voice_id when audio_id/audio_path is not provided.")
        payload["audio_generation"] = {"text": text, "voice_id": voice_id}
    else:
        raise ValueError("Hedra avatar_video requires audio/audio_id or text with voice_id.")

    if kwargs.get("batch_size") is not None:
        payload["batch_size"] = int(kwargs["batch_size"])
    for name, value in kwargs.items():
        if name not in COMMON_OPTIONS and name not in GENERATED_INPUT_OPTIONS and name not in payload and value is not None:
            payload[name] = value
    if "extra_payload" in kwargs:
        payload = merge_extra_payload(payload, kwargs)
    return payload


def generate_avatar_video(
    avatar=None,
    image_path=None,
    image_url=None,
    audio_path=None,
    audio_url=None,
    text=None,
    output_path=None,
    sync=True,
    **kwargs,
):
    if avatar is not None and not kwargs.get("start_keyframe_id"):
        kwargs = dict(kwargs)
        kwargs["start_keyframe_id"] = avatar
    _, model_data = _selected_model(kwargs)
    payload = _build_payload(model_data, image_path, image_url, audio_path, audio_url, text, kwargs)
    cost = hedra_cost(model_data, kwargs)
    normalized_output_path = normalize_output_path(output_path)
    model_name, request_id, status, video_url, normalized_output_path, raw, extra = submit_generation(
        payload,
        sync,
        normalized_output_path,
        model_data,
        cost,
        kwargs,
    )
    return build_result(PROVIDER, model_name, status, request_id, video_url, normalized_output_path, cost["cost_usd"], cost["cost_is_estimated"], cost["cost_source"], raw, extra)


def get_generation_status(request_id, **kwargs):
    _, model_data = _selected_model(kwargs)
    return hedra_status_result(request_id, model_data, kwargs)


def get_generation_result(request_id, output_path=None, **kwargs):
    _, model_data = _selected_model(kwargs)
    cost = hedra_cost(model_data, kwargs)
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
