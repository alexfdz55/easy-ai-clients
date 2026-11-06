"""HeyGen v3 contract tests that avoid live API calls."""

from __future__ import annotations

from types import SimpleNamespace

import pytest


def test_heygen_headers_use_x_api_key(monkeypatch):
    from easy_ai_clients import _heygen

    monkeypatch.setenv("HEYGEN_KEY", "test-heygen")

    headers = _heygen.api_headers()

    assert headers["x-api-key"] == "test-heygen"
    assert headers["X-HeyGen-Source"] == "easy-ai-clients"


def test_heygen_audio_speech_payload_and_download(monkeypatch):
    from easy_ai_clients.audio._synthesize._apis import heygen as provider

    captured = {}

    def fake_request_json(method, path, payload=None, **kwargs):
        captured.update(method=method, path=path, payload=payload)
        return {
            "data": {
                "audio_url": "https://cdn.example.com/speech.mp3",
                "duration": 1.0,
                "word_timestamps": [{"word": "Hello", "start": 0, "end": 0.5}],
                "request_id": "speech-1",
            }
        }

    monkeypatch.setattr(provider._heygen, "request_json", fake_request_json)
    monkeypatch.setattr(provider._heygen, "download_url", lambda *args, **kwargs: b"audio-bytes")
    monkeypatch.setattr(
        provider,
        "_finalize_synthesis_output",
        lambda chunks, cost_usd: {"cost_usd": cost_usd, "audio": object(), "words": {}},
    )

    result = provider.generate("Hello", voice="voice-1", language_code="en")

    assert result["request_id"] == "speech-1"
    assert captured["path"] == "/v3/voices/speech"
    assert captured["payload"]["text"] == "Hello"
    assert captured["payload"]["voice_id"] == "voice-1"
    assert captured["payload"]["language"] == "en"


def test_heygen_video_agent_payload(monkeypatch):
    from easy_ai_clients.video._agent_video._apis import heygen as provider

    captured = {}

    def fake_request_json(method, path, payload=None, **kwargs):
        captured.update(method=method, path=path, payload=payload)
        return {"data": {"session_id": "session-1", "status": "generating", "created_at": 1}}

    monkeypatch.setattr(provider._heygen, "request_json", fake_request_json)

    result = provider.generate_agent_video("Make a launch video", sync=False, style_id="style-1")

    assert result["provider"] == "heygen"
    assert result["request_id"] == "session-1"
    assert captured["path"] == "/v3/video-agents"
    assert captured["payload"] == {"prompt": "Make a launch video", "style_id": "style-1"}


def test_heygen_avatar_video_payload(monkeypatch):
    from easy_ai_clients.video import _heygen_common as common
    from easy_ai_clients.video._avatar_video._apis import heygen as provider

    captured = {}

    def fake_request_json(method, path, payload=None, **kwargs):
        captured.update(method=method, path=path, payload=payload)
        return {"data": {"video_id": "video-1", "status": "waiting"}}

    monkeypatch.setattr(common._heygen, "request_json", fake_request_json)

    result = provider.generate_avatar_video(
        avatar="avatar-1",
        text="Hello",
        voice_id="voice-1",
        sync=False,
    )

    assert result["request_id"] == "video-1"
    assert captured["path"] == "/v3/videos"
    assert captured["payload"]["type"] == "avatar"
    assert captured["payload"]["avatar_id"] == "avatar-1"
    assert captured["payload"]["script"] == "Hello"
    assert captured["payload"]["voice_id"] == "voice-1"


def test_heygen_translate_supports_webhook_and_on_submitted(monkeypatch):
    from easy_ai_clients.video._translate._apis import heygen as provider

    captured = {}
    receipts = []

    def fake_request_json(method, path, payload=None, **kwargs):
        captured.update(method=method, path=path, payload=payload)
        return {"data": {"video_translation_id": "translate-1", "status": "pending"}}

    monkeypatch.setattr(provider._heygen, "request_json", fake_request_json)

    result = provider.translate_video(
        video_url="https://example.com/source.mp4",
        output_languages=["Spanish"],
        sync=False,
        webhook_url="https://notice.example/heygen",
        on_submitted=receipts.append,
    )

    assert captured["path"] == "/v3/video-translations"
    assert captured["payload"]["callback_url"] == "https://notice.example/heygen"
    assert "webhook_url" not in captured["payload"]
    assert receipts and receipts[0]["data"]["video_translation_id"] == "translate-1"
    assert result["request_id"] == "translate-1"


def test_heygen_translate_submission_skips_post_and_waits(monkeypatch):
    from easy_ai_clients.video._translate._apis import heygen as provider

    calls = []

    def fake_request_json(method, path, payload=None, **kwargs):
        calls.append((method, path))
        if method == "POST":
            raise AssertionError("submit POST should not run when submission is provided")
        return {
            "data": {
                "video_translation_id": "translate-2",
                "status": "completed",
                "video_url": "https://cdn.example.com/translated.mp4",
            }
        }

    monkeypatch.setattr(provider._heygen, "request_json", fake_request_json)
    monkeypatch.setattr(provider._heygen, "wait_for_result", lambda getter, **kwargs: getter())

    result = provider.translate_video(
        sync=True,
        submission={"data": {"video_translation_id": "translate-2", "status": "pending"}},
    )

    assert calls == [("GET", "https://api.heygen.com/v3/video-translations/translate-2")]
    assert result["request_id"] == "translate-2"
    assert result["video_url"] == "https://cdn.example.com/translated.mp4"


def test_public_dispatcher_propagates_heygen_translate_on_submitted_exception(monkeypatch):
    from easy_ai_clients import video
    from easy_ai_clients.video._translate._apis import heygen as provider

    expected = RuntimeError("stop translation after submit")

    monkeypatch.setattr(
        provider._heygen,
        "request_json",
        lambda method, path, payload=None, **kwargs: {"data": {"video_translation_id": "translate-stop-1", "status": "pending"}},
    )

    with pytest.raises(RuntimeError) as raised:
        video.translate(
            video="https://example.com/source.mp4",
            output_languages=["Spanish"],
            api="heygen",
            sync=False,
            on_submitted=lambda _receipt: (_ for _ in ()).throw(expected),
        )

    assert raised.value is expected


def test_heygen_lipsync_payload_and_resource_delete_guard(monkeypatch):
    from easy_ai_clients import video
    from easy_ai_clients.video import _heygen_common as common
    from easy_ai_clients.video._resources._apis import heygen as resources
    from easy_ai_clients.video._video_lipsync._apis import heygen as provider

    captured = {}

    def fake_request_json(method, path, payload=None, **kwargs):
        captured.update(method=method, path=path, payload=payload)
        return {"data": {"lipsync_id": "lip-1", "status": "pending"}}

    monkeypatch.setattr(common._heygen, "request_json", fake_request_json)
    result = provider.generate_video_lipsync(
        video_url="https://example.com/video.mp4",
        audio_url="https://example.com/audio.mp3",
        sync=False,
    )

    assert result["request_id"] == "lip-1"
    assert captured["path"] == "/v3/lipsyncs"
    assert captured["payload"]["video"] == {"type": "url", "url": "https://example.com/video.mp4"}
    assert captured["payload"]["audio"] == {"type": "url", "url": "https://example.com/audio.mp3"}

    guarded = video.delete_lipsync("lip-1", api="heygen")
    assert guarded["status"] == "failed"
    assert "confirm=True" in guarded["warnings"]

    monkeypatch.setattr(resources._heygen, "request_json", lambda method, path, **kwargs: {"data": {"id": "lip-1"}})
    deleted = video.delete_lipsync("lip-1", api="heygen", confirm=True)
    assert deleted["data"]["id"] == "lip-1"


def test_heygen_media_upload_uses_multipart(monkeypatch, tmp_path):
    from easy_ai_clients import _heygen, media

    upload = tmp_path / "asset.txt"
    upload.write_text("hello", encoding="utf-8")
    captured = {}

    class Response:
        status_code = 200
        content = b"{}"
        reason = "OK"
        headers = {}
        text = "{}"

        def json(self):
            return {"data": {"asset_id": "asset-1", "url": "https://cdn.example.com/a.txt"}}

    def fake_post(url, headers=None, files=None, timeout=None):
        captured.update(url=url, headers=headers, files=files, timeout=timeout)
        return Response()

    monkeypatch.setenv("HEYGEN_KEY", "test-heygen")
    monkeypatch.setattr(_heygen.requests, "post", fake_post)

    result = media.upload_asset(str(upload), api="heygen")

    assert result["data"]["asset_id"] == "asset-1"
    assert captured["url"].endswith("/v3/assets")
    assert captured["files"]["file"][0] == "asset.txt"


def test_heygen_account_and_webhooks_dispatch(monkeypatch):
    from easy_ai_clients import _heygen, account, webhooks

    calls = []

    def fake_request_json(method, path, payload=None, params=None, **kwargs):
        calls.append(SimpleNamespace(method=method, path=path, payload=payload, params=params))
        return {"data": {"ok": True}}

    monkeypatch.setattr(_heygen, "request_json", fake_request_json)

    assert account.get_current_user(api="heygen")["data"]["ok"] is True
    assert webhooks.create_endpoint("https://example.com/hook", api="heygen", events=["video_agent.success"])["data"]["ok"] is True
    assert calls[0].path == "/v3/users/me"
    assert calls[1].path == "/v3/webhooks/endpoints"
    assert calls[1].payload["url"] == "https://example.com/hook"


def test_heygen_local_asset_input_base64(tmp_path):
    from easy_ai_clients import _heygen

    image = tmp_path / "image.png"
    image.write_bytes(b"png-data")

    payload = _heygen.asset_input(str(image), field_name="image")

    assert payload["type"] == "base64"
    assert payload["media_type"] == "image/png"
    assert payload["data"]
