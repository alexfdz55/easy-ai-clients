"""Provider-scoped model aliases used by the public runtime."""

PROVIDERS = (
    "deapi",
    "elevenlabs",
    "google",
    "kie",
    "runware",
)

MODEL_ALIASES = {
    "deapi": {
        "ace_step_v1_5_turbo": "AceStep_1_5_Turbo",
        "ace_step_1_5_xl_turbo_int8": "AceStep_1_5_XL_Turbo_INT8",
    },
    "elevenlabs": {
        "eleven_music": "music_v2",
        "eleven_music_v2": "music_v2",
        "music_v2": "music_v2",
    },
    "google": {
        "lyria_3_clip_preview": "lyria-3-clip-preview",
        "lyria_3_pro_preview": "lyria-3-pro-preview",
    },
    "kie": {
        "suno_v5_5": "V5_5",
        "V5_5": "V5_5",
    },
    "runware": {
        "ace_step_v1_5_turbo": "runware:ace-step@v1.5-turbo",
        "ace_step_v1_5_xl_base": "runware:ace-step@v1.5-xl-base",
        "ace_step_v1_5_xl_sft": "runware:ace-step@v1.5-xl-sft",
        "ace_step_v1_5_xl_turbo": "runware:ace-step@v1.5-xl-turbo",
    },
}

DEFAULT_MODELS = {
    "deapi": "AceStep_1_5_Turbo",
    "elevenlabs": "music_v2",
    "google": "lyria-3-clip-preview",
    "kie": "V5_5",
    "runware": "runware:ace-step@v1.5-xl-turbo",
}

DEFAULT_MODEL_KEYS = {
    "deapi": "ace_step_v1_5_turbo",
    "elevenlabs": "eleven_music",
    "google": "lyria_3_clip_preview",
    "kie": "suno_v5_5",
    "runware": "ace_step_v1_5_xl_turbo",
}


def resolve_model(provider, model):
    """Return the provider-native model ID and standardized model key.

    Args:
        provider: Required. Provider key.
        model: Optional. Provider-native model ID or standardized model key.
            When omitted, the provider-specific validated default is used.

    Returns:
        A tuple with `(native_model, model_key)`.

    Raises:
        ValueError: If the model is empty or unsupported for the provider.
    """
    if model is None or not str(model).strip():
        model_key = DEFAULT_MODEL_KEYS.get(provider)
        native_model = DEFAULT_MODELS.get(provider)
        if not model_key or not native_model:
            raise ValueError("model is required")
        return native_model, model_key

    if not model:
        raise ValueError("model is required")

    value = str(model).strip()
    aliases = MODEL_ALIASES.get(provider, {})
    if value in aliases:
        return aliases[value], value

    reverse = {native: key for key, native in aliases.items()}
    if value in reverse:
        return value, reverse[value]

    raise ValueError(f"Unsupported model for {provider}: {model}")


def model_key_for(provider, model):
    """Return the standardized key for a provider-native model ID."""
    return resolve_model(provider, model)[1]


