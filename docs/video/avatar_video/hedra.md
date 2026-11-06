# Hedra Avatar Video API

## Overview

This adapter targets Hedra avatar video generations with a start keyframe and either an uploaded audio asset or inline TTS.

## Current Wrapper Default

`hedra-avatar`

The friendly alias `hedra_avatar` also resolves to `hedra-avatar`.

## Parameters

Use `avatar` or `start_keyframe_id`, or pass `image` / `image_path` / `image_url`. For speech, pass `audio_id`, a local `audio` path, or `text` with `voice_id`. Hedra does not document direct `audio_url` ingestion for this endpoint, so remote audio URLs are rejected unless converted to an asset ID first.

Accepted kwargs include `model`, `duration_seconds`, `duration_ms`, `aspect_ratio`, `resolution`, `voice_id`, `batch_size`, `timeout_seconds`, `poll_interval_seconds`, `on_submitted`, `submission`, and `extra_payload`.

`webhook_url` is rejected with `ValueError` before any request is sent because
this Hedra API does not support callback/webhook URLs.
`on_submitted(receipt)` receives the Hedra submit receipt right after `POST`.
`submission` skips the submit call and resumes polling/result retrieval for the
same generation id.

## Model Coverage

| Model | Status | Notes |
| --- | --- | --- |
| `hedra-avatar`, alias `hedra_avatar` | `implemented` | Target model for image-plus-audio avatar video. |
| `hedra-character-3`, `hedra-omnia` | `implemented` | Hedra native avatar models. |
| `kling-ai-avatar-v2-standard`, `kling-ai-avatar-v2-pro` | `implemented` | Catalog-backed avatar entries. |
| `veed-fabric-1.0` | `implemented` | Catalog-backed Fabric avatar entry. |
| Hedra `video_with_audio` | `not_implemented` | Adds audio to a video but is not a facial lip-sync/avatar generation contract. |

## Pricing

The adapter reports estimated Hedra credits. USD conversion is unavailable.

No live Hedra call is made by the default test suite.
