"""Music style adapter and preset export tests."""

from __future__ import annotations

import importlib
import importlib.util
import re
from pathlib import Path

import pytest

from easy_ai_clients.music import _style_adapter as style_adapter

STYLE_DIR = Path(style_adapter.__file__).resolve().parent / "styles"
TEST_LYRICS = "Minha letra tem mais de dez caracteres para validacao local."
VOICE_PRESETS = None

REQUIRED_FIELDS = {
    "id",
    "description",
    "style_prompts",
    "default_language",
    "voice_presets",
    "tempo_bpm",
    "key_scale",
    "time_signature",
    "instrumentation",
    "arrangement",
    "energy",
    "mood",
    "mix_target",
}

REMOVED_FIELDS = {
    "default_vocal",
    "duration_seconds",
    "generation_controls",
    "negative_traits",
}

FORBIDDEN_ARTIST_NAMES = {
    "Adele",
    "Beyonce",
    "Drake",
    "Taylor Swift",
    "Bad Bunny",
    "Anitta",
    "Queen",
    "The Beatles",
    "Elvis Presley",
}

PROMPT_FACING_FIELDS = (
    "description",
    "style_prompts",
    "voice_presets",
    "instrumentation",
    "arrangement",
    "energy",
    "mood",
    "mix_target",
)
STYLE_PROMPT_LIMITS = {
    "small": (80, 100),
    "medium": (250, 300),
    "large": (500, 700),
}
VOICE_PROMPT_LIMITS = {
    "small": (80, 100),
    "medium": (150, 200),
}
FORBIDDEN_STYLE_VOICE_TERMS = {
    "vocal",
    "vocals",
    "voice",
    "voices",
    "singer",
    "singers",
    "choir",
    "duet",
    "male",
    "female",
    "melisma",
    "vibrato",
    "diction",
    "breath",
}


def test_list_styles_returns_exact_file_stems():
    stems = sorted(path.stem for path in STYLE_DIR.glob("*.py") if path.name != "__init__.py")

    assert style_adapter.list_styles() == stems
    assert len(stems) == 30


def test_resolve_style_uses_exact_matching():
    assert style_adapter.resolve_style("sertanejo")["style_source"] == "preset"
    assert style_adapter.resolve_style("hip_hop_rap_trap")["style_source"] == "preset"
    assert style_adapter.resolve_style(None)["style_source"] == "none"

    with pytest.raises(ValueError, match="Unknown style"):
        style_adapter.resolve_style("Hip Hop Rap Trap")
    with pytest.raises(ValueError, match="Unknown style"):
        style_adapter.resolve_style("hip-hop-rap-trap")


def test_preset_request_contains_stable_prompt_fragments():
    request = style_adapter.build_generation_request(
        provider="deapi",
        model="AceStep_1_5_Turbo",
        lyrics=TEST_LYRICS,
        style="sertanejo",
    )

    assert request["style_source"] == "preset"
    assert "Brazilian sertanejo" in request["kwargs"]["prompt"]
    assert "Two female lead voices" in request["kwargs"]["prompt"]
    assert "Brazilian Portuguese" in request["kwargs"]["prompt"]
    assert "92 BPM" in request["kwargs"]["prompt"]
    assert "E major" in request["kwargs"]["prompt"]
    assert "acoustic guitar" in request["kwargs"]["prompt"]
    assert "duration" not in request["kwargs"]
    assert "negative_prompt" not in request["kwargs"]


def test_prompt_kwarg_replaces_preset_prompt_without_voice_append():
    request = style_adapter.build_generation_request(
        provider="deapi",
        model="AceStep_1_5_Turbo",
        lyrics=TEST_LYRICS,
        style="sertanejo",
        prompt="extra romantic lift",
        kwargs={"gender": "male"},
    )

    assert request["kwargs"]["prompt"] == "extra romantic lift"
    assert "Two male lead voices" not in request["kwargs"]["prompt"]
    assert "duration" not in request["kwargs"]


def test_caller_kwargs_override_generated_kwargs():
    request = style_adapter.build_generation_request(
        provider="deapi",
        model="AceStep_1_5_Turbo",
        lyrics=TEST_LYRICS,
        style="sertanejo",
        kwargs={"duration": 45, "bpm": 100},
    )

    assert request["kwargs"]["duration"] == 45
    assert request["kwargs"]["bpm"] == 100
    assert request["kwargs"]["key_scale"] == "E major"


def test_language_override_updates_prompt_and_ace_vocal_language():
    request = style_adapter.build_generation_request(
        provider="runware",
        model="runware:ace-step@v1.5-xl-turbo",
        lyrics=TEST_LYRICS,
        style="hip_hop_rap_trap",
        kwargs={"language": "pt-BR"},
    )

    assert "Brazilian Portuguese lyrics" in request["kwargs"]["prompt"]
    assert request["kwargs"]["vocal_language"] == "pt"
    assert "language" not in request["kwargs"]


def test_language_override_is_prompt_only_for_non_ace_providers():
    provider_cases = [
        ("elevenlabs", "music_v2"),
        ("google", "lyria-3-pro-preview"),
    ]

    for provider, model in provider_cases:
        request = style_adapter.build_generation_request(
            provider=provider,
            model=model,
            lyrics=TEST_LYRICS,
            style="rock",
            kwargs={"language": "pt-BR"},
        )

        assert "Brazilian Portuguese lyrics" in request["kwargs"]["prompt"]
        assert "language" not in request["kwargs"]
        assert "vocal_language" not in request["kwargs"]


def test_language_override_rejects_unknown_language():
    with pytest.raises(ValueError, match="language must be one of"):
        style_adapter.build_generation_request(
            provider="runware",
            model="runware:ace-step@v1.5-xl-turbo",
            lyrics=TEST_LYRICS,
            style="rock",
            kwargs={"language": "pt-BR-extra"},
        )


def test_negative_prompt_is_rejected_by_style_adapter():
    with pytest.raises(ValueError, match="negative_prompt is not supported"):
        style_adapter.build_generation_request(
            provider="runware",
            model="runware:ace-step@v1.5-xl-sft",
            lyrics=TEST_LYRICS,
            style="sertanejo",
            kwargs={"negative_prompt": "avoid spoken word"},
        )


def test_style_none_preserves_prompt_exactly_and_kwargs():
    request = style_adapter.build_generation_request(
        provider="runware",
        model="runware:ace-step@v1.5-xl-sft",
        lyrics=TEST_LYRICS,
        style=None,
        prompt="modern romantic sertanejo",
        kwargs={
            "gender": "both",
            "duration": 90,
        },
    )

    assert request["style_source"] == "none"
    assert request["kwargs"]["prompt"] == "modern romantic sertanejo"
    assert request["kwargs"]["duration"] == 90


def test_voice_description_overrides_preset_gender_voice():
    request = style_adapter.build_generation_request(
        provider="google",
        model="lyria-3-pro-preview",
        lyrics=TEST_LYRICS,
        style="sertanejo",
        kwargs={
            "gender": "female",
            "voice_description": "Soft intimate baritone with close diction.",
        },
    )

    assert "Soft intimate baritone" in request["kwargs"]["prompt"]
    assert "Two female lead voices" not in request["kwargs"]["prompt"]


def test_kie_preset_renders_compact_tags_not_elevenlabs_prose():
    request = style_adapter.build_generation_request(
        provider="kie",
        model="V5_5",
        lyrics=TEST_LYRICS,
        style="pop",
        kwargs={"gender": "female", "language": "en-US"},
    )

    tags = request["kwargs"]["prompt"]
    assert request["kwargs"]["gender"] == "female"
    assert "pop" in tags
    assert "112 BPM" in tags
    assert "English vocals" in tags
    assert "high energy" in tags
    assert "automatic music generation" not in tags
    assert "mono compatibility" not in tags
    assert "Voice guidance:" not in tags
    assert "Natural female pop lead" not in tags


def test_kie_both_gender_does_not_inject_gender_kwarg():
    request = style_adapter.build_generation_request(
        provider="kie",
        model="V5_5",
        lyrics=TEST_LYRICS,
        style="pop",
        kwargs={"gender": "both"},
    )

    assert "gender" not in request["kwargs"]
    assert "Voice guidance:" not in request["kwargs"]["prompt"]


def test_kie_voice_description_does_not_enter_style_tags():
    request = style_adapter.build_generation_request(
        provider="kie",
        model="V5_5",
        lyrics=TEST_LYRICS,
        style="pop",
        kwargs={
            "gender": "female",
            "voice_description": "A seven-year-old girl with a bright spoken tone.",
        },
    )

    assert "seven-year-old" not in request["kwargs"]["prompt"]
    assert request["kwargs"]["gender"] == "female"


def test_elevenlabs_uses_small_voice_prompt_for_presets():
    request = style_adapter.build_generation_request(
        provider="elevenlabs",
        model="music_v2",
        lyrics=TEST_LYRICS,
        style="sertanejo",
        kwargs={"gender": "both"},
    )

    prompt = request["kwargs"]["prompt"]
    assert "Brazilian sertanejo" in prompt
    assert "Natural male sertanejo lead" in prompt
    assert "Natural female sertanejo lead" in prompt
    assert "Two male lead voices" not in prompt
    assert "Two female lead voices" not in prompt
    assert "[Verse 1 - Male Lead]" not in prompt
    assert "[Verse 2 - Female Lead]" not in prompt
    assert "[Chorus - Duet]" not in prompt


def test_invalid_gender_is_rejected():
    with pytest.raises(ValueError, match="gender must be one of"):
        style_adapter.build_generation_request(
            provider="google",
            model="lyria-3-pro-preview",
            lyrics=TEST_LYRICS,
            style="sertanejo",
            kwargs={"gender": "duet"},
        )


def test_get_style_presets_returns_full_deep_copied_presets():
    presets = style_adapter.get_style_presets()

    assert len(presets) == 30
    assert "sertanejo" in presets
    assert "description" in presets["sertanejo"]

    presets["sertanejo"]["description"]["en"] = "mutated"
    fresh = style_adapter.get_style_presets(styles="sertanejo")

    assert fresh["sertanejo"]["description"]["en"] != "mutated"


def test_get_style_presets_filters_fields_without_automatic_id():
    presets = style_adapter.get_style_presets(
        fields=["description", "style_prompts"],
        styles="sertanejo",
    )

    assert list(presets) == ["sertanejo"]
    assert list(presets["sertanejo"]) == ["description", "style_prompts"]
    assert "id" not in presets["sertanejo"]


def test_get_style_presets_filters_styles_and_fields_in_caller_order():
    presets = style_adapter.get_style_presets(
        fields=["mix_target", "description", "id"],
        styles=["gospel_br", "sertanejo"],
    )

    assert list(presets) == ["gospel_br", "sertanejo"]
    assert list(presets["gospel_br"]) == ["mix_target", "description", "id"]
    assert list(presets["sertanejo"]) == ["mix_target", "description", "id"]


def test_get_style_presets_uses_exact_matching():
    result = style_adapter.get_style_presets(
        fields="Description",
        styles="Sertanejo",
    )

    error = result["error"]
    assert error["invalid_fields"] == ["Description"]
    assert error["invalid_styles"] == ["Sertanejo"]


def test_get_style_presets_reports_invalid_filter_shapes():
    result = style_adapter.get_style_presets(
        fields=["id", 1, ""],
        styles=[],
    )

    error = result["error"]
    assert error["message"] == "Invalid style preset filters."
    assert error["usage"]["fields"] == "Use None, a string field name, or a list of string field names."
    assert "<non-string item: int>" in error["invalid_fields"]
    assert "<empty string>" in error["invalid_fields"]
    assert error["invalid_styles"] == ["<empty list>"]
    assert error["accepted_fields"][:3] == ["id", "description", "default_language"]
    assert error["accepted_styles"] == style_adapter.list_styles()


def test_get_style_presets_reports_invalid_parameter_types():
    result = style_adapter.get_style_presets(
        fields={"id": True},
        styles=object(),
    )

    error = result["error"]
    assert error["invalid_fields"] == ["<invalid type: dict>"]
    assert error["invalid_styles"] == ["<invalid type: object>"]


def test_style_package_has_expected_files():
    files = sorted(path.name for path in STYLE_DIR.glob("*.py"))

    assert len(files) == 31
    assert "__init__.py" in files
    assert len([name for name in files if name != "__init__.py"]) == 30


def test_all_style_modules_import_and_expose_valid_presets():
    expected_voice_presets = _voice_presets()
    for style in style_adapter.list_styles():
        module = importlib.import_module(f"easy_ai_clients.music.styles.{style}")
        assert hasattr(module, "STYLE_PRESET")
        preset = module.STYLE_PRESET

        assert REQUIRED_FIELDS.issubset(preset)
        assert REMOVED_FIELDS.isdisjoint(preset)
        assert preset["id"] == style
        assert set(preset["description"]) == {"pt", "en"}
        assert set(preset["style_prompts"]) == {"small", "medium", "large"}
        assert set(preset["voice_presets"]) == {"default_gender", "small", "medium", "large"}
        assert preset["voice_presets"]["large"] == {
            "male": expected_voice_presets[style]["male"],
            "female": expected_voice_presets[style]["female"],
        }
        assert preset["voice_presets"]["default_gender"] == expected_voice_presets[style]["default_gender"]
        assert preset["voice_presets"]["default_gender"] in {"male", "female"}
        _assert_style_prompt_lengths_and_terms(preset)
        _assert_prompt_text_is_complete(preset["id"], "description.pt", preset["description"]["pt"])
        _assert_prompt_text_is_complete(preset["id"], "description.en", preset["description"]["en"])
        _assert_voice_prompt_lengths(preset)
        for language in ("pt", "en"):
            assert isinstance(preset["description"][language], str)
            assert isinstance(preset["description"][language], str)
            assert preset["description"][language].strip()
            assert preset["description"][language] == preset["description"][language].strip()
            assert "\n" not in preset["description"][language]
            assert "\r" not in preset["description"][language]
        assert "lyrics" not in preset
        assert "seed" not in preset
        assert not _contains_exact_key(preset, "seed")
        assert isinstance(preset["tempo_bpm"], int)
        assert 30 <= preset["tempo_bpm"] <= 300
        assert preset["time_signature"] in {2, 3, 4, 6}
        assert_prompt_fields_have_no_artist_names(preset)


def assert_prompt_fields_have_no_artist_names(preset):
    prompt_text = " ".join(_flatten(preset[field]) for field in PROMPT_FACING_FIELDS)
    for artist_name in FORBIDDEN_ARTIST_NAMES:
        assert artist_name.lower() not in prompt_text.lower()


def _assert_style_prompt_lengths_and_terms(preset):
    for size, (minimum, maximum) in STYLE_PROMPT_LIMITS.items():
        prompt = preset["style_prompts"][size]
        assert minimum <= len(prompt) <= maximum, (preset["id"], size, len(prompt))
        _assert_prompt_text_is_complete(preset["id"], f"style_prompts.{size}", prompt)
        lowered = prompt.lower()
        for term in FORBIDDEN_STYLE_VOICE_TERMS:
            assert not re.search(rf"\b{re.escape(term)}\b", lowered), (
                preset["id"],
                size,
                term,
            )


def _assert_voice_prompt_lengths(preset):
    for size, (minimum, maximum) in VOICE_PROMPT_LIMITS.items():
        prompts = preset["voice_presets"][size]
        assert set(prompts) == {"male", "female"}
        for gender, prompt in prompts.items():
            assert minimum <= len(prompt) <= maximum, (
                preset["id"],
                size,
                gender,
                len(prompt),
            )
            _assert_prompt_text_is_complete(
                preset["id"],
                f"voice_presets.{size}.{gender}",
                prompt,
            )
    assert set(preset["voice_presets"]["large"]) == {"male", "female"}
    for gender, prompt in preset["voice_presets"]["large"].items():
        _assert_prompt_text_is_complete(
            preset["id"],
            f"voice_presets.large.{gender}",
            prompt,
        )


def _assert_prompt_text_is_complete(style_id, field, text):
    assert text == text.strip(), (style_id, field)
    assert "\n" not in text, (style_id, field)
    assert "\r" not in text, (style_id, field)
    assert text.endswith("."), (style_id, field, text)
    terminal_token = text[:-1].split()[-1].lower().strip(",:;")
    assert terminal_token not in {
        "a",
        "an",
        "and",
        "for",
        "from",
        "in",
        "into",
        "of",
        "on",
        "or",
        "that",
        "the",
        "through",
        "to",
        "while",
        "with",
    }, (style_id, field, terminal_token)
    assert not re.search(r"(?<![.!?]) Use\b", text), (style_id, field, text)
    assert " energy Use " not in text, (style_id, field)
    assert " lyrics Use " not in text, (style_id, field)


def _voice_presets():
    global VOICE_PRESETS
    if VOICE_PRESETS is not None:
        return VOICE_PRESETS
    path = Path(__file__).resolve().parent / "music_voice_preset_snapshot.py"
    spec = importlib.util.spec_from_file_location("music_voice_preset_snapshot", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    VOICE_PRESETS = module.VOICE_PRESETS
    return VOICE_PRESETS


def _contains_exact_key(value, target_key):
    if isinstance(value, dict):
        if target_key in value:
            return True
        return any(_contains_exact_key(item, target_key) for item in value.values())
    if isinstance(value, list):
        return any(_contains_exact_key(item, target_key) for item in value)
    return False


def _flatten(value):
    if isinstance(value, dict):
        return " ".join(_flatten(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten(item) for item in value)
    return str(value)
