"""Image dispatcher.

Exposes :func:`generate`, :func:`edit`, :func:`remix`, and :func:`analyze` as
the unified entrypoints for every supported provider. The provider is selected
via the ``api`` keyword argument and must match the file name (without ``.py``)
of an internal provider module.

Last updated: 2026-04-25
"""

from __future__ import annotations

import importlib
from typing import Any

from .._error_utils import attach_error, error_message
from .._submission_hooks import is_on_submitted_exception

__all__ = [
    "generate",
    "edit",
    "remix",
    "analyze",
    "update_cost",
    "available_generate_apis",
    "available_edit_apis",
    "available_remix_apis",
    "available_analyze_apis",
]


_GENERATE_APIS = (
    "bfl",
    "deepinfra",
    "falai",
    "fireworks",
    "google",
    "huggingface",
    "openai",
    "openrouter",
    "runway",
    "stability",
    "together",
    "xai",
)

_EDIT_APIS = _GENERATE_APIS

_REMIX_APIS = _GENERATE_APIS

_ANALYZE_APIS = (
    "anthropic",
    "deepinfra",
    "falai",
    "fireworks",
    "google",
    "groq",
    "huggingface",
    "mistral",
    "openai",
    "openrouter",
    "together",
    "xai",
)


def available_generate_apis():
    """Return the tuple of supported generate provider identifiers."""

    return _GENERATE_APIS


def available_edit_apis():
    """Return the tuple of supported edit provider identifiers."""

    return _EDIT_APIS


def available_remix_apis():
    """Return the tuple of supported remix provider identifiers."""

    return _REMIX_APIS


def available_analyze_apis():
    """Return the tuple of supported analyze provider identifiers."""

    return _ANALYZE_APIS


def _load_module(operation, api, allowed):
    if not isinstance(api, str) or not api:
        raise ValueError(
            f"image.{operation}(...) requires the keyword argument 'api'. "
            f"Available APIs: {', '.join(allowed)}."
        )
    if api not in allowed:
        raise ValueError(
            f"Unknown image {operation} API '{api}'. Available APIs: "
            f"{', '.join(allowed)}."
        )
    return importlib.import_module(f"._{operation}._apis.{api}", __name__)


def generate(prompt, model=None, *, api, **kwargs):
    """Generate one image from a prompt with the selected provider.

    Returns the normalized contract: `cust_usd`, `base64`, `warnings`,
    `request_id`. Provider-native options can be passed through ``**kwargs``.
    """

    try:
        module = _load_module("generate", api, _GENERATE_APIS)
        if model is None:
            result = module.generate(prompt, **kwargs)
        else:
            result = module.generate(prompt, model=model, **kwargs)
        return _attach_image_warning_error(result, api, "generate", model)
    except Exception as exc:
        return _image_failure(exc, api=api, operation="generate", model=model)


def edit(prompt, image, model=None, *, api, **kwargs):
    """Edit one image guided by a prompt and optional mask."""

    try:
        module = _load_module("edit", api, _EDIT_APIS)
        if model is None:
            result = module.edit(prompt, image, **kwargs)
        else:
            result = module.edit(prompt, image, model=model, **kwargs)
        return _attach_image_warning_error(result, api, "edit", model)
    except Exception as exc:
        return _image_failure(exc, api=api, operation="edit", model=model)


def remix(prompt, reference_images, model=None, *, api, **kwargs):
    """Remix one prompt with reference images using the selected provider."""

    try:
        module = _load_module("remix", api, _REMIX_APIS)
        arguments: dict[str, Any] = dict(kwargs)
        if model is not None:
            arguments["model"] = model
        result = module.remix(prompt, reference_images, **arguments)
        return _attach_image_warning_error(result, api, "remix", model)
    except Exception as exc:
        return _image_failure(exc, api=api, operation="remix", model=model)


def analyze(prompt, image, model=None, *, api, **kwargs):
    """Run vision/multimodal analysis with the selected provider."""

    try:
        module = _load_module("analyze", api, _ANALYZE_APIS)
        if model is None:
            result = module.analyze(prompt, image, **kwargs)
        else:
            result = module.analyze(prompt, image, model=model, **kwargs)
        return _attach_analyze_output_error(result, api, "analyze", model)
    except Exception as exc:
        if is_on_submitted_exception(exc):
            raise
        message = error_message(exc)
        return attach_error(
            {
                "request_id": "",
                "cost_usd": 0.0,
                "cost_currency": "USD",
                "cost_is_estimated": False,
                "cost_source": "unavailable",
                "cost_details": {},
                "input_text": prompt.strip() if isinstance(prompt, str) else "",
                "output": message,
                "warnings": message,
            },
            exc,
            provider=api,
            operation="analyze",
            model=model,
        )


def _image_failure(exc, *, api, operation, model):
    if is_on_submitted_exception(exc):
        raise exc
    message = error_message(exc)
    return attach_error(
        {
            "cust_usd": 0.0,
            "cost_usd": 0.0,
            "cost_currency": "USD",
            "cost_is_estimated": False,
            "cost_source": "unavailable",
            "cost_details": {},
            "base64": "",
            "warnings": message,
            "request_id": "",
        },
        exc,
        provider=api,
        operation=operation,
        model=model,
    )


def _attach_image_warning_error(result, api, operation, model):
    if not isinstance(result, dict):
        return result
    if result.get("error"):
        return result
    warning = str(result.get("warnings") or "").strip()
    if warning and not result.get("base64"):
        return attach_error(
            result,
            RuntimeError(warning),
            provider=api,
            operation=operation,
            model=model,
        )
    return result


def _attach_analyze_output_error(result, api, operation, model):
    if not isinstance(result, dict) or result.get("error"):
        return result
    output = str(result.get("output") or "").strip()
    if output.startswith("Provider error:"):
        result = dict(result)
        result["warnings"] = output
        return attach_error(
            result,
            RuntimeError(output),
            provider=api,
            operation=operation,
            model=model,
        )
    return result


def update_cost(operation, result, *, api):
    """Refresh `cust_usd` / `cost_usd` from a provider that supports lookups."""

    operation = str(operation or "").strip()
    allowed = {
        "generate": _GENERATE_APIS,
        "edit": _EDIT_APIS,
        "remix": _REMIX_APIS,
        "analyze": _ANALYZE_APIS,
    }
    if operation not in allowed:
        raise ValueError(
            "image.update_cost(...) operation must be one of: "
            f"{', '.join(sorted(allowed))}."
        )
    module = _load_module(operation, api, allowed[operation])
    if not hasattr(module, "update_cost"):
        raise NotImplementedError(
            f"image.update_cost is not implemented for {operation} api='{api}'."
        )
    return module.update_cost(result)
