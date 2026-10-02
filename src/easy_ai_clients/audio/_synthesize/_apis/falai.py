"""fal.ai text-to-speech adapter: ElevenLabs voices served through fal, with character timings.

Validated on 2026-10-02 with `elevenlabs/tts/eleven-v4-turbo`:
  - `voice` takes an ElevenLabs voice id (or a preset name). An unknown one fails with
    HTTP 422 `Voice not found`: it never falls back to another voice.
  - `timestamps: true` returns a list of blocks, each with `characters`,
    `character_start_times_seconds` and `character_end_times_seconds`.
  - `speed` is accepted and has no effect on this model.

Official references:
  - Eleven v4 Turbo on fal.ai: https://fal.ai/models/elevenlabs/tts/eleven-v4-turbo/api
  - Pricing API: https://fal.ai/docs/platform-apis/v1/models/pricing
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

import requests

from .._apis._shared import (
    normalize_language_code,
    reject_unknown_kwargs,
    request_with_retries,
    response_json,
)
from ..post_processing import _finalize_synthesis_output, build_chunk_record
from ..pre_processing import (
    chunk_text_for_provider,
    compute_operational_char_limit,
    ensure_env_var,
    resolve_language_code,
)
from .elevenlabs import _normalize_audio_bytes

QUEUE_URL = "https://queue.fal.run"
PRICING_API_URL = "https://api.fal.ai/v1/models/pricing"
MODELS_URL = "https://fal.ai/models/elevenlabs/tts/eleven-v4-turbo/api"
PRICING_URL = "https://fal.ai/models/elevenlabs/tts/eleven-v4-turbo"

DEFAULT_MODEL = "elevenlabs/tts/eleven-v4-turbo"
DEFAULT_VOICE = "Rachel"
#: Used only when fal does not report what it billed. `char_limit` is per request.
DOCUMENTED_MODEL_METADATA = {
    "elevenlabs/tts/eleven-v4-turbo": {"char_limit": 5000, "usd_per_million_chars": 40.0},
}
_UNKNOWN_MODEL_METADATA = {"char_limit": 5000, "usd_per_million_chars": 0.0}
DOCUMENTED_KWARGS = {
    "stability",
    "similarity_boost",
    "seed",
    "apply_text_normalization",
    "output_format",
    "timeout_seconds",
}
_POLL_INTERVAL_SECONDS = 0.7


def generate(
    text: str,
    model: str = DEFAULT_MODEL,
    voice: str = DEFAULT_VOICE,
    language_code: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Generate speech through fal.ai's queue. See `docs/audio/generate/falai.md`."""
    options = reject_unknown_kwargs("fal.ai", model, kwargs, DOCUMENTED_KWARGS)
    output_format = str(options.pop("output_format", "mp3_44100_128")).strip()
    timeout_seconds = float(options.pop("timeout_seconds", 180))
    model_config = DOCUMENTED_MODEL_METADATA.get(model, _UNKNOWN_MODEL_METADATA)
    documented_model = model in DOCUMENTED_MODEL_METADATA

    api_key = ensure_env_var("FAL_KEY")
    # Como en ElevenLabs directo: sin idioma pedido no se manda ninguno, y el modelo lo
    # detecta del texto. Un "en" por omisión hace leer en inglés las cifras de otro idioma.
    resolved_language = (
        resolve_language_code(normalize_language_code(language_code))
        if str(language_code or "").strip()
        else None
    )
    text_chunks = chunk_text_for_provider(
        text, compute_operational_char_limit(model_config["char_limit"])
    )

    chunk_records: list[dict[str, Any]] = []
    request_ids: list[str] = []
    billable_units: list[float] = []
    for chunk_index, chunk_text in enumerate(text_chunks):
        payload = {
            "text": chunk_text,
            "voice": voice,
            "timestamps": True,
            "output_format": output_format,
        }
        if resolved_language:
            payload["language_code"] = resolved_language
        payload.update({key: value for key, value in options.items() if value is not None})
        record, request_id, units = _generate_chunk(
            api_key=api_key,
            model=model,
            payload=payload,
            chunk_text=chunk_text,
            chunk_index=chunk_index,
            output_format=output_format,
            timeout_seconds=timeout_seconds,
        )
        chunk_records.append(record)
        if request_id:
            request_ids.append(request_id)
        if units is not None:
            billable_units.append(units)

    cost = _resolve_cost(
        api_key,
        model,
        # Every chunk has to report its units, or the sum would undercount.
        billable_units=sum(billable_units) if len(billable_units) == len(text_chunks) else None,
        characters=sum(len(chunk) for chunk in text_chunks),
        usd_per_million_chars=model_config["usd_per_million_chars"],
    )
    result = _finalize_synthesis_output(chunk_records, cost_usd=cost["cost_usd"])
    result.update(cost)
    result["provider"] = "falai"
    result["model"] = model
    if not documented_model and not cost["cost_usd"]:
        result["warnings"] = f"No documented pricing metadata is available for fal.ai model `{model}`."
    if request_ids:
        # One request per chunk: the first identifies the synthesis, all of them are kept.
        result["request_id"] = request_ids[0]
        result["request_ids"] = request_ids
    return result


def _generate_chunk(
    *,
    api_key: str,
    model: str,
    payload: Mapping[str, Any],
    chunk_text: str,
    chunk_index: int,
    output_format: str,
    timeout_seconds: float,
) -> tuple[dict[str, Any], str, float | None]:
    """Submit one chunk to the queue, wait for it and return (record, request id, units)."""
    headers = {"Authorization": f"Key {api_key}"}
    submit_response = request_with_retries(
        "POST",
        f"{QUEUE_URL}/{model}",
        headers={**headers, "Content-Type": "application/json"},
        json_body=payload,
        timeout=(15.0, float(timeout_seconds)),
    )
    submit_payload = response_json(submit_response)
    request_id = str(submit_payload.get("request_id") or "").strip()
    status_url = str(submit_payload.get("status_url") or "").strip()
    response_url = str(submit_payload.get("response_url") or "").strip()
    if not status_url or not response_url:
        raise _failure("fal.ai queue response did not include status_url/response_url.", request_id)

    try:
        _wait_for_completion(headers, status_url, timeout_seconds=timeout_seconds)
        # A rejected input (an unknown voice, for one) completes in the queue and fails
        # here, with the reason in the body.
        final_response = request_with_retries("GET", response_url, headers=headers, timeout=(15.0, 120.0))
    except Exception as error:
        if request_id and not getattr(error, "request_id", None):
            error.request_id = request_id  # type: ignore[attr-defined]
        raise
    body = response_json(final_response)

    audio = body.get("audio")
    audio_url = str(audio.get("url") or "").strip() if isinstance(audio, Mapping) else ""
    if not audio_url:
        raise _failure(f"fal.ai speech result for chunk {chunk_index + 1} did not include an audio URL.", request_id)
    alignment = _char_alignment(body.get("timestamps"))
    if not alignment["characters"]:
        raise _failure(f"fal.ai speech result for chunk {chunk_index + 1} did not include usable timestamps.", request_id)

    audio_bytes, audio_format = _normalize_audio_bytes(
        _download_bytes(audio_url, timeout_seconds=timeout_seconds, request_id=request_id),
        output_format=output_format,
    )
    record = build_chunk_record(
        text=chunk_text,
        audio_bytes=audio_bytes,
        audio_format=audio_format,
        char_alignment={
            "text": chunk_text,
            **alignment,
            "start_key": "character_start_times_seconds",
            "end_key": "character_end_times_seconds",
            "unit": "seconds",
        },
    )
    return record, request_id, _billable_units(final_response.headers)


def _char_alignment(timestamps: Any) -> dict[str, list[Any]]:
    """Join fal's timestamp blocks into one character alignment, in ElevenLabs' shape."""
    characters: list[str] = []
    starts: list[float] = []
    ends: list[float] = []
    for block in timestamps if isinstance(timestamps, list) else []:
        if not isinstance(block, Mapping):
            continue
        block_characters = block.get("characters") or []
        block_starts = block.get("character_start_times_seconds") or []
        block_ends = block.get("character_end_times_seconds") or []
        if not (len(block_characters) == len(block_starts) == len(block_ends)):
            continue
        characters.extend(str(character) for character in block_characters)
        starts.extend(float(value) for value in block_starts)
        ends.extend(float(value) for value in block_ends)
    return {
        "characters": characters,
        "character_start_times_seconds": starts,
        "character_end_times_seconds": ends,
    }


def _wait_for_completion(headers: Mapping[str, str], status_url: str, *, timeout_seconds: float) -> None:
    """Poll the fal.ai queue until the request completes, fails or runs out of time."""
    deadline = time.monotonic() + float(timeout_seconds)
    last_payload: dict[str, Any] = {}
    while True:
        status_response = request_with_retries("GET", status_url, headers=headers, timeout=(15.0, 60.0))
        last_payload = response_json(status_response)
        status = str(last_payload.get("status") or "").strip().upper()
        if status == "COMPLETED":
            return
        if status in {"FAILED", "CANCELLED", "CANCELED", "ERROR"}:
            raise RuntimeError(f"fal.ai request failed with status '{status}': {last_payload}")
        if time.monotonic() >= deadline:
            raise TimeoutError(f"fal.ai request did not complete within {timeout_seconds:.0f} s: {last_payload}")
        time.sleep(_POLL_INTERVAL_SECONDS)


def _download_bytes(url: str, *, timeout_seconds: float, request_id: str) -> bytes:
    response = requests.get(url, timeout=float(timeout_seconds))
    if response.status_code >= 400:
        raise _failure(f"fal.ai audio download failed with HTTP {response.status_code}.", request_id)
    return bytes(response.content or b"")


def _billable_units(headers: Any) -> float | None:
    """What fal says it billed for the request (thousands of characters), if it says so."""
    try:
        raw = headers.get("x-fal-billable-units")
    except Exception:
        return None
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError):
        return None


def _resolve_cost(
    api_key: str,
    model: str,
    *,
    billable_units: float | None,
    characters: int,
    usd_per_million_chars: float,
) -> dict[str, Any]:
    """Billed units times fal's current unit price; the documented table when either is missing."""
    if billable_units is not None:
        try:
            pricing_response = request_with_retries(
                "GET",
                PRICING_API_URL,
                headers={"Authorization": f"Key {api_key}"},
                params={"endpoint_id": model},
                timeout=(15.0, 60.0),
            )
            prices = response_json(pricing_response).get("prices") or []
            unit_price = float(prices[0].get("unit_price"))
        except Exception:
            unit_price = None
        if unit_price is not None:
            return {
                "cost_usd": round(float(billable_units) * unit_price, 6),
                "cost_source": "pricing_api_billable_units",
                "cost_is_estimated": True,
                "cost_details": {"billable_units": billable_units, "unit_price": unit_price},
            }
    cost_usd = round((int(characters) / 1_000_000.0) * float(usd_per_million_chars), 6)
    return {
        "cost_usd": cost_usd,
        "cost_source": "official_pricing_table" if cost_usd else "unavailable",
        "cost_is_estimated": True,
        "cost_details": {},
    }


def _failure(message: str, request_id: str) -> RuntimeError:
    """A RuntimeError that keeps the fal request id, so the failure can be traced."""
    error = RuntimeError(message)
    if request_id:
        error.request_id = request_id  # type: ignore[attr-defined]
    return error


__all__ = [
    "DEFAULT_MODEL",
    "DEFAULT_VOICE",
    "DOCUMENTED_KWARGS",
    "DOCUMENTED_MODEL_METADATA",
    "MODELS_URL",
    "PRICING_URL",
    "QUEUE_URL",
    "generate",
]
