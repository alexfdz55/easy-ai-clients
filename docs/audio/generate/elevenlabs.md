# ElevenLabs Speech Synthesis

Snapshot date: 2026-04-24.

## Overview

ElevenLabs speech synthesis is available through the public dispatcher `easy_ai_clients.audio.generate(..., api="elevenlabs")`; the provider adapter exposes `generate(text, model="eleven_flash_v2_5", voice="NndrHq4eUijN4wsQVtzW", language_code=None, **kwargs)`.

- Signup/account: https://elevenlabs.io/app/sign-up
- API key variable: `ELEVENLABS_API_KEY`
- TTS endpoint docs: https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps
- Model catalog API: https://elevenlabs.io/docs/api-reference/models/get-all
- Voice discovery API: https://elevenlabs.io/docs/api-reference/voices/search
- Pricing: https://elevenlabs.io/pricing/api

## Defaults And Cost Behavior

- Default model: `eleven_flash_v2_5`
- Default voice: `NndrHq4eUijN4wsQVtzW`
- Default language behavior: no `language_code` is sent unless the caller passes one, and
  the model detects the language from the text. `language_code` ENFORCES a language for the
  model and for text normalization, so a wrong one makes digits be read in that language
  (a Portuguese "Em 1959" read as "nineteen fifty-nine" on Eleven v4 Turbo with `"en"`).
  When passed, it is forwarded only to models that support it.
- Lowest-cost default: Flash v2.5 with normal MP3 output, automatic text normalization, no premium extras.
- Word timing source: native ElevenLabs character alignment from `/with-timestamps`.
- Cost: characters of the text times the model's list price per character. It is an
  estimate (`cost_is_estimated: true`): a temporary discount on the account is not applied.
  `cost_details` carries `characters` and `provider_credits`, the account credits the
  provider reports in its `character-cost` header. A credit is one character only on the
  older models, so credits are never priced as characters.

## Public Parameters

- `text`, `model`, `voice`, `language_code`
- Voice settings: `stability`, `similarity_boost`, `style`, `use_speaker_boost`, `speed`
- Text controls: `apply_text_normalization`, `apply_language_text_normalization`, `pronunciation_dictionary_locators`
- Determinism/context: `seed`, `previous_text`, `next_text`, `previous_request_ids`, `next_request_ids`
- Voice conversion behavior: `use_pvc_as_ivc`
- Request controls: `enable_logging`, `optimize_streaming_latency`, `output_format`, `timeout_seconds`

Supported `output_format` values are the ElevenLabs documented MP3, PCM, u-law, A-law, and Opus variants implemented in `OUTPUT_FORMATS`.

## Voice Coverage

Voices are account-dependent. The wrapper accepts any voice id supplied through `voice` and validates the resulting provider call. The default voice was validated on the active account.

## Model Coverage

### Model: `eleven_v4`

Inherits the shared ElevenLabs parameter surface.

- Supports `language_code`.
- List price: 0.08 USD per 1,000 characters.

### Model: `eleven_v4_turbo`

Inherits the shared ElevenLabs parameter surface.

- Supports `language_code`.
- List price: 0.04 USD per 1,000 characters.
- `speed` is accepted and has no effect: the same text came out with the same
  duration at 0.8 and at 1.1.
- Validated: yes, speech with timestamps on 2026-10-02.

### Model: `eleven_v3`

Inherits the shared ElevenLabs parameter surface.

- Supports `language_code`.
- Supports the default voice when the account allows it.
- Validated: yes, model smoke passed.

### Model: `eleven_multilingual_v2`

Inherits the shared ElevenLabs parameter surface.

- Supports `language_code`.
- Validated: yes, model smoke passed.

### Model: `eleven_multilingual_v1`

Inherits the shared ElevenLabs parameter surface.

- Supports `language_code`.
- Validated: yes, model smoke passed.

### Model: `eleven_flash_v2_5`

Inherits the shared ElevenLabs parameter surface.

- Default model and lowest-cost wrapper path.
- Supports `language_code`.
- Validated: yes, model smoke and `seed` + text normalization + compact MP3 parameter cluster passed.

### Model: `eleven_flash_v2`

Inherits the shared ElevenLabs parameter surface.

- Does not support non-English `language_code` in this wrapper.
- Validated: yes, model smoke passed.

### Model: `eleven_turbo_v2_5`

Inherits the shared ElevenLabs parameter surface.

- Supports `language_code`.
- Validated: yes, model smoke passed.

### Model: `eleven_turbo_v2`

Inherits the shared ElevenLabs parameter surface.

- Does not support non-English `language_code` in this wrapper.
- Validated: yes, model smoke passed.

### Model: `eleven_monolingual_v1`

Inherits the shared ElevenLabs parameter surface.

- English-only behavior; non-English `language_code` is rejected.
- Validated: yes, model smoke passed.

## Output Notes

The wrapper returns the standard synthesis bundle. Raw PCM, u-law, and A-law responses are wrapped into WAV internally so downstream decoding and timing projection stay stable.

## Example

~~~python
from easy_ai_clients import audio

result = audio.generate(
    "Hello from elevenlabs.",
    api="elevenlabs",
)
print(result["cost_usd"])
~~~

## Validation Note

The bundled unit tests validate imports and dispatcher routing without calling paid provider APIs. Provider model catalogs, account access, prices, and rate limits can change independently of this package; run your own provider smoke tests with your credentials before relying on a specific model in production.