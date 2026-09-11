"""Internal provider routing used by the public `music` surface."""

import importlib

from ._common import normalize_cost, sanitize
from ._errors import MusicInputLimitError
from ._model_registry import PROVIDERS, resolve_model
from ._style_adapter import build_generation_request

REMOVED_PUBLIC_KWARGS = {
    "audio_settings",
    "include_cost",
    "negative_prompt",
    "number_results",
    "output_format",
    "output_type",
    "seed",
    "ttl",
    "_force_instrumental",
}
PUBLIC_GENERATION_KEYS = (
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
)
PROMPT_SIZE_ATTEMPTS = (
    ("large", "large"),
    ("large", "medium"),
    ("medium", "medium"),
    ("medium", "small"),
    ("small", "small"),
)


def generate(lyrics, model=None, *, api, style=None, prompt=None, **kwargs):
    """Submit a music generation request through one provider module.

    Args:
        lyrics: Required. Lyrics to send to the provider.
        model: Optional. Provider model ID or standardized model key. When
            omitted, a validated provider default is used.
        api: Required. Provider module key from `music/_apis/`.
        style: Optional. Exact predefined style name. Use `None` for no preset.
        prompt: Optional. Music prompt. Required when `style` is `None`.
            When both `style` and `prompt` are passed, `prompt` wins.
        **kwargs: Optional. Standardized music parameters.

    Returns:
        The normalized public generation dictionary returned by the provider.

    Raises:
        ValueError: If `api` is not in the explicit provider registry.
        ValueError: Provider modules can also raise this for unsupported models,
            unsupported standardized parameters, missing required prompt, or
            unsupported kwargs.
    """
    _validate_api(api, "generate")
    _reject_removed_public_kwargs(kwargs)

    native_model, model_key = resolve_model(api, model)
    module = _load_api(api)
    generation = _generate_with_adaptive_prompt_size(
        module,
        api,
        native_model,
        lyrics,
        style,
        prompt,
        kwargs,
    )
    generation["model_key"] = model_key
    return _public_generation(generation)


def _generate_with_adaptive_prompt_size(module, api, native_model, lyrics, style, prompt, kwargs):
    attempts = _prompt_size_attempts(style, prompt, api=api)
    seen_requests = set()
    can_retry_with_large_prompt = len(attempts) > 1

    for style_prompt_size, voice_prompt_size in attempts:
        request = build_generation_request(
            provider=api,
            model=native_model,
            lyrics=lyrics,
            style=style,
            prompt=prompt,
            kwargs=kwargs,
            style_prompt_size=style_prompt_size,
            voice_prompt_size=voice_prompt_size,
        )
        if request["kwargs"].get("prompt") is None:
            raise ValueError("style or prompt is required")

        request_key = repr((request["lyrics"], request["model"], request["kwargs"]))
        if request_key in seen_requests:
            continue
        seen_requests.add(request_key)

        try:
            return module.generate(
                lyrics=request["lyrics"],
                model=request["model"],
                **request["kwargs"],
            )
        except MusicInputLimitError:
            if not can_retry_with_large_prompt:
                raise
            continue

    if not can_retry_with_large_prompt:
        raise RuntimeError("music generation did not produce a provider request")

    request = build_generation_request(
        provider=api,
        model=native_model,
        lyrics=lyrics,
        style=style,
        prompt=prompt,
        kwargs=kwargs,
        style_prompt_size="large",
        voice_prompt_size="large",
    )
    if request["kwargs"].get("prompt") is None:
        raise ValueError("style or prompt is required")
    return module.generate(
        lyrics=request["lyrics"],
        model=request["model"],
        **request["kwargs"],
    )


def _prompt_size_attempts(style, prompt, api=None):
    if api == "kie" or style is None or _has_direct_prompt(prompt):
        return (("large", "large"),)
    return PROMPT_SIZE_ATTEMPTS


def _has_direct_prompt(prompt):
    return isinstance(prompt, str) and bool(prompt.strip())


def get_status(generation, *, api=None):
    """Return an updated normalized generation status.

    Args:
        generation: Required. Normalized generation dictionary returned by
            `generate()`.
        api: Optional. Provider key. When omitted, the provider is inferred from
            `generation["provider"]`.

    Returns:
        The normalized public generation dictionary.
    """
    selected_api = _resolve_generation_api(generation, api, "get_status")
    module = _load_api(selected_api)
    updated = module.get_status(generation)
    public = _public_generation(updated)
    generation.clear()
    generation.update(public)
    return public


def download_result(generation, *, api=None):
    """Download a completed result when the provider exposes a result URL.

    Args:
        generation: Required. Normalized generation dictionary returned by
            `generate()`.
        api: Optional. Provider key. When omitted, the provider is inferred from
            `generation["provider"]`.

    Returns:
        The normalized public generation dictionary.
    """
    selected_api = _resolve_generation_api(generation, api, "download_result")
    module = _load_api(selected_api)
    updated = module.download_result(generation)
    public = _public_generation(updated)
    generation.clear()
    generation.update(public)
    return public


def _reject_removed_public_kwargs(kwargs):
    blocked = sorted(set(kwargs) & REMOVED_PUBLIC_KWARGS)
    if blocked:
        raise ValueError(f"Unsupported kwargs: {', '.join(blocked)}")


def _load_api(api):
    _validate_api(api, "music operation")
    return importlib.import_module(f"._apis.{api}", __package__)


def _validate_api(api, operation):
    if not isinstance(api, str) or not api.strip():
        raise ValueError(
            f"music.{operation}(...) requires api. "
            f"Available APIs: {', '.join(PROVIDERS)}."
        )
    if api not in PROVIDERS:
        raise ValueError(
            f"Unknown music API '{api}'. Available APIs: {', '.join(PROVIDERS)}."
        )


def _resolve_generation_api(generation, api, operation):
    if not isinstance(generation, dict):
        raise ValueError("generation must be a dictionary")
    provider = generation.get("provider")
    selected_api = api or provider
    _validate_api(selected_api, operation)
    if api is not None and provider and provider != api:
        raise ValueError(
            f"generation provider '{provider}' does not match api '{api}'"
        )
    return selected_api


def _public_generation(generation):
    output = {key: generation.get(key) for key in PUBLIC_GENERATION_KEYS}
    cost_usd = normalize_cost(output["cost_usd"])
    if cost_usd is None:
        output["cost_usd"] = 0.0
        output["cost_source"] = "unavailable"
        output["cost_is_estimated"] = False
    else:
        output["cost_usd"] = cost_usd
    output["cost_currency"] = output["cost_currency"] or "USD"
    output["cost_source"] = output["cost_source"] or "unavailable"
    output["cost_is_estimated"] = bool(output["cost_is_estimated"])
    output["cost_details"] = sanitize(dict(output["cost_details"] or {}))
    raw_metadata = dict(output["metadata"] or {})
    output["metadata"] = sanitize(raw_metadata)
    # The second take of a Kie/Suno generate is a plain provider CDN URL the caller
    # needs verbatim to download it (it expires); `sanitize` redacts every `*_url`
    # key, which silently turned the two-take contract into one take (2026-09-10).
    alternate = raw_metadata.get("alternate_audio_url")
    if isinstance(alternate, str) and alternate.startswith(("http://", "https://")):
        output["metadata"]["alternate_audio_url"] = alternate
    return output


