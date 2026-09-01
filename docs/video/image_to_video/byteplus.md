# BytePlus Seedance Image To Video API

Implementation status: implemented

## Overview

This wrapper targets BytePlus ModelArk inference for Seedance 2.x first-frame
and first-plus-last-frame video generation. Snapshot date for model and limit
assumptions: 2026-09-01.

## Account And Credentials

Use `ARK_API_KEY` from the environment. Optional `ARK_BASE_URL` overrides the
default ModelArk host.

Default base URL: `https://ark.ap-southeast.bytepluses.com/api/v3`

## Official Sources

- Video generation API: https://docs.byteplus.com/en/docs/ModelArk/1520757
- ModelArk API reference: https://docs.byteplus.com/en/docs/ModelArk/Video_Generation_API

## Current Wrapper Default

`dreamina-seedance-2-5-260628`

## Lowest-Cost Default Policy

Prefer Seedance 2.5 unless you need 4K, which is documented only on
`dreamina-seedance-2-0-260128`. Use Mini when 720p and 4-15 seconds are enough.

## Parameter Reference

Public dispatcher signature:

```python
def image_to_video(prompt, image=None, model=None, *, api, **kwargs):
    pass
```

Accepted `kwargs`: `model`, `image_path`, `image_url`, `end_image_url` (aliases
`last_image_url`, `last_frame`), `resolution`, `ratio`, `duration` (alias
`duration_seconds`), `generate_audio`, `watermark`, `seed`, `camera_fixed`,
`image_urls`, `video_urls`, `audio_urls`, `timeout_seconds`,
`poll_interval_seconds`, and `extra_payload`.

The source image is sent as `role: "first_frame"`. When `end_image_url` is
provided it is sent as `role: "last_frame"`. For Seedance 2.5, omitted `ratio`
defaults to `adaptive` because first-frame and first-plus-last-frame tasks
reject a concrete aspect ratio.

`generate_audio` defaults to `true`. Local image files are encoded as data URLs
by the shared video media helper.

## Model Coverage

| Model or endpoint | Official source | Status | Implemented default | Notes |
| --- | --- | --- | --- | --- |
| `dreamina-seedance-2-5-260628` | https://docs.byteplus.com/en/docs/ModelArk/1520757 | `implemented` | yes | First frame and first+last frame. |
| `dreamina-seedance-2-0-260128` | https://docs.byteplus.com/en/docs/ModelArk/1520757 | `implemented` | no | Includes documented 4K output. |
| `dreamina-seedance-2-0-fast-260128` | https://docs.byteplus.com/en/docs/ModelArk/1520757 | `implemented` | no | 480p/720p. |
| `dreamina-seedance-2-0-mini-260615` | https://docs.byteplus.com/en/docs/ModelArk/1520757 | `implemented` | no | 480p/720p. |

## Domain Notes

`sync=False` returns the task id as `request_id`. Use `video.get_status`,
`video.get_result`, and `video.download` with operation `image_to_video` for
async follow-up work.

## Python Example

```python
from easy_ai_clients import video

result = video.image_to_video(
    "Animate the scene with a slow dolly-in and drifting fog.",
    "https://example.com/first.png",
    api="byteplus",
    end_image_url="https://example.com/last.png",
    duration=6,
    output_path="outputs/byteplus_image_to_video.mp4",
)
print(result["video_url"])
```

## Pricing Notes

`cost_source="unavailable"`. ModelArk billing is token-based and is not mapped
to USD in this wrapper.

## Validation Note

Validated locally with HTTP-mocked payload tests. No paid ModelArk generation
request was made for this release.
