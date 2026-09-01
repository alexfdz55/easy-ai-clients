"""BytePlus ModelArk Seedance 2.x payload and polling contract tests."""

from __future__ import annotations

import pytest


def _patch_http(monkeypatch, handler):
    from easy_ai_clients.video import _byteplus_common as common

    monkeypatch.setenv("ARK_API_KEY", "test-ark")
    monkeypatch.setattr(common, "http_json", handler)
    monkeypatch.setattr(common.time, "sleep", lambda _seconds: None)
    return common


def test_byteplus_text_to_video_payload_and_async_refs(monkeypatch):
    from easy_ai_clients.video._text_to_video._apis import byteplus as provider

    captured = {}

    def fake_http_json(method, url, headers=None, payload=None, timeout_seconds=None):
        captured.update(
            method=method,
            url=url,
            headers=headers,
            payload=payload,
            timeout_seconds=timeout_seconds,
        )
        return {"id": "cgt-text-1", "status": "queued"}

    _patch_http(monkeypatch, fake_http_json)

    result = provider.generate_text_to_video(
        "A cinematic orbit around a glass greenhouse.",
        duration=8,
        resolution="720p",
        ratio="16:9",
        seed=42,
        watermark=False,
        camera_fixed=False,
        sync=False,
        timeout_seconds=30,
    )

    assert result["provider"] == "byteplus"
    assert result["model"] == "dreamina-seedance-2-5-260628"
    assert result["status"] == "submitted"
    assert result["request_id"] == "cgt-text-1"
    assert result["video_url"] is None
    assert result["cost_source"] == "unavailable"
    assert result["task_url"].endswith("/contents/generations/tasks/cgt-text-1")
    assert captured["method"] == "POST"
    assert captured["url"] == (
        "https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks"
    )
    assert captured["headers"]["Authorization"] == "Bearer test-ark"
    assert captured["payload"]["model"] == "dreamina-seedance-2-5-260628"
    assert captured["payload"]["content"] == [
        {"type": "text", "text": "A cinematic orbit around a glass greenhouse."}
    ]
    assert captured["payload"]["generate_audio"] is True
    assert captured["payload"]["duration"] == 8
    assert captured["payload"]["resolution"] == "720p"
    assert captured["payload"]["ratio"] == "16:9"
    assert captured["payload"]["seed"] == 42
    assert captured["payload"]["watermark"] is False
    assert captured["payload"]["camera_fixed"] is False
    assert "omni_reference_task_type" not in captured["payload"]


def test_byteplus_text_to_video_multimodal_refs(monkeypatch):
    from easy_ai_clients.video._text_to_video._apis import byteplus as provider

    captured = {}

    def fake_http_json(method, url, headers=None, payload=None, timeout_seconds=None):
        captured["payload"] = payload
        return {"id": "cgt-refs-1", "status": "queued"}

    _patch_http(monkeypatch, fake_http_json)

    provider.generate_text_to_video(
        "Match the lighting of @Image1 and the motion of @Video1.",
        image_urls=["https://example.com/door.png"],
        video_urls=[{"url": "https://example.com/ref.mp4", "role": "reference_video"}],
        audio_urls="https://example.com/bed.mp3",
        generate_audio=True,
        sync=False,
    )

    types = [item["type"] for item in captured["payload"]["content"]]
    assert types == ["text", "image_url", "video_url", "audio_url"]
    assert captured["payload"]["content"][1]["role"] == "reference_image"
    assert captured["payload"]["content"][1]["image_url"]["url"] == "https://example.com/door.png"
    assert captured["payload"]["content"][2]["video_url"]["url"] == "https://example.com/ref.mp4"
    assert captured["payload"]["content"][3]["audio_url"]["url"] == "https://example.com/bed.mp3"
    assert captured["payload"]["content"][3]["role"] == "reference_audio"


def test_byteplus_image_to_video_first_and_last_frame(monkeypatch):
    from easy_ai_clients.video._image_to_video._apis import byteplus as provider

    captured = {}

    def fake_http_json(method, url, headers=None, payload=None, timeout_seconds=None):
        captured["payload"] = payload
        return {"id": "cgt-i2v-1", "status": "queued"}

    _patch_http(monkeypatch, fake_http_json)

    result = provider.generate_image_to_video(
        "Animate a slow dolly-in between the two frames.",
        image_url="https://example.com/first.png",
        end_image_url="https://example.com/last.png",
        duration=6,
        generate_audio=False,
        sync=False,
    )

    assert result["request_id"] == "cgt-i2v-1"
    content = captured["payload"]["content"]
    assert content[0]["type"] == "text"
    assert content[1] == {
        "type": "image_url",
        "image_url": {"url": "https://example.com/first.png"},
        "role": "first_frame",
    }
    assert content[2] == {
        "type": "image_url",
        "image_url": {"url": "https://example.com/last.png"},
        "role": "last_frame",
    }
    assert captured["payload"]["generate_audio"] is False
    assert captured["payload"]["ratio"] == "adaptive"
    assert captured["payload"]["duration"] == 6


def test_byteplus_video_to_video_edit_and_extend(monkeypatch):
    from easy_ai_clients.video._video_to_video._apis import byteplus as provider

    captured = {}

    def fake_http_json(method, url, headers=None, payload=None, timeout_seconds=None):
        captured["payload"] = payload
        return {"id": "cgt-v2v-1", "status": "queued"}

    _patch_http(monkeypatch, fake_http_json)

    provider.generate_video_to_video(
        "Replace the background with a rainy Tokyo street.",
        video_url="https://example.com/source.mp4",
        image_url="https://example.com/bg.png",
        sync=False,
    )

    payload = captured["payload"]
    assert payload["omni_reference_task_type"] == "edit"
    assert payload["duration"] == -1
    assert payload["ratio"] == "adaptive"
    assert payload["content"][1]["role"] == "reference_video"
    assert payload["content"][2]["role"] == "reference_image"

    provider.generate_video_to_video(
        "Extend the shot as the camera continues down the hallway.",
        video_url="https://example.com/source.mp4",
        extend=True,
        duration=11,
        sync=False,
    )
    assert captured["payload"]["omni_reference_task_type"] == "extend"
    assert captured["payload"]["duration"] == 11


def test_byteplus_sync_poll_extracts_content_video_url(monkeypatch):
    from easy_ai_clients.video._text_to_video._apis import byteplus as provider

    calls = []

    def fake_http_json(method, url, headers=None, payload=None, timeout_seconds=None):
        calls.append({"method": method, "url": url, "payload": payload})
        if method == "POST":
            return {"id": "cgt-sync-1", "status": "queued"}
        return {
            "id": "cgt-sync-1",
            "status": "succeeded",
            "content": {"video_url": "https://cdn.example/out.mp4"},
        }

    _patch_http(monkeypatch, fake_http_json)

    result = provider.generate_text_to_video(
        "A still product shot.",
        duration=4,
        sync=True,
        poll_interval_seconds=1,
    )

    assert result["status"] == "completed"
    assert result["request_id"] == "cgt-sync-1"
    assert result["video_url"] == "https://cdn.example/out.mp4"
    assert calls[0]["method"] == "POST"
    assert calls[1]["method"] == "GET"
    assert calls[1]["url"].endswith("/contents/generations/tasks/cgt-sync-1")
    assert calls[1]["payload"] is None


def test_byteplus_get_status_and_result(monkeypatch):
    from easy_ai_clients.video._text_to_video._apis import byteplus as provider

    def fake_http_json(method, url, headers=None, payload=None, timeout_seconds=None):
        assert method == "GET"
        return {
            "id": "cgt-status-1",
            "status": "succeeded",
            "content": {"video_url": "https://cdn.example/done.mp4"},
        }

    _patch_http(monkeypatch, fake_http_json)

    status = provider.get_generation_status("cgt-status-1")
    assert status["status"] == "completed"
    assert status["request_id"] == "cgt-status-1"
    assert status["task_url"].endswith("/contents/generations/tasks/cgt-status-1")

    result = provider.get_generation_result("cgt-status-1")
    assert result["video_url"] == "https://cdn.example/done.mp4"
    assert result["status"] == "completed"


def test_byteplus_base_url_override(monkeypatch):
    from easy_ai_clients.video._text_to_video._apis import byteplus as provider

    captured = {}

    def fake_http_json(method, url, headers=None, payload=None, timeout_seconds=None):
        captured["url"] = url
        return {"id": "cgt-base-1", "status": "queued"}

    monkeypatch.setenv("ARK_BASE_URL", "https://ark.example.test/api/v3/")
    _patch_http(monkeypatch, fake_http_json)

    provider.generate_text_to_video("A quiet room.", sync=False)
    assert captured["url"] == "https://ark.example.test/api/v3/contents/generations/tasks"


def test_byteplus_requires_api_key(monkeypatch):
    from easy_ai_clients.video._text_to_video._apis import byteplus as provider

    monkeypatch.delenv("ARK_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ARK_API_KEY"):
        provider.generate_text_to_video("A quiet room.", sync=False)


def test_byteplus_duration_and_resolution_limits():
    from easy_ai_clients.video import _byteplus_common as common

    with pytest.raises(ValueError, match="4-30"):
        common.build_generation_payload(
            model=common.MODEL_2_5,
            prompt="too long",
            mode="text_to_video",
            kwargs={"duration": 31},
        )

    with pytest.raises(ValueError, match="4k"):
        common.build_generation_payload(
            model=common.MODEL_2_5,
            prompt="uhd",
            mode="text_to_video",
            kwargs={"resolution": "4K"},
        )

    with pytest.raises(ValueError, match="1080p"):
        common.build_generation_payload(
            model=common.MODEL_2_0_FAST,
            prompt="hd",
            mode="text_to_video",
            kwargs={"resolution": "1080p"},
        )

    payload = common.build_generation_payload(
        model=common.MODEL_2_0,
        prompt="uhd full",
        mode="text_to_video",
        kwargs={"resolution": "4K", "duration": 15},
    )
    assert payload["resolution"] == "4k"
    assert payload["duration"] == 15


def test_byteplus_extract_video_url_from_content():
    from easy_ai_clients.video import _byteplus_common as common

    assert common.extract_video_url(
        {"status": "succeeded", "content": {"video_url": "https://cdn.example/a.mp4"}}
    ) == "https://cdn.example/a.mp4"
    assert common.extract_video_url(
        {"result": {"content": {"video_url": "https://cdn.example/b.mp4"}}}
    ) == "https://cdn.example/b.mp4"


def test_byteplus_public_dispatcher_registers_api(monkeypatch):
    from easy_ai_clients import video

    assert "byteplus" in video.available_text_to_video_apis()
    assert "byteplus" in video.available_image_to_video_apis()
    assert "byteplus" in video.available_video_to_video_apis()

    def fake_http_json(method, url, headers=None, payload=None, timeout_seconds=None):
        return {"id": "cgt-disp-1", "status": "queued"}

    _patch_http(monkeypatch, fake_http_json)
    result = video.text_to_video("A still shot.", api="byteplus", sync=False)
    assert result["provider"] == "byteplus"
    assert result["request_id"] == "cgt-disp-1"
