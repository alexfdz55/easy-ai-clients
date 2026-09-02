"""Public dispatcher for music generation."""

from ._errors import MusicInputLimitError
from ._generation_options import get_generation_options as _get_generation_options
from ._lyrics_prompt import build_lyrics_prompt as _build_lyrics_prompt
from ._model_registry import PROVIDERS as _PROVIDERS
from ._router import (
    download_result as _download_result,
)
from ._router import (
    generate as _generate,
)
from ._router import (
    get_status as _get_status,
)
from ._style_adapter import get_style_presets as _get_style_presets

__all__ = [
    "MusicInputLimitError",
    "available_apis",
    "build_lyrics_prompt",
    "download_result",
    "generate",
    "get_generation_options",
    "get_status",
    "get_style_presets",
]


def available_apis():
    """Return the tuple of supported music provider identifiers."""
    return _PROVIDERS


def generate(lyrics, model=None, *, api, style=None, prompt=None, **kwargs):
    """Submit a music generation request through one provider module.

    Args:
        lyrics: Required. Lyrics to send to the provider.
        model: Optional. Provider model ID or standardized model key. When
            omitted, a validated provider default is used.
        api: Required. Provider key. Accepted values:
            - `"deapi"`: deAPI ACE-Step music generation.
            - `"elevenlabs"`: ElevenLabs Music.
            - `"google"`: Google Lyria.
            - `"kie"`: Kie.ai Suno V5.5.
            - `"runware"`: Runware ACE-Step.
        style: Optional. Exact predefined style name. Use `None` for no preset.
        prompt: Optional. Music prompt. Required when `style` is `None`.
            When both `style` and `prompt` are passed, `prompt` wins.
        **kwargs: Optional. Standardized music parameters.

    Returns:
        The normalized public generation dictionary.
    """
    return _generate(
        lyrics=lyrics,
        model=model,
        api=api,
        style=style,
        prompt=prompt,
        **kwargs,
    )


def get_status(generation, *, api=None):
    """Return an updated normalized generation status.

    Args:
        generation: Required. Dictionary returned by `generate()`.
        api: Optional. Provider key. When omitted, the provider is inferred from
            `generation["provider"]`.

    Returns:
        The normalized public generation dictionary.
    """
    return _get_status(generation, api=api)


def download_result(generation, *, api=None):
    """Download a completed generation result when available.

    Args:
        generation: Required. Dictionary returned by `generate()`.
        api: Optional. Provider key. When omitted, the provider is inferred from
            `generation["provider"]`.

    Returns:
        The normalized public generation dictionary.
    """
    return _download_result(generation, api=api)


def get_generation_options(api=None, model=None):
    """Return read-only metadata for implemented generation options.

    Args:
        api: Optional. Provider key used to filter options. Use `True` with
            `model=True` to return only the index summary.
        model: Optional. Standardized model key used to filter options. Native
            provider model IDs are treated as invalid filters. Use `True` with
            `api=True` to return only the index summary.

    Returns:
        A local dictionary describing implemented models, providers, and public
        generation parameters. This function does not call provider APIs.
    """
    return _get_generation_options(api=api, model=model)


def get_style_presets(fields=None, styles=None):
    """Return read-only copies of predefined style preset metadata.

    Args:
        fields: Optional. Use `None`, a string field name, or a list of string
            field names to filter returned preset fields.
        styles: Optional. Use `None`, a string style id, or a list of string
            style ids to filter returned presets.

    Returns:
        A local dictionary keyed by preset `id`. Invalid filters return an error
        dictionary. This function does not call provider APIs.
    """
    return _get_style_presets(fields=fields, styles=styles)


def build_lyrics_prompt(
    prompt,
    lyrics_text=None,
    duration=None,
    style=None,
    gender=None,
    voice_description=None,
    api=None,
):
    """Build prompt text for an external LLM to create or adapt song lyrics.

    Args:
        prompt: Required. User creative intent for the lyric.
        lyrics_text: Optional. Existing lyric text to adapt.
        duration: Optional. Approximate target duration in seconds.
        style: Optional. Exact predefined style name.
        gender: Optional. Accepted values: `"male"`, `"female"`, or `"both"`.
        voice_description: Optional. Direct voice guidance. Overrides preset
            and generic gender voice guidance.
        api: Optional. Use `"elevenlabs"` to add lyric-format guidance tuned
            for that music generator. Other values preserve the default prompt.

    Returns:
        A dictionary with exactly `system_prompt` and `prompt`. This function
        does not call provider APIs or language model APIs.
    """
    return _build_lyrics_prompt(
        prompt=prompt,
        lyrics_text=lyrics_text,
        duration=duration,
        style=style,
        gender=gender,
        voice_description=voice_description,
        api=api,
    )
