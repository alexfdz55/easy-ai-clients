# fal.ai Text To Video API

Implementation status: implemented

## Overview

This wrapper targets fal.ai queued model endpoints for prompt-only video generation. Snapshot date for model and pricing assumptions: 2026-05-13.

The implemented executable default is `fal-ai/wan/v2.2-5b/text-to-video/distill` because it is an officially documented low-cost text-to-video endpoint with a simple normalized prompt contract and a defensible per-video USD price.

## Account And Credentials

Use `FAL_KEY` from the environment. Create and manage keys from the fal.ai dashboard. The wrapper never accepts or logs API keys directly.

## Official Sources

- fal.ai model APIs: https://fal.ai/docs/documentation/model-apis
- fal.ai queue: https://fal.ai/docs/documentation/model-apis/inference/queue
- fal.ai pricing: https://fal.ai/docs/documentation/model-apis/pricing
- Default model page: https://fal.ai/models/fal-ai/wan/v2.2-5b/text-to-video/distill/api
- Pricing API: https://fal.ai/docs/documentation/model-apis/pricing

## Current Wrapper Default

`fal-ai/wan/v2.2-5b/text-to-video/distill`

The default was selected because the official model page documents a low-cost fal.ai text-to-video option whose payload maps cleanly to the public `video.text_to_video(...)` dispatcher.

## Lowest-Cost Default Policy

Prefer the lowest-cost official endpoint whose schema can be validated without a provider-specific public signature. Models with unclear pricing units, more complex schemas, LoRA-specific behavior, or a mismatched operation contract are documented as not implemented.

## Parameter Reference

Public dispatcher signature:

```python
def text_to_video(prompt, model=None, *, api, **kwargs):
    pass
```

Normalized parameters:

| Parameter | Required | Notes |
| --- | ---: | --- |
| `prompt` | yes | Sent as the provider prompt without rewriting. |
| `output_path` | no | Downloads the completed video when `sync=True`. |
| `sync` | no | `True` submits and polls; `False` returns queue identifiers. |

Accepted `kwargs` for the implemented default: `model`, `num_frames`, `frames_per_second`, `seed`, `resolution`, `aspect_ratio`, `num_inference_steps`, `enable_safety_checker`, `enable_output_safety_checker`, `enable_prompt_expansion`, `guidance_scale`, `shift`, `interpolator_model`, `num_interpolated_frames`, `adjust_fps_for_interpolation`, `video_quality`, `video_write_mode`, `timeout_seconds`, `poll_interval_seconds`, `extra_payload`, `webhook_url`, `on_submitted`, and `submission`.

Validated values include `resolution` `580p` or `720p`, `aspect_ratio` `16:9`, `9:16`, or `1:1`, `num_frames` 17 to 161, `frames_per_second` 4 to 60, `seed` 0 to 4294967295, `num_inference_steps` 2 to 50, `guidance_scale` 1 to 10, `shift` 1 to 10, `interpolator_model` `none`, `film`, or `rife`, `num_interpolated_frames` 0 to 4, `video_quality` `low`, `medium`, `high`, or `maximum`, and `video_write_mode` `fast`, `balanced`, or `small`.

Documented kwargs are reference metadata only. Undocumented kwargs are forwarded; provider rejections are returned through the normalized public error shape. `extra_payload` may override the generated REST payload.

## Model Coverage

2026-05-14 update: the adapter now submits all listed fal.ai text-to-video
endpoints through the queue API. The original table notes are retained for
schema/pricing context, but rows that say `official_available` are now executable
via `model=...`; cost is estimated only when the billing unit can be inferred or
the caller supplies an explicit billing quantity such as `duration_seconds`,
`compute_seconds`, `billing_megapixels`, `billing_tokens`, or the generic
`billing_unit_quantity` / `unit_quantity` fields.

| Model or endpoint | Official source | Status | Implemented default | Notes |
| --- | --- | --- | --- | --- |
| `fal-ai/wan/v2.2-5b/text-to-video/distill` | https://fal.ai/models/fal-ai/wan/v2.2-5b/text-to-video/distill/api | `implemented` | yes | Estimated from documented per-video price. |
| `fal-ai/ltx-2-19b/distilled/text-to-video` | fal.ai model catalog | `official_available` | no | Not implemented because schema and pricing differ from the selected default. |
| `fal-ai/ltx-2-19b/distilled/text-to-video/lora` | fal.ai model catalog | `official_available` | no | LoRA-specific schema is not normalized in this wrapper. |
| `fal-ai/ltx-2.3-22b/distilled/text-to-video` | fal.ai model catalog | `official_available` | no | Higher-cost/alternate schema candidate. |
| `fal-ai/animatediff-sparsectrl-lcm` | fal.ai model catalog | `official_available` | no | Documented candidate, not the lowest-cost stable default. |
| `fal-ai/fast-animatediff/text-to-video` | fal.ai model catalog | `official_available` | no | Documented candidate; not implemented in the first executable set. |
| `fal-ai/kandinsky5/text-to-video` | fal.ai model catalog | `official_available` | no | Documented candidate; pricing and schema must be rechecked before adding. |
| `fal-ai/minimax/hailuo-02/pro/text-to-video` | fal.ai model catalog | `official_available` | no | More expensive provider-backed endpoint. |
| `fal-ai/wan/v2.2-a14b/text-to-video` | fal.ai model catalog | `official_available` | no | Alternate WAN family endpoint. |
| `fal-ai/kling-video/v2.6/pro/text-to-video` | fal.ai model catalog | `official_available` | no | Pro tier endpoint; not lowest-cost default. |
| `fal-ai/veo3.1` | fal.ai model catalog | `official_available` | no | Provider-backed Veo endpoint; Google wrapper covers direct Gemini API separately. |
| `fal-ai/bytedance/seedance/v1/pro/fast/text-to-video` | fal.ai model catalog | `official_available` | no | Candidate retained for future explicit schema mapping. |
| `fal-ai/bytedance/seedance/v1.5/pro/text-to-video` | fal.ai model catalog | `official_available` | no | Candidate retained for future explicit schema mapping. |
| `moonvalley/marey/t2v` | fal.ai model catalog | `official_available` | no | Candidate retained; pricing/schema not selected for default. |
| `fal-ai/bytedance/seedance/v1/pro/text-to-video` | fal.ai model catalog | `official_available` | no | Candidate retained for future explicit schema mapping. |

## Domain Notes

fal.ai uses queue submission, status polling, and response retrieval. `sync=False` returns `request_id`, `status_url`, and `response_url`. Use `video.get_status`, `video.get_result`, and `video.download` with operation `text_to_video` for async follow-up work.

When `webhook_url` is provided, queue submission includes `?fal_webhook=<urlencoded value>`. `on_submitted` receives the submission receipt right after a successful submit and raised exceptions are re-raised. `submission` skips submit and reuses a previously returned receipt for polling and result retrieval.

When fal.ai returns queue URLs, the adapter preserves them and uses them for
`sync=True` polling. Pass `status_url` back to `video.get_status(...)` and
`response_url` back to `video.get_result(...)` when present. Calls that only
provide `request_id`, `model`, and `api` continue to reconstruct queue URLs.

Local files are converted to data URLs only in contexts that accept media. Text-to-video sends no media.

## Python Example

```python
from easy_ai_clients import video

result = video.text_to_video(
    "A quiet sunrise over a futuristic coastal city.",
    api="falai",
    output_path="outputs/falai_text_to_video.mp4",
)
print(result["cost_usd"])
```

## Pricing Notes

The default wrapper estimates `cost_usd` as `$0.08` per generated video using fal.ai model pricing. If `billing_unit_quantity` or `unit_quantity` is supplied, the wrapper calls fal.ai's official pricing estimate API and reports `cost_source="fal_pricing_estimate_api"`. The result includes `cost_is_estimated=True` because safe validation does not call the paid endpoint or reconcile with usage records.

## Validation Note

Validated locally with package import and dispatcher tests. No paid fal.ai generation request was made.
