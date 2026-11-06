# fal.ai Video To Video API

## Overview

This adapter submits video-to-video and reference-video endpoints through the fal.ai queue API. It accepts a source video plus optional prompt, image, and reference media.

## Current Wrapper Default

`wan/v2.6/reference-to-video/flash`

## Parameters

Required input: `video` / `video_path` / `video_url`.

Accepted kwargs are provider-native and include common billing helpers such as `duration_seconds`, `billing_duration_seconds`, `compute_seconds`, `billing_compute_seconds`, `megapixels`, `billing_megapixels`, `num_videos`, and `number_of_videos`, plus transport helpers `webhook_url`, `on_submitted`, and `submission`.

## Model Coverage

| Model | Status | Pricing basis |
| --- | --- | --- |
| `wan/v2.6/reference-to-video/flash` | `implemented` | compute seconds. |
| `fal-ai/ltx-2.3-22b/distilled/reference-video-to-video`, `/lora`, `fal-ai/ltx-2.3-22b/reference-video-to-video` | `implemented` | megapixels; pass `billing_megapixels` for cost. |
| `fal-ai/kling-video/o1/standard/video-to-video/reference`, `fal-ai/kling-video/o1/video-to-video/reference` | `implemented` | seconds. |
| `fal-ai/wan-vace-14b/reframe`, `fal-ai/wan-vace-apps/long-reframe`, `decart/lucy-edit/pro` | `implemented` | seconds. |
| `fal-ai/wan-vace`, `fal-ai/pika/v2/pikadditions`, `fal-ai/video-as-prompt` | `implemented` | per video. |
| `fal-ai/infinitalk/video-to-video` | `implemented` | seconds; also exposed through `video.video_lipsync`. |

## Async References

When fal.ai returns queue URLs, the adapter preserves them and uses them for
`sync=True` polling. Pass `status_url` back to `video.get_status(...)` and
`response_url` back to `video.get_result(...)` when present. Calls that only
provide `request_id`, `model`, and `api` continue to reconstruct queue URLs.

When `webhook_url` is provided, queue submission includes `?fal_webhook=<urlencoded value>`. `on_submitted` runs right after successful submit with the receipt dictionary, and `submission` skips submit and reuses a previous receipt for polling/result retrieval.

## Pricing

When the fal.ai unit is not inferable from request parameters, the wrapper sends the request and returns `cost_source="unavailable"` with a reason. If `billing_unit_quantity` or `unit_quantity` is supplied, the wrapper calls fal.ai's official pricing estimate API and reports `cost_source="fal_pricing_estimate_api"`.
