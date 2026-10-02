"""Offline tests: a failed call says why, and ElevenLabs voices can be asked through fal.

An unpaid invoice on the provider's account used to look like any other failure
(`Failed to synthesize ElevenLabs chunk 1`). These tests pin down that the HTTP status,
the provider's own code and message and the `account` category survive, and that the
fal.ai speech adapter returns the same word timings as the direct one.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
import requests

PAYMENT_BODY = json.dumps(
    {
        "detail": {
            "type": "payment_required",
            "code": "payment_issue",
            "message": "Your subscription has a failed or incomplete payment.",
            "status": "payment_issue",
        }
    }
)


def _http_error(status: int, body: str, headers: dict | None = None) -> requests.HTTPError:
    response = SimpleNamespace(status_code=status, text=body, headers=headers or {})
    return requests.HTTPError(f"HTTP {status} during API request. body={body}", response=response)


def test_a_wrapped_http_failure_keeps_its_status_and_the_providers_words():
    from easy_ai_clients._error_utils import build_error

    try:
        try:
            raise _http_error(401, PAYMENT_BODY)
        except requests.HTTPError as low_level:
            raise RuntimeError("Failed to synthesize ElevenLabs chunk 1") from low_level
    except RuntimeError as wrapped:
        error = build_error(wrapped, provider="elevenlabs", operation="generate", model="m")

    assert error["http_status"] == 401
    assert error["provider_code"] == "payment_issue"
    assert error["provider_message"] == "Your subscription has a failed or incomplete payment."
    assert error["category"] == "account"


@pytest.mark.parametrize("status", [401, 402, 403])
def test_the_account_statuses_are_the_ones_a_retry_cannot_fix(status):
    from easy_ai_clients._error_utils import http_failure_of

    assert http_failure_of(_http_error(status, ""))["category"] == "account"


@pytest.mark.parametrize("status", [400, 404, 422, 429, 500, 503])
def test_other_statuses_carry_no_category(status):
    from easy_ai_clients._error_utils import http_failure_of

    failure = http_failure_of(_http_error(status, ""))

    assert failure == {"http_status": status}


def test_the_providers_code_and_message_are_read_from_each_body_shape():
    from easy_ai_clients._error_utils import http_failure_of

    fal_body = json.dumps({"detail": [{"msg": "Voice not found: X", "type": "feature_not_supported"}]})
    openai_body = json.dumps({"error": {"message": "You exceeded your quota.", "code": "insufficient_quota"}})

    fal = http_failure_of(_http_error(422, fal_body))
    openai = http_failure_of(_http_error(429, openai_body))
    plain = http_failure_of(_http_error(403, "User is locked. Reason: Exhausted balance."))

    assert (fal["provider_code"], fal["provider_message"]) == ("feature_not_supported", "Voice not found: X")
    assert (openai["provider_code"], openai["provider_message"]) == ("insufficient_quota", "You exceeded your quota.")
    assert "provider_code" not in plain
    assert plain["provider_message"] == "User is locked. Reason: Exhausted balance."
    assert plain["category"] == "account"


def test_classes_that_carry_the_status_themselves_are_read_too():
    from easy_ai_clients._error_utils import http_failure_of

    error = RuntimeError("provider said no")
    error.status_code = 402
    error.response_text = json.dumps({"error": {"type": "billing", "message": "Add credits."}})

    assert http_failure_of(error) == {
        "http_status": 402,
        "provider_code": "billing",
        "provider_message": "Add credits.",
        "category": "account",
    }


def test_an_unpaid_elevenlabs_account_is_reported_as_such(monkeypatch):
    from easy_ai_clients import audio
    from easy_ai_clients.audio._synthesize._apis import elevenlabs

    def refuse(*args, **kwargs):
        raise _http_error(401, PAYMENT_BODY, headers={"request-id": "tts-401"})

    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setattr(elevenlabs, "request_with_retries", refuse)

    result = audio.generate("Hola, mundo.", api="elevenlabs", model="eleven_v4_turbo", voice="v1")

    error = result["error"]
    assert result["audio"] is None
    assert error["type"] == "RuntimeError"
    assert error["http_status"] == 401
    assert error["provider_code"] == "payment_issue"
    assert error["category"] == "account"
    assert error["request_id"] == "tts-401"
    assert "HTTP 401 during API request" in error["message"]


def test_the_v4_models_are_documented_with_their_price():
    from easy_ai_clients.audio._synthesize._apis.elevenlabs import DOCUMENTED_MODEL_METADATA

    assert DOCUMENTED_MODEL_METADATA["eleven_v4"]["usd_per_million_chars"] == 80.0
    assert DOCUMENTED_MODEL_METADATA["eleven_v4_turbo"]["usd_per_million_chars"] == 40.0
    assert DOCUMENTED_MODEL_METADATA["eleven_multilingual_v2"]["usd_per_million_chars"] == 80.0


# --- fal.ai speech -----------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, payload=None, *, headers=None):
        self._payload = payload or {}
        self.headers = headers or {}
        self.text = json.dumps(self._payload)
        self.content = self.text.encode("utf-8")

    def json(self):
        return self._payload


def _fal_transport(captured, *, timestamps, result_error=None, billable="0.012"):
    def fake_request(method, url, **kwargs):
        captured.append((method, url, kwargs.get("json_body")))
        if url.startswith("https://queue.fal.run/") and method == "POST":
            return _FakeResponse(
                {
                    "request_id": f"fal-{len([c for c in captured if c[0] == 'POST'])}",
                    "status_url": "https://queue.fal.run/status",
                    "response_url": "https://queue.fal.run/result",
                }
            )
        if url.endswith("/status"):
            return _FakeResponse({"status": "COMPLETED"})
        if url.endswith("/result"):
            if result_error is not None:
                raise result_error
            return _FakeResponse(
                {"audio": {"url": "https://fal.media/out.mp3"}, "timestamps": timestamps},
                headers={"x-fal-billable-units": billable},
            )
        if url.startswith("https://api.fal.ai/v1/models/pricing"):
            return _FakeResponse({"prices": [{"unit_price": 0.04, "unit": "1000 characters"}]})
        raise AssertionError(f"unexpected request: {method} {url}")

    return fake_request


HOLA_MUNDO = [
    {"characters": [], "character_start_times_seconds": [], "character_end_times_seconds": []},
    {
        "characters": list("Hola "),
        "character_start_times_seconds": [0.0, 0.1, 0.2, 0.3, 0.4],
        "character_end_times_seconds": [0.1, 0.2, 0.3, 0.4, 0.5],
    },
    {
        "characters": list("mundo."),
        "character_start_times_seconds": [0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
        "character_end_times_seconds": [0.6, 0.7, 0.8, 0.9, 1.0, 1.1],
    },
]


def _patch_fal(monkeypatch, transport):
    from easy_ai_clients.audio._synthesize._apis import falai

    finalized = {}

    def fake_finalize(records, cost_usd):
        finalized["records"] = records
        return {
            "cost_usd": cost_usd,
            "cost_currency": "USD",
            "cost_source": "official_pricing_table",
            "cost_is_estimated": True,
            "cost_details": {},
            "audio": object(),
            "words": {},
        }

    monkeypatch.setenv("FAL_KEY", "fal-test-key")
    monkeypatch.setattr(falai, "request_with_retries", transport)
    monkeypatch.setattr(falai, "_download_bytes", lambda url, **kwargs: b"mp3-bytes")
    monkeypatch.setattr(falai, "_finalize_synthesis_output", fake_finalize)
    monkeypatch.setattr(falai, "_POLL_INTERVAL_SECONDS", 0.0)
    return finalized


def test_fal_speech_asks_for_the_voice_with_timestamps_and_joins_the_blocks(monkeypatch):
    from easy_ai_clients import audio

    captured = []
    finalized = _patch_fal(monkeypatch, _fal_transport(captured, timestamps=HOLA_MUNDO))

    result = audio.generate(
        "Hola mundo.",
        api="falai",
        model="elevenlabs/tts/eleven-v4-turbo",
        voice="15bJsujCI3tcDWeoZsQP",
        language_code="es",
        output_format="mp3_44100_128",
    )

    assert "error" not in result
    method, url, payload = captured[0]
    assert (method, url) == ("POST", "https://queue.fal.run/elevenlabs/tts/eleven-v4-turbo")
    assert payload == {
        "text": "Hola mundo.",
        "voice": "15bJsujCI3tcDWeoZsQP",
        "timestamps": True,
        "output_format": "mp3_44100_128",
        "language_code": "es",
    }
    record = finalized["records"][0]
    assert record["audio_bytes"] == b"mp3-bytes"
    assert record["audio_format"] == "mp3"
    alignment = record["char_alignment"]
    assert "".join(alignment["characters"]) == "Hola mundo."
    assert alignment["character_start_times_seconds"][5] == 0.5
    assert alignment["unit"] == "seconds"
    assert result["provider"] == "falai"
    assert result["request_id"] == "fal-1"
    assert result["request_ids"] == ["fal-1"]
    # 0,012 miles de caracteres facturados × 0,04 USD
    assert result["cost_usd"] == pytest.approx(0.00048)
    assert result["cost_source"] == "pricing_api_billable_units"


def test_fal_speech_words_match_the_direct_adapter_for_the_same_timings():
    """Same characters, same times: the scenes are re-timed by word index, so the
    tokenization must not depend on the route the voice took."""
    from easy_ai_clients.audio._synthesize._apis.falai import _char_alignment
    from easy_ai_clients.audio._synthesize.post_processing import _words_from_char_alignment

    joined = _char_alignment(HOLA_MUNDO)
    direct = {
        "characters": list("Hola mundo."),
        "character_start_times_seconds": joined["character_start_times_seconds"],
        "character_end_times_seconds": joined["character_end_times_seconds"],
    }
    keys = {"start_key": "character_start_times_seconds", "end_key": "character_end_times_seconds", "unit": "seconds"}

    assert joined["characters"] == direct["characters"]
    assert _words_from_char_alignment({"text": "Hola mundo.", **joined, **keys}) == _words_from_char_alignment(
        {"text": "Hola mundo.", **direct, **keys}
    )


def test_fal_speech_without_timestamps_fails_instead_of_guessing(monkeypatch):
    from easy_ai_clients import audio

    captured = []
    _patch_fal(monkeypatch, _fal_transport(captured, timestamps=None))

    result = audio.generate("Hola mundo.", api="falai", voice="v1")

    assert result["audio"] is None
    assert "usable timestamps" in result["error"]["message"]
    assert result["error"]["request_id"] == "fal-1"


def test_fal_speech_reports_an_unknown_voice_with_the_providers_reason(monkeypatch):
    from easy_ai_clients import audio

    body = json.dumps({"detail": [{"loc": ["body", "voice"], "msg": "Voice not found: nope", "type": "feature_not_supported"}]})
    captured = []
    _patch_fal(monkeypatch, _fal_transport(captured, timestamps=HOLA_MUNDO, result_error=_http_error(422, body)))

    result = audio.generate("Hola mundo.", api="falai", voice="nope")

    error = result["error"]
    assert error["http_status"] == 422
    assert error["provider_code"] == "feature_not_supported"
    assert error["provider_message"] == "Voice not found: nope"
    assert "category" not in error
    assert error["request_id"] == "fal-1"


def test_fal_speech_falls_back_to_the_documented_price_without_billed_units(monkeypatch):
    from easy_ai_clients import audio

    captured = []
    _patch_fal(monkeypatch, _fal_transport(captured, timestamps=HOLA_MUNDO, billable=""))

    result = audio.generate("Hola mundo.", api="falai", voice="v1")

    # 11 caracteres a 40 USD por millón
    assert result["cost_usd"] == pytest.approx(0.00044)
    assert result["cost_source"] == "official_pricing_table"
