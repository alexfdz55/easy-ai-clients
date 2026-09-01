# BytePlus Seedance Text To Video API

Implementation status: implemented

## Overview

This wrapper targets BytePlus ModelArk inference for Seedance 2.x prompt-only
video generation. It creates a content-generation task, polls until the task
succeeds, and returns the signed `content.video_url`. Snapshot date for model
and limit assumptions: 2026-09-01.

## Account And Credentials

Use `ARK_API_KEY` from the environment. Optional `ARK_BASE_URL` overrides the
default ModelArk host. The wrapper does not accept API keys as public
parameters.

Default base URL: `https://ark.ap-southeast.bytepluses.com/api/v3`

Create: `POST /contents/generations/tasks`

Retrieve: `GET /contents/generations/tasks/{id}`

## Official Sources

- Video generation API: https://docs.byteplus.com/en/docs/ModelArk/1520757
- ModelArk API reference: https://docs.byteplus.com/en/docs/ModelArk/Video_Generation_API

## Current Wrapper Default

`dreamina-seedance-2-5-260628`

This is the documented Seedance 2.5 ModelArk model ID. It supports 4-30 second
clips, multimodal references, and native audio in the same pass.

## Lowest-Cost Default Policy

Prefer the current Seedance 2.x ModelArk ID. Use `dreamina-seedance-2-0-mini-260615`
when you want the cheapest documented 2.0-family option and can stay at 720p or
below with a 4-15 second duration.

## Parameter Reference

Public dispatcher signature:

```python
def text_to_video(prompt, model=None, *, api, **kwargs):
    pass
```

Accepted `kwargs`: `model`, `resolution`, `ratio`, `duration` (alias
`duration_seconds`), `generate_audio`, `watermark`, `seed`, `camera_fixed`,
`return_last_frame`, `output_format`, `image_urls`, `video_urls`, `audio_urls`,
`timeout_seconds`, `poll_interval_seconds`, and `extra_payload`.

`generate_audio` defaults to `true`. Documented duration limits are 4-30 seconds
for Seedance 2.5 and 4-15 seconds for Seedance 2.0 family models. `-1` lets the
model choose duration. 4K is documented only for `dreamina-seedance-2-0-260128`.
1080p is not documented for Fast or Mini.

`image_urls` / `video_urls` / `audio_urls` append multimodal reference items.
Each item may be a URL string or a dict with `url` and optional `role`
(`reference_image`, `reference_video`, `reference_audio`).

## Model Coverage

| Model or endpoint | Official source | Status | Implemented default | Notes |
| --- | --- | --- | --- | --- |
| `dreamina-seedance-2-5-260628` | https://docs.byteplus.com/en/docs/ModelArk/1520757 | `implemented` | yes | 4-30s; 480p/720p/1080p. |
| `dreamina-seedance-2-0-260128` | https://docs.byteplus.com/en/docs/ModelArk/1520757 | `implemented` | no | 4-15s; 480p/720p/1080p/4k. |
| `dreamina-seedance-2-0-fast-260128` | https://docs.byteplus.com/en/docs/ModelArk/1520757 | `implemented` | no | 4-15s; 480p/720p. |
| `dreamina-seedance-2-0-mini-260615` | https://docs.byteplus.com/en/docs/ModelArk/1520757 | `implemented` | no | 4-15s; 480p/720p. |

Seedance 1.x model IDs are not documented or tested in this wrapper.

## Domain Notes

The wrapper uses ModelArk REST through the shared video HTTP helper, not the
BytePlus Python SDK and not Lake AI Service (LAS). Task IDs
look like `cgt-...`. Signed video URLs expire; download them if you need a
durable copy. Do not send the API key when fetching `video_url`.

`sync=False` returns the task id as `request_id` plus `task_url`. Use
`video.get_status`, `video.get_result`, and `video.download` with operation
`text_to_video` for async follow-up work.

## Python Example

```python
from easy_ai_clients import video

result = video.text_to_video(
    "A cinematic orbit shot around a glass greenhouse at dusk.",
    api="byteplus",
    duration=8,
    resolution="720p",
    ratio="16:9",
    output_path="outputs/byteplus_text_to_video.mp4",
)
print(result["request_id"], result["video_url"])
```

## Pricing Notes

ModelArk Seedance billing is token-based. The wrapper sets
`cost_source="unavailable"` and `cost_usd=0.0` because the task response does
not expose a stable USD amount.

## Validation Note

Validated locally with package import, dispatcher, and HTTP-mocked payload
tests. No paid ModelArk generation request was made for this release.
