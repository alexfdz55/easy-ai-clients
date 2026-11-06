# fal.ai Video Lip Sync API

Implementation status: implemented

## Overview

This wrapper targets fal.ai source-video plus audio lip-sync generation. Snapshot date for model and pricing assumptions: 2026-05-13.

The implemented default is `fal-ai/infinitalk/video-to-video`, the official fal.ai source-video plus audio talking-video endpoint that maps directly to this operation.

## Account And Credentials

Use `FAL_KEY` from the environment. The wrapper validates the key before making a request.

## Official Sources

- fal.ai model APIs: https://fal.ai/docs/documentation/model-apis
- fal.ai queue: https://fal.ai/docs/documentation/model-apis/inference/queue
- fal.ai pricing: https://fal.ai/docs/documentation/model-apis/pricing
- InfiniteTalk video model page: https://fal.ai/models/fal-ai/infinitalk/video-to-video/api

## Current Wrapper Default

`fal-ai/infinitalk/video-to-video`

This model is the implemented fal.ai candidate that fits the source-video plus audio lip-sync definition directly.

## Lowest-Cost Default Policy

Use the lowest-cost verified fal.ai source-video plus audio lip-sync endpoint. Do not classify generic video editing or video-with-audio as lip sync without explicit facial/lip synchronization behavior.

## Parameter Reference

Public dispatcher signature:

```python
def video_lipsync(video=None, audio=None, text=None, model=None, *, api, **kwargs):
    pass
```

Required normalized inputs: `video_path` or `video_url`, and `audio_path` or `audio_url`. `text` is rejected because this wrapper does not expose text-to-speech for the selected model.

Accepted `kwargs`: `model`, `prompt`, `num_frames`, `resolution`, `seed`, `acceleration`, `duration_seconds`, `billing_duration_seconds`, `timeout_seconds`, `poll_interval_seconds`, `extra_payload`, `webhook_url`, `on_submitted`, and `submission`.

Validated values: `resolution` `480p` or `720p`, `num_frames` 41 to 241, `seed` 0 to 4294967295, and `acceleration` `none`, `regular`, or `high`.

The fal.ai page currently contains contradictory generated prose for `num_frames`; the embedded request schema and the default example allow `145`, so the wrapper follows the schema range `41` to `241`.

## Model Coverage

| Model or endpoint | Official source | Status | Implemented default | Notes |
| --- | --- | --- | --- | --- |
| `fal-ai/infinitalk/video-to-video` | https://fal.ai/models/fal-ai/infinitalk/video-to-video/api | `implemented` | yes | Source video plus audio talking-video/lip-sync candidate. |

## Domain Notes

`duration_seconds` or `billing_duration_seconds` can be supplied for cost precision. If omitted, the wrapper estimates duration from `num_frames / 25` and otherwise follows the provider default when `num_frames` is not provided. Queue helper functions are available.

When `webhook_url` is provided, queue submission includes `?fal_webhook=<urlencoded value>`. `on_submitted` runs right after successful submit with the receipt dictionary, and `submission` skips submit and reuses a previous receipt for polling/result retrieval.

When fal.ai returns queue URLs, the adapter preserves them and uses them for
`sync=True` polling. Pass `status_url` back to `video.get_status(...)` and
`response_url` back to `video.get_result(...)` when present. Calls that only
provide `request_id`, `model`, and `api` continue to reconstruct queue URLs.

## Python Example

```python
from easy_ai_clients import video

result = video.video_lipsync(
    video="inputs/speaker.mp4",
    audio="inputs/voice.wav",
    api="falai",
    duration_seconds=6,
    output_path="outputs/falai_video_lipsync.mp4",
)
print(result["cost_usd"])
```

## Pricing Notes

The wrapper estimates `cost_usd` as `$0.30 * generated_seconds`. The estimate source is documented model pricing and does not include live usage reconciliation.

## Validation Note

Validated locally with package import, dispatcher, and selected parameter-validation tests. No paid fal.ai generation request was made.
