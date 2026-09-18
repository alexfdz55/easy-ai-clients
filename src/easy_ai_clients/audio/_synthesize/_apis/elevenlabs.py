"""ElevenLabs TTS adapter with native character-level alignment.

Last updated: 2026-04-22
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

import requests

from .._apis._shared import (
    normalize_language_code,
    pcm_to_wav_bytes,
    reject_unknown_kwargs,
    request_with_retries,
    response_json,
    validate_choice,
    validate_number_range,
)
from ..post_processing import _finalize_synthesis_output, build_chunk_record
from ..pre_processing import (
    chunk_text_for_provider,
    compute_operational_char_limit,
    decode_base64_bytes,
    ensure_env_var,
    resolve_language_code,
    split_near_middle,
)
from ._simple import _result_from_audio_bytes

API_URL_TEMPLATE = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
SOUND_EFFECTS_URL = "https://api.elevenlabs.io/v1/sound-generation"
MUSIC_COMPOSE_URL = "https://api.elevenlabs.io/v1/music/compose"
MODELS_URL = "https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps"
CATALOG_URL = "https://elevenlabs.io/docs/api-reference/models/get-all"
PRICING_URL = "https://elevenlabs.io/pricing/api/"

DOCUMENTED_MODEL_METADATA = {
    "eleven_v3": {
        "char_limit": 5000,
        "usd_per_million_chars": 100.0,
        "supports_language_code": True,
    },
    "eleven_multilingual_v2": {
        "char_limit": 10000,
        "usd_per_million_chars": 100.0,
        "supports_language_code": True,
    },
    "eleven_multilingual_v1": {
        "char_limit": 10000,
        "usd_per_million_chars": 100.0,
        "supports_language_code": True,
    },
    "eleven_flash_v2_5": {
        "char_limit": 40000,
        "usd_per_million_chars": 50.0,
        "supports_language_code": True,
    },
    "eleven_flash_v2": {
        "char_limit": 40000,
        "usd_per_million_chars": 50.0,
        "supports_language_code": False,
    },
    "eleven_turbo_v2_5": {
        "char_limit": 40000,
        "usd_per_million_chars": 50.0,
        "supports_language_code": True,
    },
    "eleven_turbo_v2": {
        "char_limit": 40000,
        "usd_per_million_chars": 50.0,
        "supports_language_code": False,
    },
    "eleven_monolingual_v1": {
        "char_limit": 10000,
        "usd_per_million_chars": 100.0,
        "supports_language_code": False,
    },
}

APPLY_TEXT_NORMALIZATION_VALUES = {"auto", "on", "off"}
OUTPUT_FORMATS = {
    "mp3_22050_32",
    "mp3_44100_32",
    "mp3_44100_64",
    "mp3_44100_96",
    "mp3_44100_128",
    "mp3_44100_192",
    "pcm_8000",
    "pcm_16000",
    "pcm_22050",
    "pcm_24000",
    "pcm_44100",
    "pcm_48000",
    "ulaw_8000",
    "alaw_8000",
    "opus_48000_32",
    "opus_48000_64",
    "opus_48000_96",
    "opus_48000_128",
    "opus_48000_192",
}
DOCUMENTED_KWARGS = {
    "audio_type",
    "duration_seconds",
    "prompt_influence",
    "stability",
    "similarity_boost",
    "style",
    "use_speaker_boost",
    "speed",
    "apply_text_normalization",
    "apply_language_text_normalization",
    "seed",
    "pronunciation_dictionary_locators",
    "previous_text",
    "next_text",
    "previous_request_ids",
    "next_request_ids",
    "use_pvc_as_ivc",
    "enable_logging",
    "optimize_streaming_latency",
    "output_format",
    "timeout_seconds",
}
DEFAULT_VOICE = "NndrHq4eUijN4wsQVtzW"
_UNKNOWN_MODEL_METADATA = {
    "char_limit": 5000,
    "usd_per_million_chars": 0.0,
    "supports_language_code": True,
}


def generate(
    text: str,
    model: str = "eleven_flash_v2_5",
    voice: str = DEFAULT_VOICE,
    language_code: str = "en",
    **kwargs: Any,
) -> dict[str, Any]:
    """Generate speech with ElevenLabs TTS. See `synthesize/docs/elevenlabs.md`."""
    model_config = DOCUMENTED_MODEL_METADATA.get(model, _UNKNOWN_MODEL_METADATA)
    documented_model = model in DOCUMENTED_MODEL_METADATA
    options = reject_unknown_kwargs("ElevenLabs", model, kwargs, DOCUMENTED_KWARGS)
    audio_type = str(options.pop("audio_type", "speech")).strip().lower()
    if audio_type in {"sound", "sound_effect", "sound_effects", "sfx"}:
        return _generate_sound_effect(text, model=model, options=options)
    if audio_type in {"music", "song"}:
        return _generate_music(text, model=model, options=options)
    stability = validate_number_range(options.pop("stability", 0.7), parameter_name="stability", provider="ElevenLabs", model=model, minimum=0.0, maximum=1.0)
    similarity_boost = validate_number_range(options.pop("similarity_boost", 0.9), parameter_name="similarity_boost", provider="ElevenLabs", model=model, minimum=0.0, maximum=1.0)
    style = validate_number_range(options.pop("style", 0.0), parameter_name="style", provider="ElevenLabs", model=model, minimum=0.0, maximum=1.0)
    speed = validate_number_range(options.pop("speed", 0.96), parameter_name="speed", provider="ElevenLabs", model=model, minimum=0.7, maximum=1.2)
    apply_text_normalization = str(options.pop("apply_text_normalization", "auto")).strip()
    validate_choice(
        apply_text_normalization,
        APPLY_TEXT_NORMALIZATION_VALUES,
        parameter_name="apply_text_normalization",
        provider="ElevenLabs",
        model=model,
    )
    output_format = str(options.pop("output_format", "mp3_44100_128")).strip()
    validate_choice(output_format, OUTPUT_FORMATS, parameter_name="output_format", provider="ElevenLabs", model=model)
    optimize_streaming_latency = options.pop("optimize_streaming_latency", None)
    if optimize_streaming_latency is not None:
        optimize_streaming_latency = int(validate_number_range(
            optimize_streaming_latency,
            parameter_name="optimize_streaming_latency",
            provider="ElevenLabs",
            model=model,
            minimum=0,
            maximum=4,
        ))
    enable_logging = bool(options.pop("enable_logging", True))
    seed = options.pop("seed", 4_294_967_295)
    if seed is not None:
        seed = int(validate_number_range(seed, parameter_name="seed", provider="ElevenLabs", model=model, minimum=0, maximum=4_294_967_295))
    language_code = normalize_language_code(language_code)

    api_key = ensure_env_var("ELEVENLABS_API_KEY")
    chunk_limit = compute_operational_char_limit(model_config["char_limit"])
    resolved_language = resolve_language_code(language_code)
    text_chunks = chunk_text_for_provider(text, chunk_limit)

    voice_settings = {
        "stability": stability,
        "similarity_boost": similarity_boost,
        "style": style,
        "use_speaker_boost": bool(options.pop("use_speaker_boost", True)),
        "speed": speed,
    }

    total_billed_characters = 0
    chunk_records: list[dict[str, Any]] = []
    for chunk_index, chunk_text in enumerate(text_chunks):
        chunk_records.extend(
            _generate_chunk(
                api_key=api_key,
                chunk_text=chunk_text,
                voice_id=voice,
                model_id=model,
                language_code=resolved_language,
                voice_settings=voice_settings,
                apply_text_normalization=apply_text_normalization,
                apply_language_text_normalization=bool(options.get("apply_language_text_normalization", False)),
                seed=seed,
                pronunciation_dictionary_locators=options.get("pronunciation_dictionary_locators"),
                previous_text=options.get("previous_text"),
                next_text=options.get("next_text"),
                previous_request_ids=options.get("previous_request_ids"),
                next_request_ids=options.get("next_request_ids"),
                use_pvc_as_ivc=bool(options.get("use_pvc_as_ivc", False)),
                enable_logging=enable_logging,
                optimize_streaming_latency=optimize_streaming_latency,
                output_format=output_format,
                timeout_seconds=float(options.get("timeout_seconds", 120)),
                extra_payload={
                    key: value
                    for key, value in options.items()
                    if key
                    not in {
                        "apply_language_text_normalization",
                        "pronunciation_dictionary_locators",
                        "previous_text",
                        "next_text",
                        "previous_request_ids",
                        "next_request_ids",
                        "use_pvc_as_ivc",
                        "timeout_seconds",
                    }
                },
                chunk_index=chunk_index,
            )
        )

    request_ids: list[str] = []
    for chunk in chunk_records:
        total_billed_characters += int(chunk.pop("character_cost", 0) or 0)
        chunk_request_id = chunk.pop("request_id", "")
        if chunk_request_id:
            request_ids.append(str(chunk_request_id))

    cost_usd = round((total_billed_characters / 1_000_000.0) * model_config["usd_per_million_chars"], 6)
    result = _finalize_synthesis_output(
        chunk_records,
        cost_usd=cost_usd if documented_model else 0.0,
    )
    if not documented_model:
        result["warnings"] = f"No documented pricing metadata is available for ElevenLabs model `{model}`."
    if request_ids:
        # One request per chunk: the first identifies the synthesis, all of them are kept.
        result["request_id"] = request_ids[0]
        result["request_ids"] = request_ids
    return result


def _generate_sound_effect(text: str, *, model: str, options: dict[str, Any]) -> dict[str, Any]:
    api_key = ensure_env_var("ELEVENLABS_API_KEY")
    timeout_seconds = float(options.pop("timeout_seconds", 120))
    output_format = str(options.pop("output_format", "mp3_44100_128")).strip()
    duration_seconds = options.pop("duration_seconds", None)
    payload = {"text": text}
    if duration_seconds is not None:
        payload["duration_seconds"] = float(duration_seconds)
    if options.get("prompt_influence") is not None:
        payload["prompt_influence"] = float(options.pop("prompt_influence"))
    payload.update({key: value for key, value in options.items() if value is not None})
    response = request_with_retries(
        "POST",
        SOUND_EFFECTS_URL,
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        params={"output_format": output_format},
        json_body=payload,
        timeout=(10.0, timeout_seconds),
    )
    return _result_from_audio_bytes(
        bytes(response.content or b""),
        audio_format=_audio_format_from_output_format(output_format),
        text="",
        cost_usd=0.0,
        cost_source="unavailable",
        cost_is_estimated=False,
        provider="elevenlabs",
        model=model,
        request_id=getattr(response, "headers", {}).get("request-id"),
        audio_type="sound_effect",
        cost_details={"character_cost": _parse_character_cost(response.headers, fallback=len(text))},
    )


def _generate_music(text: str, *, model: str, options: dict[str, Any]) -> dict[str, Any]:
    api_key = ensure_env_var("ELEVENLABS_API_KEY")
    timeout_seconds = float(options.pop("timeout_seconds", 300))
    output_format = str(options.pop("output_format", "mp3_44100_128")).strip()
    payload = {"prompt": text}
    if options.get("duration_seconds") is not None:
        payload["duration_seconds"] = float(options.pop("duration_seconds"))
    payload.update({key: value for key, value in options.items() if value is not None})
    response = request_with_retries(
        "POST",
        MUSIC_COMPOSE_URL,
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        params={"output_format": output_format},
        json_body=payload,
        timeout=(10.0, timeout_seconds),
    )
    return _result_from_audio_bytes(
        bytes(response.content or b""),
        audio_format=_audio_format_from_output_format(output_format),
        text="",
        cost_usd=0.0,
        cost_source="unavailable",
        cost_is_estimated=False,
        provider="elevenlabs",
        model=model,
        request_id=getattr(response, "headers", {}).get("request-id"),
        audio_type="music",
        cost_details={"character_cost": _parse_character_cost(response.headers, fallback=len(text))},
    )


def _calculate_read_timeout(text_length: int, timeout_seconds: float) -> float:
    """Scale the read timeout with the chunk size so larger chunks do not trip early."""
    minimum_timeout = 45.0 + float(text_length) * 0.06
    return min(360.0, max(float(timeout_seconds), minimum_timeout))


def _request_tts(
    *,
    api_key: str,
    text: str,
    voice_id: str,
    model_id: str,
    language_code: str,
    voice_settings: Mapping[str, Any],
    apply_text_normalization: str,
    apply_language_text_normalization: bool,
    seed: int | None,
    pronunciation_dictionary_locators: list[dict[str, str]] | None,
    previous_text: str | None,
    next_text: str | None,
    previous_request_ids: list[str] | None,
    next_request_ids: list[str] | None,
    use_pvc_as_ivc: bool,
    enable_logging: bool,
    optimize_streaming_latency: int | None,
    output_format: str,
    timeout_seconds: float,
    extra_payload: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], Mapping[str, Any]]:
    """Call ElevenLabs `/with-timestamps` for one chunk."""
    payload: dict[str, Any] = {
        "text": text,
        "model_id": model_id,
        "voice_settings": dict(voice_settings),
        "apply_text_normalization": apply_text_normalization,
        "apply_language_text_normalization": bool(apply_language_text_normalization),
        "use_pvc_as_ivc": bool(use_pvc_as_ivc),
    }
    if DOCUMENTED_MODEL_METADATA.get(model_id, _UNKNOWN_MODEL_METADATA)["supports_language_code"]:
        payload["language_code"] = language_code
    if seed is not None:
        payload["seed"] = int(seed)
    if pronunciation_dictionary_locators:
        payload["pronunciation_dictionary_locators"] = list(pronunciation_dictionary_locators)
    if previous_text:
        payload["previous_text"] = previous_text
    if next_text:
        payload["next_text"] = next_text
    if previous_request_ids:
        payload["previous_request_ids"] = list(previous_request_ids)
    if next_request_ids:
        payload["next_request_ids"] = list(next_request_ids)
    if extra_payload:
        payload.update({key: value for key, value in extra_payload.items() if value is not None})

    params: dict[str, Any] = {
        "enable_logging": "true" if enable_logging else "false",
        "output_format": output_format,
    }
    if optimize_streaming_latency is not None:
        params["optimize_streaming_latency"] = int(optimize_streaming_latency)
    response = request_with_retries(
        "POST",
        API_URL_TEMPLATE.format(voice_id=voice_id),
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "accept": "application/json",
        },
        params=params,
        json_body=payload,
        timeout=(10.0, _calculate_read_timeout(len(text), timeout_seconds)),
    )
    return response_json(response), response.headers


def _is_retryable_error(error: Exception) -> bool:
    if isinstance(error, requests.Timeout | requests.ConnectionError):
        return True
    if isinstance(error, requests.HTTPError) and error.response is not None:
        return int(error.response.status_code) in {408, 409, 425, 429, 500, 502, 503, 504}
    return False


def _generate_chunk(
    *,
    api_key: str,
    chunk_text: str,
    voice_id: str,
    model_id: str,
    language_code: str,
    voice_settings: Mapping[str, Any],
    apply_text_normalization: str,
    apply_language_text_normalization: bool,
    seed: int | None,
    pronunciation_dictionary_locators: list[dict[str, str]] | None,
    previous_text: str | None,
    next_text: str | None,
    previous_request_ids: list[str] | None,
    next_request_ids: list[str] | None,
    use_pvc_as_ivc: bool,
    enable_logging: bool,
    optimize_streaming_latency: int | None,
    output_format: str,
    timeout_seconds: float,
    extra_payload: Mapping[str, Any] | None = None,
    chunk_index: int,
    depth: int = 0,
) -> list[dict[str, Any]]:
    """Synthesize one chunk, recursively splitting on retryable failures."""
    try:
        payload, response_headers = _request_tts(
            api_key=api_key,
            text=chunk_text,
            voice_id=voice_id,
            model_id=model_id,
            language_code=language_code,
            voice_settings=voice_settings,
            apply_text_normalization=apply_text_normalization,
            apply_language_text_normalization=apply_language_text_normalization,
            seed=seed,
            pronunciation_dictionary_locators=pronunciation_dictionary_locators,
            previous_text=previous_text,
            next_text=next_text,
            previous_request_ids=previous_request_ids,
            next_request_ids=next_request_ids,
            use_pvc_as_ivc=use_pvc_as_ivc,
            enable_logging=enable_logging,
            optimize_streaming_latency=optimize_streaming_latency,
            output_format=output_format,
            timeout_seconds=timeout_seconds,
            extra_payload=extra_payload,
        )
    except Exception as error:
        can_split = _is_retryable_error(error) and depth < 6 and len(chunk_text) >= 440
        split_pair = split_near_middle(chunk_text) if can_split else None
        if not split_pair:
            excerpt = re.sub(r"\s+", " ", chunk_text.strip())
            if len(excerpt) > 180:
                excerpt = f"{excerpt[:177]}..."
            raise RuntimeError(
                f"Failed to synthesize ElevenLabs chunk {chunk_index + 1} "
                f"(depth={depth}, chars={len(chunk_text)}). Excerpt: '{excerpt}'."
            ) from error

        left_text, right_text = split_pair
        shared_kwargs = dict(
            api_key=api_key,
            voice_id=voice_id,
            model_id=model_id,
            language_code=language_code,
            voice_settings=voice_settings,
            apply_text_normalization=apply_text_normalization,
            apply_language_text_normalization=apply_language_text_normalization,
            seed=seed,
            pronunciation_dictionary_locators=pronunciation_dictionary_locators,
            previous_text=previous_text,
            next_text=next_text,
            previous_request_ids=previous_request_ids,
            next_request_ids=next_request_ids,
            use_pvc_as_ivc=use_pvc_as_ivc,
            enable_logging=enable_logging,
            optimize_streaming_latency=optimize_streaming_latency,
            output_format=output_format,
            timeout_seconds=timeout_seconds,
            extra_payload=extra_payload,
            chunk_index=chunk_index,
            depth=depth + 1,
        )
        return _generate_chunk(chunk_text=left_text, **shared_kwargs) + _generate_chunk(chunk_text=right_text, **shared_kwargs)

    audio_bytes, audio_format = _normalize_audio_bytes(
        decode_base64_bytes(payload.get("audio_base64")),
        output_format=output_format,
    )
    alignment = payload.get("alignment") or payload.get("normalized_alignment") or {}
    if not isinstance(alignment, Mapping) or not alignment.get("characters"):
        raise RuntimeError(f"ElevenLabs payload for chunk {chunk_index + 1} did not include usable alignment.")

    chunk_record = build_chunk_record(
        text=chunk_text,
        audio_bytes=audio_bytes,
        audio_format=audio_format,
        char_alignment={
            "text": "".join(alignment.get("characters") or []) if payload.get("normalized_alignment") and not payload.get("alignment") else chunk_text,
            "characters": list(alignment.get("characters") or []),
            "character_start_times_seconds": list(alignment.get("character_start_times_seconds") or []),
            "character_end_times_seconds": list(alignment.get("character_end_times_seconds") or []),
            "start_key": "character_start_times_seconds",
            "end_key": "character_end_times_seconds",
            "unit": "seconds",
        },
    )
    chunk_record["character_cost"] = _parse_character_cost(response_headers, fallback=len(chunk_text))
    chunk_record["request_id"] = _response_request_id(response_headers)
    return [chunk_record]


def _response_request_id(headers: Mapping[str, Any]) -> str:
    """ElevenLabs reports the id of each synthesis request in the `request-id` header."""
    if not isinstance(headers, Mapping):
        return ""
    return str(headers.get("request-id") or "").strip()


def _parse_character_cost(headers: Mapping[str, Any], *, fallback: int) -> int:
    """Read the billed character count from the `character-cost` response header."""
    raw = headers.get("character-cost") if isinstance(headers, Mapping) else None
    if raw is None:
        return int(fallback)
    try:
        parsed = int(str(raw).strip())
    except (TypeError, ValueError):
        return int(fallback)
    return parsed if parsed > 0 else int(fallback)


def _audio_format_from_output_format(output_format: str) -> str:
    """Return the container/codec token from an ElevenLabs output format enum."""
    return str(output_format or "mp3").split("_", 1)[0]


def _sample_rate_from_output_format(output_format: str, default: int = 44100) -> int:
    """Extract the sample-rate token from an ElevenLabs output format enum."""
    parts = str(output_format or "").split("_")
    if len(parts) < 2:
        return default
    try:
        parsed = int(parts[1])
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _normalize_audio_bytes(audio_bytes: bytes, *, output_format: str) -> tuple[bytes, str]:
    """Wrap raw telephony/PCM ElevenLabs audio in WAV when needed."""
    codec = _audio_format_from_output_format(output_format)
    if codec == "pcm":
        return (
            pcm_to_wav_bytes(
                audio_bytes,
                sample_rate=_sample_rate_from_output_format(output_format),
                sample_width=2,
                channels=1,
            ),
            "wav",
        )
    if codec in {"ulaw", "alaw"}:
        import audioop

        if codec == "ulaw":
            pcm_bytes = audioop.ulaw2lin(audio_bytes, 2)
        else:
            pcm_bytes = audioop.alaw2lin(audio_bytes, 2)
        return (
            pcm_to_wav_bytes(
                pcm_bytes,
                sample_rate=_sample_rate_from_output_format(output_format, default=8000),
                sample_width=2,
                channels=1,
            ),
            "wav",
        )
    return audio_bytes, codec


__all__ = [
    "API_URL_TEMPLATE",
    "CATALOG_URL",
    "DEFAULT_VOICE",
    "DOCUMENTED_MODEL_METADATA",
    "MUSIC_COMPOSE_URL",
    "MODELS_URL",
    "OUTPUT_FORMATS",
    "PRICING_URL",
    "SOUND_EFFECTS_URL",
    "generate",
]
