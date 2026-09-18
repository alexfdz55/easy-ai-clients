"""Helpers neutros de provedor compartilhados pelos wrappers.

Última atualização: 2026-04-23
"""

from __future__ import annotations

import base64
import binascii
import io
import json
import time
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
from typing import Any

from PIL import Image

from ..._error_utils import error_message
from .cost_utils import decimal_to_float
from .errors import BlockedOperation, ProviderResponseError
from .http_utils import download_bytes, request
from .types import AnalyzeOperationResult, ImageOperationResult, JsonDict

_OPENROUTER_MODELS_CACHE: dict[str, Any] = {"fetched_at": 0.0, "models": []}
_OPENROUTER_TTL_SECONDS = 3600.0


def join_warnings(*parts: str | None) -> str:
    """Join warning fragments into a stable, deduplicated message string.

    Args:
        *parts: Warning fragments, each possibly empty or `None`.

    Returns:
        Single semicolon-separated warning string with duplicate fragments
        removed and whitespace normalized.
    """

    cleaned: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if not part:
            continue
        text = " ".join(part.strip().split())
        if not text or text in seen:
            continue
        cleaned.append(text)
        seen.add(text)
    return "; ".join(cleaned)


def consume_kwargs(
    kwargs: dict[str, Any],
    defaults: dict[str, Any],
    *,
    passthrough_keys: Iterable[str] = (),
) -> tuple[dict[str, Any], str]:
    """Consume documented keyword arguments and preserve provider-native extras.

    Args:
        kwargs: Mutable kwargs dictionary received by a public wrapper.
        defaults: Supported keyword names and their default values.
        passthrough_keys: Extra supported names that should be forwarded only
            when explicitly supplied.

    Returns:
        Tuple `(values, warning)`. `values` contains defaults plus supplied
        values. Unknown names are stored under `_provider_kwargs` and forwarded
        by `payload_from_keys`; `warning` is kept for provider/local issues.
    """

    values = dict(defaults)
    for key in list(kwargs):
        if key in values:
            values[key] = kwargs.pop(key)

    for key in passthrough_keys:
        if key in kwargs:
            values[key] = kwargs.pop(key)

    values["_provider_kwargs"] = dict(kwargs)
    return values, ""


def payload_from_keys(values: dict[str, Any], keys: Iterable[str]) -> dict[str, Any]:
    """Return explicitly supplied provider payload fields from consumed values."""

    payload = {key: values[key] for key in keys if key in values and values[key] is not None}
    payload.update({key: value for key, value in values.get("_provider_kwargs", {}).items() if value is not None})
    return payload


def provider_error_to_warning(exc: Exception) -> str:
    """Convert a provider exception into a public `warnings` string.

    Args:
        exc: Exception raised by shared HTTP logic or provider-specific code.

    Returns:
        Warning text suitable for the normalized public result contract.
    """

    if isinstance(exc, ProviderResponseError):
        pieces = [str(exc)]
        if exc.response_text:
            pieces.append(exc.response_text[:400])
        return f"Provider error: {error_message(join_warnings(*pieces))}"
    return f"Provider error: {error_message(exc)}"


def extract_request_id(
    response: Any | None = None,
    payload: JsonDict | None = None,
) -> str:
    """Extract the best available request identifier from headers or payloads.

    Args:
        response: Optional HTTP response object.
        payload: Optional parsed JSON payload.

    Returns:
        Request id, generation id, or job id as a string. Returns `""` when the
        provider does not expose a usable identifier.
    """

    header_candidates = [
        "x-fal-request-id",
        "x-request-id",
        "request-id",
        "openai-request-id",
        "anthropic-request-id",
    ]
    if response is not None:
        headers = getattr(response, "headers", {}) or {}
        for key in header_candidates:
            value = headers.get(key)
            if value:
                return str(value)

    if payload:
        for key in ("request_id", "response_id", "id"):
            value = payload.get(key)
            if value:
                return str(value)
    return ""


def response_json(response: Any) -> JsonDict:
    """Parse a response as JSON with a deterministic empty-dict fallback.

    Args:
        response: HTTP response object.

    Returns:
        Parsed JSON dictionary, or `{}` when parsing fails or the JSON body is
        not an object.
    """

    try:
        parsed = response.json()
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def extract_text_from_openai_style_response(payload: JsonDict) -> str:
    """Extract text from OpenAI-compatible Responses or Chat payloads.

    Args:
        payload: Parsed provider payload following an OpenAI-like schema.

    Returns:
        Combined text content, or `""` when no text blocks are present.
    """

    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]

    output = payload.get("output")
    if isinstance(output, list):
        text_parts: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            for content in item.get("content", []):
                if not isinstance(content, dict):
                    continue
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    text_parts.append(str(content["text"]))
        if text_parts:
            return "\n".join(text_parts).strip()

    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                    text_parts.append(str(item["text"]))
            if text_parts:
                return "\n".join(text_parts).strip()
    return ""


def _extract_data_url_base64(data_url: str) -> str:
    if data_url.startswith("data:") and "," in data_url:
        return data_url.split(",", 1)[1]
    return data_url


def normalize_base64_image_to_png(value: str) -> str:
    """Normalize a base64 image payload or data URL into PNG base64.

    Args:
        value: Base64 payload or `data:` URL returned by a provider.

    Returns:
        Pure PNG base64 string without a data URL prefix.

    Raises:
        ProviderResponseError: If the payload is not valid base64 image data.
    """

    try:
        raw_bytes = base64.b64decode(_extract_data_url_base64(value), validate=False)
    except (binascii.Error, ValueError) as exc:
        raise ProviderResponseError("Provider returned an invalid base64 image payload.") from exc
    return image_bytes_to_base64_png(raw_bytes)


def image_bytes_to_base64_png(raw_bytes: bytes) -> str:
    """Normalize raw image bytes to PNG and return pure base64 content.

    Args:
        raw_bytes: Original image bytes from a provider response.

    Returns:
        PNG base64 string suitable for the normalized public contract.
    """

    with Image.open(io.BytesIO(raw_bytes)) as image:
        image.load()
        if image.mode not in {"RGB", "RGBA", "L", "LA"}:
            image = image.convert("RGBA" if "A" in image.mode else "RGB")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def download_image_as_base64_png(
    image_url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout_seconds: int = 60,
) -> str:
    """Download a provider image URL and normalize it to PNG base64.

    Args:
        image_url: Temporary or signed image URL.
        headers: Optional request headers for signed downloads.
        timeout_seconds: Download timeout.

    Returns:
        PNG base64 string without a data URL prefix.
    """

    raw_bytes = download_bytes(
        image_url,
        headers=headers,
        timeout_seconds=timeout_seconds,
    )
    return image_bytes_to_base64_png(raw_bytes)


def extract_image_output(payload: JsonDict, *, timeout_seconds: int = 60) -> tuple[str, str]:
    """Extract an output image from common provider payload shapes.

    Args:
        payload: Parsed provider response.
        timeout_seconds: Timeout used when a temporary URL must be downloaded.

    Returns:
        Tuple `(base64_content, warning_text)`. The warning is empty on success.
    """

    data = payload.get("data")
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            if first.get("b64_json"):
                return normalize_base64_image_to_png(str(first["b64_json"])), ""
            if first.get("url"):
                return (
                    download_image_as_base64_png(str(first["url"]), timeout_seconds=timeout_seconds),
                    "",
                )

    if payload.get("base64"):
        images = payload["base64"]
        if isinstance(images, list) and images:
            return normalize_base64_image_to_png(str(images[0])), ""
        if isinstance(images, str):
            return normalize_base64_image_to_png(images), ""

    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message", {})
        images = message.get("images")
        if isinstance(images, list) and images:
            image_url = images[0].get("image_url", {}).get("url")
            if image_url:
                value = str(image_url)
                if value.startswith("data:"):
                    return normalize_base64_image_to_png(value), ""
                return (
                    download_image_as_base64_png(value, timeout_seconds=timeout_seconds),
                    "",
                )
    return "", "Provider response did not contain an image payload."


def detect_block(payload: JsonDict, *, operation: str) -> BlockedOperation | None:
    """Detect provider-side moderation, safety blocks, or empty blocked outputs.

    Args:
        payload: Parsed provider payload.
        operation: Public operation name (`generate`, `edit`, `analyze`,
            `remix`) used in warning text.

    Returns:
        :class:`BlockedOperation` when the payload clearly signals policy
        intervention, otherwise `None`.
    """

    finish_reason = str(
        payload.get("finishReason")
        or payload.get("finish_reason")
        or payload.get("status")
        or ""
    ).lower()
    if any(token in finish_reason for token in ("moderated", "filtered", "blocked", "safety")):
        warning = f"{operation} was blocked by provider policy: {finish_reason}."
        return BlockedOperation(warning=warning, request_id=str(payload.get("id") or ""))

    error = payload.get("error")
    if isinstance(error, dict):
        message = error.get("message") or error.get("error") or json.dumps(error)
        lowered = str(message).lower()
        if any(
            token in lowered
            for token in ("moderation", "policy", "safety", "blocked", "not allowed")
        ):
            return BlockedOperation(
                warning=f"{operation} was blocked by provider policy: {message}",
                request_id=str(payload.get("id") or ""),
            )
    if isinstance(error, str):
        lowered = error.lower()
        if any(token in lowered for token in ("moderation", "policy", "safety", "blocked")):
            return BlockedOperation(
                warning=f"{operation} was blocked by provider policy: {error}",
                request_id=str(payload.get("id") or ""),
            )
    return None


def image_result(
    *,
    base64_value: str = "",
    warnings: str = "",
    cust_usd: Decimal | float = 0.0,
    request_id: str = "",
    cost_source: str | None = None,
    cost_is_estimated: bool = True,
    cost_details: dict[str, Any] | None = None,
) -> ImageOperationResult:
    """Build the normalized result contract for image-returning operations.

    Args:
        base64_value: Pure base64 PNG string, or `""` on failure/block.
        warnings: Public warning text.
        cust_usd: Exact or best-known USD cost.
        request_id: Provider request/job identifier, or `""`.
        cost_source: Source used for cost calculation.
        cost_is_estimated: Whether the value is table/estimate based.
        cost_details: Provider/adapter specific cost metadata.

    Returns:
        Dictionary containing the legacy `cust_usd` key plus the standard
        `cost_usd` cost metadata used by other modalities.
    """

    cost_value = decimal_to_float(cust_usd)
    if cost_source is None:
        cost_source = "official_pricing_table" if cost_value else "unavailable"
    return {
        "cust_usd": cost_value,
        "cost_usd": cost_value,
        "cost_currency": "USD",
        "cost_is_estimated": bool(cost_is_estimated),
        "cost_source": cost_source,
        "cost_details": dict(cost_details or {}),
        "base64": base64_value,
        "warnings": warnings,
        "request_id": request_id,
    }


def analyze_result(
    *,
    request_id: str = "",
    cost_usd: Decimal | float = 0.0,
    input_text: str = "",
    output: str = "",
    cost_source: str | None = None,
    cost_is_estimated: bool = True,
    cost_details: dict[str, Any] | None = None,
) -> AnalyzeOperationResult:
    """Build the normalized result contract for analyze operations.

    Args:
        request_id: Provider request identifier, or `""`.
        cost_usd: Exact or best-known USD cost.
        input_text: Normalized prompt sent to the provider.
        output: Text returned by the provider or normalized error text.
        cost_source: Source used for cost calculation.
        cost_is_estimated: Whether the value is table/estimate based.
        cost_details: Provider/adapter specific cost metadata.

    Returns:
        Dictionary containing normalized text output and standard cost metadata.
    """

    cost_value = decimal_to_float(cost_usd)
    if cost_source is None:
        cost_source = "official_pricing_table" if cost_value else "unavailable"
    return {
        "request_id": request_id,
        "cost_usd": cost_value,
        "cost_currency": "USD",
        "cost_is_estimated": bool(cost_is_estimated),
        "cost_source": cost_source,
        "cost_details": dict(cost_details or {}),
        "input_text": input_text,
        "output": output,
    }


def extract_openrouter_usage_cost(payload: JsonDict) -> Decimal | None:
    """Extract exact OpenRouter cost from usage or generation metadata."""

    if not isinstance(payload, dict):
        return None

    usage = payload.get("usage")
    if isinstance(usage, dict):
        for key in ("cost", "total_cost"):
            cost = _decimal_or_none(usage.get(key))
            if cost is not None:
                return cost
    else:
        cost = _decimal_or_none(usage)
        if cost is not None:
            return cost

    for key in ("total_cost", "cost"):
        cost = _decimal_or_none(payload.get(key))
        if cost is not None:
            return cost
    return None


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def get_openrouter_models(*, timeout_seconds: int = 60) -> list[JsonDict]:
    """Return cached OpenRouter model metadata used for capability validation.

    Args:
        timeout_seconds: Timeout for the live model catalog request.

    Returns:
        List of model metadata dictionaries. Results are cached in-memory for one
        hour to avoid repeated paid or rate-limited lookups.
    """

    now = time.time()
    if now - _OPENROUTER_MODELS_CACHE["fetched_at"] < _OPENROUTER_TTL_SECONDS:
        return list(_OPENROUTER_MODELS_CACHE["models"])

    response = request(
        "GET",
        "https://openrouter.ai/api/v1/models?output_modalities=all",
        timeout_seconds=timeout_seconds,
    )
    payload = response_json(response)
    models = payload.get("data", [])
    if not isinstance(models, list):
        models = []
    _OPENROUTER_MODELS_CACHE["fetched_at"] = now
    _OPENROUTER_MODELS_CACHE["models"] = models
    return list(models)


def validate_openrouter_model(
    *,
    model: str,
    operation: str,
    timeout_seconds: int = 60,
) -> str | None:
    """Keep OpenRouter catalog lookup as documentation, not a local acceptance gate.

    Args:
        model: OpenRouter model id.
        operation: Public operation name.
        timeout_seconds: Timeout for live model-catalog lookup.

    Returns:
        `None` when the model is compatible, otherwise a user-facing warning that
        explains why the model cannot be used safely for the operation.
    """

    return None


def update_openrouter_cost_from_request_id(
    result_dict: dict[str, Any],
    *,
    api_key: str,
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    """Resolve o custo final do OpenRouter a partir de um `request_id`.

    ### Parâmetros:
        result_dict: Resultado público normalizado retornado previamente.
        api_key: Chave do OpenRouter usada para consultar o custo final.
        timeout_seconds: Timeout da consulta.

    ### Retorna:
        Novo dict com o mesmo contrato público. Quando o custo final não estiver
        disponível, preserva o valor existente sem adicionar campos extras.
    """

    request_id = str(result_dict.get("request_id") or "")
    output = str(result_dict.get("output") or "")
    input_text = str(result_dict.get("input_text") or "")
    current_cost = result_dict.get("cost_usd") or 0.0
    current_source = result_dict.get("cost_source")
    current_is_estimated = result_dict.get("cost_is_estimated", True)
    current_details = result_dict.get("cost_details")
    if not isinstance(current_details, dict):
        current_details = {}
    if not request_id:
        return analyze_result(
            request_id=request_id,
            cost_usd=current_cost,
            cost_source=current_source,
            cost_is_estimated=bool(current_is_estimated),
            cost_details=current_details,
            input_text=input_text,
            output=output,
        )

    response = request(
        "GET",
        "https://openrouter.ai/api/v1/generation",
        headers={"Authorization": f"Bearer {api_key}"},
        params={"id": request_id},
        timeout_seconds=timeout_seconds,
    )
    parsed = response_json(response)
    payload = parsed.get("data") or parsed
    total_cost = extract_openrouter_usage_cost(payload)
    if total_cost is None:
        return analyze_result(
            request_id=request_id,
            cost_usd=current_cost,
            cost_source=current_source,
            cost_is_estimated=bool(current_is_estimated),
            cost_details=current_details,
            input_text=input_text,
            output=output,
        )
    return analyze_result(
        request_id=request_id,
        cost_usd=total_cost,
        cost_source="openrouter_generation_lookup",
        cost_is_estimated=False,
        cost_details={"request_id": request_id},
        input_text=input_text,
        output=output,
    )


def update_openrouter_image_cost_from_request_id(
    result_dict: dict[str, Any],
    *,
    api_key: str,
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    """Resolve o custo final do OpenRouter para contratos públicos com imagem."""

    request_id = str(result_dict.get("request_id") or "")
    base64_value = str(result_dict.get("base64") or "")
    warnings = str(result_dict.get("warnings") or "")
    current_cost = result_dict.get("cust_usd") or result_dict.get("cost_usd") or 0.0
    current_source = result_dict.get("cost_source")
    current_is_estimated = result_dict.get("cost_is_estimated", True)
    current_details = result_dict.get("cost_details")
    if not isinstance(current_details, dict):
        current_details = {}
    if not request_id:
        return image_result(
            base64_value=base64_value,
            warnings=warnings,
            cust_usd=current_cost,
            request_id=request_id,
            cost_source=current_source,
            cost_is_estimated=bool(current_is_estimated),
            cost_details=current_details,
        )

    response = request(
        "GET",
        "https://openrouter.ai/api/v1/generation",
        headers={"Authorization": f"Bearer {api_key}"},
        params={"id": request_id},
        timeout_seconds=timeout_seconds,
    )
    parsed = response_json(response)
    payload = parsed.get("data") or parsed
    total_cost = extract_openrouter_usage_cost(payload)
    if total_cost is None:
        return image_result(
            base64_value=base64_value,
            warnings=warnings,
            cust_usd=current_cost,
            request_id=request_id,
            cost_source=current_source,
            cost_is_estimated=bool(current_is_estimated),
            cost_details=current_details,
        )
    return image_result(
        base64_value=base64_value,
        warnings=warnings,
        cust_usd=total_cost,
        request_id=request_id,
        cost_source="openrouter_generation_lookup",
        cost_is_estimated=False,
        cost_details={"request_id": request_id},
    )
