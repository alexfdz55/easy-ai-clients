import json
import re

from .._common import (
    api_timeout,
    apply_cost_metadata,
    auth_header,
    download_generation_audio,
    raise_input_limit_error,
    reject_parameter_present,
    reject_unknown_kwargs,
    request_json,
    sanitize,
    standard_generation,
    text_limit_field,
    normalize_duration,
)

MODELS = {
    "V5_5": {
        "endpoint": "https://api.kie.ai/api/v1/generate",
        "status_endpoint": "https://api.kie.ai/api/v1/generate/record-info",
        "doc": "https://docs.kie.ai/suno-api/generate-music",
    },
}

GENERATE_ENDPOINT = MODELS["V5_5"]["endpoint"]
STATUS_ENDPOINT = MODELS["V5_5"]["status_endpoint"]
DEFAULT_CALLBACK_URL = "https://example.com/kie-callback"
LYRICS_LIMIT = 5000
STYLE_LIMIT = 1000
TITLE_LIMIT = 80
DURATION_MIN = 10
DURATION_MAX = 360
DURATION_DEFAULT = 60
ESTIMATED_COST_USD = 0.06
ESTIMATED_CREDITS = 12
VOCAL_GENDER = {"male": "m", "female": "f"}
SUCCESS_STATUSES = {"success"}
FAILED_STATUSES = {
    "failed",
    "error",
    "cancelled",
    "canceled",
    "create_task_failed",
    "generate_audio_failed",
    "callback_exception",
    "sensitive_word_error",
}
SUCCESS_RESPONSE_CODES = {0, 200}


def generate(lyrics, model="V5_5", **kwargs):
    """Submit one Kie.ai Suno custom-mode generation request.

    Args:
        lyrics: Required. Exact lyrics sent as Kie `prompt`.
        model: Optional. Accepted value: `"V5_5"`.
        **kwargs: Optional provider parameters:
            - `prompt`: Required. Compact style tags sent as Kie `style`.
            - `negative_tags`: Optional. Text or list of what must NOT sound
              (sent as Kie `negativeTags`).
            - `negative_prompt`: Not supported. Passing a value raises
              `ValueError`.
            - `duration`: Song duration in seconds. Missing or invalid values
              use `60`. Numeric values are clamped to `10..360`.
            - `title`: Track title, max 80 characters. When omitted, the first
              non-empty lyric line is used.
            - `gender`: Local `"male"` / `"female"` mapped to `vocalGender`
              `m` / `f`. `"both"` is omitted.
            - `webhook_url`: HTTPS callback URL. Kie requires `callBackUrl`
              even when the caller only polls. Defaults to a dummy URL.

    Returns:
        A normalized generation dictionary.

    Raises:
        ValueError: If the model is unsupported, `prompt` is missing,
            `negative_prompt` is passed, or kwargs include unsupported keys.
    """
    if model not in MODELS:
        raise ValueError(f"Unsupported model: {model}")
    style = kwargs.pop("prompt", None)
    reject_parameter_present(kwargs, "negative_prompt", "kie")
    if style is None:
        raise ValueError("prompt is required for kie")
    duration = normalize_duration(
        kwargs.pop("duration", None),
        DURATION_MIN,
        DURATION_MAX,
        default=DURATION_DEFAULT,
    )
    reject_unknown_kwargs(kwargs, {"title", "gender", "webhook_url", "negative_tags"})
    gender = kwargs.pop("gender", None)
    negative_tags = _clean_negative_tags(kwargs.pop("negative_tags", None))
    title = _title_from_lyrics(lyrics, kwargs.pop("title", None))
    callback_url = kwargs.pop("webhook_url", None) or DEFAULT_CALLBACK_URL
    # Kie/Suno NO tiene parámetro de duración: la longitud la fija la letra y el
    # propio modelo (medido 2026-09-10: 115 palabras pedidas para 60 s → 110 s, con
    # 19 s de intro y 20 s de cola instrumentales). `duration` viaja como pista de
    # estilo, que Suno sí lee, y queda en `cost_details` para el caller.
    style = _style_with_duration(style, duration)
    _check_input_limits(model, style, lyrics)

    payload = {
        "prompt": lyrics,
        "style": style,
        "title": title,
        "customMode": True,
        "instrumental": False,
        "model": model,
        "callBackUrl": callback_url,
    }
    vocal_gender = _vocal_gender(gender)
    if vocal_gender:
        payload["vocalGender"] = vocal_gender
    if negative_tags:
        payload["negativeTags"] = negative_tags

    response = request_json(
        "POST",
        GENERATE_ENDPOINT,
        headers=_headers(),
        json_payload=payload,
        timeout=api_timeout(120),
    )
    data = _data_or_raise(response, "submit")
    request_id = _task_id_or_raise(data, "submit")
    provider_status = _provider_status_value(data)
    if _is_failed_status(provider_status):
        raise RuntimeError(_failure_message("submit", data))
    return standard_generation(
        provider="kie",
        model=model,
        request_id=request_id,
        status=_standard_status(provider_status, initial=True),
        cost_usd=ESTIMATED_COST_USD,
        cost_source="kie_generate_flat_estimate",
        cost_is_estimated=True,
        cost_details={
            "credits": ESTIMATED_CREDITS,
            "duration_seconds": duration,
        },
    )


def get_status(generation):
    """Return an updated Kie generation dictionary.

    Args:
        generation: Required. Dictionary returned by `generate()`.

    Returns:
        The updated generation dictionary.

    Raises:
        RuntimeError: If the provider reports a terminal failure.
    """
    response_data = _status_data(generation, "status")
    status = _provider_status(response_data, "status")
    if _is_failed_status(status):
        generation["status"] = "failed"
        raise RuntimeError(_failure_message("status", response_data))
    if _is_success_status(status):
        generation["status"] = "completed"
        try:
            _attach_take_metadata(generation, response_data)
        except RuntimeError:
            pass
    else:
        generation["status"] = "running"
    return generation


def download_result(generation):
    """Download the first completed Kie take and return the generation dictionary.

    Args:
        generation: Required. Dictionary returned by `generate()`.

    Returns:
        The updated generation dictionary.

    Raises:
        RuntimeError: If the provider reports a terminal failure.
    """
    response_data = _status_data(generation, "download")
    status = _provider_status(response_data, "download")
    if _is_failed_status(status):
        generation["status"] = "failed"
        raise RuntimeError(_failure_message("download", response_data))
    if not _is_success_status(status):
        generation["status"] = "running"
        return generation
    try:
        audio_urls = _audio_urls(response_data)
        _attach_take_metadata(generation, response_data, audio_urls=audio_urls)
        return download_generation_audio(generation, "kie", audio_urls[0], "mp3")
    except Exception:
        generation["status"] = "failed"
        raise


def _headers():
    headers = auth_header("KIE_API_KEY", "bearer")
    headers["Accept"] = "application/json"
    headers["Content-Type"] = "application/json"
    return headers


def _check_input_limits(model, style, lyrics):
    fields = {}
    style_limit = text_limit_field(style, STYLE_LIMIT)
    lyrics_limit = text_limit_field(lyrics, LYRICS_LIMIT)
    if style_limit is not None:
        fields["style"] = style_limit
    if lyrics_limit is not None:
        fields["prompt"] = lyrics_limit
    if fields:
        raise_input_limit_error("kie", model, fields)


def _status_data(generation, stage):
    response = request_json(
        "GET",
        STATUS_ENDPOINT,
        headers=_headers(),
        params={"taskId": generation["request_id"]},
        timeout=api_timeout(120),
    )
    return _data_or_raise(response, stage)


def _data_or_raise(response, stage):
    if not isinstance(response, dict):
        raise RuntimeError(f"kie {stage} response was not a JSON object")
    code = response.get("code")
    if code not in SUCCESS_RESPONSE_CODES and code is not None:
        raise RuntimeError(
            f"kie {stage} failed with code {code}: {_safe_detail(response)}"
        )
    data = response.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(
            f"kie {stage} response did not include a data object: {_safe_detail(response)}"
        )
    return data


def _task_id_or_raise(data, stage):
    request_id = data.get("taskId") or data.get("task_id")
    if not request_id:
        raise RuntimeError(
            f"kie {stage} response did not include data.taskId: {_safe_detail(data)}"
        )
    return str(request_id)


def _provider_status(data, stage):
    status = _provider_status_value(data)
    if not status:
        raise RuntimeError(
            f"kie {stage} response did not include data.status: {_safe_detail(data)}"
        )
    return status


def _provider_status_value(data):
    return str(data.get("status") or data.get("state") or "").strip().lower()


def _audio_urls(data):
    tracks = _suno_tracks(data)
    urls = []
    for track in tracks:
        if not isinstance(track, dict):
            continue
        audio_url = (
            track.get("audioUrl")
            or track.get("audio_url")
            or track.get("streamAudioUrl")
            or track.get("stream_audio_url")
        )
        if audio_url:
            urls.append(str(audio_url))
    if not urls:
        raise RuntimeError(
            "kie completed response did not include sunoData audio URLs: "
            f"{_safe_detail(data)}"
        )
    return urls


def _suno_tracks(data):
    response = data.get("response")
    if isinstance(response, dict):
        tracks = response.get("sunoData") or response.get("suno_data")
        if isinstance(tracks, list):
            return tracks
        nested = response.get("data")
        if isinstance(nested, list):
            return nested
    tracks = data.get("sunoData") or data.get("suno_data")
    if isinstance(tracks, list):
        return tracks
    return []


def _attach_take_metadata(generation, data, audio_urls=None):
    urls = audio_urls if audio_urls is not None else _audio_urls(data)
    metadata = dict(generation.get("metadata") or {})
    metadata["take_count"] = len(urls)
    metadata["selected_take"] = 1
    if len(urls) > 1:
        metadata["alternate_audio_url"] = urls[1]
    generation["metadata"] = metadata
    if generation.get("cost_source") == "unavailable":
        apply_cost_metadata(
            generation,
            ESTIMATED_COST_USD,
            source="kie_generate_flat_estimate",
            is_estimated=True,
        )
    return generation


def _clean_negative_tags(value):
    """`negativeTags` de Kie: texto libre (o lista) de lo que NO debe sonar."""
    if value is None:
        return None
    if isinstance(value, (list, tuple, set)):
        value = ", ".join(str(v).strip() for v in value if str(v).strip())
    if not isinstance(value, str):
        raise ValueError("negative_tags must be a string or a list of strings")
    text = value.strip()
    return text[:STYLE_LIMIT] or None


def _style_with_duration(style, duration):
    """Pista de duración en los tags de estilo (Suno no acepta `duration`)."""
    if not style or not duration:
        return style
    hint = f"about {int(duration)} seconds long, short intro, ends right after the last line"
    if hint in style:
        return style
    combined = f"{style}, {hint}"
    return combined if len(combined) <= STYLE_LIMIT else style


def _title_from_lyrics(lyrics, title=None):
    if title is not None:
        text = str(title).strip()
        if text:
            return text[:TITLE_LIMIT]
    for line in str(lyrics or "").splitlines():
        cleaned = re.sub(r"^\[[^\]]+\]\s*", "", line).strip()
        if cleaned:
            return cleaned[:TITLE_LIMIT]
    return "Untitled"


def _vocal_gender(gender):
    if gender is None:
        return None
    if not isinstance(gender, str):
        raise ValueError("gender must be one of: male, female, both")
    value = gender.strip().lower()
    if value == "both":
        return None
    if value not in VOCAL_GENDER:
        raise ValueError("gender must be one of: male, female, both")
    return VOCAL_GENDER[value]


def _failure_message(stage, data):
    status = str(data.get("status") or data.get("state") or "error").strip().lower()
    # errorCode/errorMessage PRIMERO: el `param` (tags + letra) llenaba el detalle
    # recortado y el motivo real («artist name skank», «Internal Error») no se veía.
    code = data.get("errorCode")
    message = str(data.get("errorMessage") or "").strip()
    reason = f" (code {code}: {message})" if code is not None or message else ""
    return f"kie generation failed during {stage} with status {status}{reason}: {_safe_detail(data)}"


def _safe_detail(value):
    return json.dumps(sanitize(value), ensure_ascii=False)[:1200]


def _standard_status(provider_status, initial=False):
    if _is_success_status(provider_status):
        return "completed"
    if _is_failed_status(provider_status):
        return "failed"
    return "submitted" if initial else "running"


def _is_success_status(provider_status):
    return str(provider_status or "").strip().lower() in SUCCESS_STATUSES


def _is_failed_status(provider_status):
    return str(provider_status or "").strip().lower() in FAILED_STATUSES
