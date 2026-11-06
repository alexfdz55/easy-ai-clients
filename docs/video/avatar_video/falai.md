# fal.ai Avatar Video API

## Overview

This adapter covers fal.ai image/audio-to-video and avatar/talking-video endpoints that fit a visual identity plus speech source flow.

## Current Wrapper Default

`fal-ai/longcat-single-avatar/image-audio-to-video`

## Parameters

Inputs: `image` / `image_path` / `image_url`, `audio` / `audio_path` / `audio_url`, or provider-native text/TTS kwargs when the selected fal.ai endpoint supports them.

Transport helpers: `webhook_url` appends `?fal_webhook=<urlencoded value>` to queue submission, `on_submitted` runs right after successful submit with the receipt dictionary, and `submission` skips submit and reuses a previous receipt for polling/result retrieval.

## Model Coverage

| Model | Status | Pricing basis |
| --- | --- | --- |
| `fal-ai/bytedance/omnihuman/v1.5`, alias `fal_omnihuman_v1_5` | `implemented` | seconds; pass duration for cost. |
| `veed/fabric-1.0`, alias `fal_veed_fabric_1_0` | `implemented` | seconds by resolution; pass duration for cost. |
| `fal-ai/longcat-single-avatar/image-audio-to-video` | `implemented` | resolution-weighted units. |
| `fal-ai/longcat-multi-avatar/image-audio-to-video` | `implemented` | resolution-weighted units. |
| `veed/fabric-1.0/fast` | `implemented` | compute seconds; pass billing quantity for cost. |
| `fal-ai/flashtalk`, `fal-ai/ai-avatar`, `fal-ai/infinitalk`, `fal-ai/echomimic-v3`, `fal-ai/wan/v2.2-14b/speech-to-video` | `implemented` | seconds. |
| `fal-ai/creatify/aurora` | `implemented` | units; pass `billing_units` for cost. |

## Target Aliases

`fal_omnihuman_v1_5` maps to `fal-ai/bytedance/omnihuman/v1.5`.

The payload uses `image_url`, `audio_url`, `resolution`, optional `prompt`, and
`turbo_mode=True` by default. The wrapper default resolution for this alias is
`720p`.

`fal_veed_fabric_1_0` maps to `veed/fabric-1.0`.

The payload uses `image_url`, `audio_url`, and `resolution`. The wrapper default
resolution for this alias is `480p`.

## Async References

When fal.ai returns queue URLs, the adapter preserves them and uses them for
`sync=True` polling. Pass `status_url` back to `video.get_status(...)` and
`response_url` back to `video.get_result(...)` when present. Calls that only
provide `request_id`, `model`, and `api` continue to reconstruct queue URLs.

## Pricing

Known pricing units are mapped from fal.ai model pricing.

Unknown billable quantities return `cost_source="unavailable"` instead of
guessing. If `billing_unit_quantity` or `unit_quantity` is supplied, the wrapper
calls fal.ai's official pricing estimate API and reports
`cost_source="fal_pricing_estimate_api"`.

No live fal.ai call is made by the default test suite.
