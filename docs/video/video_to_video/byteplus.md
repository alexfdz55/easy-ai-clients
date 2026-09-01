# BytePlus Seedance Video To Video API

Implementation status: implemented

## Overview

This wrapper targets BytePlus ModelArk inference for Seedance 2.x video edit and
extend tasks. The source video is sent as `role: "reference_video"`. Snapshot
date for model and limit assumptions: 2026-09-01.

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

Prefer Seedance 2.5 for edit/extend task-type constraints. Use Mini only when
720p and a 4-15 second output are enough.

## Parameter Reference

Public dispatcher signature:

```python
def video_to_video(prompt=None, video=None, model=None, *, api, **kwargs):
    pass
```

Accepted `kwargs`: `model`, `video_path`, `video_url`, `image` / `image_url`
(optional reference image), `task_type` or `omni_reference_task_type`
(`edit` / `extend` / `auto`), `extend=True` as a shorthand for extend,
`resolution`, `ratio`, `duration` (alias `duration_seconds`), `generate_audio`,
`watermark`, `seed`, `camera_fixed`, `image_urls`, `video_urls`, `audio_urls`,
`timeout_seconds`, `poll_interval_seconds`, and `extra_payload`.

Default task type is `edit`. For edit tasks, omitted `duration` is sent as `-1`
so output length follows the source clip. For Seedance 2.5, omitted `ratio`
defaults to `adaptive`.

`generate_audio` defaults to `true`. Prefer a public `video_url` over a local
file; ModelArk does not recommend Base64 for large videos.

## Model Coverage

| Model or endpoint | Official source | Status | Implemented default | Notes |
| --- | --- | --- | --- | --- |
| `dreamina-seedance-2-5-260628` | https://docs.byteplus.com/en/docs/ModelArk/1520757 | `implemented` | yes | Edit and extend. |
| `dreamina-seedance-2-0-260128` | https://docs.byteplus.com/en/docs/ModelArk/1520757 | `implemented` | no | Edit and extend. |
| `dreamina-seedance-2-0-fast-260128` | https://docs.byteplus.com/en/docs/ModelArk/1520757 | `implemented` | no | Edit and extend. |
| `dreamina-seedance-2-0-mini-260615` | https://docs.byteplus.com/en/docs/ModelArk/1520757 | `implemented` | no | Edit and extend. |

## Domain Notes

`sync=False` returns the task id as `request_id`. Use `video.get_status`,
`video.get_result`, and `video.download` with operation `video_to_video` for
async follow-up work.

## Python Example

```python
from easy_ai_clients import video

edited = video.video_to_video(
    "Replace the background with a rainy Tokyo street at night.",
    video="https://example.com/source.mp4",
    api="byteplus",
    output_path="outputs/byteplus_edit.mp4",
)

extended = video.video_to_video(
    "Extend the shot as the camera continues down the hallway.",
    video="https://example.com/source.mp4",
    api="byteplus",
    extend=True,
    duration=11,
    output_path="outputs/byteplus_extend.mp4",
)
print(edited["request_id"], extended["request_id"])
```

## Pricing Notes

`cost_source="unavailable"`. ModelArk billing is token-based and is not mapped
to USD in this wrapper.

## Validation Note

Validated locally with HTTP-mocked payload tests. No paid ModelArk generation
request was made for this release.
