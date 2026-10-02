"""Audio dispatcher.

Exposes :func:`generate` for text-to-speech, :func:`transcribe` for
speech-to-text, and :func:`update_cost` for supported post-hoc audio cost
refreshes. The provider is selected via the ``api`` keyword argument and must
match the file name (without ``.py``) of an internal provider module.

Last updated: 2026-04-25
"""

from __future__ import annotations

import importlib
from typing import Any

from .._error_utils import attach_error, error_message
from ._transcribe.pre_processing import PreparedTranscriptionAudio, prepare_transcription_audio

__all__ = [
    "PreparedTranscriptionAudio",
    "generate",
    "list_voices",
    "get_voice",
    "design_voice",
    "clone_voice",
    "prepare_transcription_audio",
    "transcribe",
    "update_cost",
    "available_synthesize_apis",
    "available_transcribe_apis",
    "available_voice_apis",
]


_SYNTHESIZE_APIS = (
    "deepgram",
    "deepinfra",
    "elevenlabs",
    "falai",
    "google",
    "groq",
    "heygen",
    "mistral",
    "openai",
    "openrouter",
    "runway",
    "stability",
    "together",
    "xai",
)

_TRANSCRIBE_APIS = (
    "deepinfra",
    "deepgram",
    "elevenlabs",
    "falai",
    "fireworks",
    "google",
    "groq",
    "huggingface",
    "mistral",
    "openai",
    "openrouter",
    "speechmatics",
    "together",
    "xai",
)

_AUDIO_OPTION_UNSET = object()
_VOICE_APIS = ("deepinfra", "elevenlabs", "heygen", "mistral", "together")


def available_synthesize_apis():
    """Return the tuple of supported synthesis provider identifiers."""

    return _SYNTHESIZE_APIS


def available_transcribe_apis():
    """Return the tuple of supported transcription provider identifiers."""

    return _TRANSCRIBE_APIS


def available_voice_apis():
    """Return the tuple of supported voice-management provider identifiers."""

    return _VOICE_APIS


def _load_synthesize(api):
    if not isinstance(api, str) or not api:
        raise ValueError(
            "audio.generate(...) requires the keyword argument 'api'. "
            f"Available APIs: {', '.join(_SYNTHESIZE_APIS)}."
        )
    if api not in _SYNTHESIZE_APIS:
        raise ValueError(
            f"Unknown audio synthesis API '{api}'. Available APIs: "
            f"{', '.join(_SYNTHESIZE_APIS)}."
        )
    return importlib.import_module(f"._synthesize._apis.{api}", __name__)


def _load_transcribe(api):
    if not isinstance(api, str) or not api:
        raise ValueError(
            "audio.transcribe(...) requires the keyword argument 'api'. "
            f"Available APIs: {', '.join(_TRANSCRIBE_APIS)}."
        )
    if api not in _TRANSCRIBE_APIS:
        raise ValueError(
            f"Unknown audio transcription API '{api}'. Available APIs: "
            f"{', '.join(_TRANSCRIBE_APIS)}."
        )
    return importlib.import_module(f"._transcribe._apis.{api}", __name__)


def _load_voice(api):
    if not isinstance(api, str) or not api:
        raise ValueError(
            "audio voice operations require the keyword argument 'api'. "
            f"Available APIs: {', '.join(_VOICE_APIS)}."
        )
    if api not in _VOICE_APIS:
        raise ValueError(
            f"Unknown audio voice API '{api}'. Available APIs: {', '.join(_VOICE_APIS)}."
        )
    return importlib.import_module(f"._voices._apis.{api}", __name__)


def generate(text, model=None, voice=None, language_code="en", *, api, **kwargs):
    """Synthesize speech with the selected provider.

    ### Parameters:
    - text (str): Input text to synthesize.
    - model (str | None): Provider-specific model identifier. When omitted, the
      provider default is used.
    - voice (str | None): Provider-specific voice identifier. When omitted, the
      provider default is used.
    - language_code (str): BCP-47 language code used by the provider.
    - api (str): Provider identifier listed by :func:`available_synthesize_apis`.
    - **kwargs: Extra provider-native parameters.

    ### Returns:
    - dict: Provider-normalized audio result with `cost_usd`, `audio` and
      `words` fields.
    """

    try:
        module = _load_synthesize(api)
        arguments: dict[str, Any] = {"language_code": language_code, **kwargs}
        if model is not None:
            arguments["model"] = model
        if voice is not None:
            arguments["voice"] = voice
        return module.generate(text, **arguments)
    except Exception as exc:
        return attach_error(
            {
                "cost_usd": 0.0,
                "cost_currency": "USD",
                "cost_source": "unavailable",
                "cost_is_estimated": False,
                "cost_details": {},
                "audio": None,
                "words": {},
                "warnings": error_message(exc),
            },
            exc,
            provider=api,
            operation="generate",
            model=model,
        )


def transcribe(
    audio_input,
    model=None,
    *,
    api,
    audio_normalize: bool | object = _AUDIO_OPTION_UNSET,
    audio_upload_format: str | object = _AUDIO_OPTION_UNSET,
    audio_upload_codec: str | None | object = _AUDIO_OPTION_UNSET,
    audio_upload_bitrate: str | None | object = _AUDIO_OPTION_UNSET,
    **kwargs,
):
    """Transcribe audio with the selected provider.

    ### Parameters:
    - audio_input: Path, URL, bytes, base64 string, or `pydub.AudioSegment`.
    - model (str | None): Provider-specific model identifier. When omitted, the
      provider default is used.
    - api (str): Provider identifier listed by :func:`available_transcribe_apis`.
    - audio_normalize (bool): Normalize local audio to 16 kHz mono PCM16 before upload.
    - audio_upload_format (str): Upload/export format for prepared audio. Defaults to WAV.
    - audio_upload_codec (str | None): Optional export codec, for example `libopus`.
    - audio_upload_bitrate (str | None): Optional export bitrate, for example `24k`.
    - **kwargs: Extra provider-native parameters.

    ### Returns:
    - dict: Normalized transcription bundle with transcript data and explicit
      cost metadata.
    """

    try:
        module = _load_transcribe(api)
        audio_options_requested = any(
            value is not _AUDIO_OPTION_UNSET
            for value in (
                audio_normalize,
                audio_upload_format,
                audio_upload_codec,
                audio_upload_bitrate,
            )
        )
        if isinstance(audio_input, PreparedTranscriptionAudio) and not audio_options_requested:
            request_audio_input = audio_input
        else:
            request_audio_input = prepare_transcription_audio(
                audio_input,
                normalize=True
                if audio_normalize is _AUDIO_OPTION_UNSET
                else bool(audio_normalize),
                upload_format="wav"
                if audio_upload_format is _AUDIO_OPTION_UNSET
                else str(audio_upload_format),
                codec=None
                if audio_upload_codec is _AUDIO_OPTION_UNSET
                else audio_upload_codec,
                bitrate=None
                if audio_upload_bitrate is _AUDIO_OPTION_UNSET
                else audio_upload_bitrate,
            )
        if model is None:
            return module.transcribe(request_audio_input, **kwargs)
        return module.transcribe(request_audio_input, model=model, **kwargs)
    except Exception as exc:
        message = error_message(exc)
        return attach_error(
            {
                "text": "",
                "words": {},
                "segments": {},
                "silences": {},
                "provider_metadata": {},
                "request_id": None,
                "cost_usd": 0.0,
                "cost_currency": "USD",
                "cost_source": "unavailable",
                "cost_is_estimated": False,
                "cost_details": {},
                "cost_lookup_error": message,
                "warnings": message,
            },
            exc,
            provider=api,
            operation="transcribe",
            model=model,
        )


def list_voices(*, api, **kwargs):
    """List voices exposed by the selected provider."""

    try:
        return _load_voice(api).list_voices(**kwargs)
    except Exception as exc:
        return _voice_failure(exc, api=api, operation="list_voices")


def get_voice(voice_id, *, api, **kwargs):
    """Fetch one provider voice by id."""

    try:
        return _load_voice(api).get_voice(voice_id, **kwargs)
    except Exception as exc:
        return _voice_failure(exc, api=api, operation="get_voice")


def design_voice(prompt, *, api, **kwargs):
    """Design or search for voices from a natural-language prompt."""

    try:
        return _load_voice(api).design_voice(prompt, **kwargs)
    except Exception as exc:
        return _voice_failure(exc, api=api, operation="design_voice")


def clone_voice(audio_input=None, voice_name=None, *, api, **kwargs):
    """Create a cloned voice when the selected provider supports cloning."""

    try:
        return _load_voice(api).clone_voice(audio_input=audio_input, voice_name=voice_name, **kwargs)
    except Exception as exc:
        return _voice_failure(exc, api=api, operation="clone_voice")


def _voice_failure(exc, *, api, operation):
    message = error_message(exc)
    return attach_error(
        {
            "provider": api,
            "operation": operation,
            "data": None,
            "raw_response": {},
            "warnings": message,
        },
        exc,
        provider=api,
        operation=operation,
    )


def update_cost(operation, result, *, api):
    """Refresh cost metadata for an audio result when the provider supports it."""

    if operation != "transcribe":
        raise ValueError("audio.update_cost currently supports operation='transcribe' only.")

    module = _load_transcribe(api)
    if not hasattr(module, "update_cost"):
        raise NotImplementedError(
            f"audio.update_cost is not implemented for operation='transcribe' and api='{api}'."
        )
    return module.update_cost(result)
