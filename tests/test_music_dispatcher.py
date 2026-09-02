"""Music dispatcher tests that do not call provider APIs."""

from __future__ import annotations

import base64
import importlib
import inspect

import pytest

from easy_ai_clients.music import MusicInputLimitError

TEST_LYRICS = "Minha letra tem mais de dez caracteres para dispatch local."
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


class FakeProviderModule:
    def __init__(self, provider="deapi"):
        self.provider = provider
        self.request = None
        self.status_generation = None
        self.download_generation = None

    def generate(self, **kwargs):
        self.request = kwargs
        return {
            "provider": self.provider,
            "model": kwargs["model"],
            "model_key": "placeholder",
            "status": "submitted",
            "request_id": "req_123",
            "output_path": None,
            "cost_usd": 0.0,
            "cost_currency": "USD",
            "cost_source": "unavailable",
            "cost_is_estimated": False,
            "cost_details": {},
            "metadata": {},
        }

    def get_status(self, generation):
        self.status_generation = generation
        generation["status"] = "running"
        return generation

    def download_result(self, generation):
        self.download_generation = generation
        generation["status"] = "completed"
        generation["output_path"] = "outputs/music/temp/deapi/demo.mp3"
        return generation


def provider_import(fake_module, provider="deapi"):
    real_import_module = importlib.import_module

    def fake_import_module(module_name, package=None):
        if module_name == f"._apis.{provider}" and package == "easy_ai_clients.music":
            return fake_module
        return real_import_module(module_name, package)

    return fake_import_module


class LimitThenSuccessProviderModule(FakeProviderModule):
    def __init__(self, provider="deapi", failures=1):
        super().__init__(provider)
        self.failures = failures
        self.requests = []

    def generate(self, **kwargs):
        self.requests.append(kwargs)
        if len(self.requests) <= self.failures:
            raise MusicInputLimitError(
                provider=self.provider,
                model=kwargs["model"],
                model_key="placeholder",
                fields={"caption": {"unit": "characters", "maximum": 1, "observed": 2}},
            )
        return super().generate(**kwargs)


def test_public_signature_uses_api_keyword():
    from easy_ai_clients import music

    signature = inspect.signature(music.generate)

    assert str(signature) == "(lyrics, model=None, *, api, style=None, prompt=None, **kwargs)"


def test_public_exports_are_exact():
    from easy_ai_clients import music

    assert music.__all__ == [
        "MusicInputLimitError",
        "available_apis",
        "build_lyrics_prompt",
        "download_result",
        "generate",
        "get_generation_options",
        "get_status",
        "get_style_presets",
    ]


def test_available_apis_returns_validated_provider_tuple():
    from easy_ai_clients import music

    assert music.available_apis() == ("deapi", "elevenlabs", "google", "kie", "runware")


def test_generate_rejects_unknown_style():
    from easy_ai_clients import music

    with pytest.raises(ValueError, match="Unknown style"):
        music.generate(
            lyrics=TEST_LYRICS,
            model="AceStep_1_5_Turbo",
            api="deapi",
            style="Hip Hop Rap Trap",
        )


def test_generate_rejects_unknown_api():
    from easy_ai_clients import music

    with pytest.raises(ValueError, match="Unknown music API 'unknown_provider'"):
        music.generate(
            lyrics=TEST_LYRICS,
            model="unknown_model",
            api="unknown_provider",
            style="sertanejo",
        )


def test_generate_rejects_empty_api():
    from easy_ai_clients import music

    with pytest.raises(ValueError, match="requires api"):
        music.generate(
            lyrics=TEST_LYRICS,
            model="AceStep_1_5_Turbo",
            api="",
            style="sertanejo",
        )


def test_generate_dispatches_normalized_request(monkeypatch):
    from easy_ai_clients import music
    from easy_ai_clients.music import _router

    fake_module = FakeProviderModule()

    monkeypatch.setattr(
        _router.importlib,
        "import_module",
        provider_import(fake_module),
    )
    result = music.generate(
        lyrics=TEST_LYRICS,
        model="ace_step_v1_5_turbo",
        api="deapi",
        style="sertanejo",
        duration=45,
    )

    assert result["model_key"] == "ace_step_v1_5_turbo"
    assert fake_module.request["lyrics"] == TEST_LYRICS
    assert fake_module.request["model"] == "AceStep_1_5_Turbo"
    assert fake_module.request["duration"] == 45
    assert "negative_prompt" not in fake_module.request
    assert "Brazilian sertanejo" in fake_module.request["prompt"]


def test_generate_uses_validated_default_model(monkeypatch):
    from easy_ai_clients import music
    from easy_ai_clients.music import _router

    fake_module = FakeProviderModule()

    monkeypatch.setattr(_router.importlib, "import_module", provider_import(fake_module))
    result = music.generate(
        lyrics=TEST_LYRICS,
        api="deapi",
        prompt="modern romantic sertanejo",
    )

    assert fake_module.request["model"] == "AceStep_1_5_Turbo"
    assert result["model_key"] == "ace_step_v1_5_turbo"


@pytest.mark.parametrize(
    ("provider", "native_model", "model_key"),
    [
        ("deapi", "AceStep_1_5_Turbo", "ace_step_v1_5_turbo"),
        ("elevenlabs", "music_v2", "eleven_music"),
        ("google", "lyria-3-clip-preview", "lyria_3_clip_preview"),
        ("kie", "V5_5", "suno_v5_5"),
        ("runware", "runware:ace-step@v1.5-xl-turbo", "ace_step_v1_5_xl_turbo"),
    ],
)
def test_generate_uses_validated_default_models_for_all_providers(
    monkeypatch,
    provider,
    native_model,
    model_key,
):
    from easy_ai_clients import music
    from easy_ai_clients.music import _router

    fake_module = FakeProviderModule(provider)

    monkeypatch.setattr(
        _router.importlib,
        "import_module",
        provider_import(fake_module, provider),
    )
    result = music.generate(
        lyrics=TEST_LYRICS,
        api=provider,
        prompt="validated default model route",
    )

    assert fake_module.request["model"] == native_model
    assert result["model_key"] == model_key


def test_generate_accepts_style_none_with_prompt_kwarg(monkeypatch):
    from easy_ai_clients import music
    from easy_ai_clients.music import _router

    fake_module = FakeProviderModule()

    monkeypatch.setattr(_router.importlib, "import_module", provider_import(fake_module))
    music.generate(
        lyrics=TEST_LYRICS,
        model="AceStep_1_5_Turbo",
        api="deapi",
        prompt="modern romantic sertanejo",
    )

    assert fake_module.request["prompt"] == "modern romantic sertanejo"


def test_generate_requires_style_or_prompt():
    from easy_ai_clients import music

    with pytest.raises(ValueError, match="style or prompt is required"):
        music.generate(
            lyrics=TEST_LYRICS,
            model="AceStep_1_5_Turbo",
            api="deapi",
        )


def test_generate_prompt_wins_over_preset_style_prompt(monkeypatch):
    from easy_ai_clients import music
    from easy_ai_clients.music import _router

    fake_module = FakeProviderModule()

    monkeypatch.setattr(_router.importlib, "import_module", provider_import(fake_module))
    music.generate(
        lyrics=TEST_LYRICS,
        model="AceStep_1_5_Turbo",
        api="deapi",
        style="sertanejo",
        prompt="custom direct prompt",
    )

    assert fake_module.request["prompt"] == "custom direct prompt"
    assert "duration" not in fake_module.request


def test_elevenlabs_style_uses_small_voice_without_role_tags(monkeypatch):
    from easy_ai_clients import music
    from easy_ai_clients.music import _router

    fake_module = FakeProviderModule("elevenlabs")

    monkeypatch.setattr(
        _router.importlib,
        "import_module",
        provider_import(fake_module, "elevenlabs"),
    )
    music.generate(
        lyrics=TEST_LYRICS,
        api="elevenlabs",
        style="sertanejo",
        gender="both",
    )

    prompt = fake_module.request["prompt"]
    assert fake_module.request["model"] == "music_v2"
    assert "Brazilian sertanejo" in prompt
    assert "Natural male sertanejo lead" in prompt
    assert "Natural female sertanejo lead" in prompt
    assert "[Verse 1 - Male Lead]" not in prompt
    assert "[Verse 2 - Female Lead]" not in prompt
    assert "[Chorus - Duet]" not in prompt


def test_generate_reduces_preset_prompt_sizes_after_input_limit(monkeypatch):
    from easy_ai_clients import music
    from easy_ai_clients.music import _router

    fake_module = LimitThenSuccessProviderModule(provider="runware", failures=2)

    monkeypatch.setattr(_router.importlib, "import_module", provider_import(fake_module, "runware"))
    music.generate(
        lyrics=TEST_LYRICS,
        model="ace_step_v1_5_xl_turbo",
        api="runware",
        style="sertanejo",
    )

    assert len(fake_module.requests) == 3
    assert len(fake_module.requests[0]["prompt"]) > len(fake_module.requests[1]["prompt"])
    assert len(fake_module.requests[1]["prompt"]) > len(fake_module.requests[2]["prompt"])


def test_generate_raises_original_limit_error_after_all_prompt_sizes_fail(monkeypatch):
    from easy_ai_clients import music
    from easy_ai_clients.music import _router

    fake_module = LimitThenSuccessProviderModule(provider="runware", failures=10)

    monkeypatch.setattr(_router.importlib, "import_module", provider_import(fake_module, "runware"))
    with pytest.raises(MusicInputLimitError) as exc_info:
        music.generate(
            lyrics=TEST_LYRICS,
            model="ace_step_v1_5_xl_turbo",
            api="runware",
            style="sertanejo",
        )

    assert exc_info.value.fields["caption"]["maximum"] == 1
    assert len(fake_module.requests) == 6


def test_generate_does_not_retry_explicit_prompt_after_input_limit(monkeypatch):
    from easy_ai_clients import music
    from easy_ai_clients.music import _router

    fake_module = LimitThenSuccessProviderModule(provider="runware", failures=10)

    monkeypatch.setattr(_router.importlib, "import_module", provider_import(fake_module, "runware"))
    with pytest.raises(MusicInputLimitError):
        music.generate(
            lyrics=TEST_LYRICS,
            model="ace_step_v1_5_xl_turbo",
            api="runware",
            style="sertanejo",
            prompt="custom direct prompt",
        )

    assert len(fake_module.requests) == 1
    assert fake_module.requests[0]["prompt"] == "custom direct prompt"


@pytest.mark.parametrize(
    "parameter",
    [
        "audio_settings",
        "include_cost",
        "negative_prompt",
        "number_results",
        "output_format",
        "output_type",
        "seed",
        "ttl",
    ],
)
def test_generate_rejects_removed_public_kwargs(parameter):
    from easy_ai_clients import music

    with pytest.raises(ValueError, match="Unsupported kwargs"):
        music.generate(
            lyrics=TEST_LYRICS,
            model="AceStep_1_5_Turbo",
            api="deapi",
            style="sertanejo",
            **{parameter: "value"},
        )


def test_generate_rejects_internal_force_instrumental_public_kwarg():
    from easy_ai_clients import music

    with pytest.raises(ValueError, match="Unsupported kwargs"):
        music.generate(
            lyrics=TEST_LYRICS,
            api="elevenlabs",
            prompt="upbeat rock",
            _force_instrumental=True,
        )


def test_generate_accepts_provider_native_model_id(monkeypatch):
    from easy_ai_clients import music
    from easy_ai_clients.music import _router

    fake_module = FakeProviderModule()

    monkeypatch.setattr(_router.importlib, "import_module", provider_import(fake_module))
    result = music.generate(
        lyrics=TEST_LYRICS,
        model="AceStep_1_5_XL_Turbo_INT8",
        api="deapi",
        style="sertanejo",
    )

    assert fake_module.request["model"] == "AceStep_1_5_XL_Turbo_INT8"
    assert result["model_key"] == "ace_step_1_5_xl_turbo_int8"


def test_generate_filters_provider_extra_fields(monkeypatch):
    from easy_ai_clients import music
    from easy_ai_clients.music import _router

    class ExtraProviderModule(FakeProviderModule):
        def generate(self, **kwargs):
            result = super().generate(**kwargs)
            result["raw_response"] = {"secret": "value"}
            result["audio_url"] = "https://example.test/audio.mp3"
            result["metadata"] = {
                "audio_url": "https://example.test/audio.mp3?signature=abc",
                "Authorization": "Bearer provider-secret",
                "audio_base64": base64.b64encode(b"x" * 600).decode(),
            }
            result["cost_details"] = {
                "signed_url": "https://example.test/cost?token=abc",
            }
            return result

    fake_module = ExtraProviderModule()

    monkeypatch.setattr(_router.importlib, "import_module", provider_import(fake_module))
    result = music.generate(
        lyrics=TEST_LYRICS,
        model="AceStep_1_5_Turbo",
        api="deapi",
        prompt="modern romantic sertanejo",
    )

    assert set(result) == PUBLIC_GENERATION_KEYS
    assert "raw_response" not in result
    assert "audio_url" not in result
    result_text = repr(result)
    assert "https://example.test/audio.mp3" not in result_text
    assert "provider-secret" not in result_text
    assert "signature=abc" not in result_text
    assert "token=abc" not in result_text


def test_generate_normalizes_malformed_provider_cost(monkeypatch):
    from easy_ai_clients import music
    from easy_ai_clients.music import _router

    class InvalidCostProviderModule(FakeProviderModule):
        def generate(self, **kwargs):
            result = super().generate(**kwargs)
            result["cost_usd"] = "not-a-number"
            result["cost_source"] = "provider_response"
            result["cost_is_estimated"] = True
            return result

    fake_module = InvalidCostProviderModule()

    monkeypatch.setattr(_router.importlib, "import_module", provider_import(fake_module))
    result = music.generate(
        lyrics=TEST_LYRICS,
        model="AceStep_1_5_Turbo",
        api="deapi",
        prompt="modern romantic sertanejo",
    )

    assert result["cost_usd"] == 0.0
    assert result["cost_source"] == "unavailable"
    assert result["cost_is_estimated"] is False


def test_status_and_download_route_to_provider(monkeypatch):
    from easy_ai_clients import music
    from easy_ai_clients.music import _router

    fake_module = FakeProviderModule()
    generation = {
        "provider": "deapi",
        "model": "AceStep_1_5_Turbo",
        "model_key": "ace_step_v1_5_turbo",
        "status": "submitted",
        "request_id": "req_123",
        "output_path": None,
        "cost_usd": 0.0,
        "cost_currency": "USD",
        "cost_source": "unavailable",
        "cost_is_estimated": False,
        "cost_details": {},
        "metadata": {},
    }

    monkeypatch.setattr(_router.importlib, "import_module", provider_import(fake_module))
    status = music.get_status(generation)
    download = music.download_result(generation)

    assert status["status"] == "running"
    assert download["status"] == "completed"
    assert generation["output_path"] == "outputs/music/temp/deapi/demo.mp3"


def test_status_and_download_filter_provider_extra_fields(monkeypatch):
    from easy_ai_clients import music
    from easy_ai_clients.music import _router

    class ExtraProviderModule(FakeProviderModule):
        def get_status(self, generation):
            result = super().get_status(generation)
            result["raw_response"] = {"token": "provider-secret"}
            result["metadata"] = {
                "message": "audio at https://example.test/audio.mp3?signature=abc",
                "Authorization": "Bearer provider-secret",
            }
            return result

        def download_result(self, generation):
            result = super().download_result(generation)
            result["raw_response"] = {"token": "provider-secret"}
            result["cost_details"] = {
                "signed_url": "https://example.test/download.mp3?token=abc",
            }
            return result

    fake_module = ExtraProviderModule()
    generation = {
        "provider": "deapi",
        "model": "AceStep_1_5_Turbo",
        "model_key": "ace_step_v1_5_turbo",
        "status": "submitted",
        "request_id": "req_123",
        "output_path": None,
        "cost_usd": 0.0,
        "cost_currency": "USD",
        "cost_source": "unavailable",
        "cost_is_estimated": False,
        "cost_details": {},
        "metadata": {},
    }

    monkeypatch.setattr(_router.importlib, "import_module", provider_import(fake_module))
    status = music.get_status(generation)
    download = music.download_result(generation)

    for result in (status, download):
        result_text = repr(result)
        assert set(result) == PUBLIC_GENERATION_KEYS
        assert "raw_response" not in result
        assert "provider-secret" not in result_text
        assert "signature=abc" not in result_text
        assert "token=abc" not in result_text
        assert "https://example.test/audio.mp3" not in result_text
        assert "https://example.test/download.mp3" not in result_text


def test_status_rejects_mismatched_explicit_api():
    from easy_ai_clients import music

    generation = {"provider": "deapi", "model": "AceStep_1_5_Turbo", "request_id": "req_123"}

    with pytest.raises(ValueError, match="does not match api"):
        music.get_status(generation, api="runware")
