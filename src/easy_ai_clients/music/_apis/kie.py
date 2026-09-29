import json
import re
import time

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

#: V5_5 va por la API vieja (`/generate`, camelCase). V6 va por la API de tareas
#: (`/jobs/createTask`, `input` en snake_case): es la única que acepta `duration` de verdad y
#: `persona_model` (voz fija). Kie ya lista V4–V5.5 como discontinuados.
JOBS_CREATE_ENDPOINT = "https://api.kie.ai/api/v1/jobs/createTask"
JOBS_STATUS_ENDPOINT = "https://api.kie.ai/api/v1/jobs/recordInfo"
MODELS = {
    "V5_5": {
        "endpoint": "https://api.kie.ai/api/v1/generate",
        "status_endpoint": "https://api.kie.ai/api/v1/generate/record-info",
        "doc": "https://docs.kie.ai/suno-api/generate-music",
    },
    "V6": {
        "endpoint": JOBS_CREATE_ENDPOINT,
        "status_endpoint": JOBS_STATUS_ENDPOINT,
        "doc": "https://docs.kie.ai/suno-api/generate-music",
    },
}
JOBS_MODELS = {"V6"}
V6_TASK_MODEL = "ai-music-api/generate"
PERSONA_TASK_MODEL = "ai-music-api/generate-persona"
PERSONA_MODELS = ("voice_persona", "style_persona")
PERSONA_WINDOW_MIN = 10
PERSONA_WINDOW_MAX = 30
#: Precio de un crédito de Kie (1.000 créditos = 5 USD). `creditsConsumed` × esto = costo real.
KIE_CREDIT_USD = 0.005
JOBS_SUCCESS_STATES = {"success"}
JOBS_FAILED_STATES = {"fail", "failed", "error"}

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
        lyrics: Required. Exact lyrics sent as Kie `prompt` (V5_5) or
            `lyrics` (V6).
        model: Optional. Accepted values: `"V5_5"` (legacy endpoint, duration
            only as a style hint) and `"V6"` (jobs endpoint, real duration and
            personas).
        **kwargs: Optional provider parameters:
            - `prompt`: Required. Compact style tags sent as Kie `style`.
            - `negative_tags`: Optional. Text or list of what must NOT sound
              (sent as Kie `negativeTags` / `negative_tags`).
            - `negative_prompt`: Not supported. Passing a value raises
              `ValueError`.
            - `duration`: Song duration in seconds. Missing or invalid values
              use `60`. Numeric values are clamped to `10..360`. V6 honors it;
              V5_5 only reads it as a style hint.
            - `title`: Track title, max 80 characters. When omitted, the first
              non-empty lyric line is used.
            - `gender`: Local `"male"` / `"female"` mapped to the vocal gender
              `m` / `f`. `"both"` is omitted.
            - `persona_id`: V6 only. Persona or custom voice ID to apply.
            - `persona_model`: V6 only, required with `persona_id`:
              `"voice_persona"` keeps the voice and lets the style change;
              `"style_persona"` keeps the style.
            - `webhook_url`: HTTPS callback URL. V5_5 requires `callBackUrl`
              even when the caller only polls (defaults to a dummy URL); V6
              sends it only when given.

    Returns:
        A normalized generation dictionary.

    Raises:
        ValueError: If the model is unsupported, `prompt` is missing,
            `negative_prompt` is passed, kwargs include unsupported keys, or a
            persona is requested on V5_5.
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
    if model in JOBS_MODELS:
        return _generate_jobs(lyrics, model, style, duration, kwargs)
    if "persona_id" in kwargs or "persona_model" in kwargs:
        raise ValueError("persona_id and persona_model require kie model V6")
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
        raise _failure_error(_failure_message("submit", data), request_id)
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
    if generation.get("model") in JOBS_MODELS:
        return _jobs_get_status(generation)
    response_data = _status_data(generation, "status")
    status = _provider_status(response_data, "status")
    if _is_failed_status(status):
        generation["status"] = "failed"
        raise _failure_error(_failure_message("status", response_data), generation.get("request_id"))
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
    if generation.get("model") in JOBS_MODELS:
        return _jobs_download_result(generation)
    response_data = _status_data(generation, "download")
    status = _provider_status(response_data, "download")
    if _is_failed_status(status):
        generation["status"] = "failed"
        raise _failure_error(_failure_message("download", response_data), generation.get("request_id"))
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


def create_persona(
    task_id,
    audio_id,
    name,
    description,
    vocal_start=0,
    vocal_end=30,
    style=None,
    timeout_seconds=300,
    poll_interval_seconds=5,
):
    """Create a Suno persona from one take of a completed Kie generation.

    Creating a persona costs no Kie credits (pricing page, 2026-09-28). Each
    audio ID can produce a persona only once. The persona is used afterwards
    as `persona_id` with `persona_model` on V6 generations.

    Args:
        task_id: Required. Task ID of the completed generation.
        audio_id: Required. ID of the take (Kie `data[].id`).
        name: Required. Persona name.
        description: Required. Voice and style description.
        vocal_start: Optional. Start of the analyzed window, in seconds.
        vocal_end: Optional. End of the analyzed window, in seconds. The window
            must last between 10 and 30 seconds.
        style: Optional. Style tag supplement.
        timeout_seconds: Optional. Maximum wait when Kie answers with a task.
        poll_interval_seconds: Optional. Pause between status checks.

    Returns:
        A dictionary with `persona_id`, `request_id`, `name` and `description`.

    Raises:
        ValueError: If an argument is missing or the window is out of range.
        RuntimeError: If Kie reports a failure or returns no persona ID.
        TimeoutError: If the persona task does not finish in time.
    """
    for label, value in (("task_id", task_id), ("audio_id", audio_id), ("name", name), ("description", description)):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{label} must be a non-empty string")
    start, end = float(vocal_start), float(vocal_end)
    window = end - start
    if start < 0 or not PERSONA_WINDOW_MIN <= window <= PERSONA_WINDOW_MAX:
        raise ValueError(
            f"vocal window must last between {PERSONA_WINDOW_MIN} and {PERSONA_WINDOW_MAX} seconds"
        )
    task_input = {
        "task_id": task_id.strip(),
        "audio_id": audio_id.strip(),
        "name": name.strip()[:TITLE_LIMIT],
        "description": description.strip()[:STYLE_LIMIT],
        "vocal_start": start,
        "vocal_end": end,
    }
    if style is not None and str(style).strip():
        task_input["style"] = str(style).strip()[:STYLE_LIMIT]
    response = request_json(
        "POST",
        JOBS_CREATE_ENDPOINT,
        headers=_headers(),
        json_payload={"model": PERSONA_TASK_MODEL, "input": task_input},
        timeout=api_timeout(120),
    )
    data = _data_or_raise(response, "persona")
    persona_id = _find_value(data, ("persona_id", "personaId"))
    request_id = str(data.get("taskId") or data.get("task_id") or "")
    if not persona_id:
        request_id = _task_id_or_raise(data, "persona")
        deadline = time.monotonic() + float(timeout_seconds)
        while True:
            record = _jobs_record(request_id, "persona")
            state = _jobs_state(record)
            if state in JOBS_FAILED_STATES:
                raise _failure_error(_jobs_failure_message("persona", record), request_id)
            if state in JOBS_SUCCESS_STATES:
                persona_id = _find_value(_jobs_result(record), ("persona_id", "personaId"))
                if not persona_id:
                    raise RuntimeError(
                        f"kie persona task finished without persona_id: {_safe_detail(record)}"
                    )
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(f"kie persona task {request_id} did not finish in time")
            time.sleep(float(poll_interval_seconds))
    return {
        "persona_id": str(persona_id),
        "request_id": request_id,
        "name": task_input["name"],
        "description": task_input["description"],
    }


def _generate_jobs(lyrics, model, style, duration, kwargs):
    """V6 por la API de tareas: letra en `lyrics`, duración real y persona opcional."""
    reject_unknown_kwargs(
        kwargs, {"title", "gender", "webhook_url", "negative_tags", "persona_id", "persona_model"}
    )
    gender = kwargs.pop("gender", None)
    negative_tags = _clean_negative_tags(kwargs.pop("negative_tags", None))
    title = _title_from_lyrics(lyrics, kwargs.pop("title", None))
    callback_url = kwargs.pop("webhook_url", None)
    persona_id, persona_model = _resolve_persona(
        kwargs.pop("persona_id", None), kwargs.pop("persona_model", None)
    )
    _check_input_limits(model, style, lyrics)

    task_input = {
        "custom_mode": True,
        "instrumental": False,
        "model": model,
        "title": title,
        "style": style,
        "lyrics": lyrics,
        # En V6 la duración es un parámetro de verdad (tanda 1b de la spec 041: 30 s pedidos
        # dieron de 28,8 a 30,4 s). Sin él, Kie compone 20 s.
        "duration": duration,
    }
    vocal_gender = _vocal_gender(gender)
    if vocal_gender:
        task_input["vocal_gender"] = vocal_gender
    if negative_tags:
        task_input["negative_tags"] = negative_tags
    if persona_id:
        task_input["persona_id"] = persona_id
        task_input["persona_model"] = persona_model
    payload = {"model": V6_TASK_MODEL, "input": task_input}
    if callback_url:
        payload["callBackUrl"] = callback_url

    response = request_json(
        "POST",
        JOBS_CREATE_ENDPOINT,
        headers=_headers(),
        json_payload=payload,
        timeout=api_timeout(120),
    )
    data = _data_or_raise(response, "submit")
    request_id = _task_id_or_raise(data, "submit")
    details = {"credits": ESTIMATED_CREDITS, "duration_seconds": duration}
    if persona_id:
        details["persona_model"] = persona_model
    return standard_generation(
        provider="kie",
        model=model,
        request_id=request_id,
        status="submitted",
        cost_usd=ESTIMATED_COST_USD,
        cost_source="kie_generate_flat_estimate",
        cost_is_estimated=True,
        cost_details=details,
    )


def _resolve_persona(persona_id, persona_model):
    """Persona pedida, o `(None, None)`. Con `persona_id` hace falta decir el modelo."""
    if persona_id is None and persona_model is None:
        return None, None
    if not isinstance(persona_id, str) or not persona_id.strip():
        raise ValueError("persona_id must be a non-empty string")
    if persona_model not in PERSONA_MODELS:
        raise ValueError(f"persona_model must be one of: {', '.join(PERSONA_MODELS)}")
    return persona_id.strip(), persona_model


def _jobs_get_status(generation):
    record = _jobs_record(generation["request_id"], "status")
    state = _jobs_state(record)
    if state in JOBS_FAILED_STATES:
        generation["status"] = "failed"
        raise _failure_error(_jobs_failure_message("status", record), generation.get("request_id"))
    if state in JOBS_SUCCESS_STATES:
        generation["status"] = "completed"
        tracks = _jobs_tracks(_jobs_result(record))
        if tracks:
            _attach_jobs_takes(generation, record, tracks)
    else:
        generation["status"] = "running"
    return generation


def _jobs_download_result(generation):
    record = _jobs_record(generation["request_id"], "download")
    state = _jobs_state(record)
    if state in JOBS_FAILED_STATES:
        generation["status"] = "failed"
        raise _failure_error(_jobs_failure_message("download", record), generation.get("request_id"))
    if state not in JOBS_SUCCESS_STATES:
        generation["status"] = "running"
        return generation
    try:
        tracks = _jobs_tracks(_jobs_result(record))
        if not tracks:
            raise RuntimeError(
                f"kie completed task did not include audio URLs: {_safe_detail(record)}"
            )
        _attach_jobs_takes(generation, record, tracks)
        return download_generation_audio(generation, "kie", tracks[0]["audio_url"], "mp3")
    except Exception:
        generation["status"] = "failed"
        raise


def _jobs_record(request_id, stage):
    response = request_json(
        "GET",
        JOBS_STATUS_ENDPOINT,
        headers=_headers(),
        params={"taskId": request_id},
        timeout=api_timeout(120),
    )
    return _data_or_raise(response, stage)


def _jobs_state(record):
    return str(record.get("state") or "").strip().lower()


def _jobs_result(record):
    """`resultJson` ya decodificado. Kie lo manda como texto con JSON adentro."""
    raw = record.get("resultJson")
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return {}
        try:
            return json.loads(text)
        except ValueError as error:
            raise RuntimeError(f"kie resultJson is not valid JSON: {_safe_detail(record)}") from error
    return raw if isinstance(raw, (dict, list)) else {}


def _jobs_tracks(result):
    """Las tomas del resultado: `{"data": [...]}` (visto el 2026-09-28), variantes o `resultUrls`."""
    candidates = []
    if isinstance(result, list):
        candidates = result
    elif isinstance(result, dict):
        for key in ("data", "sunoData", "suno_data", "tracks"):
            value = result.get(key)
            if isinstance(value, list):
                candidates = value
                break
            if isinstance(value, dict):
                nested = value.get("data") or value.get("sunoData")
                if isinstance(nested, list):
                    candidates = nested
                    break
        if not candidates and isinstance(result.get("resultUrls"), list):
            candidates = [{"audio_url": url} for url in result["resultUrls"]]
    tracks = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        url = (
            item.get("audio_url")
            or item.get("audioUrl")
            or item.get("stream_audio_url")
            or item.get("streamAudioUrl")
        )
        if url:
            tracks.append(
                {
                    "id": str(item.get("id") or item.get("audio_id") or ""),
                    "audio_url": str(url),
                    "duration": item.get("duration"),
                }
            )
    return tracks


def _attach_jobs_takes(generation, record, tracks):
    metadata = dict(generation.get("metadata") or {})
    metadata["take_count"] = len(tracks)
    metadata["selected_take"] = 1
    if len(tracks) > 1:
        metadata["alternate_audio_url"] = tracks[1]["audio_url"]
    ids = [track["id"] for track in tracks if track["id"]]
    if ids:
        # Hacen falta para crear una persona desde una toma (`create_persona`).
        metadata["take_audio_ids"] = ids
    durations = [track["duration"] for track in tracks if isinstance(track["duration"], (int, float))]
    if durations:
        metadata["take_durations"] = durations
    generation["metadata"] = metadata
    credits = record.get("creditsConsumed")
    if isinstance(credits, (int, float)) and not isinstance(credits, bool) and credits >= 0:
        apply_cost_metadata(
            generation,
            round(float(credits) * KIE_CREDIT_USD, 6),
            source="kie_credits_consumed",
            is_estimated=False,
            details={"credits": credits},
        )
    return generation


def _jobs_failure_message(stage, record):
    state = _jobs_state(record) or "fail"
    code = record.get("failCode")
    message = str(record.get("failMsg") or "").strip()
    reason = f" (code {code}: {message})" if code or message else ""
    return f"kie generation failed during {stage} with state {state}{reason}: {_safe_detail(record)}"


def _find_value(value, keys):
    """Primer valor no vacío de alguna de `keys`, buscando en todo el árbol."""
    if isinstance(value, dict):
        for key in keys:
            found = value.get(key)
            if found:
                return str(found)
        for item in value.values():
            found = _find_value(item, keys)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_value(item, keys)
            if found:
                return found
    return None


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


def _failure_error(message, request_id):
    """The same RuntimeError as always, carrying the Kie ``taskId`` as ``request_id``."""
    error = RuntimeError(message)
    error.request_id = str(request_id or "")
    return error


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
