# OpenRouter Avatar Video API

Implementation status: implemented

## Overview

This wrapper targets OpenRouter's asynchronous Video API for avatar models: one photo
lip-synced to a supplied audio track. Snapshot date for model and limit assumptions:
2026-10-09.

## Account And Credentials

Use `OPENROUTER_API_KEY` from the environment. Optional `OPENROUTER_BASE_URL` overrides the
default host.

Default base URL: `https://openrouter.ai/api/v1`

## Official Sources

- Video generation: https://openrouter.ai/docs/guides/overview/multimodal/video-generation
- Provider-specific options: https://openrouter.ai/docs/cookbook/video-generation/provider-specific-video-options
- HeyGen Avatar IV: https://openrouter.ai/heygen/avatar-iv

## Current Wrapper Default

`heygen/avatar-iv`

## Model Coverage

| Model | Status | Pricing basis |
| --- | --- | --- |
| `heygen/avatar-iv` | `implemented` | per second of output, reported in `usage.cost`. List price 0.05 USD per second at `720p` and `1080p`. |

Any other model raises `ValueError`: avatar models are the ones the wrapper documents with
a provider slug, because their options travel under that slug.

## Parameters

- `image` / `image_url`: required. The photo to animate.
- `audio` / `audio_url`: the track the photo is lip-synced to. The clip lasts as long as
  the audio; `duration`, `duration_seconds` and `billing_duration_seconds` are accepted and
  not sent.
- `text`: with an audio track, the motion instruction (sent as HeyGen's `motion_prompt`).
  Without an audio track, the script HeyGen voices (sent as `prompt`); pass `voice_id` to
  choose the voice and `motion_prompt` for the motion instruction.
- `resolution`: `720p` or `1080p`. `aspect_ratio`: `16:9`, `9:16` or `1:1`. Both are sent
  only when given.
- HeyGen options, sent under `provider.options.heygen`: `voice_id`, `voice_settings`,
  `motion_prompt`, `expressiveness`, `fit`, `remove_background`, `background`, `caption`,
  `title`. Any other keyword argument is dropped.

## Public URLs Only

HeyGen downloads the photo and the audio itself. `image_path`, `audio_path` and data URLs
raise `ValueError`: upload the file first and pass its public URL.

The content type the URL is served with has to match the file. A PNG stored under a
`.webp` name and served as `image/webp` is rejected with
`Content type not match image/webp != image/png` (no charge).

## Payload

Accepted as is by a live call on 2026-10-09 (5.84 s of audio, 0.291 USD):

```json
{
  "model": "heygen/avatar-iv",
  "resolution": "720p",
  "aspect_ratio": "9:16",
  "input_references": [
    {"type": "image_url", "image_url": {"url": "https://example.com/shot.png"}},
    {"type": "audio_url", "audio_url": {"url": "https://example.com/fragment.mp3"}}
  ],
  "provider": {"options": {"heygen": {"motion_prompt": "She sings to the camera."}}}
}
```

`prompt` is not sent together with an audio track: for this model it is the script to
voice, not a description of the clip.

## Async References

The submit response carries `id` and `polling_url`. `sync=True` polls until the job
completes and reads the video from `unsigned_urls`, which needs the same
`Authorization` header to download. Pass `request_id` (and `poll_url` when present) to
`video.get_status(...)` and `video.get_result(...)` to resume.

## Pricing

Cost comes from `usage.cost` on the finished job and is not estimated. A submitted job
reports `cost_source="unavailable"` until it finishes.

No live OpenRouter call is made by the default test suite.
