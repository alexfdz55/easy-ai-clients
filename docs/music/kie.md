# Kie.ai Suno Music Provider

Public dispatcher: `music.generate(..., api="kie")`.

## Public Models

| Native model ID | Standard model key | Default |
| --- | --- | ---: |
| `V5_5` | `suno_v5_5` | Yes |
| `V5_5` | `V5_5` | No |

`model` may be either the native model ID or the standard model key.

When `model` is omitted, `music.generate(..., api="kie")` uses `V5_5`.

This cut implements only `V5_5`, because that is the Kie Suno model that honors
`duration`.

## Endpoints

| Purpose | Endpoint |
| --- | --- |
| Submit generation | `https://api.kie.ai/api/v1/generate` |
| Status and result | `https://api.kie.ai/api/v1/generate/record-info?taskId={taskId}` |

Credential variable: `KIE_API_KEY`.

The wrapper submits an async custom-mode job (`customMode: true`,
`instrumental: false`) and polls until `SUCCESS`. `FIRST_SUCCESS` is treated as
still running so both takes exist before download.

Kie requires `callBackUrl` even when the caller only polls. When `webhook_url`
is omitted, the wrapper sends `https://example.com/kie-callback`.

## Public Call

```python
from easy_ai_clients import music

generation = music.generate(
    lyrics="...",
    api="kie",
    model="suno_v5_5",
    style="pop",
    gender="female",
    duration=60,
)

generation = music.get_status(generation)
generation = music.download_result(generation)
```

## Accepted Parameters

`style` or `prompt` is required.

If both are passed, `prompt` wins.

When `style` is used, the local preset is rendered as **compact Suno tags**
(genre, mood, energy, BPM, instrumentation, language vocals, one-sentence
description). The ElevenLabs/ACE-Step prose in `style_prompts` and
`voice_presets` is not sent. `gender` maps to Kie `vocalGender` (`m` / `f`);
`both` is omitted. `voice_description` is not added to the Kie `style` field.

The local `prompt` built by the style adapter is sent as Kie `style`. Caller
`lyrics` are sent as Kie `prompt` (exact lyrics).

Duration behavior:

| Standard model key | Native model ID | Min | Max | Missing or invalid `duration` | Provider application |
| --- | --- | ---: | ---: | --- | --- |
| `suno_v5_5` | `V5_5` | `10s` | `360s` | Uses `60s` | Not a Kie parameter: appended to `style` as a hint (`about N seconds long, short intro, ends right after the last line`). The real length follows the lyrics (≈1.6 sung words/s plus intro/outro). |

| Parameter | Behavior |
| --- | --- |
| `duration` | Kie has no duration field. Clamped to `10`-`360` (default `60`), appended to `style` as a hint and recorded in `cost_details`. Control the length through the lyrics. |
| `title` | Sent as `title`, max 80 characters. When omitted, the first non-empty lyric line is used. |
| `gender` | `male` / `female` map to `vocalGender` `m` / `f`. `both` is not sent. |
| `webhook_url` | Passed through as `callBackUrl`. |

`negative_prompt` is rejected by presence, including `None`.

Input guards run before the generation call:

| Field | Limit |
| --- | ---: |
| `style` / local prompt | `1000` characters |
| `prompt` / lyrics | `5000` characters |

Over-limit input raises `music.MusicInputLimitError` with repair prompts for
the exceeded fields.

Removed technical kwargs are rejected before provider dispatch:
`audio_settings`, `include_cost`, `number_results`, `output_format`,
`output_type`, `seed`, and `ttl`.

## Normalized Result

A Kie generate always returns two takes. The public contract is one
`output_path`: `download_result` saves `sunoData[0]`. The second URL is stored
in `metadata.alternate_audio_url` **verbatim** (the only `*_url` key the public
sanitizer keeps, because the caller must download it before it expires) together
with `take_count` and `selected_take`.

```python
{
    "provider": "kie",
    "model": "V5_5",
    "model_key": "suno_v5_5",
    "status": "submitted",
    "request_id": "...",
    "output_path": None,
    "cost_usd": 0.06,
    "cost_currency": "USD",
    "cost_source": "kie_generate_flat_estimate",
    "cost_is_estimated": True,
    "cost_details": {"credits": 12, "duration_seconds": 60},
    "metadata": {},
}
```

Cost source policy:

| Source | Meaning |
| --- | --- |
| `kie_generate_flat_estimate` | Flat estimate of 12 Kie credits per generate (~$0.06). Duration does not change the charge. |
| `unavailable` | No usable cost was returned. `cost_usd` is `0.0`. |

Raw provider responses, credentials, and auth headers are not returned in the
public dictionary. Result URLs in metadata keys ending with `_url` are redacted
by the public sanitizer.
