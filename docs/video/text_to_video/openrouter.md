# OpenRouter Seedance Text To Video API

Implementation status: implemented

## Overview

This wrapper targets OpenRouter's asynchronous Video API for ByteDance Seedance
prompt-only generation. It submits `POST /api/v1/videos`, polls the job until
it finishes, and returns `unsigned_urls[0]` (or the authenticated content URL).
Snapshot date for model and limit assumptions: 2026-09-14.

## Account And Credentials

Use `OPENROUTER_API_KEY` from the environment. Optional `OPENROUTER_BASE_URL`
overrides the default host. The wrapper does not accept API keys as public
parameters.

Default base URL: `https://openrouter.ai/api/v1`

Create: `POST /videos`

Retrieve: `GET /videos/{id}`

Download: `GET /videos/{id}/content` (Bearer required) or `unsigned_urls`

## Official Sources

- Video generation: https://openrouter.ai/docs/guides/overview/multimodal/video-generation
- Seedance 2.0 Mini: https://openrouter.ai/bytedance/seedance-2.0-mini
- Seedance 2.0 Fast: https://openrouter.ai/bytedance/seedance-2.0-fast
- Seedance 2.0: https://openrouter.ai/bytedance/seedance-2.0
- Seedance 2.5: https://openrouter.ai/bytedance/seedance-2.5
- Seedance 1.5 Pro: https://openrouter.ai/bytedance/seedance-1-5-pro

## Current Wrapper Default

`bytedance/seedance-2.0-mini`

This is the lowest-cost documented Seedance option on OpenRouter. It supports
4-15 second clips at 480p or 720p, first/last frame control, and native audio.

## Lowest-Cost Default Policy

Prefer Mini. Use Fast when you want the 2.0 family at a discount without 1080p.
Use standard 2.0 when you need 1080p or 4K. Use 2.5 for clips longer than 15
seconds (OpenRouter 2.5 is 480p/720p only, up to 30s).

## Parameter Reference

Public dispatcher signature:

```python
def text_to_video(prompt, model=None, *, api, **kwargs):
    pass
```

Accepted `kwargs`: `model`, `resolution`, `aspect_ratio` (alias `ratio`; `auto`
is omitted), `duration` (alias `duration_seconds`), `generate_audio`, `seed`,
`callback_url`, `size`, `image_urls`, `video_urls`, `audio_urls`,
`timeout_seconds`, `poll_interval_seconds`, and `extra_payload`.

`generate_audio` is sent only when the caller supplies it. Documented duration
limits are 4-15 seconds for Seedance 2.0 family models, 4-30 seconds for 2.5,
and 4-12 seconds for 1.5 Pro. 4K is documented only for
`bytedance/seedance-2.0`. 1080p is not documented for Mini, Fast, or 2.5.

`image_urls` become OpenRouter `input_references` with `type: image_url`.
`video_urls` / `audio_urls` are forwarded with matching `video_url` /
`audio_url` types; the public OpenRouter schema documents images only, so
video/audio refs may be rejected upstream.

## Model Coverage

| Model or endpoint | Official source | Status | Implemented default | Notes |
| --- | --- | --- | --- | --- |
| `bytedance/seedance-2.0-mini` | https://openrouter.ai/bytedance/seedance-2.0-mini | `implemented` | yes | 4-15s; 480p/720p. |
| `bytedance/seedance-2.0-fast` | https://openrouter.ai/bytedance/seedance-2.0-fast | `implemented` | no | 4-15s; 480p/720p. |
| `bytedance/seedance-2.0` | https://openrouter.ai/bytedance/seedance-2.0 | `implemented` | no | 4-15s; 480p/720p/1080p/4K. |
| `bytedance/seedance-2.5` | https://openrouter.ai/bytedance/seedance-2.5 | `implemented` | no | 4-30s; 480p/720p. |
| `bytedance/seedance-1-5-pro` | https://openrouter.ai/bytedance/seedance-1-5-pro | `implemented` | no | 4-12s; 480p/720p/1080p. Audio off is cheaper. |

## Domain Notes

The wrapper uses OpenRouter REST, not chat/completions. Job IDs look like
`job-...`. Prefer `unsigned_urls` for unauthenticated downloads. Content URLs
on `openrouter.ai` require the Bearer token.

`sync=False` returns the job id as `request_id` plus `poll_url`. Use
`video.get_status`, `video.get_result`, and `video.download` with operation
`text_to_video` for async follow-up work.

## Python Example

```python
from easy_ai_clients import video

result = video.text_to_video(
    "A cinematic orbit shot around a glass greenhouse at dusk.",
    api="openrouter",
    duration=8,
    resolution="720p",
    aspect_ratio="16:9",
    output_path="outputs/openrouter_text_to_video.mp4",
)
print(result["request_id"], result["video_url"], result["cost_usd"])
```

## Pricing Notes

Completed jobs expose `usage.cost` in USD. The wrapper sets
`cost_source="openrouter_video_usage"` and `cost_is_estimated=False` when that
field is present. Submitted (async) jobs leave cost unavailable until poll
completes.

## Validation Note

Validated locally with package import, dispatcher, and HTTP-mocked payload
tests. No paid OpenRouter generation request was made for this release.
