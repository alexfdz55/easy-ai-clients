# fal.ai Image Lip Sync API

Implementation status: implemented

## Overview

This wrapper targets fal.ai image/avatar plus audio video generation. Snapshot date for model and pricing assumptions: 2026-05-13.

The implemented default is `fal-ai/longcat-single-avatar/image-audio-to-video`, which accepts one visual identity image and one audio source and returns a talking video.

## Account And Credentials

Use `FAL_KEY` from the environment. Missing keys raise an error naming the variable and provider.

## Official Sources

- fal.ai model APIs: https://fal.ai/docs/documentation/model-apis
- fal.ai queue: https://fal.ai/docs/documentation/model-apis/inference/queue
- fal.ai pricing: https://fal.ai/docs/documentation/model-apis/pricing
- Default model page: https://fal.ai/models/fal-ai/longcat-single-avatar/image-audio-to-video/api

## Current Wrapper Default

`fal-ai/longcat-single-avatar/image-audio-to-video`

This model was selected because it matches the context definition directly: image plus audio creates a lip-synced/talking-avatar video.

## Lowest-Cost Default Policy

Prefer direct image-plus-audio lip-sync endpoints with documented pricing units and no required avatar account setup. Preset-avatar or text-to-speech-only flows are documented separately unless they fit the fixed public signature.

## Parameter Reference

Public dispatcher signature:

```python
def image_lipsync(image=None, audio=None, text=None, model=None, *, api, **kwargs):
    pass
```

Required normalized inputs: `image_path` or `image_url`, and `audio_path` or `audio_url`. The wrapper rejects `text` because the selected fal.ai LongCat endpoint does not expose text-to-speech through this normalized wrapper.

Accepted `kwargs`: `model`, `prompt`, `negative_prompt`, `num_inference_steps`, `text_guidance_scale`, `audio_guidance_scale`, `resolution`, `num_segments`, `seed`, `enable_safety_checker`, `enable_prompt_expansion`, `timeout_seconds`, `poll_interval_seconds`, `extra_payload`, `webhook_url`, `on_submitted`, and `submission`.

Validated values include `resolution` `480p` or `720p`, `num_segments` 1 to 10, `num_inference_steps` 10 to 100, and guidance scales 1 to 10.

## Model Coverage

| Model or endpoint | Official source | Status | Implemented default | Notes |
| --- | --- | --- | --- | --- |
| `fal-ai/longcat-single-avatar/image-audio-to-video` | https://fal.ai/models/fal-ai/longcat-single-avatar/image-audio-to-video/api | `implemented` | yes | Direct image plus audio talking-video flow. |
| `veed/fabric-1.0` | fal.ai model catalog | `official_available` | no | Avatar/talking-video candidate; not selected for first wrapper. |
| `veed/fabric-1.0/fast` | fal.ai model catalog | `official_available` | no | Faster Fabric candidate; not implemented. |
| `fal-ai/flashtalk` | fal.ai model catalog | `official_available` | no | Candidate retained; schema differs. |
| `fal-ai/longcat-multi-avatar/image-audio-to-video` | fal.ai model catalog | `official_available` | no | Multi-avatar schema does not fit the simple single-visual contract cleanly. |
| `fal-ai/ai-avatar` | fal.ai model catalog | `official_available` | no | Avatar/preset flow; not normalized here. |
| `fal-ai/infinitalk` | fal.ai model catalog | `official_available` | no | Candidate retained; video variant implemented under video lip sync. |
| `fal-ai/echomimic-v3` | fal.ai model catalog | `official_available` | no | Candidate retained; not implemented due schema/cost review. |
| `fal-ai/wan/v2.2-14b/speech-to-video` | fal.ai model catalog | `adjacent_only` | no | Speech-to-video is adjacent unless visual identity input is confirmed for this context. |
| `fal-ai/creatify/aurora` | fal.ai model catalog | `official_available` | no | Candidate retained; likely avatar product flow. |

## Domain Notes

`sync=True` uses fal.ai queue submit, poll, response retrieval, and optional download. `sync=False` returns queue URLs and `request_id`. Use `video.get_status`, `video.get_result`, and `video.download` with operation `image_lipsync` for async follow-up work.

When `webhook_url` is provided, queue submission includes `?fal_webhook=<urlencoded value>`. `on_submitted` runs right after successful submit with the receipt dictionary, and `submission` skips submit and reuses a previous receipt for polling/result retrieval.

When fal.ai returns queue URLs, the adapter preserves them and uses them for
`sync=True` polling. Pass `status_url` back to `video.get_status(...)` and
`response_url` back to `video.get_result(...)` when present. Calls that only
provide `request_id`, `model`, and `api` continue to reconstruct queue URLs.

## Python Example

```python
from easy_ai_clients import video

result = video.image_lipsync(
    image="inputs/avatar.png",
    audio="inputs/voice.wav",
    api="falai",
    output_path="outputs/falai_image_lipsync.mp4",
)
print(result["cost_usd"])
```

## Pricing Notes

The wrapper estimates cost from LongCat documented units: `480p` uses 1 unit per second, `720p` uses 4 units per second, and one unit is estimated at `$0.15`. Segment duration is estimated from `num_segments`. Results include `cost_credits` for the billing units and `cost_is_estimated=True`.

## Validation Note

Validated locally with package import and dispatcher tests. No paid fal.ai generation request was made.
