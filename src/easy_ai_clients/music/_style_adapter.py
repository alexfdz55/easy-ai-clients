"""Resolve reusable music styles into provider-safe generation requests."""

import importlib
from copy import deepcopy
from pathlib import Path

STYLE_DIR = Path(__file__).resolve().parent / "styles"

VALID_GENDERS = {"male", "female", "both"}
PROMPT_SIZES = ("small", "medium", "large")

GENERIC_VOICE_DESCRIPTIONS = {
    "male": (
        "Male lead vocal with clear diction, steady breath support, centered "
        "pitch, and a natural balanced tone. Keep the lyric intelligible and "
        "in front, using clean attacks, controlled sustain, subtle dynamic "
        "shaping, restrained vibrato or small ornaments only where they "
        "support the phrase, and clear releases at line endings."
    ),
    "female": (
        "Female lead vocal with clear diction, steady breath support, centered "
        "pitch, and a natural balanced tone. Keep the lyric intelligible and "
        "in front, using clean attacks, controlled sustain, subtle dynamic "
        "shaping, restrained vibrato or small ornaments only where they "
        "support the phrase, and clean releases at line endings."
    ),
}

MULTI_VOICE_GUIDANCE = (
    "Use distinct male and female roles only where the lyric structure needs "
    "them. Prefer section tags such as [Verse 1 - Male Lead], [Verse 2 - "
    "Female Lead], and [Chorus - Duet]. Do not use line labels like Male: or "
    "Female:."
)

_LANGUAGE_LABELS = {
    "pt-BR": "Brazilian Portuguese",
    "en-US": "English",
    "en-GB": "British English",
    "en-IE": "Irish English",
    "es-ES": "Spanish",
    "pt-PT": "European Portuguese",
    "fr-FR": "French",
    "de-DE": "German",
}

_ACE_STEP_LANGUAGE_CODES = {
    "pt-BR": "pt",
    "pt-PT": "pt",
    "en-US": "en",
    "en-GB": "en",
    "en-IE": "en",
    "es-ES": "es",
    "fr-FR": "fr",
    "de-DE": "de",
}

_DEAPI_ACE_STEP_MODELS = {
    "AceStep_1_5_Turbo",
    "AceStep_1_5_XL_Turbo_INT8",
}

_GOOGLE_LYRIA_MODELS = {
    "lyria-3-clip-preview",
    "lyria-3-pro-preview",
}

_RUNWARE_ACE_STEPS = {
    "runware:ace-step@v1.5-turbo": 10,
    "runware:ace-step@v1.5-xl-base": 100,
    "runware:ace-step@v1.5-xl-turbo": 8,
    "runware:ace-step@v1.5-xl-sft": 80,
}


def list_styles():
    """Return exact predefined style names from `music/styles/`."""
    return sorted(
        path.stem
        for path in STYLE_DIR.glob("*.py")
        if path.name != "__init__.py"
    )


def get_style_presets(fields=None, styles=None):
    """Return copied style presets with optional exact filters.

    Args:
        fields: Optional. Use `None` for full presets, a string field name, or
            a list of string field names. Field names must match preset keys.
        styles: Optional. Use `None` for all styles, a string style id, or a
            list of string style ids. Style ids must match preset `id` values.

    Returns:
        A dictionary keyed by preset `id`. Invalid filters return an error
        dictionary instead of raising an exception.
    """
    accepted_styles = list_styles()
    accepted_fields = _style_preset_fields(accepted_styles)
    selected_fields, invalid_fields = _normalize_preset_filter(fields, accepted_fields)
    selected_styles, invalid_styles = _normalize_preset_filter(styles, accepted_styles)

    if invalid_fields or invalid_styles:
        return _style_preset_filter_error(
            accepted_fields,
            accepted_styles,
            invalid_fields,
            invalid_styles,
        )

    style_ids = accepted_styles if selected_styles is None else selected_styles
    result = {}
    for style in style_ids:
        preset = _load_style_preset(style)
        preset_id = preset["id"]
        if selected_fields is None:
            result[preset_id] = deepcopy(preset)
        else:
            result[preset_id] = {
                field: deepcopy(preset[field])
                for field in selected_fields
            }
    return result


def resolve_style(style):
    """Resolve an optional exact style name to a preset request.

    Args:
        style: Optional. Exact style file stem. Use `None` for no preset.

    Returns:
        A dictionary with `style_source`, `style`, and optional `style_preset`.

    Raises:
        ValueError: If `style` is not `None` and does not match a style file.
    """
    if style is None:
        return {
            "style_source": "none",
            "style": None,
            "style_preset": None,
        }
    if _is_predefined_style(style):
        return {
            "style_source": "preset",
            "style": style,
            "style_preset": _load_style_preset(style),
        }
    raise ValueError(f"Unknown style: {style}")


def build_voice_guidance(
    style=None,
    gender=None,
    voice_description=None,
    voice_prompt_size="large",
    role_tag_guidance=True,
):
    """Return prompt-ready voice guidance for style/gender inputs."""
    style_preset = resolve_style(style)["style_preset"]
    voice_prompt_size = _validate_prompt_size("voice_prompt_size", voice_prompt_size)
    return _voice_guidance(
        style_preset,
        gender,
        voice_description,
        voice_prompt_size,
        role_tag_guidance,
    )


def default_language_for_style(style):
    """Return the preset default language for a style, when present."""
    style_preset = resolve_style(style)["style_preset"]
    if style_preset is None:
        return None
    return style_preset["default_language"]


def build_generation_request(
    provider,
    model,
    lyrics,
    style=None,
    prompt=None,
    kwargs=None,
    style_prompt_size="large",
    voice_prompt_size="large",
):
    """Build a normalized local request without calling provider APIs.

    Args:
        provider: Required. Provider file name from `music/_apis/`.
        model: Required. Exact provider model.
        lyrics: Required. Caller-provided lyrics.
        style: Optional. Exact predefined style name. Use `None` for no preset.
        prompt: Optional. Caller prompt. If provided with a preset, it replaces
            the preset-rendered prompt.
        kwargs: Optional. Caller kwargs. These override generated preset kwargs.
            `language`, `gender`, and `voice_description` are local prompt
            controls consumed before provider dispatch.
        style_prompt_size: Optional. Preset style prompt size. Accepted values:
            - "small": Use the shortest style prompt.
            - "medium": Use the medium style prompt.
            - "large": Use the full style prompt. Defaults to "large".
        voice_prompt_size: Optional. Preset voice prompt size. Accepted values:
            - "small": Use the shortest voice prompt.
            - "medium": Use the medium voice prompt.
            - "large": Use the full voice prompt. Defaults to "large".

    Returns:
        A local request dictionary for `music.generate()`.
    """
    user_kwargs = dict(kwargs or {})
    if "negative_prompt" in user_kwargs:
        raise ValueError("negative_prompt is not supported for music")

    language_override = user_kwargs.pop("language", None)
    gender = user_kwargs.pop("gender", None)
    voice_description = user_kwargs.pop("voice_description", None)
    user_prompt = _clean_prompt_text("prompt", prompt)
    user_prompt_provided = user_prompt is not None

    resolved = resolve_style(style)
    style_preset = resolved["style_preset"]
    language = _style_language(style_preset, language_override)
    style_prompt_size = _validate_prompt_size("style_prompt_size", style_prompt_size)
    voice_prompt_size = _validate_prompt_size("voice_prompt_size", voice_prompt_size)
    if provider == "elevenlabs":
        voice_prompt_size = "small"

    voice_guidance = None
    if provider != "kie" and not user_prompt_provided:
        voice_guidance = _voice_guidance(
            style_preset,
            gender,
            voice_description,
            voice_prompt_size,
            role_tag_guidance=provider != "elevenlabs",
        )

    if style_preset is None:
        prompt = user_prompt
        generated_kwargs = {}
        style_source = "none"
    else:
        if user_prompt_provided:
            prompt = user_prompt
        else:
            prompt = _provider_prompt(
                provider,
                model,
                style_preset,
                language,
                voice_guidance,
                style_prompt_size,
            )
        generated_kwargs = _provider_kwargs(provider, model, style_preset, language)
        style_source = "preset"

    if provider == "kie":
        selected_gender = _validate_gender(gender)
        if selected_gender in {"male", "female"}:
            generated_kwargs["gender"] = selected_gender

    if prompt is not None:
        generated_kwargs["prompt"] = prompt

    return {
        "lyrics": lyrics,
        "model": model,
        "kwargs": _merge_kwargs(generated_kwargs, user_kwargs),
        "style_source": style_source,
        "style": style,
    }


def _clean_prompt_text(parameter, value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{parameter} must be a string")
    text = value.strip()
    return text or None


def _load_style_preset(style):
    module = importlib.import_module(f".styles.{style}", __package__)
    return module.STYLE_PRESET


def _style_preset_fields(styles):
    if not styles:
        return []
    return list(_load_style_preset(styles[0]).keys())


def _normalize_preset_filter(value, accepted_values):
    accepted = set(accepted_values)
    if value is None:
        return None, []
    if isinstance(value, str):
        if not value:
            return [], ["<empty string>"]
        if value not in accepted:
            return [], [value]
        return [value], []
    if isinstance(value, list):
        if not value:
            return [], ["<empty list>"]
        selected = []
        invalid = []
        for item in value:
            if not isinstance(item, str):
                invalid.append(f"<non-string item: {type(item).__name__}>")
            elif not item:
                invalid.append("<empty string>")
            elif item not in accepted:
                invalid.append(item)
            else:
                selected.append(item)
        return selected, invalid
    return [], [f"<invalid type: {type(value).__name__}>"]


def _style_preset_filter_error(
    accepted_fields,
    accepted_styles,
    invalid_fields,
    invalid_styles,
):
    return {
        "error": {
            "message": "Invalid style preset filters.",
            "usage": {
                "fields": "Use None, a string field name, or a list of string field names.",
                "styles": "Use None, a string style id, or a list of string style ids.",
            },
            "accepted_fields": accepted_fields,
            "accepted_styles": accepted_styles,
            "invalid_fields": invalid_fields,
            "invalid_styles": invalid_styles,
        }
    }


def _is_predefined_style(style):
    return style in list_styles()


def _style_language(style_preset, language_override):
    if language_override is not None:
        return _validate_language(language_override)
    if style_preset is None:
        return None
    return _validate_language(style_preset["default_language"])


def _validate_language(language):
    if not isinstance(language, str):
        raise ValueError("language must be a string")
    text = language.strip()
    if text not in _LANGUAGE_LABELS:
        accepted = ", ".join(sorted(_LANGUAGE_LABELS))
        raise ValueError(f"language must be one of: {accepted}")
    return text


def _validate_gender(gender):
    if gender is None:
        return None
    if not isinstance(gender, str):
        raise ValueError("gender must be one of: male, female, both")
    value = gender.strip().lower()
    if value not in VALID_GENDERS:
        raise ValueError("gender must be one of: male, female, both")
    return value


def _validate_prompt_size(parameter, value):
    if not isinstance(value, str) or value not in PROMPT_SIZES:
        accepted = ", ".join(PROMPT_SIZES)
        raise ValueError(f"{parameter} must be one of: {accepted}")
    return value


def _voice_guidance(
    style_preset,
    gender,
    voice_description,
    voice_prompt_size="large",
    role_tag_guidance=True,
):
    direct = _clean_prompt_text("voice_description", voice_description)
    selected_gender = _validate_gender(gender)
    if direct is not None:
        if selected_gender == "both":
            return _multi_voice_text(direct, direct, role_tag_guidance)
        return direct

    if style_preset is not None:
        voice_presets = style_preset["voice_presets"]
        selected_voice_prompts = voice_presets[voice_prompt_size]
        if selected_gender == "both":
            return _multi_voice_text(
                selected_voice_prompts["male"],
                selected_voice_prompts["female"],
                role_tag_guidance,
            )
        if selected_gender in {"male", "female"}:
            return selected_voice_prompts[selected_gender]
        return selected_voice_prompts[voice_presets["default_gender"]]

    if selected_gender == "both":
        return _multi_voice_text(
            GENERIC_VOICE_DESCRIPTIONS["male"],
            GENERIC_VOICE_DESCRIPTIONS["female"],
            role_tag_guidance,
        )
    if selected_gender in {"male", "female"}:
        return GENERIC_VOICE_DESCRIPTIONS[selected_gender]
    return None


def _multi_voice_text(male_voice, female_voice, role_tag_guidance=True):
    if not role_tag_guidance:
        return (
            f"Male voice: {male_voice} Female voice: {female_voice} "
            "Let the two voices share the song naturally through call-and-response, "
            "overlap, and chorus energy without labeling lines by singer gender."
        )
    return (
        f"Male voice: {male_voice} Female voice: {female_voice} "
        f"{MULTI_VOICE_GUIDANCE}"
    )


def _append_voice_guidance(prompt, voice_guidance):
    if prompt is None or voice_guidance is None:
        return prompt
    return f"{prompt}\n\nVoice guidance: {voice_guidance}"


def _provider_prompt(
    provider,
    model,
    style_preset,
    language,
    voice_guidance,
    style_prompt_size,
):
    if provider == "kie":
        return _render_kie_style_tags(style_preset, language)
    if provider == "deapi" and model in _DEAPI_ACE_STEP_MODELS:
        return _render_prompt(
            style_preset,
            language,
            voice_guidance,
            style_prompt_size,
            compact=True,
            max_chars=300,
        )
    if provider == "google" and model in _GOOGLE_LYRIA_MODELS:
        return _render_prompt(style_preset, language, voice_guidance, style_prompt_size)
    return _render_prompt(style_preset, language, voice_guidance, style_prompt_size)


def _render_prompt(
    style_preset,
    language,
    voice_guidance,
    style_prompt_size,
    compact=False,
    max_chars=None,
):
    language = _language_label(language)
    bpm = style_preset["tempo_bpm"]
    key_scale = style_preset["key_scale"]

    if compact:
        return _render_compact_prompt(
            style_preset,
            language,
            voice_guidance,
            style_prompt_size,
            bpm,
            key_scale,
            max_chars,
        )

    parts = [
        style_preset["style_prompts"][style_prompt_size],
        voice_guidance,
        f"{language} lyrics",
        f"{bpm} BPM",
        key_scale,
        f"{style_preset['time_signature']}/4 time",
        f"{style_preset['energy']} energy",
    ]

    text = _sentence(parts)
    if max_chars is None or len(text) <= max_chars:
        return text
    return _render_compact_prompt(
        style_preset,
        language,
        voice_guidance,
        style_prompt_size,
        bpm,
        key_scale,
        max_chars,
    )


def _render_compact_prompt(
    style_preset,
    language,
    voice_guidance,
    style_prompt_size,
    bpm,
    key_scale,
    max_chars,
):
    selected_style_prompt = style_preset["style_prompts"][style_prompt_size]
    critical = [
        selected_style_prompt,
        voice_guidance,
        f"{language} lyrics",
        f"{bpm} BPM",
        key_scale,
    ]

    text = _sentence(critical)
    if max_chars is None or len(text) <= max_chars:
        return text

    shorter_critical = [
        _clip(selected_style_prompt, 130),
        _clip(voice_guidance, 78),
        f"{language} lyrics",
        f"{bpm} BPM",
        key_scale,
    ]
    text = _sentence(shorter_critical)
    if len(text) <= max_chars:
        return text

    shortest_critical = [
        _clip(selected_style_prompt, 84),
        _clip(voice_guidance, 58),
        f"{language} lyrics",
        f"{bpm} BPM",
        key_scale,
    ]
    return _clip(_sentence(shortest_critical), max_chars)


def _render_kie_style_tags(style_preset, language):
    parts = []
    genre = str(style_preset.get("id") or "").replace("_", " ").strip()
    if genre:
        parts.append(genre)
    moods = style_preset.get("mood") or []
    if isinstance(moods, list):
        parts.extend(str(mood).strip() for mood in moods if str(mood).strip())
    energy = str(style_preset.get("energy") or "").strip()
    if energy:
        parts.append(f"{energy} energy")
    bpm = style_preset.get("tempo_bpm")
    if bpm is not None:
        parts.append(f"{bpm} BPM")
    instruments = style_preset.get("instrumentation") or []
    if isinstance(instruments, list):
        parts.extend(
            str(item).strip() for item in instruments[:6] if str(item).strip()
        )
    language_label = _language_label(language)
    if language_label:
        parts.append(f"{language_label} vocals")
    description = ""
    raw_description = style_preset.get("description")
    if isinstance(raw_description, dict):
        description = str(raw_description.get("en") or "").strip()
    elif isinstance(raw_description, str):
        description = raw_description.strip()
    if description:
        first = description.split(".")[0].strip()
        if first:
            parts.append(_clip(first, 80))
    return _clip(", ".join(part for part in parts if part), 1000)


def _provider_kwargs(provider, model, style_preset, language):
    if provider == "deapi" and model in _DEAPI_ACE_STEP_MODELS:
        return {
            "steps": 8,
            "bpm": style_preset["tempo_bpm"],
            "key_scale": style_preset["key_scale"],
            "time_signature": style_preset["time_signature"],
            "vocal_language": _ace_step_language(language),
        }

    if provider == "elevenlabs" and model == "music_v2":
        return {}

    if provider == "kie" and model == "V5_5":
        return {}

    if provider == "google" and model in _GOOGLE_LYRIA_MODELS:
        return {}

    if provider == "runware" and model in _RUNWARE_ACE_STEPS:
        return {
            "steps": _RUNWARE_ACE_STEPS[model],
            "bpm": style_preset["tempo_bpm"],
            "key_scale": style_preset["key_scale"],
            "time_signature": style_preset["time_signature"],
            "vocal_language": _ace_step_language(language),
        }

    return {}


def _merge_kwargs(generated_kwargs, user_kwargs):
    merged = dict(generated_kwargs)
    merged.update(user_kwargs)
    return merged


def _language_label(language):
    return _LANGUAGE_LABELS.get(language, language)


def _ace_step_language(language):
    return _ACE_STEP_LANGUAGE_CODES.get(language, "unknown")


def _sentence(parts):
    text = ", ".join(str(part).strip() for part in parts if str(part).strip())
    if text.endswith("."):
        return text
    return f"{text}."


def _clip(text, max_chars):
    if text is None:
        return ""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip(" ,.;:") + "..."
