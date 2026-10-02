# audio.generate(api="falai")

ElevenLabs voices served through fal.ai's queue, with character timings.

Environment variable: `FAL_KEY`

Default model: `elevenlabs/tts/eleven-v4-turbo`

It exists as a second route to the same voices: when the ElevenLabs account
cannot serve a request (see `category: "account"` in [errors](../../errors.md)),
the same model and the same voice id can be asked through fal.

## Defaults And Cost Behavior

- The request goes through `https://queue.fal.run/{model}` and is polled until
  it completes.
- `timestamps` is always requested. The result carries `words` built from the
  character timings, with the same tokenization as `api="elevenlabs"`.
- Texts longer than the per-request limit are split into chunks; `request_ids`
  lists one fal request id per chunk.
- Cost is the billed units fal reports (`X-Fal-Billable-Units`) times the
  current unit price from fal's pricing API (`cost_source:
  "pricing_api_billable_units"`). When either is missing it falls back to the
  documented table (`"official_pricing_table"`).

## Public Parameters

| Parameter | Notes |
| --- | --- |
| `voice` | An ElevenLabs voice id or a preset name. An unknown one fails with HTTP 422 `Voice not found`; it never falls back to another voice. Voices cloned in your own ElevenLabs account do not exist on fal. |
| `language_code` | ISO 639-1. |
| `output_format` | Same enum as ElevenLabs, default `mp3_44100_128`. |
| `stability`, `similarity_boost`, `seed`, `apply_text_normalization` | Forwarded as given. |
| `timeout_seconds` | Per chunk, default 180. |

Other keyword arguments are forwarded to the payload untouched.

## Model Coverage

### Model: `elevenlabs/tts/eleven-v4-turbo`

- List price: 0.04 USD per 1,000 characters.
- `speed` is accepted and has no effect.
- Validated: yes, on 2026-10-02 with a library voice id, an unknown voice id
  and `timestamps`.

## Example

```python
from easy_ai_clients import audio

result = audio.generate(
    "El agua del océano alimenta la tormenta.",
    api="falai",
    model="elevenlabs/tts/eleven-v4-turbo",
    voice="15bJsujCI3tcDWeoZsQP",
    language_code="es",
)
```
