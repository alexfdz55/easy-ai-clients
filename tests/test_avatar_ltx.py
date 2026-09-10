"""LTX 2.3 audio-to-video como modelo de avatar (foto + audio → video con movimiento)."""

from easy_ai_clients.video._avatar_video._apis import falai


def _prepared(image="https://i/a.webp", audio="https://a/b.mp3"):
    return {"image": image, "audio": audio, "text": None, "output_path": None}


def test_ltx_payload_uses_prompt_explicit_size_and_follows_the_audio():
    payload = falai._build_payload(
        falai.LTX_AUDIO_TO_VIDEO, _prepared(),
        {"resolution": "720p", "aspect_ratio": "9:16", "prompt": "singing to camera", "timeout_seconds": 900, "duration_seconds": 4.2},
    )
    assert payload == {
        "image_url": "https://i/a.webp",
        "audio_url": "https://a/b.mp3",
        "prompt": "singing to camera",
        "match_audio_length": True,
        "video_size": {"width": 720, "height": 1280},
    }
    landscape = falai._build_payload(falai.LTX_AUDIO_TO_VIDEO, _prepared(), {"resolution": "480p", "aspect_ratio": "16:9"})
    assert landscape["video_size"] == {"width": 852, "height": 480}


def test_ltx_cost_is_per_second_by_resolution():
    cost = falai._cost(falai.LTX_AUDIO_TO_VIDEO, {"resolution": "720p", "duration_seconds": 10})
    assert cost["cost_usd"] == 0.36
    assert falai._cost(falai.LTX_AUDIO_TO_VIDEO, {"resolution": "720p"})["cost_source"] == "unavailable"


def test_aspect_ratio_is_not_forwarded_to_other_models():
    payload = falai._build_payload("fal-ai/flashtalk", _prepared("i", "a"), {"resolution": "720p", "aspect_ratio": "9:16"})
    assert "aspect_ratio" not in payload
