"""OpenRouter Seedance video payload and polling contract tests."""

from __future__ import annotations

import pytest


def _patch_http(monkeypatch, handler):
    from easy_ai_clients.video import _openrouter_video_common as common

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-or")
    monkeypatch.setattr(common, "http_json", handler)
    monkeypatch.setattr(common.time, "sleep", lambda _seconds: None)
    return common


def test_openrouter_text_to_video_payload_and_async_refs(monkeypatch):
    from easy_ai_clients.video._text_to_video._apis import openrouter as provider

    captured = {}

    def fake_http_json(method, url, headers=None, payload=None, timeout_seconds=None):
        captured.update(
            method=method,
            url=url,
            headers=headers,
            payload=payload,
            timeout_seconds=timeout_seconds,
        )
        return {
            "id": "job-text-1",
            "polling_url": "/api/v1/videos/job-text-1",
            "status": "pending",
        }

    _patch_http(monkeypatch, fake_http_json)

    result = provider.generate_text_to_video(
        "A cinematic orbit around a glass greenhouse.",
        duration=8,
        resolution="720p",
        aspect_ratio="16:9",
        generate_audio=False,
        seed=42,
        sync=False,
        timeout_seconds=30,
    )

    assert result["provider"] == "openrouter"
    assert result["model"] == "bytedance/seedance-2.0-mini"
    assert result["status"] == "submitted"
    assert result["request_id"] == "job-text-1"
    assert result["video_url"] is None
    assert result["cost_source"] == "unavailable"
    assert result["poll_url"] == "https://openrouter.ai/api/v1/videos/job-text-1"
    assert captured["method"] == "POST"
    assert captured["url"] == "https://openrouter.ai/api/v1/videos"
    assert captured["headers"]["Authorization"] == "Bearer test-or"
    assert captured["payload"] == {
        "model": "bytedance/seedance-2.0-mini",
        "prompt": "A cinematic orbit around a glass greenhouse.",
        "duration": 8,
        "resolution": "720p",
        "aspect_ratio": "16:9",
        "generate_audio": False,
        "seed": 42,
    }


def test_openrouter_text_to_video_multimodal_refs(monkeypatch):
    from easy_ai_clients.video._text_to_video._apis import openrouter as provider

    captured = {}

    def fake_http_json(method, url, headers=None, payload=None, timeout_seconds=None):
        captured["payload"] = payload
        return {"id": "job-refs-1", "status": "pending"}

    _patch_http(monkeypatch, fake_http_json)

    provider.generate_text_to_video(
        "Match the lighting of the first reference.",
        image_urls=["https://example.com/door.png"],
        video_urls=[{"url": "https://example.com/ref.mp4"}],
        audio_urls="https://example.com/bed.mp3",
        generate_audio=True,
        sync=False,
    )

    assert captured["payload"]["input_references"] == [
        {"type": "image_url", "image_url": {"url": "https://example.com/door.png"}},
        {"type": "video_url", "video_url": {"url": "https://example.com/ref.mp4"}},
        {"type": "audio_url", "audio_url": {"url": "https://example.com/bed.mp3"}},
    ]


def test_openrouter_image_to_video_first_and_last_frame(monkeypatch):
    from easy_ai_clients.video._image_to_video._apis import openrouter as provider

    captured = {}

    def fake_http_json(method, url, headers=None, payload=None, timeout_seconds=None):
        captured["payload"] = payload
        return {"id": "job-i2v-1", "status": "pending"}

    _patch_http(monkeypatch, fake_http_json)

    result = provider.generate_image_to_video(
        "Animate a slow dolly-in between the two frames.",
        image_url="https://example.com/first.png",
        end_image_url="https://example.com/last.png",
        duration=6,
        generate_audio=False,
        sync=False,
    )

    assert result["request_id"] == "job-i2v-1"
    assert captured["payload"]["frame_images"] == [
        {
            "type": "image_url",
            "image_url": {"url": "https://example.com/first.png"},
            "frame_type": "first_frame",
        },
        {
            "type": "image_url",
            "image_url": {"url": "https://example.com/last.png"},
            "frame_type": "last_frame",
        },
    ]
    assert captured["payload"]["generate_audio"] is False
    assert captured["payload"]["duration"] == 6
    assert "aspect_ratio" not in captured["payload"]


def test_openrouter_sync_poll_extracts_unsigned_url_and_usage_cost(monkeypatch):
    from easy_ai_clients.video._text_to_video._apis import openrouter as provider

    calls = []

    def fake_http_json(method, url, headers=None, payload=None, timeout_seconds=None):
        calls.append({"method": method, "url": url, "payload": payload})
        if method == "POST":
            return {
                "id": "job-sync-1",
                "polling_url": "/api/v1/videos/job-sync-1",
                "status": "pending",
            }
        return {
            "id": "job-sync-1",
            "status": "completed",
            "unsigned_urls": ["https://cdn.example/out.mp4"],
            "usage": {"cost": 0.12},
        }

    _patch_http(monkeypatch, fake_http_json)

    result = provider.generate_text_to_video(
        "A still product shot.",
        duration=4,
        sync=True,
        poll_interval_seconds=1,
    )

    assert result["status"] == "completed"
    assert result["request_id"] == "job-sync-1"
    assert result["video_url"] == "https://cdn.example/out.mp4"
    assert result["cost_usd"] == 0.12
    assert result["cost_is_estimated"] is False
    assert result["cost_source"] == "openrouter_video_usage"
    assert calls[0]["method"] == "POST"
    assert calls[1]["method"] == "GET"
    assert calls[1]["url"] == "https://openrouter.ai/api/v1/videos/job-sync-1"
    assert calls[1]["payload"] is None


def test_openrouter_get_status_and_result(monkeypatch):
    from easy_ai_clients.video._text_to_video._apis import openrouter as provider

    def fake_http_json(method, url, headers=None, payload=None, timeout_seconds=None):
        assert method == "GET"
        return {
            "id": "job-status-1",
            "status": "completed",
            "unsigned_urls": ["https://cdn.example/done.mp4"],
            "usage": {"cost": 0.05},
        }

    _patch_http(monkeypatch, fake_http_json)

    status = provider.get_generation_status("job-status-1")
    assert status["status"] == "completed"
    assert status["request_id"] == "job-status-1"

    result = provider.get_generation_result("job-status-1")
    assert result["video_url"] == "https://cdn.example/done.mp4"
    assert result["cost_usd"] == 0.05
    assert result["cost_source"] == "openrouter_video_usage"


def test_openrouter_requires_api_key(monkeypatch):
    from easy_ai_clients.video._text_to_video._apis import openrouter as provider

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        provider.generate_text_to_video("A quiet room.", sync=False)


def test_openrouter_duration_and_resolution_limits():
    from easy_ai_clients.video import _openrouter_video_common as common

    with pytest.raises(ValueError, match="4-15"):
        common.build_generation_payload(
            model=common.MODEL_2_0_MINI,
            prompt="too long",
            mode="text_to_video",
            kwargs={"duration": 16},
        )

    with pytest.raises(ValueError, match="1080p"):
        common.build_generation_payload(
            model=common.MODEL_2_5,
            prompt="uhd",
            mode="text_to_video",
            kwargs={"resolution": "1080p"},
        )

    with pytest.raises(ValueError, match="4K"):
        common.build_generation_payload(
            model=common.MODEL_2_0_FAST,
            prompt="uhd",
            mode="text_to_video",
            kwargs={"resolution": "4K"},
        )

    payload = common.build_generation_payload(
        model=common.MODEL_2_0,
        prompt="uhd full",
        mode="text_to_video",
        kwargs={"resolution": "4k", "duration": 15, "aspect_ratio": "auto"},
    )
    assert payload["resolution"] == "4K"
    assert payload["duration"] == 15
    assert "aspect_ratio" not in payload


def test_openrouter_extract_video_url_prefers_unsigned():
    from easy_ai_clients.video import _openrouter_video_common as common

    assert (
        common.extract_video_url(
            {"status": "completed", "unsigned_urls": ["https://cdn.example/a.mp4"]}
        )
        == "https://cdn.example/a.mp4"
    )
    assert (
        common.extract_video_url({"status": "completed"}, job_id="job-1")
        == "https://openrouter.ai/api/v1/videos/job-1/content?index=0"
    )


def test_openrouter_download_headers_only_for_openrouter_host():
    from easy_ai_clients.video import _openrouter_video_common as common

    assert common.download_headers_for_url("https://cdn.example/a.mp4", "test-or") == {}
    assert common.download_headers_for_url(
        "https://openrouter.ai/api/v1/videos/job-1/content?index=0",
        "test-or",
    ) == {"Authorization": "Bearer test-or"}


def test_openrouter_public_dispatcher_registers_api(monkeypatch):
    from easy_ai_clients import video

    assert "openrouter" in video.available_text_to_video_apis()
    assert "openrouter" in video.available_image_to_video_apis()

    def fake_http_json(method, url, headers=None, payload=None, timeout_seconds=None):
        return {"id": "job-disp-1", "status": "pending"}

    _patch_http(monkeypatch, fake_http_json)
    result = video.text_to_video("A still shot.", api="openrouter", sync=False)
    assert result["provider"] == "openrouter"
    assert result["request_id"] == "job-disp-1"
