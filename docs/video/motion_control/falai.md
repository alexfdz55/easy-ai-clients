# fal.ai Motion Control API

Implementation status: implemented

## Overview

This wrapper targets fal.ai motion/reference controlled video generation. Snapshot date for model and pricing assumptions: 2026-05-13.

The implemented default is `fal-ai/kling-video/v2.6/standard/motion-control`, which uses a character image and a motion reference video.

## Account And Credentials

Use `FAL_KEY` from the environment. The wrapper validates the key before submission.

## Official Sources

- fal.ai model APIs: https://fal.ai/docs/documentation/model-apis
- fal.ai queue: https://fal.ai/docs/documentation/model-apis/inference/queue
- fal.ai pricing: https://fal.ai/docs/documentation/model-apis/pricing
- Default model page: https://fal.ai/models/fal-ai/kling-video/v2.6/standard/motion-control/api

## Current Wrapper Default

`fal-ai/kling-video/v2.6/standard/motion-control`

The default was selected because the official model page matches the context definition and has documented per-second pricing.

## Lowest-Cost Default Policy

Prefer explicit motion-control endpoints over generic video editing. Generic video-to-video, reframe, edit, or prompt-as-video flows are documented as adjacent unless motion/reference semantics are explicit.

## Parameter Reference

Public dispatcher signature:

```python
def motion_control(prompt=None, image=None, video=None, reference=None, model=None, *, api, **kwargs):
    pass
```

Required normalized inputs for the implemented model: `image_path` or `image_url` for the character image, `video_path` or `video_url` for the motion reference, `character_orientation`, and `duration_seconds` or `billing_duration_seconds` for cost estimation.

Accepted `kwargs`: `model`, `character_orientation`, `keep_original_sound`, `duration_seconds`, `billing_duration_seconds`, `timeout_seconds`, `poll_interval_seconds`, `extra_payload`, `webhook_url`, `on_submitted`, and `submission`.

Validated values: `character_orientation` must be `image` or `video`. `duration_seconds` must be greater than zero.

## Model Coverage

2026-05-14 update: the adapter now forwards the listed fal.ai motion/reference
models through the queue API. The Kling motion-control default keeps stricter
input requirements (`image_url`, `video_url`, and `character_orientation`);
adjacent reference/edit models are also exposed through `video.video_to_video`.
Cost is estimated only when the documented billing unit can be calculated.

| Model or endpoint | Official source | Status | Implemented default | Notes |
| --- | --- | --- | --- | --- |
| `fal-ai/kling-video/v2.6/standard/motion-control` | https://fal.ai/models/fal-ai/kling-video/v2.6/standard/motion-control/api | `implemented` | yes | Character image plus motion reference video. |
| `fal-ai/wan-motion` | fal.ai model catalog | `official_available` | no | Candidate retained; schema not normalized. |
| `fal-ai/controlnext` | fal.ai model catalog | `official_available` | no | Candidate retained. |
| `fal-ai/ltx-2.3-22b/distilled/reference-video-to-video` | fal.ai model catalog | `official_available` | no | Reference-video candidate retained. |
| `fal-ai/ltx-2.3-22b/distilled/reference-video-to-video/lora` | fal.ai model catalog | `official_available` | no | LoRA-specific candidate. |
| `fal-ai/ltx-2.3-22b/reference-video-to-video` | fal.ai model catalog | `official_available` | no | Candidate retained. |
| `fal-ai/wan/v2.2-14b/animate/move` | fal.ai model catalog | `official_available` | no | Animate/move candidate retained. |
| `fal-ai/wan/v2.2-14b/animate/replace` | fal.ai model catalog | `official_available` | no | Animate/replace candidate retained. |
| `fal-ai/kling-video/v2.6/pro/motion-control` | fal.ai model catalog | `official_available` | no | Pro endpoint not selected as lowest-cost default. |
| `fal-ai/kling-video/o1/standard/video-to-video/reference` | fal.ai model catalog | `official_available` | no | Reference video candidate. |
| `fal-ai/kling-video/o1/video-to-video/reference` | fal.ai model catalog | `official_available` | no | Reference video candidate. |
| `fal-ai/kling-video/v3/pro/motion-control` | fal.ai model catalog | `official_available` | no | Higher-tier candidate retained. |
| `fal-ai/wan-move` | fal.ai model catalog | `official_available` | no | Candidate retained. |
| `fal-ai/video-as-prompt` | fal.ai model catalog | `adjacent_only` | no | Related reference-video flow; not implemented as this fixed contract. |
| `moonvalley/marey/motion-transfer` | fal.ai model catalog | `official_available` | no | Candidate retained. |

## Domain Notes

The wrapper uses `video_path` or `video_url` as the motion reference for this fal.ai model. `reference_path` and `reference_url` are rejected for this provider to avoid ambiguous mapping.

When `webhook_url` is provided, queue submission includes `?fal_webhook=<urlencoded value>`. `on_submitted` runs right after successful submit with the receipt dictionary, and `submission` skips submit and reuses a previous receipt for polling/result retrieval.

When fal.ai returns queue URLs, the adapter preserves them and uses them for
`sync=True` polling. Pass `status_url` back to `video.get_status(...)` and
`response_url` back to `video.get_result(...)` when present. Calls that only
provide `request_id`, `model`, and `api` continue to reconstruct queue URLs.

## Python Example

```python
from easy_ai_clients import video

result = video.motion_control(
    image="inputs/character.png",
    video="inputs/dance_reference.mp4",
    api="falai",
    character_orientation="image",
    duration_seconds=5,
    output_path="outputs/falai_motion_control.mp4",
)
print(result["cost_usd"])
```

## Pricing Notes

The wrapper estimates `cost_usd` as `$0.07 * duration_seconds` for the default model. `duration_seconds` is required because the queue submission response does not guarantee final billable duration. If `billing_unit_quantity` or `unit_quantity` is supplied, the wrapper calls fal.ai's official pricing estimate API and reports `cost_source="fal_pricing_estimate_api"`.

## Validation Note

Validated locally with package import and dispatcher tests. No paid fal.ai generation request was made.
