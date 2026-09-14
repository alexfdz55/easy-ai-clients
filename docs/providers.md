# Providers

This page is the entry point for the per-provider documentation pages. It
mirrors the operation tree of the public API and lists which environment
variable each provider needs.

The detailed per-provider notes (documented default models, analyzed
parameters, pricing, validation status, known limitations) live alongside this
file under the matching modality directory.

Documented models and parameters are reference metadata, not a local acceptance
list. Public operations forward undocumented `model` values and provider-native
kwargs whenever a request can be assembled; if the provider rejects them, the
dispatcher returns the operation's normalized failure shape with an `error`
object.

`easy_ai_clients.music` is intentionally narrower. It uses the validated matrix
documented under [Music](#music---easy_ai_clientsmusic) and rejects unsupported
models or removed public kwargs before provider dispatch.

For copyable dispatcher examples and normalized response structures, see
[`usage.md`](usage.md). For a compact example of every public subcategory, see
[`operation_examples.md`](operation_examples.md).

## Text — `easy_ai_clients.text`

| API | Env var | Notes |
| --- | --- | --- |
| [`anthropic`](text/anthropic.md) | `ANTHROPIC_API_KEY` | Messages API. |
| [`cohere`](text/cohere.md) | `COHERE_API_KEY` | Chat v2. |
| [`deepinfra`](text/deepinfra.md) | `DEEPINFRA_API_KEY` | OpenAI-compatible. |
| [`deepseek`](text/deepseek.md) | `DEEPSEEK_API_KEY` | DeepSeek chat with reasoning. |
| [`falai`](text/falai.md) | `FAL_KEY`; catalog uses `OPENROUTER_API_KEY` | Fal.ai LLM gateway. |
| [`fireworks`](text/fireworks.md) | `FIREWORKS_API_KEY` | Reasoning + speculation kwargs. |
| [`google`](text/google.md) | `GOOGLE_API_KEY` | Gemini `generateContent`. |
| [`groq`](text/groq.md) | `GROQ_API_KEY` | OpenAI-compatible chat. |
| [`huggingface`](text/huggingface.md) | `HUGGINGFACE_API_KEY` | Router / serverless inference. |
| [`mistral`](text/mistral.md) | `MISTRAL_API_KEY` | Chat completions. |
| [`openai`](text/openai.md) | `OPENAI_API_KEY` | Responses API + cost lookup. |
| [`openrouter`](text/openrouter.md) | `OPENROUTER_API_KEY` | Aggregator with `update_cost`. |
| [`together`](text/together.md) | `TOGETHER_API_KEY` | Chat completions + reasoning. |
| [`xai`](text/xai.md) | `XAI_API_KEY` | Grok chat. |

## Audio — `easy_ai_clients.audio`

### `audio.generate(...)` (text-to-speech)

| API | Env var | Notes |
| --- | --- | --- |
| [`deepgram`](audio/generate/deepgram.md) | `DEEPGRAM_API_KEY` | Aura TTS. |
| [`deepinfra`](audio/generate/deepinfra.md) | `DEEPINFRA_API_KEY` | Multiple Kokoro/Sesame voices. |
| [`elevenlabs`](audio/generate/elevenlabs.md) | `ELEVENLABS_API_KEY` | Speech and sound effects. |
| [`google`](audio/generate/google.md) | `GOOGLE_API_KEY` | Gemini speech. |
| [`groq`](audio/generate/groq.md) | `GROQ_API_KEY` | PlayAI TTS. |
| [`heygen`](audio/generate/heygen.md) | `HEYGEN_KEY` | HeyGen v3 Starfish speech. |
| [`mistral`](audio/generate/mistral.md) | `MISTRAL_API_KEY` | Voxtral / Le Chat speech. |
| [`openai`](audio/generate/openai.md) | `OPENAI_API_KEY` | `gpt-4o-mini-tts` + `tts-1`. |
| [`openrouter`](audio/generate/openrouter.md) | `OPENROUTER_API_KEY` | OpenRouter TTS. |
| [`runway`](audio/generate/runway.md) | `RUNWAYML_API_SECRET` | Speech/sound generation. |
| [`stability`](audio/generate/stability.md) | `STABILITY_API_KEY` | Stable Audio. |
| [`together`](audio/generate/together.md) | `TOGETHER_API_KEY` | OpenAI-compatible TTS. |
| [`xai`](audio/generate/xai.md) | `XAI_API_KEY` | Grok speech. |

### `audio.list_voices(...)` and voice helpers

| API | Env var | Notes |
| --- | --- | --- |
| [`deepinfra`](audio/voices/deepinfra.md) | `DEEPINFRA_API_KEY` | Voice catalog; design/clone return normalized unsupported-operation results. |
| [`elevenlabs`](audio/voices/elevenlabs.md) | `ELEVENLABS_API_KEY` | List/get/design/clone voices. |
| [`heygen`](audio/voices/heygen.md) | `HEYGEN_KEY` | HeyGen v3 public/custom voices, voice design, and cloning. |
| [`mistral`](audio/voices/mistral.md) | `MISTRAL_API_KEY` | Voice catalog; design/clone return normalized unsupported-operation results. |
| [`together`](audio/voices/together.md) | `TOGETHER_API_KEY` | Voice catalog; design/clone return normalized unsupported-operation results. |

### `audio.transcribe(...)` (speech-to-text)

`easy_ai_clients.audio.prepare_transcription_audio(...)` prepares a reusable
normalized WAV payload by default and can opt into compressed upload formats
such as MP3, FLAC, or Ogg/Opus where the selected provider supports them.

| API | Env var | Notes |
| --- | --- | --- |
| [`deepinfra`](audio/transcribe/deepinfra.md) | `DEEPINFRA_API_KEY` | OpenAI-compatible STT gateway. |
| [`deepgram`](audio/transcribe/deepgram.md) | `DEEPGRAM_API_KEY` (+ optional `DEEPGRAM_PROJECT_ID`) | Kept Nova, Enhanced, Base specialty, and Whisper models; supports `audio.update_cost`. |
| [`elevenlabs`](audio/transcribe/elevenlabs.md) | `ELEVENLABS_API_KEY` | Scribe v1/v2 with omitted-language detection. |
| [`falai`](audio/transcribe/falai.md) | `FAL_KEY` | Routes to ElevenLabs Scribe via Fal.ai Pricing API. |
| [`fireworks`](audio/transcribe/fireworks.md) | `FIREWORKS_API_KEY` | Whisper v3 and Whisper v3 Turbo. |
| [`google`](audio/transcribe/google.md) | `GOOGLE_API_KEY` | Gemini audio understanding. |
| [`groq`](audio/transcribe/groq.md) | `GROQ_API_KEY` | Whisper STT on Groq. |
| [`huggingface`](audio/transcribe/huggingface.md) | `HUGGINGFACE_API_KEY` | Inference Providers ASR. |
| [`mistral`](audio/transcribe/mistral.md) | `MISTRAL_API_KEY` | Voxtral transcription. |
| [`openai`](audio/transcribe/openai.md) | `OPENAI_API_KEY` | OpenAI Audio transcriptions. |
| [`openrouter`](audio/transcribe/openrouter.md) | `OPENROUTER_API_KEY` | OpenRouter audio transcriptions. |
| [`speechmatics`](audio/transcribe/speechmatics.md) | `SPEECHMATICS_API_KEY` | Standard/enhanced batch with `language="auto"`. |
| [`together`](audio/transcribe/together.md) | `TOGETHER_API_KEY` | Whisper-large-v3 and Parakeet serverless models. |
| [`xai`](audio/transcribe/xai.md) | `XAI_API_KEY` | xAI STT. |

## Image — `easy_ai_clients.image`

### `image.generate(...)` (text-to-image)

| API | Env var | Doc |
| --- | --- | --- |
| `bfl` | `BFL_API_KEY` | [`bfl`](image/generate/bfl.md) |
| `deepinfra` | `DEEPINFRA_API_KEY` | [`deepinfra`](image/generate/deepinfra.md) |
| `falai` | `FAL_KEY` | [`falai`](image/generate/falai.md); uses fal.ai pricing estimate API for image cost estimates |
| `fireworks` | `FIREWORKS_API_KEY` | [`fireworks`](image/generate/fireworks.md) |
| `google` | `GOOGLE_API_KEY` | [`google`](image/generate/google.md) |
| `huggingface` | `HUGGINGFACE_API_KEY` | [`huggingface`](image/generate/huggingface.md) |
| `openai` | `OPENAI_API_KEY` | [`openai`](image/generate/openai.md) |
| `openrouter` | `OPENROUTER_API_KEY` | [`openrouter`](image/generate/openrouter.md) |
| `runway` | `RUNWAYML_API_SECRET` | [`runway`](image/generate/runway.md) |
| `stability` | `STABILITY_API_KEY` | [`stability`](image/generate/stability.md) |
| `together` | `TOGETHER_API_KEY` | [`together`](image/generate/together.md) |
| `xai` | `XAI_API_KEY` | [`xai`](image/generate/xai.md) |

### `image.edit(...)` (prompt + mask editing)

| API | Env var | Doc |
| --- | --- | --- |
| `bfl` | `BFL_API_KEY` | [`bfl`](image/edit/bfl.md) |
| `deepinfra` | `DEEPINFRA_API_KEY` | [`deepinfra`](image/edit/deepinfra.md) |
| `falai` | `FAL_KEY` | [`falai`](image/edit/falai.md); uses fal.ai pricing estimate API for image cost estimates |
| `fireworks` | `FIREWORKS_API_KEY` | [`fireworks`](image/edit/fireworks.md) |
| `google` | `GOOGLE_API_KEY` | [`google`](image/edit/google.md) |
| `huggingface` | `HUGGINGFACE_API_KEY` | [`huggingface`](image/edit/huggingface.md) |
| `openai` | `OPENAI_API_KEY` | [`openai`](image/edit/openai.md) |
| `openrouter` | `OPENROUTER_API_KEY` | [`openrouter`](image/edit/openrouter.md) |
| `runway` | `RUNWAYML_API_SECRET` | [`runway`](image/edit/runway.md) |
| `stability` | `STABILITY_API_KEY` | [`stability`](image/edit/stability.md) |
| `together` | `TOGETHER_API_KEY` | [`together`](image/edit/together.md) |
| `xai` | `XAI_API_KEY` | [`xai`](image/edit/xai.md) |

For `edit`, the public mask convention is **black = editable, white =
preserve**. Each provider adapter converts that contract to whatever the
underlying API expects.

### `image.remix(...)` (reference-image guided)

| API | Env var | Doc |
| --- | --- | --- |
| `bfl` | `BFL_API_KEY` | [`bfl`](image/remix/bfl.md) |
| `deepinfra` | `DEEPINFRA_API_KEY` | [`deepinfra`](image/remix/deepinfra.md) |
| `falai` | `FAL_KEY` | [`falai`](image/remix/falai.md); uses fal.ai pricing estimate API for image cost estimates |
| `fireworks` | `FIREWORKS_API_KEY` | [`fireworks`](image/remix/fireworks.md) |
| `google` | `GOOGLE_API_KEY` | [`google`](image/remix/google.md) |
| `huggingface` | `HUGGINGFACE_API_KEY` | [`huggingface`](image/remix/huggingface.md) |
| `openai` | `OPENAI_API_KEY` | [`openai`](image/remix/openai.md) |
| `openrouter` | `OPENROUTER_API_KEY` | [`openrouter`](image/remix/openrouter.md) |
| `runway` | `RUNWAYML_API_SECRET` | [`runway`](image/remix/runway.md) |
| `stability` | `STABILITY_API_KEY` | [`stability`](image/remix/stability.md) |
| `together` | `TOGETHER_API_KEY` | [`together`](image/remix/together.md) |
| `xai` | `XAI_API_KEY` | [`xai`](image/remix/xai.md) |

### `image.analyze(...)` (vision)

| API | Env var | Doc |
| --- | --- | --- |
| `anthropic` | `ANTHROPIC_API_KEY` | [`anthropic`](image/analyze/anthropic.md) |
| `deepinfra` | `DEEPINFRA_API_KEY` | [`deepinfra`](image/analyze/deepinfra.md) |
| `falai` | `FAL_KEY` | [`falai`](image/analyze/falai.md) |
| `fireworks` | `FIREWORKS_API_KEY` | [`fireworks`](image/analyze/fireworks.md) |
| `google` | `GOOGLE_API_KEY` | [`google`](image/analyze/google.md) |
| `groq` | `GROQ_API_KEY` | [`groq`](image/analyze/groq.md) |
| `huggingface` | `HUGGINGFACE_API_KEY` | [`huggingface`](image/analyze/huggingface.md) |
| `mistral` | `MISTRAL_API_KEY` | [`mistral`](image/analyze/mistral.md) |
| `openai` | `OPENAI_API_KEY` | [`openai`](image/analyze/openai.md) |
| `openrouter` | `OPENROUTER_API_KEY` | [`openrouter`](image/analyze/openrouter.md) |
| `together` | `TOGETHER_API_KEY` | [`together`](image/analyze/together.md) |
| `xai` | `XAI_API_KEY` | [`xai`](image/analyze/xai.md) |

## Music - `easy_ai_clients.music`

### `music.generate(...)`

| API | Env var | Doc |
| --- | --- | --- |
| `deapi` | `DEAPI_API_KEY` | [`deapi`](music/deapi.md) |
| `elevenlabs` | `ELEVENLABS_API_KEY` | [`elevenlabs`](music/elevenlabs.md) |
| `google` | `GOOGLE_API_KEY` | [`google`](music/google.md) |
| `kie` | `KIE_API_KEY` | [`kie`](music/kie.md) |
| `runware` | `RUNWARE_API_KEY` | [`runware`](music/runware.md) |

## Video - `easy_ai_clients.video`

Async video adapters preserve safe provider-native refs such as `status_url`,
`response_url`, `result_url`, `task_url`, and `operation_url` when providers
return them. Public helpers accept those refs and use them before reconstructing
provider URLs from `request_id`, `model`, and `api`. Upload URLs, upload form
fields, authorization headers, and signed credential-bearing URLs are redacted
from normalized public results. Direct `video.download(..., video_url=...)`
requires `output_path`.

### `video.generate(...)` / `video.text_to_video(...)`

| API | Env var | Doc |
| --- | --- | --- |
| `byteplus` | `ARK_API_KEY` | [`byteplus`](video/text_to_video/byteplus.md) |
| `falai` | `FAL_KEY` | [`falai`](video/text_to_video/falai.md) |
| `google` | `GOOGLE_API_KEY` | [`google`](video/text_to_video/google.md) |
| `hedra` | `HEDRA_API_KEY` | [`hedra`](video/text_to_video/hedra.md) |
| `heygen` | `HEYGEN_KEY` | [`heygen`](video/text_to_video/heygen.md) |
| `huggingface` | `HUGGINGFACE_API_KEY` | [`huggingface`](video/text_to_video/huggingface.md) |
| `openrouter` | `OPENROUTER_API_KEY` | [`openrouter`](video/text_to_video/openrouter.md) |
| `runway` | `RUNWAYML_API_SECRET` | [`runway`](video/text_to_video/runway.md) |
| `together` | `TOGETHER_API_KEY` | [`together`](video/text_to_video/together.md) |
| `xai` | `XAI_API_KEY` | [`xai`](video/text_to_video/xai.md) |

### `video.image_to_video(...)`

| API | Env var | Doc |
| --- | --- | --- |
| `byteplus` | `ARK_API_KEY` | [`byteplus`](video/image_to_video/byteplus.md) |
| `falai` | `FAL_KEY` | [`falai`](video/image_to_video/falai.md) |
| `google` | `GOOGLE_API_KEY` | [`google`](video/image_to_video/google.md) |
| `hedra` | `HEDRA_API_KEY` | [`hedra`](video/image_to_video/hedra.md) |
| `heygen` | `HEYGEN_KEY` | [`heygen`](video/image_to_video/heygen.md) |
| `openrouter` | `OPENROUTER_API_KEY` | [`openrouter`](video/image_to_video/openrouter.md) |
| `runway` | `RUNWAYML_API_SECRET` | [`runway`](video/image_to_video/runway.md) |
| `together` | `TOGETHER_API_KEY` | [`together`](video/image_to_video/together.md) |
| `xai` | `XAI_API_KEY` | [`xai`](video/image_to_video/xai.md) |

### `video.video_to_video(...)`

| API | Env var | Doc |
| --- | --- | --- |
| `byteplus` | `ARK_API_KEY` | [`byteplus`](video/video_to_video/byteplus.md) |
| `falai` | `FAL_KEY` | [`falai`](video/video_to_video/falai.md) |
| `google` | `GOOGLE_API_KEY` | [`google`](video/video_to_video/google.md) |
| `hedra` | `HEDRA_API_KEY` | [`hedra`](video/video_to_video/hedra.md) |
| `runway` | `RUNWAYML_API_SECRET` | [`runway`](video/video_to_video/runway.md) |
| `together` | `TOGETHER_API_KEY` | [`together`](video/video_to_video/together.md) |
| `xai` | `XAI_API_KEY` | [`xai`](video/video_to_video/xai.md) |

### `video.motion_control(...)`

| API | Env var | Doc |
| --- | --- | --- |
| `falai` | `FAL_KEY` | [`falai`](video/motion_control/falai.md) |
| `hedra` | `HEDRA_API_KEY` | [`hedra`](video/motion_control/hedra.md) |
| `runway` | `RUNWAYML_API_SECRET` | [`runway`](video/motion_control/runway.md) |

### `video.avatar_video(...)`

| API | Env var | Doc |
| --- | --- | --- |
| `falai` | `FAL_KEY` | [`falai`](video/avatar_video/falai.md) |
| `hedra` | `HEDRA_API_KEY` | [`hedra`](video/avatar_video/hedra.md) |
| `heygen` | `HEYGEN_KEY` | [`heygen`](video/avatar_video/heygen.md) |
| `replicate` | `REPLICATE_API_TOKEN` | [`replicate`](video/avatar_video/replicate.md) |
| `runway` | `RUNWAYML_API_SECRET` | [`runway`](video/avatar_video/runway.md) |

### `video.video_with_audio(...)`

| API | Env var | Doc |
| --- | --- | --- |
| `hedra` | `HEDRA_API_KEY` | [`hedra`](video/video_with_audio/hedra.md) |
| `runway` | `RUNWAYML_API_SECRET` | [`runway`](video/video_with_audio/runway.md) |
| `together` | `TOGETHER_API_KEY` | [`together`](video/video_with_audio/together.md) |

### `video.create_avatar(...)`

| API | Env var | Doc |
| --- | --- | --- |
| `heygen` | `HEYGEN_KEY` | [`heygen`](video/create_avatar/heygen.md) |
| `runway` | `RUNWAYML_API_SECRET` | [`runway`](video/create_avatar/runway.md) |

### `video.image_lipsync(...)`

| API | Env var | Doc |
| --- | --- | --- |
| `falai` | `FAL_KEY` | [`falai`](video/image_lipsync/falai.md) |
| `heygen` | `HEYGEN_KEY` | [`heygen`](video/image_lipsync/heygen.md) |

### `video.video_lipsync(...)`

| API | Env var | Doc |
| --- | --- | --- |
| `falai` | `FAL_KEY` | [`falai`](video/video_lipsync/falai.md) |
| `heygen` | `HEYGEN_KEY` | [`heygen`](video/video_lipsync/heygen.md) |

### `video.agent_video(...)`

| API | Env var | Doc |
| --- | --- | --- |
| `heygen` | `HEYGEN_KEY` | [`heygen`](video/agent_video/heygen.md) |

### `video.translate(...)`

| API | Env var | Doc |
| --- | --- | --- |
| `heygen` | `HEYGEN_KEY` | [`heygen`](video/translate/heygen.md) |

### HeyGen video resource helpers

| API | Env var | Doc |
| --- | --- | --- |
| `heygen` | `HEYGEN_KEY` | [`heygen`](video/resources/heygen.md) |

## Media, Webhooks, and Account

| Module | API | Env var | Doc |
| --- | --- | --- | --- |
| `easy_ai_clients.media` | `heygen` | `HEYGEN_KEY` | [`heygen`](media/heygen.md) |
| `easy_ai_clients.webhooks` | `heygen` | `HEYGEN_KEY` | [`heygen`](webhooks/heygen.md) |
| `easy_ai_clients.account` | `heygen` | `HEYGEN_KEY` | [`heygen`](account/heygen.md) |

## Deferred HeyGen APIs

HeyGen Studio/Template v2 endpoints are not implemented in this release. This
integration targets the official v3 API surface exposed by
`developers.heygen.com`; Studio/Template support should be added later as a
separate legacy provider surface if needed.
