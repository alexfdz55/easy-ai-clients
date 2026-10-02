# OpenRouter Seedance Image To Video API

Implementation status: implemented

## Overview

This wrapper targets OpenRouter's asynchronous Video API for ByteDance Seedance
first-frame and first-plus-last-frame generation. Snapshot date for model and
limit assumptions: 2026-09-14.

## Account And Credentials

Use `OPENROUTER_API_KEY` from the environment. Optional `OPENROUTER_BASE_URL`
overrides the default host.

Default base URL: `https://openrouter.ai/api/v1`

## Official Sources

- Video generation: https://openrouter.ai/docs/guides/overview/multimodal/video-generation
- Seedance 2.0 Mini: https://openrouter.ai/bytedance/seedance-2.0-mini
- Seedance 2.0 Fast: https://openrouter.ai/bytedance/seedance-2.0-fast
- Seedance 2.0: https://openrouter.ai/bytedance/seedance-2.0
- Seedance 2.5: https://openrouter.ai/bytedance/seedance-2.5
- Seedance 1.5 Pro: https://openrouter.ai/bytedance/seedance-1-5-pro

### HeyGen Video 1

`heygen/heygen-video-1` (2026-09-30) goes through the same route:
https://openrouter.ai/heygen/heygen-video-1

- First frame only. Durations 5 to 15 seconds, `480p` or `768p`, aspect ratios 21:9, 16:9,
  4:3, 1:1, 3:4 and 9:16.
- Every clip comes back with sound (dialogue, ambience, effects) and there is no audio
  switch. The model card reports `generate_audio: false` and no passthrough parameters, and
  OpenRouter answers 400 to a parameter the model does not support: the wrapper sends only
  `prompt`, `frame_images`, `duration`, `resolution`, `aspect_ratio` and `seed`, and drops
  `generate_audio` and any other keyword argument.
- Cost comes from `usage.cost` on the finished job. List price 0.02 USD per second at 480p
  and 0.03 at 768p; 50% off as a launch rate through October 2026.

### `clamp_duration`

By default the duration is truncated to a whole number and validated against the model's
documented range: an out-of-range value raises. A caller that passes the length of a scene
(5.6 seconds) can send `clamp_duration=True`: the duration is rounded **up** and brought
inside the range (5.6 → 6; 3.2 → 5 and 22 → 15 on HeyGen Video 1). The flag is never sent
to OpenRouter.

## Current Wrapper Default

`bytedance/seedance-2.0-mini`

## Lowest-Cost Default Policy

Prefer Mini. Use Fast for discounted 2.0-family clips without 1080p. Use
standard 2.0 for 1080p/4K. Use 2.5 only when duration must exceed 15 seconds.

## Parameter Reference

Public dispatcher signature:

```python
def image_to_video(prompt, image=None, model=None, *, api, **kwargs):
    pass
```

Accepted `kwargs`: `model`, `image_path`, `image_url`, `end_image_url` (aliases
`last_image_url`, `last_frame`), `resolution`, `aspect_ratio` (alias `ratio`;
`auto` is omitted), `duration` (alias `duration_seconds`), `generate_audio`,
`seed`, `image_urls`, `video_urls`, `audio_urls`, `timeout_seconds`,
`poll_interval_seconds`, and `extra_payload`.

The source image is sent as `frame_images` with `frame_type: "first_frame"`.
When `end_image_url` is provided it is sent as `frame_type: "last_frame"`.
Local image files are encoded as data URLs by the shared video media helper.
OpenRouter accepts https URLs or base64 data URLs.

## Model Coverage

| Model or endpoint | Official source | Status | Implemented default | Notes |
| --- | --- | --- | --- | --- |
| `bytedance/seedance-2.0-mini` | https://openrouter.ai/bytedance/seedance-2.0-mini | `implemented` | yes | First frame and first+last frame. |
| `bytedance/seedance-2.0-fast` | https://openrouter.ai/bytedance/seedance-2.0-fast | `implemented` | no | First frame and first+last frame. |
| `bytedance/seedance-2.0` | https://openrouter.ai/bytedance/seedance-2.0 | `implemented` | no | Includes documented 4K output. |
| `bytedance/seedance-2.5` | https://openrouter.ai/bytedance/seedance-2.5 | `implemented` | no | 480p/720p; up to 30s. |
| `bytedance/seedance-1-5-pro` | https://openrouter.ai/bytedance/seedance-1-5-pro | `implemented` | no | Audio off is cheaper. |

## Domain Notes

`sync=False` returns the job id as `request_id`. Use `video.get_status`,
`video.get_result`, and `video.download` with operation `image_to_video` for
async follow-up work.

## Python Example

```python
from easy_ai_clients import video

result = video.image_to_video(
    "Animate the scene with a slow dolly-in and drifting fog.",
    "https://example.com/first.png",
    api="openrouter",
    end_image_url="https://example.com/last.png",
    duration=6,
    output_path="outputs/openrouter_image_to_video.mp4",
)
print(result["video_url"], result["cost_usd"])
```

## Pricing Notes

Completed jobs expose `usage.cost`. The wrapper sets
`cost_source="openrouter_video_usage"` and `cost_is_estimated=False` when that
field is present.

## Validation Note

Validated locally with HTTP-mocked payload tests. No paid OpenRouter generation
request was made for this release.
