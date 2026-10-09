"""OpenRouter avatar-video (HeyGen Avatar IV) payload and result contract tests."""

from __future__ import annotations

import pytest

IMAGE = "https://cdn.example.com/shots/shot_004.png"
AUDIO = "https://cdn.example.com/audio/fragment_004.mp3"
MOTION = "She sings to the camera, lifts the fabric and shakes it gently to the beat."
AVATAR_IV = "heygen/avatar-iv"


def _provider(monkeypatch, handler=None):
    from easy_ai_clients.video import _openrouter_video_common as common
    from easy_ai_clients.video._avatar_video._apis import openrouter as provider

    captured = {}

    def fake_http_json(method, url, headers=None, payload=None, timeout_seconds=None):
        captured.setdefault("calls", []).append((method, url))
        if method == "POST":
            captured["payload"] = payload
            return {"id": "gen-vid-1", "polling_url": "/api/v1/videos/gen-vid-1", "status": "pending"}
        return {
            "id": "gen-vid-1",
            "status": "completed",
            "unsigned_urls": ["https://openrouter.ai/api/v1/videos/gen-vid-1/content?index=0"],
            "usage": {"cost": 0.291, "is_byok": False},
        }

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-or")
    monkeypatch.setattr(common, "http_json", handler or fake_http_json)
    monkeypatch.setattr(common.time, "sleep", lambda _seconds: None)
    return provider, captured


def test_avatar_iv_payload_is_the_one_a_live_call_accepted(monkeypatch):
    """Sent as is to OpenRouter on 2026-10-09: accepted on the first call, 5.84 s clip."""
    provider, captured = _provider(monkeypatch)

    result = provider.generate_avatar_video(
        image_url=IMAGE,
        audio_url=AUDIO,
        text=MOTION,
        model=AVATAR_IV,
        resolution="720p",
        aspect_ratio="9:16",
        sync=False,
    )

    assert captured["payload"] == {
        "model": AVATAR_IV,
        "resolution": "720p",
        "aspect_ratio": "9:16",
        "input_references": [
            {"type": "image_url", "image_url": {"url": IMAGE}},
            {"type": "audio_url", "audio_url": {"url": AUDIO}},
        ],
        "provider": {"options": {"heygen": {"motion_prompt": MOTION}}},
    }
    assert (result["provider"], result["model"], result["status"]) == ("openrouter", AVATAR_IV, "submitted")
    assert result["request_id"] == "gen-vid-1"
    assert result["poll_url"] == "https://openrouter.ai/api/v1/videos/gen-vid-1"


def test_with_an_audio_track_no_script_is_sent(monkeypatch):
    """`prompt` is the script HeyGen voices when there is no audio: it must not carry the
    motion instruction, and without an instruction there are no provider options at all."""
    provider, captured = _provider(monkeypatch)

    provider.generate_avatar_video(image_url=IMAGE, audio_url=AUDIO, model=AVATAR_IV, sync=False)

    assert captured["payload"] == {
        "model": AVATAR_IV,
        "input_references": [
            {"type": "image_url", "image_url": {"url": IMAGE}},
            {"type": "audio_url", "audio_url": {"url": AUDIO}},
        ],
    }


def test_the_clip_follows_the_audio_so_durations_are_not_sent(monkeypatch):
    provider, captured = _provider(monkeypatch)

    provider.generate_avatar_video(
        image_url=IMAGE,
        audio_url=AUDIO,
        text=MOTION,
        model=AVATAR_IV,
        duration_seconds=5.84,
        duration=6,
        timeout_seconds=900,
        expressiveness="high",
        not_a_heygen_option=True,
        sync=False,
    )

    payload = captured["payload"]
    assert "duration" not in payload and "duration_seconds" not in payload and "timeout_seconds" not in payload
    # Only the options the model declares travel, under the provider's slug.
    assert payload["provider"] == {"options": {"heygen": {"expressiveness": "high", "motion_prompt": MOTION}}}


def test_without_audio_the_text_is_the_script_and_motion_is_explicit(monkeypatch):
    provider, captured = _provider(monkeypatch)

    provider.generate_avatar_video(
        image_url=IMAGE,
        text="Welcome to our product tour.",
        model=AVATAR_IV,
        voice_id="voice-1",
        motion_prompt="She waves at the camera.",
        sync=False,
    )

    assert captured["payload"] == {
        "model": AVATAR_IV,
        "prompt": "Welcome to our product tour.",
        "input_references": [{"type": "image_url", "image_url": {"url": IMAGE}}],
        "provider": {"options": {"heygen": {"voice_id": "voice-1", "motion_prompt": "She waves at the camera."}}},
    }


def test_the_provider_downloads_the_files_so_they_must_be_public_urls(monkeypatch):
    provider, _ = _provider(monkeypatch)

    with pytest.raises(ValueError, match="audio_url"):
        provider.generate_avatar_video(image_url=IMAGE, audio_path="fragment.mp3", model=AVATAR_IV)
    with pytest.raises(ValueError, match="image_url"):
        provider.generate_avatar_video(image_path="shot.png", audio_url=AUDIO, model=AVATAR_IV)
    with pytest.raises(ValueError, match="public http"):
        provider.generate_avatar_video(image_url=IMAGE, audio_url="data:audio/mpeg;base64,AAAA", model=AVATAR_IV)
    with pytest.raises(ValueError, match="image_url"):
        provider.generate_avatar_video(audio_url=AUDIO, model=AVATAR_IV)
    with pytest.raises(ValueError, match="audio_url or text"):
        provider.generate_avatar_video(image_url=IMAGE, model=AVATAR_IV)


def test_only_documented_avatar_models_and_their_formats(monkeypatch):
    provider, _ = _provider(monkeypatch)

    with pytest.raises(ValueError, match="heygen/avatar-iv"):
        provider.generate_avatar_video(image_url=IMAGE, audio_url=AUDIO, model="heygen/heygen-video-1")
    with pytest.raises(ValueError, match="resolution"):
        provider.generate_avatar_video(image_url=IMAGE, audio_url=AUDIO, model=AVATAR_IV, resolution="480p")
    with pytest.raises(ValueError, match="aspect_ratio"):
        provider.generate_avatar_video(image_url=IMAGE, audio_url=AUDIO, model=AVATAR_IV, aspect_ratio="4:3")


def test_a_finished_job_reports_the_video_and_the_real_cost(monkeypatch):
    provider, captured = _provider(monkeypatch)

    result = provider.generate_avatar_video(image_url=IMAGE, audio_url=AUDIO, text=MOTION, model=AVATAR_IV)

    assert result["status"] == "completed"
    assert result["video_url"] == "https://openrouter.ai/api/v1/videos/gen-vid-1/content?index=0"
    assert (result["cost_usd"], result["cost_is_estimated"]) == (0.291, False)
    assert captured["calls"][0] == ("POST", "https://openrouter.ai/api/v1/videos")


def test_the_public_dispatcher_routes_avatar_video_to_openrouter(monkeypatch):
    from easy_ai_clients import video

    _, captured = _provider(monkeypatch)

    assert "openrouter" in video.available_avatar_video_apis()
    result = video.avatar_video(
        image=IMAGE, audio=AUDIO, text=MOTION, api="openrouter", model=AVATAR_IV, sync=False
    )

    assert result["status"] == "submitted"
    assert captured["payload"]["provider"] == {"options": {"heygen": {"motion_prompt": MOTION}}}
