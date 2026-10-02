# Error Handling

Public operations in `easy-ai-clients` prefer normalized failure dictionaries
over exceptions. When a dispatcher can preserve the operation shape, it returns
safe empty output plus an `error` object:

- `type`
- `message`
- `provider`
- `operation`
- `model`

Four more keys appear only when the failure was an HTTP response and the value
is known. They are read from the low-level HTTP error even when an adapter
wraps it in a friendlier exception:

- `http_status`: the status code the provider answered with.
- `provider_code`: the provider's own error code (`payment_issue`,
  `quota_exceeded`, `feature_not_supported`...).
- `provider_message`: the provider's own message, redacted and capped at 500
  characters.
- `category`: `"account"` when the status is 401, 402 or 403. The provider is
  turning the account away (unpaid invoice, exhausted credits, revoked key),
  not the request: retrying the same call cannot succeed, and the caller may
  switch to another provider.

Error messages are compacted and redacted where the dispatcher or adapter owns
the failure boundary. API keys, authorization headers, tokens, matching
environment-secret values, signed URLs, and large audio payloads should not be
exposed.

## Common Exceptions

| Exception | Typical cause |
| --- | --- |
| `ValueError` | Local request assembly errors, incompatible local media arguments, or unsupported helper operation. |
| `TypeError` | Invalid helper/private-adapter call shape. |
| `RuntimeError` | Missing credentials in direct private adapter paths, provider response normalization failure, or wrapped provider/network failure. |
| `music.MusicInputLimitError` | Music prompt, lyric, or Google token input exceeds the selected provider/model limit before generation. |
| `OSError` / `EnvironmentError` | Missing credentials in audio and some provider helper paths. |
| `requests.HTTPError` / `httpx.HTTPStatusError` | Provider returned a non-success HTTP status and the adapter raised the HTTP exception directly. |
| `requests.ConnectionError` / `requests.Timeout` | Network failure or timeout after retries. |
| `NotImplementedError` | Helper called for a provider that does not implement it, such as `text.update_cost(api="anthropic")`. |

Exact exception classes can still vary in helper methods and private adapters
because provider modules use different HTTP clients. Public dispatchers convert
those failures into dictionaries when possible.

## Public Failure Shapes

| Operation | Failure fields |
| --- | --- |
| `text.generate` | `output_text=""`, `cost_usd=0.0`, `cost_source="unavailable"`, `warnings`, `error` |
| `audio.generate` | `audio=None`, `words={}`, `cost_usd=0.0`, `warnings`, `error` |
| `audio.transcribe` | `text=""`, `cost_usd=0.0`, `cost_source="unavailable"`, `cost_lookup_error`, `warnings`, `error` |
| `image.generate/edit/remix` | `base64=""`, `cust_usd=0.0`, `warnings`, `error` |
| `image.analyze` | `output` contains the failure text, `cost_usd=0.0`, `cost_source="unavailable"`, `warnings`, `error` |
| `music.generate/get_status/download_result` | Local validation and provider wrapper failures can raise; successful results keep the safe normalized music schema |
| `video.*` | `status="failed"`, `video_url=None`, `cost_usd=0.0`, `cost_source="unavailable"`, `warnings`, `error` |

Music provider parser failures are raised as sanitized exceptions instead of
raw provider-envelope `KeyError`, `AttributeError`, or invalid audio writes.
Local music worker failures include provider, model, local request ID, exception
type, and a sanitized message. They do not add `error`, `raw_response`, provider
URLs, headers, or audio payloads to the public music result dictionary.

## Image Warnings

`image.generate`, `image.edit`, and `image.remix` preserve the public return
shape when a provider returns a structured failure that can be normalized:

```python
from easy_ai_clients import image

result = image.generate("a small app icon", api="openai")
if result["warnings"]:
    print("provider warning:", result["warnings"])
```

The returned dictionary still contains `cust_usd`, `base64`, `warnings`, and
`request_id`. When generation fails, `base64` may be empty and `warnings` should
be treated as the failure message.

`image.analyze` returns the normalized keys `request_id`, `cost_usd`,
`cost_currency`, `cost_is_estimated`, `cost_source`, `cost_details`,
`input_text`, and `output`. Some provider-side failures are represented in the
`output` string when the adapter can preserve the public return contract.

## Models and Provider Kwargs

Provider-native kwargs are forwarded whenever the wrapper can assemble a
request. The documented model and parameter tables are reference metadata for
defaults, examples, and pricing. They are not an acceptance gate.

```python
from easy_ai_clients import text

result = text.generate(
    "hi",
    api="openai",
    model="provider-new-model",
    provider_new_parameter=True,
)

if result.get("error"):
    print(result["error"]["message"])
```

If the provider accepts the model and kwargs, the call succeeds. If the provider
rejects them, the dispatcher returns a normalized error result. Local validation
is kept only for cases that prevent building a request, such as missing local
files, conflicting `path`/`url` arguments, or invalid internal payload shapes.

`music.generate(...)` also raises `ValueError` for invalid local request shapes,
including missing `api`, unknown music provider, unsupported model, unknown
style, missing `style`/`prompt`, removed public kwargs, and unsupported
`negative_prompt` usage. These failures happen before live provider calls.

Music input-limit failures raise `music.MusicInputLimitError`. The success
schema does not change. The exception exposes safe repair data:

```python
try:
    music.generate(
        lyrics="...",
        api="runware",
        prompt="...",
    )
except music.MusicInputLimitError as exc:
    data = exc.to_dict()
    repair_prompts = exc.repair_prompts
```

`repair_prompts` is keyed by exceeded field, such as `caption`, `lyrics`,
`prompt`, `positivePrompt`, `settings.lyrics`, or `contents`.

When a style preset is used, the music router first retries smaller
`style_prompts` and `voice_presets` variants before raising
`MusicInputLimitError`. Explicit caller `prompt` and `voice_description` values
are not rewritten by this fallback.

Music input limits:

| API | Field | Limit | Unit |
| --- | --- | ---: | --- |
| `deapi` | `caption` / prompt | `3000` | characters |
| `deapi` | `lyrics` | `3000` | characters |
| `elevenlabs` | final prompt with lyrics appended | `4100` | characters |
| `google` | final `contents` payload | `131072` | tokens via `countTokens` |
| `runware` | `positivePrompt` | `3000` | characters |
| `runware` | `settings.lyrics` | `3000` | characters |

## Cost Helper Errors

Cost refresh helpers are implemented only for providers that expose compatible
request lookup or generation lookup behavior.

```python
from easy_ai_clients import text

result = text.generate("ping", api="openrouter")
result = text.update_cost(result, api="openrouter")

try:
    text.update_cost({}, api="anthropic")
except NotImplementedError:
    print("Anthropic does not implement text.update_cost.")
```

For images, pass the operation name explicitly:

```python
from easy_ai_clients import image

result = image.generate("a tiny robot", api="openrouter")
result = image.update_cost("generate", result, api="openrouter")
```

For transcription, only Deepgram currently implements post-hoc cost refresh:

```python
from easy_ai_clients import audio

result = audio.transcribe("meeting.mp3", api="deepgram")
result = audio.update_cost("transcribe", result, api="deepgram")

try:
    audio.update_cost("transcribe", result, api="fireworks")
except NotImplementedError:
    print("Fireworks does not implement transcription cost refresh.")
```

`audio.update_cost(...)` raises `ValueError` for unsupported operations; the
only supported operation is currently `"transcribe"`.

## Unknown Cost

When cost cannot be known from provider usage, pricing APIs, or documented
metadata, results use:

- `cost_usd=0.0`
- `cost_source="unavailable"`
- `cost_is_estimated` according to the operation contract
- `warnings` or `cost_lookup_error` with a sanitized reason when one is available

When a provider price table or pricing API is used, `cost_is_estimated=True`.
Deepgram exact usage lookup still returns `cost_source="usage_lookup"` and
`cost_is_estimated=False`.

## Defensive Pattern

```python
from easy_ai_clients import text


def safe_generate(prompt: str, *, api: str, **kwargs):
    result = text.generate(prompt, api=api, **kwargs)
    if result.get("error"):
        raise SystemExit(result["error"]["message"])
    return result
```

For helper methods and direct private adapters, catch narrow exceptions around
the call you make. Do not catch broad exceptions unless you are at an application
boundary where the error is logged, redacted, and converted to a user-facing
failure.
