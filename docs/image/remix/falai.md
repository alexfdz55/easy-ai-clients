# fal.ai Remix API

## Overview

This module implements reference-conditioned image generation for fal.ai using the repository-wide normalized public contract. The public function is `remix(prompt, reference_images, **kwargs)` and returns `cust_usd`, `base64`, `warnings`, `request_id`.

Public image inputs accept local file paths, raw base64 image strings, `data:` URLs, and public HTTP(S) image URLs. Public HTTP(S) URLs are downloaded through the shared image normalization layer with scheme, timeout, content-type, and Pillow image validation.

## Account And Credentials

- Signup/account: https://fal.ai/dashboard
- API key documentation: https://fal.ai/dashboard/keys
- Required environment variable: `FAL_KEY`

## Official Sources

Endpoint documentation:
- https://docs.fal.ai/model-apis
- https://docs.fal.ai/model-endpoints/queue

Model/catalog documentation:
- https://fal.ai/models
- https://api.fal.ai/v1/models

Pricing documentation:
- https://fal.ai/pricing
- https://fal.ai/models
- https://fal.ai/docs/platform-apis/v1/models/pricing/estimate
- https://fal.ai/docs/platform-apis/v1/models/usage
- https://fal.ai/docs/platform-apis/v1/models/billing-events

## Current Wrapper Default

- Default model: `fal-ai/nano-banana-2/edit`
- Model selection: `model` keyword argument in **kwargs
- Snapshot date: 2026-04-25

The default is the lowest-cost sensible candidate selected from official pricing, official live catalogs, and the implemented source defaults. If official pricing is incomplete, the wrapper uses the strongest official pricing proxy available or returns the safest available estimate.

## Lowest-Cost Default Policy

The wrapper sends the smallest valid request shape by default: one output image for image domains, no optional enhancement or premium routing, no explicit mask unless provided, no premium reasoning unless unavoidable, and no provider-specific paid extras unless the caller supplies them in `**kwargs`.

For `remix`, the public signature intentionally has no dedicated `model` parameter. When no `model` keyword is supplied, `fal-ai/nano-banana-2/edit` is used internally as the cheapest relevant reference-capable default currently implemented for this provider.

## Parameter Reference

Supported public keyword parameters are provider-native whenever practical. Unsupported keyword arguments return a normalized warning or analyze output instead of being silently ignored.

timeout_seconds, output_format, seed, vision_endpoint, num_images, image_size, guidance_scale, num_inference_steps, enable_safety_checker, sync_mode, billing_unit_quantity, unit_quantity, webhook_url, on_submitted, submission, and fal_payload for model-specific schema fields.

Operational keyword parameters:

- `timeout_seconds`: request or polling timeout, default chosen per provider/domain.
- `mask`: accepted by `edit` wrappers where relevant; the public mask contract remains black = editable and white = protected.
- `base_image`: accepted by `remix` as a keyword where a provider supports or needs an anchor image concept.
- `billing_unit_quantity` / `unit_quantity`: optional cost-estimate quantity.
  These values are consumed by the wrapper for the fal.ai pricing estimate API
  and are not forwarded to the model payload. When neither value is supplied,
  remix estimates one output image by default, or `num_images` when it is
  provided.
- `webhook_url`: when provided, submission uses `?fal_webhook=<urlencoded value>` on the queue endpoint.
- `on_submitted`: optional callback called right after a successful queue submission with the receipt dictionary (`request_id`, `status_url`, `response_url`, ...). Exceptions raised by this callback are re-raised.
- `submission`: optional receipt dictionary from an earlier queue submission. When provided, the wrapper skips `POST` submit and goes straight to polling/result retrieval.

## Model Coverage

The live model marketplace is authoritative. The validation harness records category-filtered text-to-image, image-to-image, and vision rows plus schema compatibility for queue payloads.

fal.ai is a dynamic marketplace. The wrapper uses queue endpoints and supports model ids whose schema matches prompt/image_urls/image_url/output_format/seed conventions; incompatible schemas are treated as provider/model incompatibilities.

Coverage classes used by the validation matrix:

| Status | Meaning |
| --- | --- |
| `official_available` | The model appears in an official catalog or official documentation for this domain. |
| `implemented` | The wrapper can form a request for the model using this repository's normalized contract. |
| `tested` | A live request was attempted and returned a provider result or normalized provider rejection. |
| `blocked` | The live attempt was blocked by key, quota, billing, rate limit, region, gating, or provider policy. |
| `incompatible` | The official model/schema cannot be normalized safely into this domain's public contract. |

## Domain Notes

The wrapper preserves the repository return shape exactly. Provider-side safety blocks, auth failures, billing failures, unsupported combinations, and transport failures are converted into the normalized `warnings` field for image operations or the normalized `output` field for analyze operations.

For dynamic providers, the Markdown page is intentionally family-oriented. Provider model availability is dynamic; use the official provider docs and your own credentials for live production checks.

## Python Example

~~~python
from easy_ai_clients import image

result = image.remix(
    "Keep the subject but use watercolor style.",
    ["input.png"],
    api="falai",
)
print(result)
~~~

## Pricing Notes

For fal.ai image remixing, the queue result does not document a final
per-request cost field. The wrapper therefore calls the official
`POST /models/pricing/estimate` platform endpoint before remixing and stores
that value as `cost_source="fal_pricing_estimate_api"` with
`cost_is_estimated=True`.

This is an official estimate, not a post-run billing reconciliation. The
returned `cost_details` include the pricing estimate payload and the unit
quantity used. If the pricing estimate API is unavailable, the remix can still
complete and the result keeps `cost_source="unavailable"` with the lookup error
in `cost_details`.

OpenRouter costs can be refined with `image.update_cost("remix", result,
api="openrouter")` when a `request_id` is available.

## Validation Note

The bundled unit tests validate imports and dispatcher routing without calling paid provider APIs. Provider model catalogs, account access, prices, and rate limits can change independently of this package; run your own provider smoke tests with your credentials before relying on a specific model in production.
