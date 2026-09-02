"""Music provider contract tests without live provider calls."""

from __future__ import annotations

import base64
import inspect
import os
import time
from pathlib import Path

import pytest

PUBLIC_GENERATION_KEYS = {
    "provider",
    "model",
    "model_key",
    "status",
    "request_id",
    "output_path",
    "cost_usd",
    "cost_currency",
    "cost_source",
    "cost_is_estimated",
    "cost_details",
    "metadata",
}


@pytest.fixture(autouse=True)
def block_requests_network(monkeypatch):
    import requests

    def blocked(*args, **kwargs):
        raise AssertionError("network calls are disabled in music unit tests")

    monkeypatch.setattr(requests, "request", blocked)
    monkeypatch.setattr(requests, "get", blocked)
    monkeypatch.setattr(requests, "post", blocked)


def test_active_provider_and_model_matrix_is_explicit():
    from easy_ai_clients.music._apis import deapi, elevenlabs, google, kie, runware
    from easy_ai_clients.music._model_registry import PROVIDERS

    assert PROVIDERS == ("deapi", "elevenlabs", "google", "kie", "runware")
    assert set(deapi.MODELS) == {"AceStep_1_5_Turbo", "AceStep_1_5_XL_Turbo_INT8"}
    assert set(elevenlabs.MODELS) == {"music_v2"}
    assert set(google.MODELS) == {"lyria-3-clip-preview", "lyria-3-pro-preview"}
    assert set(kie.MODELS) == {"V5_5"}
    assert set(runware.MODELS) == {
        "runware:ace-step@v1.5-turbo",
        "runware:ace-step@v1.5-xl-base",
        "runware:ace-step@v1.5-xl-turbo",
        "runware:ace-step@v1.5-xl-sft",
    }


def test_provider_generate_signatures_use_kwargs_contract():
    import importlib

    from easy_ai_clients.music._model_registry import PROVIDERS

    for provider in PROVIDERS:
        module = importlib.import_module(f"easy_ai_clients.music._apis.{provider}")
        signature = inspect.signature(module.generate)

        assert "lyrics" in signature.parameters
        assert "model" in signature.parameters
        assert "kwargs" in signature.parameters
        assert "prompt" not in signature.parameters
        assert "negative_prompt" not in signature.parameters
        assert signature.parameters["kwargs"].kind == inspect.Parameter.VAR_KEYWORD


def test_standard_generation_uses_public_schema():
    from easy_ai_clients.music._common import standard_generation

    generation = standard_generation(
        provider="runware",
        model="runware:ace-step@v1.5-xl-turbo",
        request_id="req_123",
    )

    assert set(generation) == PUBLIC_GENERATION_KEYS
    assert generation["model_key"] == "ace_step_v1_5_xl_turbo"
    assert generation["output_path"] is None
    assert generation["cost_usd"] == 0.0
    assert generation["cost_currency"] == "USD"
    assert generation["cost_source"] == "unavailable"
    assert generation["cost_is_estimated"] is False
    assert generation["cost_details"] == {}
    assert generation["metadata"] == {}


def test_wrappers_reject_removed_public_parameters_before_network():
    from easy_ai_clients.music._apis import deapi, elevenlabs, google, kie, runware

    cases = [
        (deapi, {"output_format": "mp3"}, "Unsupported kwargs"),
        (deapi, {"seed": -1}, "Unsupported kwargs"),
        (elevenlabs, {"output_format": "mp3_44100_128"}, "Unsupported kwargs"),
        (elevenlabs, {"_force_instrumental": True}, "Unsupported kwargs"),
        (google, {"output_format": "mp3"}, "Unsupported kwargs"),
        (kie, {"output_format": "mp3"}, "Unsupported kwargs"),
        (runware, {"output_type": "URL"}, "Unsupported kwargs"),
        (runware, {"include_cost": True}, "Unsupported kwargs"),
        (runware, {"seed": 12345}, "Unsupported kwargs"),
        (deapi, {"negative_prompt": None}, "not supported"),
        (elevenlabs, {"negative_prompt": None}, "not supported"),
        (google, {"negative_prompt": None}, "not supported"),
        (kie, {"negative_prompt": None}, "not supported"),
        (runware, {"negative_prompt": None}, "not supported"),
    ]

    for module, extra, pattern in cases:
        with pytest.raises(ValueError, match=pattern):
            module.generate(
                lyrics="Minha letra tem mais de dez caracteres.",
                prompt="Brazilian gospel with expressive vocal.",
                **extra,
            )


def test_duration_normalization_accepts_numbers_and_treats_invalid_as_absent():
    from easy_ai_clients.music._common import normalize_duration

    assert normalize_duration(75, 10, 300, default=60) == 75
    assert normalize_duration(75.9, 10, 300, default=60) == 75
    assert normalize_duration("75.9", 10, 300, default=60) == 75
    assert normalize_duration(999, 10, 300, default=60) == 300
    assert normalize_duration(1, 10, 300, default=60) == 10
    assert normalize_duration("abc", 10, 300, default=60) == 60
    assert normalize_duration("", 10, 300, default=None) is None
    assert normalize_duration(True, 10, 300, default=60) == 60


def test_runware_rejects_negative_prompt_for_all_models():
    from easy_ai_clients.music._apis import runware

    with pytest.raises(ValueError, match="negative_prompt is not supported"):
        runware.generate(
            lyrics="Minha letra tem mais de dez caracteres.",
            model="runware:ace-step@v1.5-xl-sft",
            prompt="Brazilian gospel with expressive vocal.",
            negative_prompt="avoid spoken word",
        )


@pytest.mark.parametrize(
    ("duration", "expected"),
    [
        (None, 60),
        ("abc", 60),
        (True, 60),
        (999, 300),
        (1, 10),
        ("75.9", 75),
    ],
)
def test_deapi_duration_is_normalized_before_payload(monkeypatch, duration, expected):
    from easy_ai_clients.music._apis import deapi

    captured = {}

    def fake_request_json(method, url, headers=None, json_payload=None, data=None, files=None, timeout=None):
        captured["payload"] = json_payload or data
        return {"data": {"request_id": "req-1", "status": "pending"}}

    monkeypatch.setattr(deapi, "_headers", lambda: {"Authorization": "Bearer fake"})
    monkeypatch.setattr(deapi, "request_json", fake_request_json)
    monkeypatch.setattr(deapi, "_calculate_cost", lambda data: None)

    kwargs = {
        "lyrics": "Minha letra tem mais de dez caracteres.",
        "model": "AceStep_1_5_Turbo",
        "prompt": "Brazilian gospel with expressive vocal.",
    }
    if duration is not None:
        kwargs["duration"] = duration

    deapi.generate(**kwargs)

    assert captured["payload"]["duration"] == expected


@pytest.mark.parametrize(
    ("duration", "expected_duration", "expected_steps"),
    [
        (None, 60, 10),
        ("abc", 60, 10),
        (999, 300, 10),
        (1, 30, 10),
        ("75.9", 75, 10),
    ],
)
def test_runware_duration_and_default_steps_are_sent(
    monkeypatch,
    duration,
    expected_duration,
    expected_steps,
):
    from easy_ai_clients.music._apis import runware

    captured = {}

    def fake_request_json(method, url, headers=None, json_payload=None, timeout=None):
        captured["payload"] = json_payload[0]
        return {"data": [{"taskUUID": "task-1", "status": "submitted"}]}

    monkeypatch.setattr(runware, "_headers", lambda: {"Authorization": "Bearer fake"})
    monkeypatch.setattr(runware, "request_json", fake_request_json)

    kwargs = {
        "lyrics": "Minha letra tem mais de dez caracteres.",
        "model": "runware:ace-step@v1.5-turbo",
        "prompt": "Brazilian gospel with expressive vocal.",
    }
    if duration is not None:
        kwargs["duration"] = duration

    runware.generate(**kwargs)

    assert captured["payload"]["duration"] == expected_duration
    assert captured["payload"]["steps"] == expected_steps


@pytest.mark.parametrize(
    ("duration", "expected_ms"),
    [
        (None, None),
        ("abc", None),
        (999, 600000),
        (1, 3000),
        ("75.9", 75000),
    ],
)
def test_elevenlabs_duration_is_optional_and_clamped(
    monkeypatch,
    tmp_path,
    duration,
    expected_ms,
):
    from easy_ai_clients.music._apis import elevenlabs

    captured = {}

    def fake_post(*args, **kwargs):
        captured["payload"] = kwargs["json"]
        captured["params"] = kwargs["params"]
        return _fake_response(200, "audio/mpeg", b"ID3audio")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(elevenlabs, "_headers", lambda: {"xi-api-key": "fake"})
    monkeypatch.setattr(elevenlabs.requests, "post", fake_post)

    kwargs = {
        "lyrics": "Minha letra tem mais de dez caracteres.",
        "prompt": "short acoustic music",
    }
    if duration is not None:
        kwargs["duration"] = duration

    generation = elevenlabs.generate(**kwargs)
    _wait_for_local_status(generation["request_id"], "completed")

    if expected_ms is None:
        assert "music_length_ms" not in captured["payload"]
    else:
        assert captured["payload"]["music_length_ms"] == expected_ms
    assert captured["payload"]["model_id"] == "music_v2"
    assert captured["params"] == {"output_format": "auto"}
    assert "composition_plan" not in captured["payload"]
    assert "force_instrumental" not in captured["payload"]


@pytest.mark.parametrize(
    ("model", "duration", "has_duration_phrase"),
    [
        ("lyria-3-clip-preview", 120, False),
        ("lyria-3-pro-preview", 75, True),
        ("lyria-3-pro-preview", "abc", False),
    ],
)
def test_google_duration_and_count_tokens_preflight(
    monkeypatch,
    tmp_path,
    model,
    duration,
    has_duration_phrase,
):
    from easy_ai_clients.music._apis import google

    captured = []
    payload = base64.b64encode(b"audio-bytes").decode()

    def fake_request_json(method, url, headers=None, json_payload=None, timeout=None):
        captured.append((url, json_payload))
        if url.endswith(":countTokens"):
            return {"totalTokens": 100}
        return {"candidates": [{"content": {"parts": [{"inlineData": {"data": payload}}]}}]}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(google, "_headers", lambda: {"x-goog-api-key": "fake"})
    monkeypatch.setattr(google, "request_json", fake_request_json)

    generation = google.generate(
        lyrics="Minha letra tem mais de dez caracteres.",
        model=model,
        prompt="short acoustic music",
        duration=duration,
    )
    _wait_for_local_status(generation["request_id"], "completed")

    count_payload = captured[0][1]
    prompt_text = count_payload["contents"][0]["parts"][0]["text"]
    assert captured[0][0].endswith(":countTokens")
    assert captured[1][0].endswith(":generateContent")
    assert ("Target song duration: about 1 minute and 15 seconds." in prompt_text) is (
        has_duration_phrase
    )


def test_google_count_tokens_over_limit_raises_public_exception(monkeypatch):
    from easy_ai_clients.music import MusicInputLimitError
    from easy_ai_clients.music._apis import google

    def fake_request_json(method, url, headers=None, json_payload=None, timeout=None):
        assert url.endswith(":countTokens")
        return {"totalTokens": 131073}

    monkeypatch.setattr(google, "_headers", lambda: {"x-goog-api-key": "fake"})
    monkeypatch.setattr(google, "request_json", fake_request_json)

    with pytest.raises(MusicInputLimitError) as exc_info:
        google.generate(
            lyrics="Minha letra tem mais de dez caracteres.",
            model="lyria-3-pro-preview",
            prompt="short acoustic music",
        )

    data = exc_info.value.to_dict()
    assert data["provider"] == "google"
    assert data["model_key"] == "lyria_3_pro_preview"
    assert data["fields"]["contents"]["unit"] == "tokens"
    assert data["fields"]["contents"]["maximum"] == 131072
    assert data["fields"]["contents"]["observed"] == 131073
    assert exc_info.value.repair_prompts["contents"]


@pytest.mark.parametrize(
    ("provider_name", "field"),
    [
        ("deapi", "caption"),
        ("runware", "positivePrompt"),
    ],
)
def test_character_input_limits_raise_public_exception(monkeypatch, provider_name, field):
    from easy_ai_clients.music import MusicInputLimitError
    from easy_ai_clients.music._apis import deapi, runware

    module = {"deapi": deapi, "runware": runware}[provider_name]
    monkeypatch.setattr(module, "_headers", lambda: {"Authorization": "Bearer fake"})

    with pytest.raises(MusicInputLimitError) as exc_info:
        module.generate(
            lyrics="Minha letra tem mais de dez caracteres.",
            prompt="x" * 3001,
        )

    data = exc_info.value.to_dict()
    assert data["provider"] == provider_name
    assert data["fields"][field]["maximum"] == 3000
    assert data["fields"][field]["observed"] == 3001
    assert field in exc_info.value.repair_prompts


def test_elevenlabs_prompt_limit_raises_public_exception(monkeypatch):
    from easy_ai_clients.music import MusicInputLimitError
    from easy_ai_clients.music._apis import elevenlabs

    monkeypatch.setattr(elevenlabs, "_headers", lambda: {"xi-api-key": "fake"})

    with pytest.raises(MusicInputLimitError) as exc_info:
        elevenlabs.generate(
            lyrics="y" * 1000,
            prompt="x" * 4100,
        )

    data = exc_info.value.to_dict()
    assert data["provider"] == "elevenlabs"
    assert data["fields"]["prompt"]["maximum"] == 4100
    assert data["fields"]["prompt"]["observed"] > 4100


def test_model_registry_resolves_standard_keys_and_defaults():
    from easy_ai_clients.music._model_registry import MODEL_ALIASES, resolve_model

    cases = [
        ("deapi", "ace_step_v1_5_turbo", "AceStep_1_5_Turbo"),
        ("deapi", "ace_step_1_5_xl_turbo_int8", "AceStep_1_5_XL_Turbo_INT8"),
        ("elevenlabs", "eleven_music", "music_v2"),
        ("elevenlabs", "eleven_music_v2", "music_v2"),
        ("elevenlabs", "music_v2", "music_v2"),
        ("google", "lyria_3_clip_preview", "lyria-3-clip-preview"),
        ("google", "lyria_3_pro_preview", "lyria-3-pro-preview"),
        ("kie", "suno_v5_5", "V5_5"),
        ("kie", "V5_5", "V5_5"),
        ("runware", "ace_step_v1_5_turbo", "runware:ace-step@v1.5-turbo"),
        ("runware", "ace_step_v1_5_xl_base", "runware:ace-step@v1.5-xl-base"),
        ("runware", "ace_step_v1_5_xl_sft", "runware:ace-step@v1.5-xl-sft"),
        ("runware", "ace_step_v1_5_xl_turbo", "runware:ace-step@v1.5-xl-turbo"),
    ]

    for provider, model_key, native_model in cases:
        assert resolve_model(provider, model_key) == (native_model, model_key)
        if native_model not in MODEL_ALIASES[provider] or native_model == model_key:
            assert resolve_model(provider, native_model) == (native_model, model_key)

    assert resolve_model("deapi", None) == ("AceStep_1_5_Turbo", "ace_step_v1_5_turbo")
    assert resolve_model("elevenlabs", None) == ("music_v2", "eleven_music")
    assert resolve_model("google", None) == (
        "lyria-3-clip-preview",
        "lyria_3_clip_preview",
    )
    assert resolve_model("kie", None) == ("V5_5", "suno_v5_5")
    assert resolve_model("runware", None) == (
        "runware:ace-step@v1.5-xl-turbo",
        "ace_step_v1_5_xl_turbo",
    )

    with pytest.raises(ValueError, match="Unsupported model for elevenlabs"):
        resolve_model("elevenlabs", "music_v1")


def test_local_job_helpers_update_and_clear_completed_jobs(tmp_path, monkeypatch):
    from easy_ai_clients.music._common import (
        complete_local_job_generation,
        get_local_job,
        start_local_job,
        update_local_job_generation,
    )

    monkeypatch.chdir(tmp_path)

    def worker(output_path):
        return None

    generation = start_local_job("google", "lyria-3-clip-preview", worker)
    _wait_for_local_status(generation["request_id"], "completed")

    update_local_job_generation(generation)
    assert generation["status"] == "completed"
    assert generation["output_path"].endswith(".mp3")
    assert str(tmp_path / "outputs" / "music" / "temp") in generation["output_path"]

    complete_local_job_generation(generation)
    with pytest.raises(KeyError):
        get_local_job(generation["request_id"])


def test_common_http_error_formatting_redacts_env_secret(monkeypatch):
    from easy_ai_clients.music._common import format_response_error

    monkeypatch.setenv("MUSIC_TEST_API_KEY", "secret-token")

    class Response:
        status_code = 500
        url = "https://example.test/music"
        text = ""

        def json(self):
            return {"error": "Authorization failed for secret-token"}

    message = format_response_error(Response())

    assert "HTTP 500 from https://example.test/music" in message
    assert "secret-token" not in message
    assert "<redacted>" in message


def test_common_http_error_formatting_redacts_url_query():
    from easy_ai_clients.music._common import format_response_error

    class Response:
        status_code = 500
        url = "https://example.test/music?token=query-secret"
        text = ""

        def json(self):
            return {
                "audio_url": "https://example.test/audio.mp3?signature=signed-secret",
            }

    message = format_response_error(Response())

    assert "https://example.test/music?<redacted>" in message
    assert "query-secret" not in message
    assert "signed-secret" not in message
    assert "<redacted-url>" in message


def test_runware_provider_error_message_is_sanitized(monkeypatch):
    from easy_ai_clients.music._apis import runware

    def fake_request_json(method, url, headers=None, json_payload=None, timeout=None):
        return {
            "errors": [
                {
                    "status": "error",
                    "message": (
                        "failed for secret-token at "
                        "https://example.test/audio.mp3?token=query-secret"
                    ),
                }
            ]
        }

    monkeypatch.setenv("RUNWARE_API_KEY", "secret-token")
    monkeypatch.setattr(runware, "_headers", lambda: {"Authorization": "Bearer secret-token"})
    monkeypatch.setattr(runware, "request_json", fake_request_json)

    with pytest.raises(RuntimeError) as exc_info:
        runware.generate(
            lyrics="Minha letra tem mais de dez caracteres.",
            prompt="Brazilian gospel with expressive vocal.",
        )

    message = str(exc_info.value)
    assert "secret-token" not in message
    assert "query-secret" not in message
    assert "https://example.test/audio.mp3" not in message
    assert "<redacted-url>" in message


def test_google_inline_audio_accepts_camel_and_snake_case_payloads():
    from easy_ai_clients.music._apis import google

    payload = base64.b64encode(b"audio-bytes").decode()

    assert (
        google._inline_audio(  # noqa: SLF001
            {"candidates": [{"content": {"parts": [{"inlineData": {"data": payload}}]}}]}
        )
        == b"audio-bytes"
    )
    assert (
        google._inline_audio(  # noqa: SLF001
            {"candidates": [{"content": {"parts": [{"inline_data": {"data": payload}}]}}]}
        )
        == b"audio-bytes"
    )


@pytest.mark.parametrize(
    ("response", "pattern"),
    [
        ({"promptFeedback": {"blockReason": "SAFETY"}}, "promptFeedback"),
        ({"candidates": []}, "usable inline audio"),
        (
            {"candidates": [{"finishReason": "SAFETY", "finishMessage": "blocked"}]},
            "SAFETY",
        ),
        ({"candidates": [{"content": {"parts": [{"text": "lyrics only"}]}}]}, "text"),
    ],
)
def test_google_inline_audio_rejects_responses_without_audio(response, pattern):
    from easy_ai_clients.music._apis import google

    with pytest.raises(RuntimeError, match=pattern):
        google._inline_audio(response)  # noqa: SLF001


def test_google_inline_audio_rejects_invalid_base64():
    from easy_ai_clients.music._apis import google

    with pytest.raises(RuntimeError, match="invalid inline audio"):
        google._inline_audio(  # noqa: SLF001
            {"candidates": [{"content": {"parts": [{"inlineData": {"data": "not-base64!"}}]}}]}
        )


def test_local_job_error_message_includes_sanitized_context(monkeypatch, tmp_path):
    from easy_ai_clients import music
    from easy_ai_clients.music._common import LocalJobError, start_local_job

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MUSIC_TEST_API_KEY", "secret-token")

    def worker(output_path):
        raise KeyError("candidates secret-token https://example.test/audio.mp3?token=query-secret")

    generation = start_local_job("google", "lyria-3-clip-preview", worker)
    _wait_for_local_status(generation["request_id"], "failed")

    with pytest.raises(LocalJobError) as exc_info:
        music.get_status(generation)

    message = str(exc_info.value)
    assert "provider=google" in message
    assert "model=lyria-3-clip-preview" in message
    assert generation["request_id"] in message
    assert "KeyError" in message
    assert "candidates" in message
    assert "secret-token" not in message
    assert "query-secret" not in message
    assert "<redacted-url>" in message


@pytest.mark.parametrize(
    ("content_type", "content"),
    [
        ("application/json", b'{"error":"not audio"}'),
        ("text/html", b"<html>not audio</html>"),
        ("audio/mpeg", b""),
    ],
)
def test_elevenlabs_rejects_non_audio_or_empty_2xx_responses(
    monkeypatch,
    tmp_path,
    content_type,
    content,
):
    from easy_ai_clients.music._apis import elevenlabs
    from easy_ai_clients.music._common import LocalJobError, get_local_job

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(elevenlabs, "_headers", lambda: {"xi-api-key": "fake"})
    monkeypatch.setattr(
        elevenlabs.requests,
        "post",
        lambda *args, **kwargs: _fake_response(200, content_type, content),
    )

    generation = elevenlabs.generate(
        lyrics="Minha letra tem mais de dez caracteres.",
        prompt="short acoustic music",
        duration=3,
    )
    _wait_for_local_status(generation["request_id"], "failed")
    job = get_local_job(generation["request_id"])

    with pytest.raises(LocalJobError) as exc_info:
        elevenlabs.get_status(generation)

    assert "ElevenLabs music response" in str(exc_info.value)
    assert not Path(job["output_path"]).exists()


def test_elevenlabs_accepts_audio_response(monkeypatch, tmp_path):
    from easy_ai_clients.music._apis import elevenlabs

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(elevenlabs, "_headers", lambda: {"xi-api-key": "fake"})
    monkeypatch.setattr(
        elevenlabs.requests,
        "post",
        lambda *args, **kwargs: _fake_response(200, "audio/mpeg; charset=binary", b"ID3audio"),
    )

    generation = elevenlabs.generate(
        lyrics="Minha letra tem mais de dez caracteres.",
        prompt="short acoustic music",
        duration=3,
    )
    _wait_for_local_status(generation["request_id"], "completed")
    result = elevenlabs.download_result(generation)

    assert result["status"] == "completed"
    assert Path(result["output_path"]).read_bytes() == b"ID3audio"


def test_elevenlabs_http_error_remains_sanitized(monkeypatch, tmp_path):
    from easy_ai_clients.music._apis import elevenlabs
    from easy_ai_clients.music._common import LocalJobError, get_local_job

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "secret-token")
    monkeypatch.setattr(elevenlabs, "_headers", lambda: {"xi-api-key": "secret-token"})
    monkeypatch.setattr(
        elevenlabs.requests,
        "post",
        lambda *args, **kwargs: _fake_response(
            422,
            "application/json",
            b'{"detail":"bad secret-token https://example.test/audio.mp3?token=query-secret"}',
        ),
    )

    generation = elevenlabs.generate(
        lyrics="Minha letra tem mais de dez caracteres.",
        prompt="short acoustic music",
        duration=3,
    )
    _wait_for_local_status(generation["request_id"], "failed")
    job = get_local_job(generation["request_id"])

    with pytest.raises(LocalJobError) as exc_info:
        elevenlabs.get_status(generation)

    message = str(exc_info.value)
    assert "HTTP 422" in message
    assert "secret-token" not in message
    assert "query-secret" not in message
    assert "<redacted-url>" in message
    assert not Path(job["output_path"]).exists()


def test_deapi_generate_rejects_missing_data_or_request_id(monkeypatch):
    from easy_ai_clients.music._apis import deapi

    monkeypatch.setattr(deapi, "_headers", lambda: {"Authorization": "Bearer fake"})

    monkeypatch.setattr(deapi, "request_json", lambda *args, **kwargs: {})
    with pytest.raises(RuntimeError, match="data object"):
        deapi.generate(
            lyrics="Minha letra tem mais de dez caracteres.",
            prompt="Brazilian gospel",
        )

    monkeypatch.setattr(deapi, "request_json", lambda *args, **kwargs: {"data": {}})
    with pytest.raises(RuntimeError, match="request_id"):
        deapi.generate(
            lyrics="Minha letra tem mais de dez caracteres.",
            prompt="Brazilian gospel",
        )


def test_deapi_status_rejects_missing_status(monkeypatch):
    from easy_ai_clients.music._apis import deapi
    from easy_ai_clients.music._common import standard_generation

    monkeypatch.setattr(deapi, "_headers", lambda: {"Authorization": "Bearer fake"})
    monkeypatch.setattr(deapi, "request_json", lambda *args, **kwargs: {"data": {}})

    generation = standard_generation("deapi", "AceStep_1_5_Turbo", "req-1")
    with pytest.raises(RuntimeError, match="status"):
        deapi.get_status(generation)


@pytest.mark.parametrize("status", ["pending", "processing", "running", "queued"])
def test_deapi_status_maps_running_statuses(monkeypatch, status):
    from easy_ai_clients.music._apis import deapi
    from easy_ai_clients.music._common import standard_generation

    monkeypatch.setattr(deapi, "_headers", lambda: {"Authorization": "Bearer fake"})
    monkeypatch.setattr(deapi, "request_json", lambda *args, **kwargs: {"data": {"status": status}})

    generation = standard_generation("deapi", "AceStep_1_5_Turbo", "req-1")

    assert deapi.get_status(generation)["status"] == "running"


@pytest.mark.parametrize("status", ["done", "completed", "succeeded"])
def test_deapi_status_maps_success_statuses(monkeypatch, status):
    from easy_ai_clients.music._apis import deapi
    from easy_ai_clients.music._common import standard_generation

    monkeypatch.setattr(deapi, "_headers", lambda: {"Authorization": "Bearer fake"})
    monkeypatch.setattr(deapi, "request_json", lambda *args, **kwargs: {"data": {"status": status}})

    generation = standard_generation("deapi", "AceStep_1_5_Turbo", "req-1")

    assert deapi.get_status(generation)["status"] == "completed"


def test_deapi_failure_preserves_sanitized_details(monkeypatch):
    from easy_ai_clients.music._apis import deapi
    from easy_ai_clients.music._common import standard_generation

    monkeypatch.setenv("DEAPI_API_KEY", "secret-token")
    monkeypatch.setattr(deapi, "_headers", lambda: {"Authorization": "Bearer secret-token"})
    monkeypatch.setattr(
        deapi,
        "request_json",
        lambda *args, **kwargs: {
            "data": {
                "status": "error",
                "error_message": "failed for secret-token at https://example.test/audio.mp3?token=x",
            }
        },
    )

    generation = standard_generation("deapi", "AceStep_1_5_Turbo", "req-1")
    with pytest.raises(RuntimeError) as exc_info:
        deapi.get_status(generation)

    message = str(exc_info.value)
    assert generation["status"] == "failed"
    assert "secret-token" not in message
    assert "token=x" not in message
    assert "<redacted-url>" in message


def test_deapi_download_uses_result_url_and_rejects_result(monkeypatch):
    from easy_ai_clients.music._apis import deapi
    from easy_ai_clients.music._common import standard_generation

    monkeypatch.setattr(deapi, "_headers", lambda: {"Authorization": "Bearer fake"})
    captured = {}

    def fake_download(generation, provider, audio_url, extension):
        captured["audio_url"] = audio_url
        generation["output_path"] = "outputs/music/temp/deapi/result.mp3"
        generation["status"] = "completed"
        return generation

    monkeypatch.setattr(deapi, "download_generation_audio", fake_download)
    monkeypatch.setattr(
        deapi,
        "request_json",
        lambda *args, **kwargs: {"data": {"status": "done", "result_url": "https://example.test/a.mp3"}},
    )
    generation = standard_generation("deapi", "AceStep_1_5_Turbo", "req-1")

    assert deapi.download_result(generation)["status"] == "completed"
    assert captured["audio_url"] == "https://example.test/a.mp3"

    monkeypatch.setattr(
        deapi,
        "request_json",
        lambda *args, **kwargs: {"data": {"status": "done", "result": "https://example.test/a.mp3"}},
    )
    generation = standard_generation("deapi", "AceStep_1_5_Turbo", "req-1")
    with pytest.raises(RuntimeError, match="result_url"):
        deapi.download_result(generation)
    assert generation["status"] == "failed"


@pytest.mark.parametrize(
    ("response", "pattern"),
    [
        ({"errors": [{"code": "badRequest", "message": "bad"}]}, "badRequest"),
        ({"errors": {"code": "badRequest", "message": "bad"}}, "badRequest"),
        ({"error": "provider failed"}, "provider failed"),
        ({}, "data"),
        ({"data": {"status": "processing"}}, "data was not a list"),
        ({"data": ["not-object"]}, "first data item"),
        ({"data": [{"status": "error", "error": {"code": "bad", "message": "failed"}}]}, "failed"),
    ],
)
def test_runware_first_result_rejects_malformed_envelopes(response, pattern):
    from easy_ai_clients.music._apis import runware

    with pytest.raises(RuntimeError, match=pattern):
        runware._first_result(response)  # noqa: SLF001


def test_runware_generate_uses_submitted_task_uuid_when_response_omits_it(monkeypatch):
    from easy_ai_clients.music._apis import runware

    monkeypatch.setattr(runware, "_headers", lambda: {"Authorization": "Bearer fake"})
    monkeypatch.setattr(
        runware,
        "request_json",
        lambda *args, **kwargs: {"data": [{"status": "processing"}]},
    )

    result = runware.generate(
        lyrics="Minha letra tem mais de dez caracteres.",
        prompt="Brazilian gospel with expressive vocal.",
    )

    assert result["status"] == "submitted"
    assert result["request_id"]


def test_runware_status_error_marks_generation_failed(monkeypatch):
    from easy_ai_clients.music._apis import runware
    from easy_ai_clients.music._common import standard_generation

    monkeypatch.setattr(runware, "_headers", lambda: {"Authorization": "Bearer fake"})
    monkeypatch.setattr(
        runware,
        "request_json",
        lambda *args, **kwargs: {
            "data": [
                {
                    "taskUUID": "task-1",
                    "status": "error",
                    "error": {"code": "bad", "message": "provider failed"},
                }
            ]
        },
    )
    generation = standard_generation("runware", "runware:ace-step@v1.5-xl-turbo", "task-1")

    with pytest.raises(RuntimeError, match="provider failed"):
        runware.get_status(generation)

    assert generation["status"] == "failed"


def test_runware_download_rejects_success_without_audio_url(monkeypatch):
    from easy_ai_clients.music._apis import runware
    from easy_ai_clients.music._common import standard_generation

    monkeypatch.setattr(runware, "_headers", lambda: {"Authorization": "Bearer fake"})
    monkeypatch.setattr(
        runware,
        "request_json",
        lambda *args, **kwargs: {"data": [{"taskUUID": "task-1", "status": "success"}]},
    )
    generation = standard_generation("runware", "runware:ace-step@v1.5-xl-turbo", "task-1")

    with pytest.raises(RuntimeError, match="audioURL"):
        runware.download_result(generation)
    assert generation["status"] == "failed"


def test_require_env_strips_surrounding_quotes(monkeypatch):
    from easy_ai_clients.music._common import require_env

    monkeypatch.setenv("KIE_API_KEY", '"quoted-token"')
    assert require_env("KIE_API_KEY") == "quoted-token"

    monkeypatch.setenv("KIE_API_KEY", "'quoted-token'")
    assert require_env("KIE_API_KEY") == "quoted-token"


def test_load_env_preserves_existing_environment(monkeypatch, tmp_path):
    from easy_ai_clients.music._common import load_env

    env_path = tmp_path / ".env"
    env_path.write_text(
        "DEAPI_API_KEY=file-value\nRUNWARE_API_KEY=runware-file-value\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DEAPI_API_KEY", "process-value")
    monkeypatch.delenv("RUNWARE_API_KEY", raising=False)

    loaded = load_env(env_path)

    assert loaded == {"DEAPI_API_KEY", "RUNWARE_API_KEY"}
    assert os.environ["DEAPI_API_KEY"] == "process-value"
    assert os.environ["RUNWARE_API_KEY"] == "runware-file-value"


def test_music_api_timeout_uses_process_env_over_dotenv(monkeypatch, tmp_path):
    from easy_ai_clients.music._common import api_timeout

    env_path = tmp_path / ".env"
    env_path.write_text("MUSIC_API_TIMEOUT=17\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MUSIC_API_TIMEOUT", raising=False)

    assert api_timeout(120) == 17

    monkeypatch.setenv("MUSIC_API_TIMEOUT", "23")

    assert api_timeout(120) == 23


def test_music_api_timeout_rejects_invalid_values(monkeypatch):
    from easy_ai_clients.music._common import api_timeout

    monkeypatch.setenv("MUSIC_API_TIMEOUT", "not-a-number")

    with pytest.raises(ValueError, match="MUSIC_API_TIMEOUT must be a positive integer"):
        api_timeout()


def test_deapi_price_lookup_uses_short_bounded_timeout(monkeypatch):
    from easy_ai_clients.music._apis import deapi

    captured = {}

    def fake_request_json(method, url, headers=None, json_payload=None, timeout=None):
        captured["timeout"] = timeout
        return {"cost": 0.01}

    monkeypatch.setenv("MUSIC_API_TIMEOUT", "120")
    monkeypatch.setattr(deapi, "_headers", lambda: {"Authorization": "Bearer fake"})
    monkeypatch.setattr(deapi, "request_json", fake_request_json)

    assert deapi._calculate_cost(  # noqa: SLF001
        {
            "model": "AceStep_1_5_Turbo",
            "duration": 60,
            "inference_steps": 8,
        }
    ) == 0.01
    assert captured["timeout"] == 15


def _fake_response(status_code, content_type, content):
    class Response:
        url = "https://example.test/music"
        text = content.decode("utf-8", errors="ignore") if isinstance(content, bytes) else str(content)

        def __init__(self):
            self.status_code = status_code
            self.headers = {"Content-Type": content_type}
            self.content = content

        def json(self):
            if content_type == "application/json":
                return {"detail": self.text}
            raise ValueError("not json")

    return Response()


def _wait_for_local_status(request_id, expected_status):
    from easy_ai_clients.music._common import get_local_job

    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if get_local_job(request_id)["status"] == expected_status:
            return
        time.sleep(0.01)
    raise AssertionError(f"local job did not reach status {expected_status}")
