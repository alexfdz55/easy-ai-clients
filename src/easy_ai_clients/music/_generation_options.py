"""Read-only catalog for public music generation options."""

from copy import deepcopy

from ._model_registry import DEFAULT_MODEL_KEYS, MODEL_ALIASES


def get_generation_options(api=None, model=None):
    """Return local metadata for implemented generation options.

    Args:
        api: Optional. Provider key. Use a valid provider key to filter the
            detailed catalog. Use `True` with `model=True` to return the index
            summary.
        model: Optional. Standardized model key. Native provider model IDs are
            treated as invalid filters. Use `True` with `api=True` to return the
            index summary.

    Returns:
        A detailed catalog or an index summary. Invalid filters return the index
        summary instead of raising `ValueError`.
    """
    if api is True and model is True:
        return _index_summary()

    if api is None and model is None:
        return _catalog()

    valid_apis = _api_keys()
    valid_models = _model_keys()

    if api is not None and api not in valid_apis:
        return _index_summary()
    if model is not None and model not in valid_models:
        return _index_summary()

    if api is not None and model is not None and api not in _apis_for_model(model):
        return _index_summary()

    return _catalog(api=api, model=model)


def _catalog(api=None, model=None):
    catalog = {}
    for provider, models in MODEL_ALIASES.items():
        if api is not None and provider != api:
            continue
        for model_key, native_model in models.items():
            if model is not None and model_key != model:
                continue
            catalog.setdefault(model_key, {})[provider] = _parameters_for(provider, native_model)
    return deepcopy(catalog)


def _index_summary():
    return {
        "models": _model_keys(),
        "apis": _api_keys(),
        "model_apis": {model_key: _apis_for_model(model_key) for model_key in _model_keys()},
        "default_models": dict(DEFAULT_MODEL_KEYS),
    }


def _api_keys():
    return list(MODEL_ALIASES)


def _model_keys():
    keys = []
    for models in MODEL_ALIASES.values():
        for model_key in models:
            if model_key not in keys:
                keys.append(model_key)
    return keys


def _apis_for_model(model_key):
    return [
        provider
        for provider, models in MODEL_ALIASES.items()
        if model_key in models
    ]


def _parameters_for(provider, native_model):
    if provider == "deapi":
        return _deapi_parameters(native_model)
    if provider == "elevenlabs":
        return _elevenlabs_parameters()
    if provider == "google":
        return _google_parameters(native_model)
    if provider == "runware":
        return _runware_parameters(native_model)
    if provider == "kie":
        return _kie_parameters()
    return {}


def _base_text_parameters(provider):
    prompt_field = {
        "deapi": "caption",
        "elevenlabs": "prompt",
        "google": "contents[].parts[].text",
        "kie": "style",
        "runware": "positivePrompt",
    }[provider]
    lyrics_field = {
        "deapi": "lyrics",
        "elevenlabs": "prompt",
        "google": "contents[].parts[].text",
        "kie": "prompt",
        "runware": "settings.lyrics",
    }[provider]

    return {
        "lyrics": _option(
            True,
            None,
            "Free-form song lyric text.",
            "Main sung content or lyric input used by the provider.",
            lyrics_field,
            "Use normal lyric text. Optional section tags are part of the text.",
        ),
        "style": _option(
            False,
            None,
            "Exact file stem from easy_ai_clients/music/styles/*.py, without the .py extension.",
            "Builds a local prompt from preset style_prompts and voice_presets. If prompt is also passed, the explicit prompt replaces the preset style prompt.",
            "easy_ai_clients.music._style_adapter",
            "Use a reusable local style preset. Preset prompt sizes fall back from large to medium to small only after MusicInputLimitError.",
        ),
        "language": _option(
            False,
            None,
            "Accepts pt-BR, pt-PT, en-US, en-GB, en-IE, es-ES, fr-FR, or de-DE.",
            "Local language override for style-generated prompts. ACE-Step models also receive mapped vocal_language.",
            "easy_ai_clients.music._style_adapter",
            "Use with style to override the preset vocal language.",
        ),
        "gender": _option(
            False,
            None,
            "Accepted values: male, female, both.",
            "Local voice-selection control used only to build prompt text from style voice_presets or generic voice guidance.",
            "easy_ai_clients.music._style_adapter",
            "Use to request male, female, or duet-style voice guidance.",
        ),
        "voice_description": _option(
            False,
            None,
            "Free-form voice description text.",
            "Local prompt guidance that overrides style preset and generic gender voice guidance.",
            "easy_ai_clients.music._style_adapter",
            "Use when you need a specific vocal description.",
        ),
        "prompt": _option(
            False,
            None,
            "Free-form text. Required when style is not used.",
            "Describes genre, arrangement, voice, mix, and musical intent. With style, it replaces the preset prompt.",
            prompt_field,
            "Use for direct musical direction.",
        ),
    }


def _deapi_parameters(native_model):
    parameters = _base_text_parameters("deapi")
    parameters.update(
        {
            "duration": _option(
                False,
                60,
                "Integer, float, or numeric string in seconds. Numeric values are clamped to 10 to 300. Invalid or missing values use 60.",
                "Sets the duration sent in the payload. The wrapper always sends a normalized duration.",
                "duration",
                "Use to request a shorter or longer song within the local limit.",
            ),
            "steps": _option(
                False,
                8,
                _deapi_steps_values(native_model),
                "Controls inference_steps. When omitted, the wrapper sends 8.",
                "inference_steps",
                "Use to adjust the inference effort allowed by the model.",
            ),
            "bpm": _option(
                False,
                116,
                "Number from 30 to 300 when provided. None is not blocked by local validation.",
                "Sets the tempo sent to the provider.",
                "bpm",
                "Use to control rhythmic tempo.",
            ),
            "key_scale": _option(
                False,
                "A minor",
                "Free-form text. There is no local enum.",
                "Sets the key and scale sent to the provider.",
                "keyscale",
                "Use to guide harmony.",
            ),
            "time_signature": _option(
                False,
                4,
                "Accepts 2, 3, 4, or 6.",
                "Sets the time signature sent to the provider.",
                "timesignature",
                "Use to guide rhythmic division.",
            ),
            "vocal_language": _option(
                False,
                "pt",
                "Free-form text. There is no local enum.",
                "Sets the vocal language sent to the provider.",
                "vocal_language",
                "Use to guide pronunciation and sung language.",
            ),
            "reference_audio": _option(
                False,
                None,
                "Local audio file path.",
                "When provided, the wrapper opens the local file and sends multipart data.",
                "reference_audio",
                "Use to provide a local audio reference to the provider.",
            ),
            "webhook_url": _option(
                False,
                None,
                "Free-form URL. There is no local HTTPS validation.",
                "Passed through to the payload for job status notifications.",
                "webhook_url",
                "Use when the provider should call an external URL.",
            ),
        }
    )
    return parameters


def _elevenlabs_parameters():
    parameters = _base_text_parameters("elevenlabs")
    parameters["duration"] = _option(
        False,
        None,
        "Integer, float, or numeric string in seconds. Numeric values are clamped to 3 to 600. Invalid or missing values are omitted.",
        "The wrapper converts valid duration values to music_length_ms. When omitted or invalid, music_length_ms is not sent.",
        "music_length_ms",
        "Use to control composition duration.",
    )
    return parameters


def _google_parameters(native_model):
    parameters = _base_text_parameters("google")
    if native_model == "lyria-3-clip-preview":
        parameters["duration"] = _option(
            False,
            None,
            "Ignored. Lyria Clip output is fixed at about 30 seconds.",
            "Not sent and not added to the prompt.",
            "Not sent",
            "Use Pro when prompt-guided duration is required.",
        )
        parameters["token_preflight"] = _option(
            False,
            True,
            "Google countTokens is run against the final contents payload before generateContent.",
            "Blocks generation when the final contents exceed 131072 input tokens or token counting fails.",
            "models/{model}:countTokens",
            "Protects the generation call from over-limit inputs.",
        )
        return parameters
    parameters["duration"] = _option(
        False,
        None,
        "Integer, float, or numeric string in seconds. Numeric values are clamped to 15 to 180. Invalid or missing values are omitted.",
        "Not sent as a provider field. Valid values are added to the prompt as natural English target duration text.",
        "contents[].parts[].text",
        "Use to guide Lyria Pro toward an approximate song duration.",
    )
    parameters["token_preflight"] = _option(
        False,
        True,
        "Google countTokens is run against the final contents payload before generateContent.",
        "Blocks generation when the final contents exceed 131072 input tokens or token counting fails.",
        "models/{model}:countTokens",
        "Protects the generation call from over-limit inputs.",
    )
    return parameters


def _runware_parameters(native_model):
    parameters = _base_text_parameters("runware")
    parameters.update(
        {
            "duration": _option(
                False,
                60,
                "Integer, float, or numeric string in seconds. Numeric values are clamped to 30 to 300. Invalid or missing values use 60.",
                "The wrapper always sends a normalized duration.",
                "duration",
                "Use to request a shorter or longer song within the local limit.",
            ),
            "steps": _option(
                False,
                _runware_default_steps(native_model),
                _runware_steps_values(native_model),
                "Sent as steps. When omitted, the wrapper sends a safe model-specific default.",
                "steps",
                "Use to adjust the inference effort allowed by the model.",
            ),
            "bpm": _option(
                False,
                None,
                "Number from 30 to 300 when provided.",
                "Optional. When omitted, it is not sent in the payload.",
                "settings.bpm",
                "Use to control rhythmic tempo.",
            ),
            "key_scale": _option(
                False,
                None,
                "Free-form text. There is no local enum.",
                "Optional. When omitted, it is not sent in the payload.",
                "settings.keyScale",
                "Use to guide harmony.",
            ),
            "time_signature": _option(
                False,
                None,
                "Accepts 2, 3, 4, or 6.",
                "Optional. When omitted, it is not sent in the payload.",
                "settings.timeSignature",
                "Use to guide rhythmic division.",
            ),
            "vocal_language": _option(
                False,
                None,
                "Accepts unknown or an ISO 639-1 code present in the wrapper's local list.",
                "Optional. When omitted, it is not sent in the payload.",
                "settings.vocalLanguage",
                "Use to guide pronunciation and sung language.",
            ),
        }
    )
    return parameters


def _kie_parameters():
    parameters = _base_text_parameters("kie")
    parameters.update(
        {
            "duration": _option(
                False,
                60,
                "Integer, float, or numeric string in seconds. Numeric values are clamped to 10 to 360. Invalid or missing values use 60.",
                "Sent as duration. Only honored by native model V5_5.",
                "duration",
                "Use to request a shorter or longer song within the local limit.",
            ),
            "title": _option(
                False,
                None,
                "Free-form text, maximum 80 characters. When omitted, the first non-empty lyric line is used.",
                "Required by Kie custom mode. The wrapper always sends a title.",
                "title",
                "Use to name the generated track.",
            ),
            "webhook_url": _option(
                False,
                "https://example.com/kie-callback",
                "Free-form URL. Kie requires callBackUrl even when the caller only polls.",
                "Passed through as callBackUrl. A dummy HTTPS URL is sent when omitted.",
                "callBackUrl",
                "Use when the provider should call an external URL.",
            ),
        }
    )
    return parameters


def _deapi_steps_values(native_model):
    return "Accepts 1 to 8."


def _runware_steps_values(native_model):
    if native_model in {
        "runware:ace-step@v1.5-xl-base",
        "runware:ace-step@v1.5-xl-sft",
    }:
        return "Accepts 1 to 300."
    return "Accepts 1 to 20."


def _runware_default_steps(native_model):
    if native_model == "runware:ace-step@v1.5-turbo":
        return 10
    if native_model == "runware:ace-step@v1.5-xl-turbo":
        return 8
    if native_model in {
        "runware:ace-step@v1.5-xl-base",
        "runware:ace-step@v1.5-xl-sft",
    }:
        return 100
    return 8


def _option(required, default, accepted_values, description, provider_field, practical_use):
    return {
        "required": required,
        "default": default,
        "accepted_values": accepted_values,
        "description": description,
        "practical_use": practical_use,
        "provider_field": provider_field,
    }


