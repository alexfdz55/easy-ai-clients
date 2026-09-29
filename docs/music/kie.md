# Kie.ai Suno Music Provider

Public dispatcher: `music.generate(..., api="kie")`.

## Public Models

| Native model ID | Standard model key | Default |
| --- | --- | ---: |
| `V5_5` | `suno_v5_5` | Yes |
| `V5_5` | `V5_5` | No |
| `V6` | `suno_v6` | No |
| `V6` | `V6` | No |

`model` may be either the native model ID or the standard model key.

When `model` is omitted, `music.generate(..., api="kie")` uses `V5_5`.

`V5_5` goes through Kie's legacy endpoint and has no duration parameter. `V6`
goes through Kie's jobs endpoint: it honors `duration` and accepts personas
(`persona_id` with `persona_model`) to keep the same voice across songs. Kie
already lists V4 to V5.5 as discontinued versions, and Suno announced their
retirement with V6.

## Endpoints

| Model | Purpose | Endpoint |
| --- | --- | --- |
| `V5_5` | Submit generation | `https://api.kie.ai/api/v1/generate` |
| `V5_5` | Status and result | `https://api.kie.ai/api/v1/generate/record-info?taskId={taskId}` |
| `V6` | Submit generation or persona | `https://api.kie.ai/api/v1/jobs/createTask` |
| `V6` | Status and result | `https://api.kie.ai/api/v1/jobs/recordInfo?taskId={taskId}` |

Credential variable: `KIE_API_KEY`.

`V5_5`: the wrapper submits an async custom-mode job (`customMode: true`,
`instrumental: false`) and polls until `SUCCESS`. `FIRST_SUCCESS` is treated as
still running so both takes exist before download. Kie requires `callBackUrl`
even when the caller only polls. When `webhook_url` is omitted, the wrapper
sends `https://example.com/kie-callback`.

`V6`: the wrapper submits `{"model": "ai-music-api/generate", "input": {...}}`
with `custom_mode: true`, `instrumental: false` and the fields in snake_case.
It polls `state` (`waiting`, `queuing`, `generating`, `success`, `fail`) and
reads the takes from `resultJson`, which Kie returns as a JSON string.
`callBackUrl` is sent only when `webhook_url` is given.

## Public Call

```python
from easy_ai_clients import music

generation = music.generate(
    lyrics="...",
    api="kie",
    model="suno_v6",
    style="pop",
    gender="female",
    duration=60,
    persona_id="...",
    persona_model="voice_persona",
)

generation = music.get_status(generation)
generation = music.download_result(generation)
```

## Personas

```python
persona = music.create_persona(
    api="kie",
    task_id=generation["request_id"],
    audio_id=generation["metadata"]["take_audio_ids"][0],
    name="Warm pop voice",
    description="Clear female lead vocal, latin pop",
    vocal_start=3,
    vocal_end=28,
)
persona["persona_id"]
```

- A persona is created from one take of a completed generation. Each take can
  produce only one persona. Creating it costs no Kie credits.
- The analyzed window (`vocal_end - vocal_start`) must last between 10 and 30
  seconds.
- `persona_model="voice_persona"` keeps the voice and lets the style change;
  `"style_persona"` keeps the style. Both require `V6`.
- Measured on 2026-09-28: with one language, a `voice_persona` kept the same
  voice across reggaeton, rock and ballad. Across languages another voice
  showed up.

## Accepted Parameters

`style` or `prompt` is required.

If both are passed, `prompt` wins.

When `style` is used, the local preset is rendered as **compact Suno tags**
(genre, mood, energy, BPM, instrumentation, language vocals, one-sentence
description). The ElevenLabs/ACE-Step prose in `style_prompts` and
`voice_presets` is not sent. `gender` maps to the Kie vocal gender (`m` / `f`);
`both` is omitted. `voice_description` is not added to the Kie `style` field.

The local `prompt` built by the style adapter is sent as Kie `style`. Caller
`lyrics` are sent as Kie `prompt` on `V5_5` and as `lyrics` on `V6` (exact
lyrics).

Duration behavior:

| Standard model key | Native model ID | Min | Max | Missing or invalid `duration` | Provider application |
| --- | --- | ---: | ---: | --- | --- |
| `suno_v5_5` | `V5_5` | `10s` | `360s` | Uses `60s` | Not a Kie parameter: appended to `style` as a hint (`about N seconds long, short intro, ends right after the last line`). The real length follows the lyrics (≈1.6 sung words/s plus intro/outro). |
| `suno_v6` | `V6` | `10s` | `360s` | Uses `60s` | Sent as `duration` and honored (30 s requested gave 28.8–30.4 s; 60 s gave 59.2–61.2 s). Without it Kie composes 20 s, so the wrapper always sends it. |

| Parameter | Behavior |
| --- | --- |
| `duration` | Clamped to `10`-`360` (default `60`) and recorded in `cost_details`. `V6` sends it as `duration`; `V5_5` appends it to `style` as a hint. |
| `title` | Sent as `title`, max 80 characters. When omitted, the first non-empty lyric line is used. |
| `gender` | `male` / `female` map to `vocalGender` (`V5_5`) or `vocal_gender` (`V6`) `m` / `f`. `both` is not sent. |
| `negative_tags` | Text or list of what must not sound, sent as `negativeTags` (`V5_5`) or `negative_tags` (`V6`). |
| `persona_id` | `V6` only. Persona or custom voice ID. Requires `persona_model`. `V5_5` raises `ValueError`. |
| `persona_model` | `V6` only. `voice_persona` or `style_persona`. |
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
`output_path`: `download_result` saves the first take. The second URL is stored
in `metadata.alternate_audio_url` **verbatim** (the only `*_url` key the public
sanitizer keeps, because the caller must download it before it expires) together
with `take_count` and `selected_take`. On `V6`, `metadata.take_audio_ids` and
`metadata.take_durations` also list both takes (the IDs feed
`create_persona`).

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
| `kie_credits_consumed` | `V6`: the real `creditsConsumed` of the task × $0.005 per Kie credit. |
| `unavailable` | No usable cost was returned. `cost_usd` is `0.0`. |

Raw provider responses, credentials, and auth headers are not returned in the
public dictionary. Result URLs in metadata keys ending with `_url` are redacted
by the public sanitizer.
