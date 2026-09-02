# easy-ai-clients

[![PyPI version](https://img.shields.io/pypi/v/easy-ai-clients.svg)](https://pypi.org/project/easy-ai-clients/)
[![Python versions](https://img.shields.io/pypi/pyversions/easy-ai-clients.svg)](https://pypi.org/project/easy-ai-clients/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/reiarthur/easy-ai-clients/blob/main/LICENSE)

`easy-ai-clients` is a Python library with dispatcher-style clients for text,
audio, image, music, video, media, webhook, and account workflows across
multiple AI providers.

The package is a library, not a hosted service. It calls provider APIs only when
your code calls a public dispatcher with an explicit `api=` argument.

## Install

```bash
pip install easy-ai-clients
```

Requirements:

- Python `>=3.11`
- Credentials only for the providers you call
- Local `ffmpeg` support through `imageio-ffmpeg` / `pydub` for non-WAV audio
  inputs

## Quickstart

```python
from dotenv import load_dotenv
from easy_ai_clients import audio, image, music, text, video

load_dotenv("path/to/private.env")

text_result = text.generate(
    "Write one release note sentence.",
    instruction="Use plain English.",
    api="openai",
)
print(text_result["output_text"])

speech = audio.generate("Hello from easy-ai-clients.", api="openai", voice="alloy")
speech["audio"].export("hello.mp3", format="mp3")

transcript = audio.transcribe("hello.mp3", api="deepgram")
print(transcript["text"])

generated = image.generate("a clean paper airplane app icon", api="openai")
print(generated["request_id"])

song = music.generate(
    lyrics="[Verse]\nWe build the morning line\n[Chorus]\nThe work begins to shine",
    api="runware",
    model="ace_step_v1_5_xl_turbo",
    style="rock",
)
print(song["status"], song["request_id"])

clip = video.generate(
    "A smooth four-second product shot of a paper airplane.",
    api="google",
    duration_seconds=4,
)
print(clip["video_url"])
```

## Public API

Import public dispatchers from the top-level package:

```python
from easy_ai_clients import account, audio, image, media, music, text, video, webhooks
```

Provider modules under private `_apis` packages are implementation details.
Applications should use the public dispatcher modules.

| Module | Main Functions | Purpose |
| --- | --- | --- |
| `text` | `generate`, `list_models`, `update_cost`, `available_apis` | Text-in/text-out generation |
| `audio` | `generate`, `transcribe`, `prepare_transcription_audio`, voice helpers, `update_cost` | Speech synthesis, transcription, and voice workflows |
| `image` | `generate`, `edit`, `remix`, `analyze`, `update_cost` | Image generation, editing, remixing, and vision analysis |
| `music` | `generate`, `get_status`, `download_result`, `get_generation_options`, `get_style_presets`, `build_lyrics_prompt` | Narrow validated lyric-based music generation |
| `video` | `generate`, `text_to_video`, `image_to_video`, `video_to_video`, `motion_control`, `avatar_video`, `video_with_audio`, `create_avatar`, `image_lipsync`, `video_lipsync`, `agent_video`, `translate`, async helpers | Video generation, lip-sync, avatar, translation, and HeyGen resource workflows |
| `media` | `upload_asset`, `delete_asset`, `available_apis` | Provider asset helpers |
| `webhooks` | endpoint, event, and secret-rotation helpers | Provider webhook management |
| `account` | `get_current_user`, `available_apis` | Provider account lookup |

## Supported Providers

Use provider discovery helpers to inspect the provider IDs available for each
operation:

```python
from easy_ai_clients import account, audio, image, media, music, text, video, webhooks

text.available_apis()
audio.available_synthesize_apis()
audio.available_transcribe_apis()
audio.available_voice_apis()
image.available_generate_apis()
image.available_edit_apis()
image.available_remix_apis()
image.available_analyze_apis()
music.available_apis()
video.available_text_to_video_apis()
video.available_image_to_video_apis()
video.available_video_to_video_apis()
video.available_motion_control_apis()
video.available_avatar_video_apis()
video.available_video_with_audio_apis()
video.available_create_avatar_apis()
video.available_image_lipsync_apis()
video.available_video_lipsync_apis()
video.available_agent_video_apis()
video.available_translate_apis()
video.available_video_resource_apis()
media.available_apis()
webhooks.available_apis()
account.available_apis()
```

Detailed provider matrices live in
[docs/providers.md](https://github.com/reiarthur/easy-ai-clients/blob/main/docs/providers.md).

## Configuration

Credentials are resolved from environment variables at provider-call time.
Configure only the providers your application will call.

```bash
export OPENAI_API_KEY="sk-..."
export DEEPGRAM_API_KEY="..."
```

```powershell
$env:OPENAI_API_KEY = "sk-..."
$env:DEEPGRAM_API_KEY = "..."
```

For local dotenv workflows, load a private file explicitly before using the
library. Keep real secret files outside the repository.

```python
from dotenv import load_dotenv

load_dotenv("path/to/private.env")
```

Reference files:

- [`.env.example`](https://github.com/reiarthur/easy-ai-clients/blob/main/.env.example)
- [docs/configuration.md](https://github.com/reiarthur/easy-ai-clients/blob/main/docs/configuration.md)

## Usage Notes

### Audio

Transcription accepts local paths, supported URLs, bytes, base64 strings, data
URLs, and `pydub.AudioSegment` objects where the selected provider supports
them. `prepare_transcription_audio(...)` can prepare reusable upload payloads
for comparing providers or models.

Deepgram receives one whole prepared payload per `audio.transcribe(...)` call.
Segment long media before calling the library if your workflow needs multiple
provider requests.

### Images

Image inputs can be local file paths, public `http` / `https` URLs, raw base64
strings, or base64 data URLs. For `image.edit`, the public mask convention is
black = editable and white = preserve.

OpenRouter image analysis requires an explicit provider model ID, for example
`image.analyze(..., api="openrouter", model="qwen/qwen3.7-plus")`. The model
value is sent as provided, without local aliases.

### Music

`easy_ai_clients.music` is intentionally narrow. It supports exactly:

```python
("deapi", "elevenlabs", "google", "kie", "runware")
```

`music.generate(...)` validates provider/model support before dispatch. Public
music results exclude raw provider responses, credentials, auth headers,
provider audio URLs, signed URLs, and large audio payloads.

Music duration is normalized per provider/model:

| Provider | Duration behavior |
| --- | --- |
| `deapi` | Clamps numeric `duration` to `10..300` seconds. Missing or invalid values use `60`. |
| `elevenlabs` | Uses native `music_v2` through public keys `eleven_music`, `eleven_music_v2`, and `music_v2`. Clamps valid numeric `duration` to `3..600` seconds and sends `music_length_ms`. Missing or invalid values omit duration. |
| `google` | Clip ignores duration and remains about `30` seconds. Pro clamps valid values to `15..180` seconds and adds target duration guidance to the prompt. |
| `kie` | Uses native `V5_5` through public keys `suno_v5_5` and `V5_5`. Clamps numeric `duration` to `10..360` seconds. Missing or invalid values use `60`. Lyrics are Kie `prompt`; style tags are Kie `style`. |
| `runware` | Clamps numeric `duration` to `30..300` seconds. Missing or invalid values use `60`. |

Style presets contain `style_prompts` in `small`, `medium`, and `large`
variants, plus `voice_presets` with `default_gender` and `small`, `medium`, and
`large` male/female voice-description maps. The router starts with the `large`
style and voice prompts. If provider input limits are exceeded, it retries
progressively smaller preset prompts before raising `music.MusicInputLimitError`.
ElevenLabs uses `style_prompts.large` with `voice_presets.small` by default.

Use `gender="male"`, `gender="female"`, `gender="both"`, or
`voice_description` for prompt-level voice guidance. Over-limit music inputs
raise `music.MusicInputLimitError` with field-specific repair prompts before
generation.

### Video

Video operations support synchronous and asynchronous provider workflows where
the selected provider exposes them. Async video results preserve safe provider
references such as `status_url`, `response_url`, `result_url`, `task_url`, and
`operation_url` when available.

For direct `video.download(..., video_url=...)`, pass `output_path`; omitting it
returns a normalized failure instead of silently returning `None`.

## Return Contracts

Public dispatchers return normalized dictionaries when the operation can
preserve its public result shape.

| Operation Family | Important Result Fields |
| --- | --- |
| `text.generate(...)` | `request_id`, `cost_source`, `cost_usd`, `input_text`, `instruction`, `output_text`, optional `error` |
| `audio.generate(...)` | `cost_usd`, `audio` as `pydub.AudioSegment`, `words`, optional `error` |
| `audio.transcribe(...)` | `text`, `words`, `segments`, `speaker_*`, `provider_metadata`, `request_id`, `cost_usd`, `cost_source`, `cost_is_estimated`, `cost_lookup_error` |
| `image.generate/edit/remix(...)` | `cust_usd`, `cost_usd`, `cost_currency`, `cost_is_estimated`, `cost_source`, `cost_details`, `base64`, `warnings`, `request_id` |
| `image.analyze(...)` | `request_id`, `cost_usd`, `cost_currency`, `cost_is_estimated`, `cost_source`, `cost_details`, `input_text`, `output` |
| `music.generate/status/download(...)` | `provider`, `model`, `model_key`, `status`, `request_id`, `output_path`, `cost_usd`, `cost_currency`, `cost_source`, `cost_is_estimated`, `cost_details`, `metadata` |
| `video` operations | `provider`, `model`, `status`, `request_id`, `video_url`, `output_path`, `cost_usd`, `cost_is_estimated`, `cost_source`, `raw_response`, safe async refs when available |
| `media`, `webhooks`, `account`, video resources | `provider`, `data`, `raw_response`; destructive delete helpers require `confirm=True` |

The image `cust_usd` key is preserved as a legacy alias. New code should prefer
the standardized `cost_usd` metadata.

## Provider Parameters And Costs

Most dispatchers forward provider-native keyword arguments whenever the wrapper
can assemble a request. Documented models and parameters are metadata for
defaults, examples, and cost estimates; they are not a complete local
acceptance list.

The music dispatcher is stricter. It rejects unsupported music models, unknown
styles, removed public kwargs, and public `negative_prompt` usage before
provider dispatch.

Cost values are best-effort normalized USD values. Unknown costs use
`cost_source="unavailable"` with supporting warnings or lookup-error metadata
when available.

Fal.ai image generation, editing, and remixing use the official fal.ai pricing
estimate API when `FAL_KEY` is available. The returned value is marked with
`cost_source="fal_pricing_estimate_api"` and `cost_is_estimated=True`, because
it is an estimate rather than post-run billing reconciliation.

## Errors

Public operations return normalized failure dictionaries when possible. Error
messages are sanitized to avoid leaking credentials, authorization headers, or
signed URLs.

Some helper functions and private adapter paths can still raise standard Python
exceptions such as `ValueError`, `RuntimeError`, `OSError`, `requests`
exceptions, or `httpx` exceptions.

See
[docs/errors.md](https://github.com/reiarthur/easy-ai-clients/blob/main/docs/errors.md)
for details.

## Development And Validation

Install development dependencies:

```bash
pip install -e ".[dev]"
```

Safe local validation:

```bash
python -m compileall -q src tests
python -m pytest -m "not live"
python -m ruff check src tests
rm -rf dist build
python -m build
python -m twine check dist/*
```

Live tests are gated with explicit environment variables and are marked with
`pytest.mark.live`. Keep those gates unset during ordinary local validation.

## Documentation

- [Usage patterns](https://github.com/reiarthur/easy-ai-clients/blob/main/docs/usage.md)
- [Operation examples](https://github.com/reiarthur/easy-ai-clients/blob/main/docs/operation_examples.md)
- [Provider matrix](https://github.com/reiarthur/easy-ai-clients/blob/main/docs/providers.md)
- [Configuration](https://github.com/reiarthur/easy-ai-clients/blob/main/docs/configuration.md)
- [Error handling](https://github.com/reiarthur/easy-ai-clients/blob/main/docs/errors.md)
- [Provider gap audit](https://github.com/reiarthur/easy-ai-clients/blob/main/docs/provider_gap_audit.md)
- [Project context for future agents](https://github.com/reiarthur/easy-ai-clients/blob/main/docs/PROJECT_CONTEXT.md)
- [Changelog](https://github.com/reiarthur/easy-ai-clients/blob/main/CHANGELOG.md)
- [Contributing](https://github.com/reiarthur/easy-ai-clients/blob/main/CONTRIBUTING.md)

## License

MIT. See
[LICENSE](https://github.com/reiarthur/easy-ai-clients/blob/main/LICENSE).
