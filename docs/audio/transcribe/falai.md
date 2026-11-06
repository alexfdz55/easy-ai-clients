# Fal.ai Speech Transcription

Snapshot date: 2026-05-15.

## Overview

Use Fal.ai through `easy_ai_clients.audio.transcribe(..., api="falai")`.
The adapter exposes `transcribe(audio_input, model="fal-ai/elevenlabs/speech-to-text/scribe-v2", **kwargs)`.

- Provider homepage: https://fal.ai/
- API key: `FAL_KEY`
- Scribe v1 endpoint: https://fal.ai/models/fal-ai/elevenlabs/speech-to-text/api
- Scribe v2 endpoint: https://fal.ai/models/fal-ai/elevenlabs/speech-to-text/scribe-v2/api
- Pricing API: https://fal.ai/docs/platform-apis/v1/models/pricing

## Defaults

- Default model: `fal-ai/elevenlabs/speech-to-text/scribe-v2`
- Supported models: `fal-ai/elevenlabs/speech-to-text`, `fal-ai/elevenlabs/speech-to-text/scribe-v2`
- Language behavior with no concrete language: `language_code` is omitted and the upstream Scribe endpoint detects the language.
- Default request shape: normalized audio data URL submitted to the Fal.ai queue with diarization and audio event tagging enabled.
- Library audio preparation default: normalized WAV data URL. Prepared audio bytes are reused directly in the data URL with the prepared content type.

## Accepted Kwargs

| Parameter | Native name | Type/shape | Default | Allowed values/range | Notes | Affects cost |
| --- | --- | --- | --- | --- | --- | --- |
| `language_code` | `language_code` | string | omitted | provider language code | Omit for auto language detection. | No |
| `tag_audio_events` | `tag_audio_events` | bool | `True` | bool | Audio event tagging. | No |
| `diarize` | `diarize` | bool | `True` | bool | Speaker diarization. | No documented surcharge |
| `keyterms` | `keyterms` | list[str] | omitted | provider-native | Scribe v2 keyterms use the documented premium when present. | Yes for Scribe v2 |
| `num_speakers` | `num_speakers` | int | omitted | provider-native | Optional speaker hint. | No |
| `language_mkd` | n/a | string or `False` | `"en"` | supported Markdown languages | Controls optional `mkd`. | No |
| `timeout_seconds` | n/a | float | `300` | positive seconds | Queue submit timeout. | No |
| `webhook_url` | n/a | string | omitted | valid URL | Adds `?fal_webhook=<urlencoded value>` to queue submission. | No |
| `on_submitted` | n/a | callable | omitted | callable | Called right after successful submit with the receipt dict; raised exceptions are re-raised. | No |
| `submission` | n/a | dict | omitted | fal receipt payload | Skip submit and go straight to polling/result retrieval. | No |

Unknown kwargs raise `TypeError`.

## Model Notes

### `fal-ai/elevenlabs/speech-to-text`

Scribe v1 through Fal.ai. Pricing API currently reports a per-minute unit price.

### `fal-ai/elevenlabs/speech-to-text/scribe-v2`

Default model. Pricing API currently reports a lower per-minute unit price. When `keyterms` are supplied, the adapter applies the documented Scribe v2 keyterm premium.

## Cost Behavior

Fal.ai transcription payloads do not include final per-call cost. The adapter queries the official Pricing API:

- If `X-Fal-Billable-Units` is present, the adapter multiplies that header by the Pricing API unit price and returns `cost_source="pricing_api_billable_units"`.
- If the header is absent, the adapter calculates from audio duration and the Pricing API unit price with `cost_source="pricing_api"`.
- If the pricing lookup fails, `cost_usd=0.0`, `cost_source="unavailable"`, and `cost_lookup_error` explains the failure.

Pricing API calculations are deterministic estimates, so `cost_is_estimated=True`.

## Prepared Audio and Upload Formats

```python
from easy_ai_clients.audio import prepare_transcription_audio, transcribe

prepared = prepare_transcription_audio("audio.mp3")
bundle = transcribe(prepared, api="falai")
```

Fal.ai model inputs use `audio_url`. The adapter converts prepared bytes to a
Base64 data URI and preserves `PreparedTranscriptionAudio.content_type` in that
URI. Fal.ai also accepts hosted/uploaded file URLs in its native workflow, but
this adapter keeps the public dispatcher behavior local and reusable by sending
the prepared data URI. `language_code` remains omitted unless explicitly set.

## Examples

```python
from easy_ai_clients import audio

bundle = audio.transcribe("audio.mp3", api="falai")
```

```python
bundle = audio.transcribe(
    "audio.mp3",
    api="falai",
    model="fal-ai/elevenlabs/speech-to-text",
)
```
