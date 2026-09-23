# Project Context

## Overview

`easy-ai-clients` is a Python library that exposes public dispatcher modules for
text, audio, image, music, video, media, webhooks, and account helper
operations across multiple AI providers.

This file is the project-specific context map for future Codex sessions. It is
not a README replacement and it is not proof that validation passed in the
current task. It was refreshed from static inspection of the working tree.

## User-Provided Project Description

The user wants project-specific Codex context to live at
`docs/PROJECT_CONTEXT.md`, not at the repository root. The README and release
handoff prompt should stay in English, while user-facing chat responses should
be in Brazilian Portuguese.

The user also stated that a private dotenv file for this project now lives
outside the repository at `../.env-easy-ai-clients`. Secret values were not
inspected.

## Purpose And Domain

The package normalizes common multimodal AI client workflows behind stable
Python dispatchers:

- Text generation through `easy_ai_clients.text`.
- Speech synthesis, transcription, and voice helpers through
  `easy_ai_clients.audio`.
- Image generation, editing, remixing, and analysis through
  `easy_ai_clients.image`.
- Lyric-based music generation through `easy_ai_clients.music`.
- Video generation and provider video resources through `easy_ai_clients.video`.
- Provider asset, webhook, and account helpers through
  `easy_ai_clients.media`, `easy_ai_clients.webhooks`, and
  `easy_ai_clients.account`.

The public contract is the dispatcher layer. Provider modules under private
`_apis` packages are implementation details.

## Stack And Runtime

| Area | Verified Details |
| --- | --- |
| Language | Python |
| Package layout | `src/` layout with package code under `src/easy_ai_clients` |
| Python support | `pyproject.toml` declares `requires-python = ">=3.11"` and classifiers for Python 3.11, 3.12, and 3.13 |
| Build backend | `hatchling` |
| Runtime dependencies | `requests`, `httpx`, `Pillow`, `pydub`, `imageio-ffmpeg`, `python-dotenv`, `audioop-lts` on Python 3.13+ |
| Dev dependencies | `build`, `pytest`, `ruff`, `twine` via the `dev` extra |
| Test framework | `pytest`, configured in `pyproject.toml` |
| Linting | `ruff`, target `py311`, line length `100`, lint rules `E`, `F`, `I`, `B`, `UP` |
| Type marker | `src/easy_ai_clients/py.typed` |

## Python Environment

No repository lock file or named Conda environment was found. The documented
development setup uses:

```bash
python -m venv .venv
pip install -e ".[dev]"
```

The package version is defined in both `pyproject.toml` and
`src/easy_ai_clients/__init__.py`. Both currently show `0.19.0`.

## Repository Structure Summary

| Path | Role |
| --- | --- |
| `src/easy_ai_clients/` | Runtime package and public dispatcher modules |
| `docs/` | User documentation, provider matrix, operation docs, and this project context |
| `tests/` | Unit, contract, documentation coverage, and gated live-test modules |
| `.env.example` | Public environment-variable template with empty credentials and `MUSIC_API_TIMEOUT=60` |
| `.gitignore` | Local environment, generated artifact, cache, and local AI tooling exclusions |
| `pyproject.toml` | Package metadata, dependencies, build config, pytest config, and Ruff config |
| `README.md` | Public package overview and quick usage |
| `CONTRIBUTING.md` | Development, validation, build, and publish workflow |
| `CHANGELOG.md` | Release history |

## File And Responsibility Map

| Path | Responsibility | Related Files |
| --- | --- | --- |
| `src/easy_ai_clients/__init__.py` | Top-level package exports and `__version__` | `tests/test_imports.py`, `pyproject.toml` |
| `src/easy_ai_clients/text/` | Text generation dispatcher, provider adapters, model listing, and cost update helpers | `docs/text/`, `docs/providers.md` |
| `src/easy_ai_clients/audio/` | Speech synthesis, transcription, transcription preprocessing, cost update, and voice helpers | `docs/audio/`, `tests/test_transcription_contract.py` |
| `src/easy_ai_clients/image/` | Image generation, editing, remixing, analysis, image input handling, and cost helpers | `docs/image/`, `tests/test_dispatchers.py` |
| `src/easy_ai_clients/music/` | Narrow validated music dispatcher, provider adapters, model registry, options catalog, style presets, and lyrics prompt builder | `docs/music/`, `tests/test_music_*.py` |
| `src/easy_ai_clients/video/` | Video operation dispatchers, async helpers, provider adapters, HeyGen resources, Replicate avatar-video support, and video cost helpers | `docs/video/`, `tests/test_video_contract.py`, `tests/test_video_async_refs.py` |
| `src/easy_ai_clients/_heygen.py` | Shared HeyGen auth, JSON request, asset, polling, status, and download helpers | `src/easy_ai_clients/video/`, `src/easy_ai_clients/media/`, `src/easy_ai_clients/webhooks/`, `src/easy_ai_clients/account/` |
| `src/easy_ai_clients/_falai_pricing.py` | Shared fal.ai pricing estimate helper for image and video adapters | `src/easy_ai_clients/image/_common/falai_pricing.py`, `src/easy_ai_clients/video/_falai_pricing.py`, `tests/test_image_falai_cost.py`, `tests/test_video_contract.py` |
| `src/easy_ai_clients/media/` | Provider asset upload/delete dispatcher; currently HeyGen-backed | `docs/media/heygen.md` |
| `src/easy_ai_clients/webhooks/` | Provider webhook endpoint and event dispatcher; currently HeyGen-backed | `docs/webhooks/heygen.md` |
| `src/easy_ai_clients/account/` | Provider account/current-user dispatcher; currently HeyGen-backed | `docs/account/heygen.md` |
| `tests/test_imports.py` | Top-level imports, module exports, provider importability, and version consistency | `src/easy_ai_clients/__init__.py`, `pyproject.toml` |
| `tests/test_documentation_coverage.py` | Provider docs coverage and environment-template documentation checks | `docs/providers.md`, `.env.example` |
| `tests/test_dispatchers.py` | Dispatcher routing and non-network behavior for text/audio/image/video paths | `src/easy_ai_clients/*` |
| `tests/test_music_dispatcher.py` | Public music API, validation, routing, status/download, and sanitization behavior | `src/easy_ai_clients/music/` |
| `tests/test_music_provider_contract.py` | Music provider payloads, env loading, timeout, cost, and sanitizer behavior | `src/easy_ai_clients/music/_apis/`, `src/easy_ai_clients/music/_common.py` |
| `tests/test_music_generation_options.py` | Local music generation option metadata contract | `src/easy_ai_clients/music/_generation_options.py` |
| `tests/test_music_style_adapter.py` | Style preset schema, filters, deep copies, and anti-imitation fields | `src/easy_ai_clients/music/styles/` |
| `tests/test_music_lyrics_prompt.py` | Lyrics prompt builder validation and output keys | `src/easy_ai_clients/music/_lyrics_prompt.py` |
| `tests/test_live_*.py` | Gated live tests that require explicit env gates before provider calls | `CONTRIBUTING.md`, `docs/configuration.md` |

## Main Execution Flows

### Public Import Flow

`easy_ai_clients.__init__` imports and exposes `text`, `audio`, `image`,
`music`, `video`, `media`, `webhooks`, `account`, and `__version__`.

### Dispatcher Flow

Public functions accept an explicit `api=` keyword and route to operation-specific
provider modules. Unknown or missing providers are validated by the relevant
dispatcher before provider-specific calls where the operation supports that
preflight.

### Image Analyze Flow

`image.analyze(..., api="openrouter")` requires an explicit OpenRouter model ID.
The wrapper sends the `model` value exactly as provided, does not use local
aliases, forwards provider kwargs into the OpenRouter request body, and can
refresh provider-reported costs through
`image.update_cost("analyze", result, api="openrouter")`.

### Fal.ai Image Cost Flow

`image.generate`, `image.edit`, and `image.remix` with `api="falai"` call the
official fal.ai `POST /models/pricing/estimate` platform endpoint before the
queue generation call. The returned cost is saved as
`cost_source="fal_pricing_estimate_api"` with `cost_is_estimated=True`.

`billing_unit_quantity` and `unit_quantity` are consumed by the wrapper for the
pricing estimate and are not forwarded to the model payload. If neither is
provided, image operations estimate one output image by default, or `num_images`
when supplied. The queue result itself is not treated as final billing
reconciliation; request ids remain available for future usage/billing-event
lookups outside the current helper.

### Music Flow

`music.generate(lyrics, model=None, *, api, style=None, prompt=None, **kwargs)`
validates a narrow provider/model matrix, resolves standardized model keys to
native provider model IDs, applies exact style presets when requested, rejects
removed public kwargs including public `negative_prompt`, normalizes duration
per provider/model, checks provider input limits, dispatches to
`music._apis.<provider>`, and returns a safe normalized public dictionary.

Music style presets expose `style_prompts.small`, `style_prompts.medium`, and
`style_prompts.large` for musical direction. They also expose
`voice_presets.default_gender` plus `voice_presets.small`,
`voice_presets.medium`, and `voice_presets.large`, each with `male` and
`female` voice descriptions. `voice_presets.large` preserves the curated voice
texts.

When a style preset is used, the router starts with large style and voice
prompts. On `MusicInputLimitError`, it retries `large` style with `medium`
voice, then `medium` style with `medium` voice, then `medium` style with
`small` voice, then `small` style with `small` voice. If all attempts exceed
provider limits, it retries `large` + `large` so the normal repair data is
raised.

ElevenLabs preset generation uses `style_prompts.large` with
`voice_presets.small` by default and dispatches public keys `eleven_music`,
`eleven_music_v2`, and `music_v2` to native `music_v2`. Explicit `music_v1` is
rejected.

Music input overages raise `music.MusicInputLimitError` before generation. The
exception exposes JSON-serializable field repair data and does not change the
successful `music.generate` result schema.

Current music duration behavior:

| Provider | Duration behavior |
| --- | --- |
| `deapi` | `10..300` seconds, default `60` when missing or invalid, sent as `duration`. |
| `elevenlabs` | `3..600` seconds when valid, sent as `music_length_ms`; missing or invalid values omit duration. Native model is `music_v2`. |
| `google` | Clip ignores duration and stays about `30` seconds; Pro uses valid `15..180` seconds as prompt text. |
| `kie` | `10..360` seconds, default `60` when missing or invalid, sent as `duration` on native `V5_5`. Custom-mode `style` is compact tags, lyrics go in Kie `prompt`. |
| `runware` | `30..300` seconds, default `60` when missing or invalid, sent as `duration`. |

Current music input limits are `3000` characters for deAPI prompt/lyrics,
`4100` characters for the final ElevenLabs prompt with lyrics, `131072` Google
tokens via `countTokens`, `1000` / `5000` characters for Kie style / lyrics,
and `3000` characters for Runware prompt/lyrics.

Local music helpers `get_generation_options`, `get_style_presets`, and
`build_lyrics_prompt` do not call generation provider APIs. When `style` is a
valid preset ID, `build_lyrics_prompt` embeds the preset `style_prompts.large`
text as lyric-writing guidance. With `api="elevenlabs"`, it also uses
`voice_presets.small`, asks for short singable lines, and avoids vocal-role
tags such as `[Male Lead]`, `[Female Lead]`, and `[Duet]`. Google Lyria
generation runs `countTokens` on the final `contents` payload before
`generateContent`.

### Video Flow

`video.generate` aliases text-to-video. The video package also exposes
operation-specific dispatchers for image-to-video, video-to-video,
motion-control, avatar-video, video-with-audio, avatar creation, image/video
lip-sync, HeyGen Video Agent, translation, and HeyGen resource helpers.

Async helpers preserve safe provider references such as `status_url`,
`response_url`, `result_url`, `task_url`, and `operation_url` when available.

## Main Components

| Component | Public Surface |
| --- | --- |
| `easy_ai_clients.text` | `generate`, `list_models`, `update_cost`, `available_apis` |
| `easy_ai_clients.audio` | `generate`, `prepare_transcription_audio`, `transcribe`, voice helpers, `update_cost`, provider discovery helpers |
| `easy_ai_clients.image` | `generate`, `edit`, `remix`, `analyze`, `update_cost`, provider discovery helpers |
| `easy_ai_clients.music` | `generate`, `available_apis`, `get_status`, `download_result`, `get_generation_options`, `get_style_presets`, `build_lyrics_prompt` |
| `easy_ai_clients.video` | Generation operations, HeyGen resource helpers, async helpers, provider discovery helpers |
| `easy_ai_clients.media` | `upload_asset`, `delete_asset`, `available_apis` |
| `easy_ai_clients.webhooks` | Endpoint, event, event-type, and secret-rotation helpers |
| `easy_ai_clients.account` | `get_current_user`, `available_apis` |

## API Endpoints And Contracts

This repository does not expose an HTTP server. Its API is the Python package
surface documented in `README.md`, `docs/usage.md`, `docs/operation_examples.md`,
and `docs/providers.md`.

Important return-contract notes:

- Text, image, audio, video, and helper failures generally return normalized
  dictionaries when the dispatcher can preserve the public operation shape.
- `image.generate`, `image.edit`, and `image.remix` keep the legacy `cust_usd`
  key while also filling standardized cost metadata.
- `music.generate`, `music.get_status`, and `music.download_result` keep only
  the safe public music schema and must not expose raw provider responses,
  credentials, auth headers, provider audio URLs, signed URLs, or large audio
  payloads.
- HeyGen destructive delete helpers require explicit `confirm=True`.

## CLI Commands And Scripts

No console script entrypoint or application CLI was found in package metadata.
The documented commands are development, validation, build, and release commands:

```bash
pytest
pytest tests/test_imports.py -v
ruff check src tests
python -m build
twine check dist/*
```

## Jobs, Workers, And Automations

No standalone worker, queue, scheduler, cron job, or hosted service entrypoint
was found. Some provider adapters perform bounded polling, retry loops, async
provider-job status checks, or background model catalog warm-up inside library
calls.

## Configuration And Environment Variables

Credentials are read from environment variables at provider-call time.
`os.environ` is authoritative. Some text, image, music, and HeyGen helper paths
attempt to load `.env` from the current working directory, but application code
should load private dotenv files explicitly when it depends on dotenv behavior.

For this repository's gated live tests, `EASY_AI_CLIENTS_ENV_FILE` can point to
a private dotenv file. If it is unset, current live-test helpers look for
`../.env-easy-ai-clients`. Secret values were not inspected.

| Name | Purpose |
| --- | --- |
| `ANTHROPIC_API_KEY` | Anthropic text and image analysis |
| `BFL_API_KEY` | Black Forest Labs image operations |
| `COHERE_API_KEY` | Cohere text generation |
| `DEAPI_API_KEY` | deAPI music generation |
| `DEEPGRAM_API_KEY` | Deepgram transcription, speech, and cost lookup paths |
| `DEEPGRAM_PROJECT_ID` | Optional Deepgram project filter for transcription cost lookup |
| `DEEPINFRA_API_KEY` | DeepInfra text, audio, voices, and image operations |
| `DEEPSEEK_API_KEY` | DeepSeek text generation |
| `ELEVENLABS_API_KEY` | ElevenLabs audio, voices, transcription, and music generation |
| `FAL_KEY` | Fal.ai text, audio transcription, image, and video operations |
| `FIREWORKS_API_KEY` | Fireworks text, audio transcription, and image operations |
| `GOOGLE_API_KEY` | Google/Gemini text, audio, image, music, and video operations |
| `GROQ_API_KEY` | Groq text, audio, and image analysis |
| `HEDRA_API_KEY` | Hedra video operations |
| `HEYGEN_KEY` | Preferred HeyGen v3 credential |
| `HEYGEN_API_KEY` | Compatibility alias for `HEYGEN_KEY` |
| `HEYGEN_API_BASE` | Optional HeyGen API base URL override |
| `HUGGINGFACE_API_KEY` | Hugging Face text, audio transcription, image, and video operations |
| `MISTRAL_API_KEY` | Mistral text, audio, voices, and image analysis |
| `MUSIC_API_TIMEOUT` | Optional music-provider HTTP timeout override; `.env.example` uses `60` |
| `OPENAI_API_KEY` | OpenAI text, audio, and image operations |
| `OPENROUTER_API_KEY` | OpenRouter text, audio, image, video, and catalog/cost lookup paths |
| `REPLICATE_API_TOKEN` | Replicate avatar-video predictions |
| `RUNWARE_API_KEY` | Runware music generation |
| `RUNWAYML_API_SECRET` | Runway audio, image, video, avatar, and upload operations |
| `SPEECHMATICS_API_KEY` | Speechmatics transcription |
| `STABILITY_API_KEY` | Stability image and Stable Audio operations |
| `TOGETHER_API_KEY` | Together text, audio, image, and video operations |
| `XAI_API_KEY` | xAI text, audio, image, and video operations |

## Data, Schemas, And Persistence

No database, ORM, migration system, queue backend, or persistent storage layer
was found. Runtime data is passed through dictionaries, provider JSON payloads,
local or remote media inputs, base64 strings, and `pydub.AudioSegment` objects.

Audio transcription preprocessing supports local paths, supported URLs, bytes,
base64 strings, data URLs, `pydub.AudioSegment` objects, and reusable
`PreparedTranscriptionAudio` objects where the selected adapter supports them.

## External Integrations

The package integrates with third-party provider APIs over HTTP through
`requests` and `httpx`. Documented providers include OpenAI, Anthropic, Google,
Cohere, Groq, Mistral, DeepSeek, DeepInfra, Hugging Face, OpenRouter, Together,
Fireworks, Fal.ai, Runway, Runware, deAPI, HeyGen, xAI, ElevenLabs, Deepgram,
Speechmatics, Stability AI, and Black Forest Labs.

The video avatar-video surface includes the Replicate
`prunaai/p-video-avatar` prediction adapter through `api="replicate"`.

Provider integrations should not be exercised in ordinary unit tests. Live tests
are gated and require explicit environment variables.

## Frontend Or UI

No frontend application, UI framework, template engine, or browser runtime was
found.

## Tests And Validation

Validation was not executed during this context refresh by rule of the
`project-context-generator` skill. Use the commands below as documented local
validation paths, not as proof of current pass status:

```bash
python -m compileall -q src tests
python -m pytest tests/test_imports.py -q
python -m pytest tests/test_documentation_coverage.py -q
python -m pytest tests/test_image_falai_cost.py
python -m pytest
python -m ruff check src tests
python -m build
python -m twine check dist/*
```

Before running safe local tests, clear live-test gates in the current shell when
appropriate:

```powershell
Remove-Item Env:EASY_AI_CLIENTS_LIVE_VIDEO,Env:EASY_AI_CLIENTS_LIVE_HEYGEN,Env:EASY_AI_CLIENTS_LIVE_HEYGEN_PAID_VIDEO,Env:EASY_AI_CLIENTS_LIVE_TRANSCRIBE,Env:EASY_AI_CLIENTS_LIVE_TRANSCRIBE_MULTILINGUAL,Env:EASY_AI_CLIENTS_LIVE_MUSIC -ErrorAction SilentlyContinue
```

The test suite includes gated live modules marked with `pytest.mark.live`.
Default local validation should not call paid provider APIs.

For the 0.13.1 fal.ai image cost update, local validation used
`python -m compileall -q src tests Video_Musical\gerar_artefatos.py`,
`python -m ruff check src tests Video_Musical\gerar_artefatos.py`, and
`python -m pytest -m "not live"`. A paid fal.ai image smoke test was also run
against local `src` code and returned `cost_source="fal_pricing_estimate_api"`
with a non-zero estimated USD cost.

`tests/test_live_music.py` is the gated live music smoke test. When
`EASY_AI_CLIENTS_LIVE_MUSIC=1` and `EASY_AI_CLIENTS_LIVE_MUSIC_API` are set, it
loads credentials through `EASY_AI_CLIENTS_ENV_FILE` when provided, submits one
short music generation, polls with `music.get_status`, downloads with
`music.download_result`, verifies a non-empty output file, and removes the
generated file under the current working directory's `outputs/music/temp/`.
When `EASY_AI_CLIENTS_LIVE_MUSIC_MODEL` is set, the test chooses the shortest
practical duration for that implemented model.

## Build, Deployment, And Operations

The project builds Python distributions with `hatchling`:

```bash
python -m build
twine check dist/*
```

Wheel builds include `src/easy_ai_clients` plus `docs`, excluding generated
live benchmark reports. Source distributions include `.env.example`, `src`,
`docs`, `tests`, `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `LICENSE`, and
`pyproject.toml`, excluding the large multilingual live-test audio archive.

Publishing is documented in `CONTRIBUTING.md` with `twine upload dist/*` and a
PyPI project token. No Dockerfile, Compose config, deployment manifest, or
runtime process manager was found.

## Documentation Map

| Path | Use |
| --- | --- |
| `README.md` | Public package overview, install, quickstart, and main docs links |
| `docs/usage.md` | Detailed usage patterns and public result shapes |
| `docs/operation_examples.md` | Copyable examples for public operation categories |
| `docs/providers.md` | Provider matrix and links to per-provider docs |
| `docs/configuration.md` | Environment variables, secret handling, and credential behavior |
| `docs/errors.md` | Public error and failure-shape behavior |
| `docs/provider_gap_audit.md` | Provider gap and coverage audit |
| `docs/music/` | Narrow validated music provider docs only |
| `docs/PROJECT_CONTEXT.md` | Project-specific context map for future Codex sessions |

## Development Conventions

- Public imports should use the dispatcher modules exposed from
  `easy_ai_clients`.
- Private `_apis` modules are implementation details.
- Adding or removing provider support usually requires coordinated changes in
  runtime code, `docs/providers.md`, provider docs, `.env.example`, tests, and
  `CHANGELOG.md`.
- Public docs are written in English.
- Live provider tests must stay gated and credential-free by default.
- Do not restore the old broad multi-operation music tree unless the user
  explicitly changes the current contract.
- Music style presets use `style_prompts` and `voice_presets` data and no
  longer expose `style_prompt`, `voice_preset`, `default_vocal`,
  `duration_seconds`, `generation_controls`, or `negative_traits`.

## Technical Debt And Attention Points

- There is no lock file.
- Credential-loading behavior is intentionally uneven across older helper paths;
  application code should set environment variables or load a private dotenv
  file explicitly.
- `image.generate`, `image.edit`, and `image.remix` preserve `cust_usd` as a
  legacy alias.
- Fal.ai image costs are official pre-run estimates, not final billing-event
  reconciliation.
- Unknown costs are represented explicitly with `cost_source="unavailable"` and
  supporting warning or lookup metadata when available.
- Live tests can call paid provider APIs only when explicit gates are set.

## Quick Reference For Future Agents

| Need | Start Here |
| --- | --- |
| Public API contract | `README.md`, `docs/usage.md`, `src/easy_ai_clients/__init__.py` |
| Provider matrix | `docs/providers.md` |
| Configuration and credentials | `docs/configuration.md`, `.env.example` |
| Music runtime | `src/easy_ai_clients/music/`, `docs/music/`, `tests/test_music_*.py` |
| Text/audio/image dispatchers | `src/easy_ai_clients/text/`, `src/easy_ai_clients/audio/`, `src/easy_ai_clients/image/` |
| Video and HeyGen helpers | `src/easy_ai_clients/video/`, `src/easy_ai_clients/_heygen.py`, `tests/test_video_contract.py` |
| Packaging and release | `pyproject.toml`, `CONTRIBUTING.md`, `CHANGELOG.md` |
| Documentation coverage | `tests/test_documentation_coverage.py` |
| Final release validation | Safe commands in `Tests And Validation` |

## Uncertainties And Verification Notes

- Runtime behavior was not executed during this context refresh.
- Secret values in `.env`, `.env.*`, and `../.env-easy-ai-clients` were not
  inspected.
- Provider API availability, pricing, and model catalogs can change; verify
  against official provider documentation before changing documented provider
  metadata.

## Agent Notes

- Read this file first for orientation, then inspect task-relevant source files
  before editing.
- Treat the current working tree as the source of truth over this context when
  there is any mismatch.
