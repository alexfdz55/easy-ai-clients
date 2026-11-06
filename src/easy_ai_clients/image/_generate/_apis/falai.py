"""fal.ai generate API wrapper."""

from __future__ import annotations

from ...._falai_pricing import FAL_ESTIMATE_OPTIONS
from ...._submission_hooks import is_on_submitted_exception
from ..._common.env_utils import get_provider_api_key
from ..._common.falai_pricing import fal_image_pricing_estimate
from ..._common.falai_utils import generate_image as _generate_image
from ..._common.provider_utils import consume_kwargs, payload_from_keys, provider_error_to_warning
from ..post_processing import build_generate_result
from ..pre_processing import prepare_generate_inputs

_DEFAULTS = {
    'output_format': 'png',
    'seed': None,
    'timeout_seconds': 180,
    'webhook_url': None,
    'on_submitted': None,
    'submission': None,
}
_PAYLOAD_KEYS = ('num_images', 'image_size', 'guidance_scale', 'num_inference_steps', 'enable_safety_checker', 'sync_mode', 'fal_payload')
_EXTRA_KEYS = (*_PAYLOAD_KEYS, *FAL_ESTIMATE_OPTIONS)


def generate(prompt: str, model: str = 'fal-ai/flux/schnell', **kwargs):
    """Generate an image with fal.ai and return the normalized public contract.

Standardized public wrapper. Required image inputs accept local file paths, raw
base64 image strings, data URLs, and public HTTP(S) image URLs. Optional provider
parameters are supplied through **kwargs. Full model, pricing, parameter, and
validation details are documented in generate/docs/falai.md."""

    values, warning = consume_kwargs(dict(kwargs), _DEFAULTS, passthrough_keys=_EXTRA_KEYS)
    if warning:
        return build_generate_result(warnings=warning)
    extra_body = payload_from_keys(values, _PAYLOAD_KEYS)
    if extra_body.pop("fal_payload", None):
        fal_payload = values.get("fal_payload") or {}
        if isinstance(fal_payload, dict):
            extra_body.update(fal_payload)
        else:
            return build_generate_result(warnings="fal_payload must be a dictionary.")
    try:
        prepared = prepare_generate_inputs(prompt)
        api_key = get_provider_api_key('fal.ai', 'FAL_KEY')
        return _generate_image(
            api_key=api_key,
            prepared=prepared,
            model=model,
            output_format=values["output_format"],
            timeout_seconds=int(values["timeout_seconds"]),
            build_result=build_generate_result,
            seed=values.get("seed"),
            extra_body=extra_body,
            cost_metadata=fal_image_pricing_estimate(model, values, extra_body, api_key),
            webhook_url=values.get("webhook_url"),
            on_submitted=values.get("on_submitted"),
            submission=values.get("submission"),
        )
    except Exception as exc:
        if is_on_submitted_exception(exc):
            raise
        return build_generate_result(warnings=provider_error_to_warning(exc))

__all__ = ["generate"]
