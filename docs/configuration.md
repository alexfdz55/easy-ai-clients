# Configuration

`easy-ai-clients` resolves provider credentials from environment variables at
provider-call time. Configure only the credentials for providers your
application actually calls.

`os.environ` is always authoritative. If a variable is already present in the
process, helpers that load local `.env` files preserve that value.

## Recommended Setup

For scripts and applications, load secrets before calling the library. Keep real
secret files outside the repository:

```python
from dotenv import load_dotenv

load_dotenv("path/to/private.env")
```

or set variables in the shell:

```bash
export OPENAI_API_KEY="sk-..."
export DEEPGRAM_API_KEY="..."
```

```powershell
$env:OPENAI_API_KEY = "sk-..."
$env:DEEPGRAM_API_KEY = "..."
```

Some current text, image, music, and HeyGen helpers attempt to load a `.env`
file from the current working directory before resolving credentials. Other
audio and video helpers read the process environment directly. Because this
behavior is not uniform across every adapter, application code should load a
private dotenv file explicitly when it depends on one.

For this repository's gated live tests, set `EASY_AI_CLIENTS_ENV_FILE` or keep a
private `../.env-easy-ai-clients` file one directory above the repository. Use
the repository template:

[`../.env.example`](../.env.example)

## Recognized Environment Variables

| Variable | Used by |
| --- | --- |
| `ANTHROPIC_API_KEY` | `text.generate(api="anthropic")`, `image.analyze(api="anthropic")` |
| `ARK_API_KEY` | BytePlus ModelArk Seedance video operations using `api="byteplus"` |
| `ARK_BASE_URL` | Optional ModelArk base URL override for BytePlus video operations |
| `BFL_API_KEY` | `image.generate / edit / remix(api="bfl")` |
| `COHERE_API_KEY` | `text.generate(api="cohere")` |
| `DEAPI_API_KEY` | `music.generate(api="deapi")` |
| `DEEPGRAM_API_KEY` | `audio.transcribe(api="deepgram")`, `audio.generate(api="deepgram")`, and synthesis alignment paths where used |
| `DEEPGRAM_PROJECT_ID` | Optional Deepgram project filter for transcription cost lookup calls |
| `DEEPINFRA_API_KEY` | DeepInfra text, audio generate/transcribe/voices, and image operations |
| `DEEPSEEK_API_KEY` | `text.generate(api="deepseek")` |
| `ELEVENLABS_API_KEY` | ElevenLabs audio generation, transcription, voice helpers, and `music.generate(api="elevenlabs")` |
| `FAL_KEY` | `text.generate(api="falai")`, `audio.transcribe(api="falai")`, image operations using `api="falai"`, and video operations using `api="falai"` |
| `FIREWORKS_API_KEY` | Fireworks text, audio transcription, and image operations |
| `GOOGLE_API_KEY` | Google text, audio generation/transcription, image operations, Google Veo video operations, and `music.generate(api="google")` |
| `GROQ_API_KEY` | Groq text, audio generation/transcription, and image analysis |
| `HEYGEN_KEY` | Preferred HeyGen v3 credential for audio voices/speech, video/avatar/lip-sync/translation, media, webhook, and account operations |
| `HEYGEN_API_KEY` | Compatibility alias for `HEYGEN_KEY` |
| `HEYGEN_API_BASE` | Optional HeyGen API base URL override for tests or controlled environments |
| `HUGGINGFACE_API_KEY` | Hugging Face text, audio transcription, image operations, and text-to-video |
| `MISTRAL_API_KEY` | Mistral text, audio generation/transcription/voices, and image analysis |
| `MUSIC_API_TIMEOUT` | Optional timeout override, in seconds, for music provider HTTP calls |
| `OPENAI_API_KEY` | OpenAI text, audio, and image operations |
| `OPENROUTER_API_KEY` | OpenRouter text, audio, image, and catalog/cost lookup paths |
| `REPLICATE_API_TOKEN` | Replicate avatar-video prediction operations |
| `RUNWARE_API_KEY` | `music.generate(api="runware")` |
| `RUNWAYML_API_SECRET` | Runway audio, image, video generation, avatar-video, ephemeral uploads, and custom avatar creation |
| `HEDRA_API_KEY` | Hedra video generation, video-to-video, motion-control, video-with-audio, and avatar operations |
| `SPEECHMATICS_API_KEY` | `audio.transcribe(api="speechmatics")` |
| `STABILITY_API_KEY` | Stability image operations and Stable Audio generation |
| `TOGETHER_API_KEY` | Together text, audio, image, and video operations |
| `XAI_API_KEY` | xAI text, audio, image, and video operations |

Hedra credentials are read only when a Hedra video operation is selected. Runway
uploads use the same `RUNWAYML_API_SECRET` as the generation and avatar
endpoints.

`MUSIC_API_TIMEOUT` is an optional timeout override, in seconds, for music
provider HTTP calls. When omitted, music adapters use their built-in timeout
defaults. The template uses `60` so a loaded dotenv file does not set an empty
timeout value.

## Missing Credentials

Missing credentials are inert until the corresponding provider is called. For
example, `OPENAI_API_KEY` is not required to call `text.generate(api="anthropic")`.

If a selected provider credential is missing or empty, the call raises a standard
Python exception such as `RuntimeError`, `OSError`, `EnvironmentError`, or
`ValueError`, depending on the adapter path.

## Deepgram Cost Lookup

`audio.update_cost("transcribe", result, api="deepgram")` retries Deepgram
Management/Usage lookup for the request IDs stored in a transcription result.
The key in `DEEPGRAM_API_KEY` needs `usage:read`. `DEEPGRAM_PROJECT_ID` is
optional but recommended when the key can access multiple projects or cannot
list projects.

If exact lookup is unavailable, transcription results keep truthful cost
metadata: `cost_usd` may be `None`, `cost_source` explains the source, and
`cost_lookup_error` contains a sanitized reason.

## Security Notes

- Keep real tokens out of Git.
- Scope provider tokens to the smallest useful permission set.
- Prefer environment variables supplied by your deployment system in production.
- Avoid printing credentials in logs or exception reports.
- Rotate provider tokens after local testing or incident response.
