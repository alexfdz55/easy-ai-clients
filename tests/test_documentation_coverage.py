"""Documentation coverage checks for public provider dispatchers."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def _assert_doc(provider_doc: Path, providers_markdown: str) -> None:
    assert provider_doc.exists(), f"Missing provider doc: {provider_doc.relative_to(ROOT)}"
    relative = provider_doc.relative_to(DOCS).as_posix()
    assert relative in providers_markdown, f"docs/providers.md does not link {relative}"


def test_provider_docs_cover_public_dispatcher_matrices():
    from easy_ai_clients import account, audio, image, media, music, text, video, webhooks

    providers_markdown = (DOCS / "providers.md").read_text(encoding="utf-8")

    matrix = [
        *(("text", "", api) for api in text.available_apis()),
        *(("audio", "generate", api) for api in audio.available_synthesize_apis()),
        *(("audio", "transcribe", api) for api in audio.available_transcribe_apis()),
        *(("audio", "voices", api) for api in audio.available_voice_apis()),
        *(("image", "generate", api) for api in image.available_generate_apis()),
        *(("image", "edit", api) for api in image.available_edit_apis()),
        *(("image", "remix", api) for api in image.available_remix_apis()),
        *(("image", "analyze", api) for api in image.available_analyze_apis()),
        *(("music", "", api) for api in music.available_apis()),
        *(("video", "text_to_video", api) for api in video.available_text_to_video_apis()),
        *(("video", "image_to_video", api) for api in video.available_image_to_video_apis()),
        *(("video", "video_to_video", api) for api in video.available_video_to_video_apis()),
        *(("video", "motion_control", api) for api in video.available_motion_control_apis()),
        *(("video", "avatar_video", api) for api in video.available_avatar_video_apis()),
        *(("video", "video_with_audio", api) for api in video.available_video_with_audio_apis()),
        *(("video", "create_avatar", api) for api in video.available_create_avatar_apis()),
        *(("video", "image_lipsync", api) for api in video.available_image_lipsync_apis()),
        *(("video", "video_lipsync", api) for api in video.available_video_lipsync_apis()),
        *(("video", "agent_video", api) for api in video.available_agent_video_apis()),
        *(("video", "translate", api) for api in video.available_translate_apis()),
        *(("video", "resources", api) for api in video.available_video_resource_apis()),
        *(("media", "", api) for api in media.available_apis()),
        *(("webhooks", "", api) for api in webhooks.available_apis()),
        *(("account", "", api) for api in account.available_apis()),
    ]

    for category, operation, api in matrix:
        if operation:
            provider_doc = DOCS / category / operation / f"{api}.md"
        else:
            provider_doc = DOCS / category / f"{api}.md"
        _assert_doc(provider_doc, providers_markdown)


def test_cross_cutting_docs_include_all_helper_categories():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    usage = (DOCS / "usage.md").read_text(encoding="utf-8")
    examples = (DOCS / "operation_examples.md").read_text(encoding="utf-8")

    for token in (
        "audio.list_voices",
        "video.agent_video",
        "music.generate",
        "video.translate",
        "media.upload_asset",
        "webhooks.create_endpoint",
        "account.get_current_user",
    ):
        assert token in readme or token in usage
        assert token in examples


def test_environment_template_matches_documented_runtime_variables():
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    configuration = (DOCS / "configuration.md").read_text(encoding="utf-8")
    expected = {
        "ANTHROPIC_API_KEY",
        "ARK_API_KEY",
        "ARK_BASE_URL",
        "BFL_API_KEY",
        "COHERE_API_KEY",
        "DEAPI_API_KEY",
        "DEEPGRAM_API_KEY",
        "DEEPGRAM_PROJECT_ID",
        "DEEPINFRA_API_KEY",
        "DEEPSEEK_API_KEY",
        "ELEVENLABS_API_KEY",
        "FAL_KEY",
        "FIREWORKS_API_KEY",
        "GOOGLE_API_KEY",
        "GROQ_API_KEY",
        "HEDRA_API_KEY",
        "HEYGEN_API_BASE",
        "HEYGEN_API_KEY",
        "HEYGEN_KEY",
        "HUGGINGFACE_API_KEY",
        "KIE_API_KEY",
        "MISTRAL_API_KEY",
        "MUSIC_API_TIMEOUT",
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "REPLICATE_API_TOKEN",
        "RUNWARE_API_KEY",
        "RUNWAYML_API_SECRET",
        "SPEECHMATICS_API_KEY",
        "STABILITY_API_KEY",
        "TOGETHER_API_KEY",
        "XAI_API_KEY",
    }

    template_keys = {
        line.split("=", 1)[0]
        for line in env_example.splitlines()
        if line and not line.startswith("#") and "=" in line
    }

    assert template_keys == expected
    for name in expected:
        assert name in configuration


def test_music_provider_docs_match_model_registry():
    from easy_ai_clients.music._model_registry import DEFAULT_MODEL_KEYS, MODEL_ALIASES

    for provider, aliases in MODEL_ALIASES.items():
        provider_doc = DOCS / "music" / f"{provider}.md"
        markdown = provider_doc.read_text(encoding="utf-8")

        for model_key, native_model in aliases.items():
            assert native_model in markdown
            assert model_key in markdown
            expected_default = "Yes" if model_key == DEFAULT_MODEL_KEYS[provider] else "No"
            matching_rows = [
                line
                for line in markdown.splitlines()
                if native_model in line and model_key in line
            ]

            assert matching_rows, f"Missing docs row for {provider} {model_key}"
            assert any(f"| {expected_default} |" in row for row in matching_rows)
