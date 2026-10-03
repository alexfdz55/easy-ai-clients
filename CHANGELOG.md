# Changelog

All notable changes to **easy-ai-clients** are documented in this file.
The project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.21.0 - 2026-10-02

### Added

- Inline style presets: `style` accepts a full preset dictionary with the
  schema of the files in `music/styles/`, besides a predefined name, in
  `music.generate`, `music.build_lyrics_prompt` and the request builders.
  Callers that keep their own style catalog no longer need a library
  release per style. The generation reports the preset `id` as `style`.
- `music.validate_style_preset(style_preset)` checks a preset before it is
  stored or used and returns a copy. It raises `ValueError` naming every
  invalid field (`id`, `tempo_bpm`, `key_scale`, `time_signature`,
  `energy`, `default_language`, the three `style_prompts` sizes and the
  `voice_presets` of each size and gender).
- Eight music style presets for narrative songs: `ballad`, `singer_songwriter`,
  `corrido`, `dark_folk`, `bachata`, `musical_theatre`, `cinematic_epic` and
  `lullaby`. Same shape and limits as the other presets; the catalog goes from
  30 to 38 styles.
- Three more song languages: `it-IT`, `pl-PL` and `nl-NL` are accepted as
  `language` and as a preset's `default_language`. The style prompt names the
  language (`Italian lyrics`, `Polish vocals`) and ACE-Step models receive
  `it`, `pl` or `nl` as `vocal_language`. Before, a caller had to omit the
  language for those songs and the prompt named the preset's default one.
- Everything released as 0.19.1 to 0.19.4, which 0.20.0 did not include because
  the two lines of work were released from different branches: Eleven v4 and
  fal.ai speech with the failure reason, the speech cost and language fixes,
  HeyGen Video 1 through OpenRouter and `clamp_duration`.

### Fixed

- The eight narrative presets declared `default_language` as `en` or `es`,
  which the language check rejects: generating with one of them and no
  `language` raised `ValueError`. They now use `en-US` and `es-ES`.

## 0.20.0 - 2026-09-29

### Added

- Kie Suno `V6` (`suno_v6`) through Kie's jobs endpoint
  (`/api/v1/jobs/createTask` and `/api/v1/jobs/recordInfo`, snake_case input).
  `duration` is a real parameter on V6 (measured: 30 s requested gave
  28.8–30.4 s). The takes are read from `resultJson`; `metadata` adds
  `take_audio_ids` and `take_durations`, and the cost comes from the task's
  `creditsConsumed` (`cost_source: kie_credits_consumed`).
- Personas: `music.create_persona(api="kie", ...)` creates a persona from one
  take (free on Kie), and V6 generations accept `persona_id` with
  `persona_model` (`voice_persona` or `style_persona`) to keep the same voice.
  V5_5 rejects personas with `ValueError`.
## 0.19.7 - 2026-10-03

### Changed

- Eleven v4 and Eleven v4 Turbo are split at 4,000 characters instead of 4,200: a
  1,000-character margin under their limit, a little below the 4,178 measured in one
  request, to stay on the safe side.

## 0.19.6 - 2026-10-03

### Changed

- Eleven v4 and Eleven v4 Turbo are split into several requests at 4,200 characters
  instead of 2,200. The generic rule (`compute_operational_char_limit`) cut every model
  with a 5,000-character limit at 2,200, so a narration of two and a half minutes was
  already recorded in two requests, with a join in the middle. A model can now declare
  its own `operational_char_limit`; these two use their limit minus the same
  800-character margin the generic rule keeps. Measured on v4 Turbo: 4,178 characters in
  one request took 55 s, against a 120 s request timeout, with complete word timings and
  the same pace as the two-request recording. Every other model is cut where it was.

## 0.19.5 - 2026-10-03

### Fixed

- The words of a chunked narration no longer overlap at the join between two chunks. A
  long text is synthesized in several requests and the words of each chunk are shifted by
  the duration of the audio before them. ElevenLabs sometimes reports the last word of a
  chunk ending slightly after that chunk's audio really ends (2 ms on Multilingual v2,
  80 ms on Eleven v4 Turbo): the first word of the next chunk then started before the
  previous one had finished, and callers that require non-overlapping words rejected the
  whole narration. A word now never outlasts the audio of its own chunk.

## 0.19.4 - 2026-10-02

### Fixed

- Speech no longer invents English. `audio.generate` defaulted `language_code` to
  `"en"`, and ElevenLabs and fal.ai forwarded it. The field enforces a language for the
  model and for text normalization: Eleven v4 Turbo read the digits of a Portuguese
  script in English ("Em 1959" as "nineteen fifty-nine"). Multilingual v2 ignores the
  field, so it had gone unnoticed. Now no language is sent unless the caller names one,
  and the model detects it from the text. The other speech providers keep their own
  default.

## 0.19.3 - 2026-10-02

### Added

- HeyGen Video 1 (`heygen/heygen-video-1`) on the OpenRouter video route: 5 to 15
  seconds, 480p or 768p, first frame. Its card declares no `generate_audio` and no
  passthrough parameters, and OpenRouter answers 400 to a parameter the model does not
  support, so its payload carries only what the model declares. A documented model can
  now say `accepts_generate_audio` and `passthrough_parameters`; the Seedance models
  keep sending everything, as before.
- `clamp_duration` on the OpenRouter video route. Opt-in: the duration is rounded up to a
  whole second and brought inside the model's documented range, instead of truncated and
  rejected. For callers that ask for the length of a scene rather than a provider duration.

## 0.19.2 - 2026-10-02

### Fixed

- ElevenLabs TTS cost. It was computed from the `character-cost` response header as if it
  were a character count. The header is the cost in account credits, and a credit is one
  character only on the older models: an Eleven v4 Turbo narration of 760 characters
  reports 51 credits, so its cost came out as 0.002 USD instead of 0.03 at list price.
  The cost is now the characters of the text times the list price; `cost_details`
  carries `characters` and `provider_credits`. The Flash and Turbo v2 families were
  under-reported the same way (half a credit per character).

## 0.19.1 - 2026-10-02

Released from `main`. It does not include `0.20.0` (Suno V6 on Kie), which lives on
its own branch.

### Added

- ElevenLabs TTS models `eleven_v4` and `eleven_v4_turbo`, with their
  per-request limit and list price. They used to run as unknown models: cost 0
  and a warning.
- `audio.generate(api="falai")`: ElevenLabs voices through fal.ai's queue, with
  character timings turned into the same `words` as the direct adapter. It takes
  ElevenLabs voice ids, so the same model and voice can be asked through a
  second account.
- Failed calls say why. `build_error` adds `http_status`, `provider_code`,
  `provider_message` and `category` when the failure was an HTTP response,
  reading them from the `__cause__` chain (`http_failure_of`). `category` is
  `"account"` for 401, 402 and 403: the provider is turning the account away,
  not the request. Errors without an HTTP response keep their exact keys.

### Fixed

- A failed ElevenLabs speech chunk lost the HTTP status and the provider's body
  behind `Failed to synthesize ElevenLabs chunk N`: an unpaid invoice (401
  `payment_issue`) was indistinguishable from any other failure. The message
  now ends with the cause.
- ElevenLabs TTS list prices: 0.08 USD per 1,000 characters for
  `eleven_multilingual_v2` and `eleven_v3` (was 0.10) and 0.04 for the Flash
  and Turbo v2 families (was 0.05).

## 0.19.0 - 2026-09-23

### Added

- OpenAI text prices for `gpt-6-luna` and `gpt-6-sol` (standard, batch and
  flex). The table matches models by substring, so without them direct OpenAI
  text calls to GPT-6 reported a cost of 0.

## 0.18.0 - 2026-09-18

### Added

- Failed calls keep the provider request id. `build_error` and `attach_error`
  add `request_id` when it is known (explicitly, from the exception, or from
  the result), and `request_id_of(exc)` reads it from a `request_id` attribute
  or from response headers (`x-fal-request-id`, `x-request-id`, `request-id`)
  walking the `__cause__` chain. Errors without an id keep their exact keys.
- Video: `ProviderJobError` and `ProviderJobTimeout` (subclasses of
  `RuntimeError` and `TimeoutError`, same messages as before) carry
  `request_id` and `status_code`.
- ElevenLabs TTS results expose `request_id` and `request_ids` (one per
  chunk). Kie failures carry the `taskId` as `exc.request_id`.

### Fixed

- fal.ai image jobs that fail after the submit (an HTTP error on status or
  response) now return the submit `request_id` instead of an empty string.
  `ProviderResponseError` keeps the response headers and the request id.

## 0.17.0 - 2026-09-14

### Added

- Added OpenRouter Seedance video adapters behind `api="openrouter"` for
  `video.text_to_video` and `video.image_to_video` (first frame and
  first-plus-last frame), plus image/video/audio `input_references`. Auth uses
  `OPENROUTER_API_KEY` against `POST/GET /api/v1/videos`. Completed jobs read
  `usage.cost` as `cost_source="openrouter_video_usage"`.

## 0.16.0 - 2026-09-11

### Added

- Added `style_notes` to music generation: free text that the style adapter
  appends to the rendered style prompt (or to a caller prompt) and consumes
  before provider dispatch, so every music provider accepts it.
- Added `negative_tags` for Kie/Suno (`api="kie"`), sent as `negativeTags`
  (text or a list of strings).
- Added LTX 2.3 audio-to-video to the fal.ai avatar adapter (`video_size` by
  resolution and format, `match_audio_length`, price per resolution-second).
- fal.ai image results now price the billed quantity from
  `x-fal-billable-units` with the official pricing API
  (`cost_source="fal_billable_units"`, `cost_is_estimated=False`). Without the
  header, or with the pricing API down, the previous estimate is kept.

### Changed

- Kie/Suno does not accept `duration`: it travels as a hint inside `style` and
  is reported in `cost_details`. Kie is retried once before the fallback.

### Fixed

- `alternate_audio_url` is no longer redacted in the public music dictionary,
  so callers can download Kie's second take before it expires.
- The reggae preset no longer says "skank", which Suno rejects as an artist
  name. Kie failure messages now lead with `errorCode` and `errorMessage`.

## 0.15.0 - 2026-09-02

### Added

- Added Kie.ai Suno music generation behind `api="kie"` for native model
  `V5_5` (`suno_v5_5`). Custom mode sends lyrics as `prompt` and compact
  preset tags as `style`, polls `/generate/record-info` until `SUCCESS`, and
  downloads the first of two takes. Auth uses `KIE_API_KEY`.

## 0.14.0 - 2026-09-01

### Added

- Added BytePlus ModelArk Seedance 2.x video adapters behind `api="byteplus"`
  for `video.text_to_video`, `video.image_to_video` (first frame and
  first-plus-last frame), multimodal image/video/audio refs, and
  `video.video_to_video` edit/extend. Auth uses `ARK_API_KEY` against
  `POST/GET /contents/generations/tasks`.

## 0.13.1 - 2026-06-28

### Added

- Added fal.ai image cost metadata for `image.generate`, `image.edit`, and
  `image.remix` using the official pricing estimate API. Results are marked
  with `cost_source="fal_pricing_estimate_api"` and
  `cost_is_estimated=True`.

### Changed

- Centralized fal.ai unit-price estimation logic so image and video adapters
  share the same pricing estimate contract.

## 0.13.0 - 2026-06-26

### Added

- Added adaptive music preset prompt sizing with `style_prompts` variants and
  `voice_presets` maps containing `default_gender` plus sized male/female
  variants, so preset-based generation can retry smaller prompt text before
  raising `MusicInputLimitError`.
- Added OpenRouter image analysis documentation for 8 validated vision models,
  including pricing, validated parameters, and paid validation date.

### Changed

- Changed music style preset metadata from singular `style_prompt` and
  `voice_preset` fields to sized `style_prompts` and `voice_presets` maps.
- Changed ElevenLabs music generation to route `eleven_music`,
  `eleven_music_v2`, and `music_v2` to native `music_v2`, use internal
  `output_format=auto`, and use concise preset voice guidance for direct music
  prompts.
- Changed `image.analyze(..., api="openrouter")` to require explicit
  OpenRouter model IDs and forward model/kwargs without aliases.

### Fixed

- Hardened ElevenLabs music prompt assembly with language-neutral diction,
  diacritic, section-tag, pacing, and anti-artifact guidance while preserving
  the public `music.generate` success schema.
- Fixed OpenRouter image analysis cost refresh through
  `image.update_cost("analyze", ..., api="openrouter")` and provider-reported
  cost fields.

## 0.12.0 - 2026-06-24

### Added

- Added approved image-plus-audio avatar video targets for fal.ai OmniHuman,
  fal.ai VEED Fabric, Hedra Avatar, HeyGen Photo Avatar, and Replicate
  `prunaai/p-video-avatar` with mocked contract coverage and safe local
  documentation.

## 0.11.0 - 2026-06-13

### Added

- Added the validated `easy_ai_clients.music` public dispatcher with deAPI,
  ElevenLabs, Google Lyria, and Runware ACE-Step music generation, status,
  download, local option metadata, style preset metadata, and lyrics prompt
  helpers.

### Fixed

- Hardened music timeout handling, public kwarg rejection, and result/error
  sanitization for the validated music dispatcher.

## 0.10.0 - 2026-06-03

### Removed

- Removed the broad unvalidated music dispatcher surface from earlier
  in-development work, plus related provider adapters, documentation,
  credential references, and tests.

## 0.9.1 - 2026-05-29

### Changed

- Preserved safe provider async references across video submissions, status,
  result, and sync polling flows, including fal.ai queue URLs, Runway task URLs,
  Google operation URLs, and Hedra/HeyGen/Together/xAI task metadata.
- Updated sync video results to retain safe submission metadata alongside final
  provider responses for debugging and follow-up calls.
- Changed direct `video.download(..., video_url=...)` behavior to require
  `output_path` instead of silently returning `None`.
- Documented Hugging Face text-to-video `sync=False` as a synchronous
  signature-compatibility no-op.

### Fixed

- Fixed fal.ai video adapters so provider-returned `status_url` and
  `response_url` are used before reconstructing queue URLs from `model` and
  `request_id`.
- Redacted signed upload URLs, upload form fields, credentials, and
  credential-bearing URLs from normalized video `raw_response` values.

## 0.9.0 - 2026-05-19

### Added

- Added HeyGen v3 support for speech, voices, compatible video operations,
  Video Agent, video translation, lip-sync, avatar creation, assets, webhooks,
  and account lookup through the public dispatcher layer.
- Added `easy_ai_clients.media`, `easy_ai_clients.webhooks`, and
  `easy_ai_clients.account` modules for reusable provider helper categories.
- Added current non-legacy provider gaps across existing audio, image, and
  video subcategories, including OpenAI/Groq/xAI/OpenRouter transcription,
  Deepgram Aura TTS, ElevenLabs sound and voice helpers, Hugging Face
  media adapters, DeepInfra/Mistral vision/audio paths, Together/xAI video
  adapters, Runway image/audio/video-with-audio paths, and Stable Audio.
- Added documentation pages for audio voice helpers, HeyGen media/webhook/account
  helpers, HeyGen video resources, and a cross-category operation example guide.

### Changed

- Expanded provider discovery, docs, environment templates, and contract tests
  for the HeyGen v3 integration.
- Standardized new media return metadata around `cost_usd`, `cost_currency`,
  `cost_is_estimated`, `cost_source`, and `cost_details`, while preserving
  image `cust_usd` as a legacy alias.
- Added documentation coverage tests so public dispatcher provider matrices stay
  linked from the provider docs index.

## 0.8.2 - 2026-05-18

### Changed

- Treated Deepgram `diarize_model` as a first-class transcription parameter.
- Stopped sending the adapter's default `diarize=true` when callers pass
  `diarize_model`, so Deepgram receives only the newer diarization selector.
- Rejected explicit Deepgram transcription calls that pass both `diarize` and
  `diarize_model` with a clear `ValueError`.
- Expanded Deepgram transcription provider metadata to include the effective
  Listen request parameters used for debugging and downstream analysis.

## 0.8.1 - 2026-05-16

### Changed

- Changed Deepgram transcription to send one whole-input Listen request per
  `audio.transcribe(..., api="deepgram")` call, with no internal audio
  chunking or chunk-result merging.
- Kept explicit Deepgram fallback behavior as one whole-input attempt for the
  primary model and, when configured, one whole-input attempt for the fallback
  model.
- Reused `PreparedTranscriptionAudio` bytes, content type, file name, and
  duration directly for Deepgram uploads when provided.
- Documented that callers who need Deepgram segmentation for long media should
  segment before calling the library.

## 0.8.0 - 2026-05-15

### Added

- Added `PreparedTranscriptionAudio` and
  `audio.prepare_transcription_audio(...)` for reusable transcription upload
  payloads.
- Added dispatcher-level transcription audio options for local normalization,
  upload format, codec, and bitrate without forwarding those options as
  provider-native kwargs.

### Changed

- Transcription dispatch now prepares audio once and passes reusable payloads
  to provider adapters while preserving normalized WAV as the default.
- Provider adapters now accept prepared transcription payloads without repeated
  local decode/export where the provider path can reuse them.
- ElevenLabs transcription now sends `file_format="other"` for encoded prepared
  uploads instead of marking them as `pcm_s16le_16`.

## 0.7.0 - 2026-05-14

### Added

- Added `video.video_with_audio(...)`, `video.create_avatar(...)`,
  `available_video_with_audio_apis()`, and `available_create_avatar_apis()`.
- Added Hedra video-to-video, motion-control, and video-with-audio adapters
  with local asset uploads and catalog-backed credit estimates where available.
- Added Runway ephemeral uploads for local media, custom avatar creation, and
  create-avatar chaining for `video.avatar_video(..., create_avatar=True)`.
- Added optional fal.ai pricing estimate support when callers pass
  `billing_unit_quantity` or `unit_quantity`.
- Expanded video coverage with `video.video_to_video(...)` and
  `video.avatar_video(...)`, plus discovery helpers for both operations.
- Added Hedra video adapters for text-to-video, image-to-video, and avatar
  video using `HEDRA_API_KEY`.
- Expanded Fal.ai video model metadata and forwarding across text, image,
  video-to-video, motion/reference, and avatar/talking-video endpoints.
- Added Runway `gen4_aleph` video-to-video and `gwm1_avatars` avatar-video
  adapters, and limited Google Veo video extension support.

### Changed

- Restricted Google Veo video extension to Veo 3.1/3.1 Fast with 8-second,
  720p, single-output requests.
- Updated Runway avatar-video payload normalization to use official
  `runway-preset`, `custom`, `audio`, and `text` shapes.

## 0.6.0 - 2026-05-13

### Added

- Added `easy_ai_clients.video` with dispatchers for text-to-video,
  image-to-video, motion-control, image lip-sync, and video lip-sync workflows.
- Added video providers for Fal.ai, Google Veo, and Runway where provider
  adapters are implemented, plus async status/result/download helpers.
- Added video provider documentation, environment variable references, tests,
  and package metadata updates for publishing.

### Changed

- Corrected Google Veo validation and payload generation to match current
  documented duration, resolution, person-generation, image, last-frame, and
  per-request video limits.
- Corrected Fal.ai text-to-video seed/frame-rate support and video URL
  extraction for Fal.ai responses that return `video` as a direct string.
- Corrected the fal.ai InfiniteTalk video lip-sync `num_frames` validation
  range to follow the embedded source-video plus audio request schema.
- Added contract-level video payload, docs/env consistency, and gated live
  smoke tests.

## 0.5.0 - 2026-05-11

### Changed

- Standardized the public Fal.ai provider identifier to `falai` for text,
  transcription, and image operations. The old short text identifier is no
  longer supported.
- Updated transcription results to include explicit cost metadata:
  `cost_usd`, `cost_source`, `cost_is_estimated`, and `cost_lookup_error`.
  Unknown transcription cost is now `None` instead of a fake `0.0`.
- Added `audio.update_cost("transcribe", result, api="deepgram")` for
  post-hoc Deepgram Management/Usage cost lookup.
- Corrected transcription pricing behavior for Deepgram, ElevenLabs, Fal.ai,
  Fireworks AI, Speechmatics, and Together AI using current official lookup
  APIs or pricing tables.
- Changed Speechmatics default transcription language behavior to
  `language="auto"` and Together default transcription language behavior to
  `language="auto"`.
- Removed Deepgram's hidden default fallback to `whisper-large`; fallback is
  now explicit via `fallback_model`.
- Reworked transcription provider docs, configuration, usage, error, and
  provider matrix documentation.

### Removed

- Removed public Rev AI transcription support because it did not meet the
  no-concrete-language Portuguese validation contract.
- Removed unsupported transcription models:
  `base`, `base-general`, `whisper-tiny`, and `whisper-base` from Deepgram;
  `deepgram/flux`, `deepgram/nova-3-en`, and `deepgram/nova-3-multi` from
  Together AI.

## 0.4.1 — 2026-04-25

### Changed

- Reworked `README.md` as a PyPI-safe long description with absolute GitHub
  links for repository files and directories.
- Added `docs/usage.md` with public dispatcher examples, normalized response
  structures, media input notes, streaming behavior, and cost update helpers.
- Updated configuration and error documentation to match the current
  dispatcher and provider-adapter behavior.
- Updated provider documentation examples to use the public
  `easy_ai_clients.text`, `easy_ai_clients.audio`, and `easy_ai_clients.image`
  dispatchers instead of private or removed provider import paths.
- Improved package metadata URLs and declared the README content type
  explicitly for PyPI rendering.

## 0.4.0 — 2026-04-25

This is the first fully working release of `easy-ai-clients`. The library was
rewritten from scratch around three operation-aware dispatchers and a private
provider tree. Earlier `0.x` releases on PyPI reserved the project name but
were not functional and have been superseded.

### Added

- `easy_ai_clients.text.generate(input_text, instruction=None, model=None, *, api, **kwargs)`
  unified dispatcher across 14 text/chat providers: `anthropic`, `cohere`,
  `deepinfra`, `deepseek`, Fal.ai, `fireworks`, `google`, `groq`, `huggingface`,
  `mistral`, `openai`, `openrouter`, `together`, `xai`.
- `easy_ai_clients.audio.generate(text, model=None, voice=None, language_code="en", *, api, **kwargs)`
  for speech synthesis with `deepinfra`, `elevenlabs`, `google`, `mistral`,
  `openai`, `together`, `xai`.
- `easy_ai_clients.audio.transcribe(audio_input, model=None, *, api, **kwargs)`
  for speech transcription with `deepgram`, `elevenlabs`, `falai`, `fireworks`,
  Rev AI, `speechmatics`, `together`.
- `easy_ai_clients.image.generate / edit / remix / analyze(...)` dispatchers
  covering `bfl`, `falai`, `fireworks`, `google`, `openai`, `openrouter`,
  `stability`, `together`, `xai` (`anthropic` and `groq` for `analyze`).
- Programmatic discovery helpers: `text.available_apis()`,
  `audio.available_synthesize_apis()`, `audio.available_transcribe_apis()`,
  `image.available_generate_apis()`, `image.available_edit_apis()`,
  `image.available_remix_apis()`, `image.available_analyze_apis()`.
- `text.list_models(api=...)` and `text.update_cost(result, api=...)` for
  providers that support live catalogs and post-hoc cost lookups (currently
  `openai` and `openrouter`).
- `image.update_cost(operation, result, api=...)` for providers that support
  cost refinement after the original call (currently `openrouter`).
- Public package marker (`py.typed`) and an explicit Python `>= 3.11` baseline.
- Documentation under [`docs/`](docs/) for configuration, providers, and
  errors, plus a refreshed `README.md` and `CHANGELOG.md`.

### Changed

- The library no longer auto-loads a `.env` file from the package directory;
  callers are expected to set environment variables explicitly or use
  `python-dotenv` themselves. This matches the behaviour documented in
  [`docs/configuration.md`](docs/configuration.md).
- Internal provider modules are private (the package directories use a leading
  underscore). Only the operation dispatchers and the package-level submodules
  are part of the public API.

### Removed

- Direct imports of provider modules such as
  `easy_ai_clients.text.apis.openai` are no longer supported.
- The `0.3.0` and earlier code paths were removed entirely; nothing from those
  releases is preserved beyond the public package name.
