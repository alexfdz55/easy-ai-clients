"""fal.ai batch speech transcription with centralized pre/post-processing.

Implemented and validated with `teste/elevenlabs/audio.mp3` on 2026-04-22:
  - `fal-ai/elevenlabs/speech-to-text`
  - `fal-ai/elevenlabs/speech-to-text/scribe-v2`

Official references:
  - ElevenLabs on fal.ai: https://fal.ai/elevenlabs
  - Scribe v2 API page: https://fal.ai/models/fal-ai/elevenlabs/speech-to-text/scribe-v2/api
  - Pricing API: https://fal.ai/docs/platform-apis/v1/models/pricing
"""

import time
from typing import Any

from ...._submission_hooks import run_on_submitted
from .._apis._shared import (
    build_word_record,
    compute_cost_by_duration,
    get_required_api_key,
    reject_unknown_kwargs,
    request_with_retries,
    response_json,
    round_cost,
)
from ..post_processing import _build_transcription_bundle, build_raw_transcription_payload
from ..pre_processing import build_data_url, build_request_audio

DOCUMENTED_MODELS = {
    "fal-ai/elevenlabs/speech-to-text": {"label": "Scribe v1"},
    "fal-ai/elevenlabs/speech-to-text/scribe-v2": {"label": "Scribe v2"},
}
PRICING_URL = "https://api.fal.ai/v1/models/pricing"
DOCUMENTED_KWARGS = {
    "language_code",
    "tag_audio_events",
    "diarize",
    "keyterms",
    "num_speakers",
    "language_mkd",
    "timeout_seconds",
    "webhook_url",
    "on_submitted",
    "submission",
}


def transcribe(
    audio_input: Any,
    model: str = "fal-ai/elevenlabs/speech-to-text/scribe-v2",
    **kwargs: Any,
) -> dict[str, Any]:
    """Transcribe audio with fal.ai. See `transcribe/docs/falai.md`."""
    options = reject_unknown_kwargs("fal.ai", model, kwargs, DOCUMENTED_KWARGS)
    language_code = options.pop("language_code", None)
    tag_audio_events = bool(options.pop("tag_audio_events", True))
    diarize = bool(options.pop("diarize", True))
    keyterms = options.pop("keyterms", None)
    num_speakers = options.pop("num_speakers", None)
    language_mkd = options.pop("language_mkd", "en")
    timeout_seconds = float(options.pop("timeout_seconds", 300))
    webhook_url = options.pop("webhook_url", None)
    on_submitted = options.pop("on_submitted", None)
    submission = options.pop("submission", None)

    request_audio = build_request_audio(audio_input)
    api_key = get_required_api_key("FAL_KEY")
    input_payload = {
        "audio_url": build_data_url(request_audio["audio_bytes"], request_audio["content_type"]),
        "tag_audio_events": tag_audio_events,
        "diarize": diarize,
    }
    if language_code:
        input_payload["language_code"] = language_code
    if keyterms:
        input_payload["keyterms"] = list(keyterms)
    if num_speakers is not None:
        input_payload["num_speakers"] = int(num_speakers)
    input_payload.update({key: value for key, value in options.items() if value is not None})

    if submission is not None:
        if not isinstance(submission, dict):
            raise TypeError("submission must be a dictionary when provided.")
        submit_payload = dict(submission)
    else:
        request_params = {}
        webhook = str(webhook_url or "").strip()
        if webhook:
            request_params["fal_webhook"] = webhook
        submit_response = request_with_retries(
            "POST",
            f"https://queue.fal.run/{model}",
            headers={
                "Authorization": f"Key {api_key}",
                "Content-Type": "application/json",
            },
            params=request_params or None,
            json_body=input_payload,
            timeout=(15.0, float(timeout_seconds)),
        )
        submit_payload = response_json(submit_response)
        run_on_submitted(on_submitted, submit_payload)

    status_url = str(submit_payload.get("status_url") or "").strip()
    response_url = str(submit_payload.get("response_url") or "").strip()
    if not status_url or not response_url:
        raise ValueError("fal.ai queue response did not include status_url/response_url.")

    _wait_for_fal_completion(api_key, status_url)

    final_response = request_with_retries(
        "GET",
        response_url,
        headers={"Authorization": f"Key {api_key}"},
        timeout=(15.0, 120.0),
    )
    payload = response_json(final_response)

    words = []
    audio_events = []
    for word_payload in payload.get("words") or []:
        item_type = str(word_payload.get("type") or "word").strip().lower()
        if item_type == "spacing":
            continue
        if item_type == "audio_event":
            audio_events.append(
                {
                    "text": str(word_payload.get("text") or "").strip(),
                    "start": word_payload.get("start"),
                    "end": word_payload.get("end"),
                }
            )
            continue

        normalized_word = build_word_record(
            word_payload.get("text"),
            word_payload.get("start"),
            word_payload.get("end"),
            speaker=word_payload.get("speaker_id") or word_payload.get("speaker"),
        )
        if normalized_word:
            words.append(normalized_word)

    raw_payload = build_raw_transcription_payload(
        provider="falai",
        model=model,
        audio_duration_seconds=request_audio["audio_duration_seconds"],
        language=language_code or payload.get("language_code"),
        language_confidence=payload.get("language_probability"),
        text=payload.get("text"),
        words=words,
        provider_metadata={
            "audio_events": audio_events,
            "language_probability": payload.get("language_probability"),
            "provider_language_code": payload.get("language_code"),
            "queue_request_id": submit_payload.get("request_id"),
        },
    )
    cost_metadata = _resolve_fal_cost_metadata(
        api_key,
        model,
        request_audio["audio_duration_seconds"],
        final_response.headers.get("X-Fal-Billable-Units"),
        keyterms=keyterms,
    )
    return _build_transcription_bundle(
        raw_payload,
        language_mkd=language_mkd,
        request_id=submit_payload.get("request_id"),
        **cost_metadata,
    )


def _resolve_fal_cost_metadata(
    api_key,
    model,
    audio_duration_seconds,
    billable_units_header=None,
    *,
    keyterms=None,
):
    """Resolves fal.ai cost metadata using the official pricing API."""
    try:
        pricing_response = request_with_retries(
            "GET",
            PRICING_URL,
            headers={"Authorization": f"Key {api_key}"},
            params={"endpoint_id": model},
            timeout=(15.0, 60.0),
        )
        pricing_payload = response_json(pricing_response)
    except Exception as error:
        return {
            "cost_usd": 0.0,
            "cost_source": "unavailable",
            "cost_is_estimated": False,
            "cost_lookup_error": f"fal.ai pricing lookup failed: {error}",
        }

    prices = pricing_payload.get("prices") or []
    if not prices:
        return {
            "cost_usd": 0.0,
            "cost_source": "unavailable",
            "cost_is_estimated": False,
            "cost_lookup_error": "fal.ai pricing API did not return a price for this endpoint.",
        }

    price_payload = prices[0]
    try:
        unit_price = float(price_payload.get("unit_price"))
    except (TypeError, ValueError):
        return {
            "cost_usd": 0.0,
            "cost_source": "unavailable",
            "cost_is_estimated": False,
            "cost_lookup_error": "fal.ai pricing API returned an invalid unit_price for this endpoint.",
        }
    if keyterms and model == "fal-ai/elevenlabs/speech-to-text/scribe-v2":
        unit_price *= 1.3
    unit_name = str(price_payload.get("unit") or "minutes").strip().lower()

    try:
        if billable_units_header not in (None, ""):
            return {
                "cost_usd": round_cost(float(billable_units_header) * unit_price),
                "cost_source": "pricing_api_billable_units",
                "cost_is_estimated": True,
                "cost_lookup_error": None,
            }
    except Exception:
        pass

    billing_unit = "hour" if unit_name.startswith("hour") else "minute"
    return {
        "cost_usd": compute_cost_by_duration(
            audio_duration_seconds,
            unit_price=unit_price,
            billing_unit=billing_unit,
        ),
        "cost_source": "pricing_api",
        "cost_is_estimated": True,
        "cost_lookup_error": None,
    }


def _wait_for_fal_completion(api_key, status_url, max_polls=80, poll_interval_seconds=1.5):
    """Polls the fal.ai queue until the request completes or fails."""
    last_payload = {}
    for _ in range(int(max_polls)):
        status_response = request_with_retries(
            "GET",
            status_url,
            headers={"Authorization": f"Key {api_key}"},
            timeout=(15.0, 120.0),
        )
        last_payload = response_json(status_response)
        normalized_status = str(last_payload.get("status") or "").strip().upper()
        if normalized_status == "COMPLETED":
            return last_payload
        if normalized_status in {"FAILED", "CANCELLED", "CANCELED"}:
            raise RuntimeError(f"fal.ai request failed with status '{normalized_status}': {last_payload}")
        time.sleep(float(poll_interval_seconds))

    raise TimeoutError(f"fal.ai request did not complete within the polling window: {last_payload}")
