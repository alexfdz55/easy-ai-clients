"""Video integration contract tests that avoid real provider calls."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_video_docs_match_dispatcher_provider_matrix():
    from easy_ai_clients import video

    matrix = {
        "text_to_video": video.available_text_to_video_apis(),
        "image_to_video": video.available_image_to_video_apis(),
        "video_to_video": video.available_video_to_video_apis(),
        "motion_control": video.available_motion_control_apis(),
        "avatar_video": video.available_avatar_video_apis(),
        "video_with_audio": video.available_video_with_audio_apis(),
        "create_avatar": video.available_create_avatar_apis(),
        "image_lipsync": video.available_image_lipsync_apis(),
        "video_lipsync": video.available_video_lipsync_apis(),
        "agent_video": video.available_agent_video_apis(),
        "translate": video.available_translate_apis(),
    }
    providers_doc = (ROOT / "docs" / "providers.md").read_text(encoding="utf-8")

    for operation, apis in matrix.items():
        for api in apis:
            doc_path = ROOT / "docs" / "video" / operation / f"{api}.md"
            assert doc_path.exists(), f"Missing video docs for {operation}/{api}"
            assert f"video/{operation}/{api}.md" in providers_doc


def test_video_env_vars_are_documented_and_templated():
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    configuration = (ROOT / "docs" / "configuration.md").read_text(encoding="utf-8")
    providers = (ROOT / "docs" / "providers.md").read_text(encoding="utf-8")

    for name in (
        "ARK_API_KEY",
        "FAL_KEY",
        "GOOGLE_API_KEY",
        "HEDRA_API_KEY",
        "RUNWAYML_API_SECRET",
        "HEYGEN_KEY",
        "REPLICATE_API_TOKEN",
    ):
        assert name in env_example
        assert name in configuration
        assert name in providers

    for name in ("HEYGEN_API_KEY", "HEYGEN_API_BASE"):
        assert name in env_example
        assert name in configuration

    assert "reserved" not in configuration.lower()


def test_video_dispatcher_public_exports_do_not_expose_private_helpers():
    from easy_ai_clients import video

    expected = {
        "generate",
        "text_to_video",
        "image_to_video",
        "video_to_video",
        "motion_control",
        "avatar_video",
        "video_with_audio",
        "create_avatar",
        "image_lipsync",
        "video_lipsync",
        "agent_video",
        "translate",
        "list_videos",
        "get_video",
        "delete_video",
        "list_lipsyncs",
        "get_lipsync",
        "update_lipsync",
        "delete_lipsync",
        "list_translations",
        "get_translation",
        "update_translation",
        "delete_translation",
        "get_translation_caption",
        "list_translation_languages",
        "create_proofread",
        "get_proofread",
        "generate_proofread",
        "get_proofread_srt",
        "update_proofread_srt",
        "list_avatars",
        "get_avatar",
        "delete_avatar",
        "create_avatar_consent",
        "list_avatar_looks",
        "get_avatar_look",
        "update_avatar_look",
        "delete_avatar_look",
        "list_brand_kits",
        "list_agent_sessions",
        "get_agent_session",
        "send_agent_message",
        "stop_agent_session",
        "list_agent_styles",
        "get_agent_resource",
        "list_agent_videos",
        "get_status",
        "get_result",
        "download",
        "available_apis",
        "available_text_to_video_apis",
        "available_image_to_video_apis",
        "available_video_to_video_apis",
        "available_motion_control_apis",
        "available_avatar_video_apis",
        "available_video_with_audio_apis",
        "available_create_avatar_apis",
        "available_image_lipsync_apis",
        "available_video_lipsync_apis",
        "available_agent_video_apis",
        "available_translate_apis",
        "available_video_resource_apis",
    }

    assert set(video.__all__) == expected
    assert all(not name.startswith("_") for name in video.__all__)


def test_google_text_to_video_payload_endpoint_and_cost(monkeypatch):
    from easy_ai_clients.video._text_to_video._apis import google as provider

    captured = {}

    def fake_http_json(method, url, headers=None, payload=None, timeout_seconds=None):
        captured.update(
            method=method,
            url=url,
            headers=headers,
            payload=payload,
            timeout_seconds=timeout_seconds,
        )
        return {"name": "operations/google-video-1"}

    monkeypatch.setenv("GOOGLE_API_KEY", "test-google")
    monkeypatch.setattr(provider, "http_json", fake_http_json)

    result = provider.generate_text_to_video(
        "A quiet product shot.",
        duration_seconds=4,
        resolution="720p",
        sync=False,
        timeout_seconds=30,
    )

    assert result["status"] == "submitted"
    assert result["request_id"] == "operations/google-video-1"
    assert result["cost_usd"] == pytest.approx(0.20)
    assert captured["method"] == "POST"
    assert captured["url"].endswith(
        "/models/veo-3.1-lite-generate-preview:predictLongRunning"
    )
    assert captured["headers"]["x-goog-api-key"] == "test-google"
    assert captured["payload"]["instances"] == [{"prompt": "A quiet product shot."}]
    assert captured["payload"]["parameters"]["durationSeconds"] == 4
    assert captured["payload"]["parameters"]["resolution"] == "720p"


def test_google_veo_official_pricing_snapshot_values():
    from easy_ai_clients.video._text_to_video._apis import google as provider

    fast_4k = provider._cost(  # noqa: SLF001
        "veo-3.1-fast-generate-preview",
        {"duration_seconds": 8, "resolution": "4k"},
    )
    veo2 = provider._cost(  # noqa: SLF001
        "veo-2.0-generate-001",
        {"duration_seconds": 5, "resolution": "720p", "number_of_videos": 2},
    )

    assert fast_4k["cost_usd"] == pytest.approx(2.40)
    assert veo2["cost_usd"] == pytest.approx(3.50)
    assert fast_4k["cost_is_estimated"] is True


def test_runway_text_to_video_payload_endpoint_and_cost(monkeypatch):
    from easy_ai_clients.video._text_to_video._apis import runway as provider

    captured = {}

    def fake_submit(endpoint, payload, api_key, timeout_seconds=None):
        captured.update(
            endpoint=endpoint,
            payload=payload,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
        )
        return {"id": "runway-task-1"}

    monkeypatch.setenv("RUNWAYML_API_SECRET", "test-runway")
    monkeypatch.setattr(provider, "runway_submit", fake_submit)

    result = provider.generate_text_to_video(
        "A calm mountain landscape.",
        model="gen4.5",
        duration=2,
        ratio="1280:720",
        seed=123,
        sync=False,
    )

    assert result["status"] == "submitted"
    assert result["request_id"] == "runway-task-1"
    assert result["cost_usd"] == pytest.approx(0.24)
    assert result["cost_credits"] == pytest.approx(24)
    assert captured["endpoint"] == "/v1/text_to_video"
    assert captured["api_key"] == "test-runway"
    assert captured["payload"] == {
        "model": "gen4.5",
        "promptText": "A calm mountain landscape.",
        "ratio": "1280:720",
        "duration": 2,
        "seed": 123,
    }


def test_runway_model_specific_defaults_and_future_parameter_forwarding():
    from easy_ai_clients.video._text_to_video._apis import runway as provider

    gen45_payload = provider._build_payload(  # noqa: SLF001
        "gen4.5",
        {"prompt": "A test.", "output_path": None},
        {"audio": True, "future_parameter": "ok"},
    )
    assert gen45_payload["audio"] is True
    assert gen45_payload["future_parameter"] == "ok"

    audio_cost = provider._cost(  # noqa: SLF001
        "veo3.1_fast",
        {"duration": 4, "audio": True},
    )
    assert audio_cost["cost_usd"] == pytest.approx(0.60)
    assert audio_cost["cost_credits"] == pytest.approx(60)

    default_audio_off_payload = provider._build_payload(  # noqa: SLF001
        "veo3.1_fast",
        {"prompt": "A test.", "output_path": None},
        {"duration": 4},
    )
    default_audio_off_cost = provider._cost(  # noqa: SLF001
        "veo3.1_fast",
        {"duration": 4},
    )
    assert default_audio_off_payload["audio"] is False
    assert default_audio_off_cost["cost_usd"] == pytest.approx(0.40)

    fractional_duration_payload = provider._build_payload(  # noqa: SLF001
        "gen4.5",
        {"prompt": "A test.", "output_path": None},
        {"duration": 2.5},
    )
    assert fractional_duration_payload["duration"] == 2.5


def test_falai_text_to_video_payload_endpoint_and_limits(monkeypatch):
    from easy_ai_clients.video._text_to_video._apis import falai as provider

    captured = {}

    def fake_submit(model, payload, api_key, timeout_seconds=None):
        captured.update(
            model=model,
            payload=payload,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
        )
        return {"request_id": "fal-request-1"}

    monkeypatch.setenv("FAL_KEY", "test-fal")
    monkeypatch.setattr(provider, "fal_submit", fake_submit)

    result = provider.generate_text_to_video(
        "A short establishing shot.",
        num_frames=81,
        frames_per_second=16,
        seed=123,
        resolution="720p",
        sync=False,
    )

    assert result["status"] == "submitted"
    assert result["request_id"] == "fal-request-1"
    assert result["cost_usd"] == pytest.approx(0.08)
    assert captured["model"] == provider.DEFAULT_MODEL
    assert captured["api_key"] == "test-fal"
    assert captured["payload"]["prompt"] == "A short establishing shot."
    assert captured["payload"]["num_frames"] == 81
    assert captured["payload"]["frames_per_second"] == 16

    future_payload = provider._build_payload(  # noqa: SLF001
        provider.DEFAULT_MODEL,
        {"prompt": "A test.", "output_path": None},
        {"num_frames": 162, "future_parameter": "ok"},
    )
    assert future_payload["num_frames"] == 162
    assert future_payload["future_parameter"] == "ok"


def test_falai_media_payloads_and_cost_snapshots():
    from easy_ai_clients.video._image_lipsync._apis import falai as image_lipsync
    from easy_ai_clients.video._image_to_video._apis import falai as image_to_video
    from easy_ai_clients.video._motion_control._apis import falai as motion_control
    from easy_ai_clients.video._video_lipsync._apis import falai as video_lipsync

    image_payload = image_to_video._build_payload(  # noqa: SLF001
        image_to_video.DEFAULT_MODEL,
        {
            "prompt": "Animate this.",
            "image": "https://example.com/image.png",
            "output_path": None,
        },
        {
            "duration": 10,
            "aspect_ratio": "9:16",
            "static_mask_url": "https://example.com/static-mask.png",
            "dynamic_masks": [{"mask_url": "https://example.com/dynamic-mask.png"}],
        },
    )
    motion_payload = motion_control._build_payload(  # noqa: SLF001
        motion_control.DEFAULT_MODEL,
        {
            "prompt": None,
            "image": "https://example.com/character.png",
            "video": "https://example.com/motion.mp4",
            "reference": None,
            "output_path": None,
        },
        {"character_orientation": "image"},
    )
    lipsync_payload = image_lipsync._build_payload(  # noqa: SLF001
        image_lipsync.DEFAULT_MODEL,
        {
            "image": "https://example.com/avatar.png",
            "audio": "https://example.com/voice.wav",
            "output_path": None,
        },
        {"resolution": "720p", "num_segments": 2},
    )
    video_lipsync_payload = video_lipsync._build_payload(  # noqa: SLF001
        video_lipsync.DEFAULT_MODEL,
        {
            "video": "https://example.com/source.mp4",
            "audio": "https://example.com/voice.wav",
            "output_path": None,
        },
        {"num_frames": 145, "resolution": "480p"},
    )

    assert image_payload["duration"] == "10"
    assert image_payload["static_mask_url"] == "https://example.com/static-mask.png"
    assert image_payload["dynamic_masks"] == [
        {"mask_url": "https://example.com/dynamic-mask.png"}
    ]
    assert image_to_video._cost(image_to_video.DEFAULT_MODEL, {"duration": 10})[  # noqa: SLF001
        "cost_usd"
    ] == pytest.approx(0.98)
    assert motion_payload["image_url"] == "https://example.com/character.png"
    assert motion_payload["video_url"] == "https://example.com/motion.mp4"
    assert motion_control._cost(  # noqa: SLF001
        motion_control.DEFAULT_MODEL,
        {"duration_seconds": 5},
    )["cost_usd"] == pytest.approx(0.35)
    assert lipsync_payload["resolution"] == "720p"
    assert image_lipsync._cost(  # noqa: SLF001
        image_lipsync.DEFAULT_MODEL,
        {"resolution": "720p", "num_segments": 2},
    )["cost_usd"] == pytest.approx(6.48)
    assert video_lipsync_payload["num_frames"] == 145
    assert video_lipsync._cost(  # noqa: SLF001
        video_lipsync.DEFAULT_MODEL,
        {"num_frames": 145},
    )["cost_usd"] == pytest.approx(1.74)


def test_video_to_video_new_provider_payloads_and_costs(monkeypatch):
    from easy_ai_clients.video._video_to_video._apis import falai, google, runway

    fal_payload = falai._build_payload(  # noqa: SLF001
        falai.DEFAULT_MODEL,
        {
            "prompt": "Use this reference motion.",
            "video": "https://example.com/source.mp4",
            "image": "https://example.com/ref.png",
            "reference": None,
            "output_path": None,
        },
        {"compute_seconds": 20},
    )
    assert fal_payload["video_url"] == "https://example.com/source.mp4"
    assert fal_payload["image_url"] == "https://example.com/ref.png"
    assert falai._cost(falai.DEFAULT_MODEL, {"compute_seconds": 20})[  # noqa: SLF001
        "cost_usd"
    ] == pytest.approx(0.0014)

    google_payload = google._build_payload(  # noqa: SLF001
        google.DEFAULT_MODEL,
        {
            "prompt": "Extend this shot.",
            "video": "https://example.com/source.mp4",
            "image": None,
            "reference": None,
            "output_path": None,
        },
        {"duration_seconds": 8, "resolution": "720p"},
    )
    assert google_payload["instances"][0]["video"] == {
        "uri": "https://example.com/source.mp4"
    }
    assert google_payload["parameters"]["durationSeconds"] == 8

    captured = {}

    def fake_submit(endpoint, payload, api_key, timeout_seconds=None):
        captured.update(endpoint=endpoint, payload=payload, api_key=api_key)
        return {"id": "runway-v2v-1"}

    monkeypatch.setenv("RUNWAYML_API_SECRET", "test-runway")
    monkeypatch.setattr(runway, "runway_submit", fake_submit)

    result = runway.generate_video_to_video(
        "Edit this source.",
        video_url="https://example.com/source.mp4",
        duration=4,
        sync=False,
    )

    assert result["request_id"] == "runway-v2v-1"
    assert result["cost_usd"] == pytest.approx(0.60)
    assert captured["endpoint"] == "/v1/video_to_video"
    assert captured["payload"]["model"] == "gen4_aleph"
    assert captured["payload"]["videoUri"] == "https://example.com/source.mp4"
    assert "duration" not in captured["payload"]


def test_avatar_video_runway_and_falai_payloads(monkeypatch):
    from easy_ai_clients.video._avatar_video._apis import falai, runway

    fal_payload = falai._build_payload(  # noqa: SLF001
        falai.DEFAULT_MODEL,
        {
            "image": "https://example.com/avatar.png",
            "audio": "https://example.com/voice.wav",
            "text": None,
            "output_path": None,
        },
        {"resolution": "720p", "num_segments": 1},
    )
    assert fal_payload["image_url"] == "https://example.com/avatar.png"
    assert fal_payload["audio_url"] == "https://example.com/voice.wav"
    assert falai._cost(  # noqa: SLF001
        falai.DEFAULT_MODEL,
        {"resolution": "720p", "num_segments": 1},
    )["cost_usd"] == pytest.approx(3.48)

    captured = {}

    def fake_submit(endpoint, payload, api_key, timeout_seconds=None):
        captured.update(endpoint=endpoint, payload=payload, api_key=api_key)
        return {"id": "runway-avatar-1"}

    monkeypatch.setenv("RUNWAYML_API_SECRET", "test-runway")
    monkeypatch.setattr(runway, "runway_submit", fake_submit)

    result = runway.generate_avatar_video(
        avatar="influencer",
        text="Hello there.",
        voice="default",
        duration_seconds=12,
        sync=False,
    )

    assert result["request_id"] == "runway-avatar-1"
    assert result["cost_credits"] == pytest.approx(6)
    assert captured["endpoint"] == "/v1/avatar_videos"
    assert captured["payload"]["model"] == "gwm1_avatars"
    assert captured["payload"]["avatar"]["type"] == "runway-preset"
    assert captured["payload"]["avatar"]["presetId"] == "influencer"
    assert captured["payload"]["speech"]["text"] == "Hello there."
    assert captured["payload"]["speech"]["voice"] == {"type": "preset", "presetId": "default"}


def test_avatar_video_approved_target_alias_payloads(monkeypatch):
    from easy_ai_clients.video._avatar_video._apis import falai, hedra, replicate

    omni_model = falai._selected_model({"model": "fal_omnihuman_v1_5"})  # noqa: SLF001
    omni_payload = falai._build_payload(  # noqa: SLF001
        omni_model,
        {
            "image": "https://example.com/avatar.png",
            "audio": "https://example.com/voice.mp3",
            "text": None,
            "output_path": None,
        },
        {"model": "fal_omnihuman_v1_5", "duration_seconds": 10},
    )
    veed_model = falai._selected_model({"model": "fal_veed_fabric_1_0"})  # noqa: SLF001
    veed_payload = falai._build_payload(  # noqa: SLF001
        veed_model,
        {
            "image": "https://example.com/avatar.png",
            "audio": "https://example.com/voice.mp3",
            "text": None,
            "output_path": None,
        },
        {"model": "fal_veed_fabric_1_0", "duration_seconds": 8},
    )

    assert omni_model == "fal-ai/bytedance/omnihuman/v1.5"
    assert omni_payload["image_url"] == "https://example.com/avatar.png"
    assert omni_payload["audio_url"] == "https://example.com/voice.mp3"
    assert omni_payload["resolution"] == "720p"
    assert omni_payload["turbo_mode"] is True
    assert "text" not in omni_payload
    assert falai._cost(omni_model, {"duration_seconds": 10})["cost_usd"] == pytest.approx(1.60)  # noqa: SLF001

    assert veed_model == "veed/fabric-1.0"
    assert veed_payload == {
        "image_url": "https://example.com/avatar.png",
        "audio_url": "https://example.com/voice.mp3",
        "resolution": "480p",
    }
    assert falai._cost(veed_model, {"duration_seconds": 8})["cost_usd"] == pytest.approx(0.64)  # noqa: SLF001

    monkeypatch.setenv("HEDRA_API_KEY", "test-hedra")
    _, hedra_model = hedra._selected_model({"model": "hedra_avatar"})  # noqa: SLF001
    hedra_payload = hedra._build_payload(  # noqa: SLF001
        hedra_model,
        None,
        None,
        None,
        None,
        None,
        {
            "model": "hedra_avatar",
            "start_keyframe_url": "https://example.com/avatar.png",
            "audio_id": "audio-id",
            "duration_seconds": 5,
            "aspect_ratio": "9:16",
            "resolution": "540p",
        },
    )

    assert hedra_model["id"] == "26f0fc66-152b-40ab-abed-76c43df99bc8"
    assert hedra_payload["start_keyframe_url"] == "https://example.com/avatar.png"
    assert hedra_payload["audio_id"] == "audio-id"
    assert hedra_payload["generated_video_inputs"]["aspect_ratio"] == "9:16"
    assert hedra_payload["generated_video_inputs"]["resolution"] == "540p"

    replicate_payload = replicate._build_payload(  # noqa: SLF001
        replicate._selected_model({"model": "replicate_prunaai_p_video_avatar"}),  # noqa: SLF001
        {
            "image": "data:image/png;base64,aW1hZ2U=",
            "audio": "data:audio/mpeg;base64,YXVkaW8=",
            "text": None,
            "output_path": None,
        },
        {
            "model": "replicate_prunaai_p_video_avatar",
            "duration_seconds": 5,
            "video_prompt": "The person is talking naturally.",
        },
    )
    assert replicate_payload["input"] == {
        "image": "data:image/png;base64,aW1hZ2U=",
        "audio": "data:audio/mpeg;base64,YXVkaW8=",
        "resolution": "720p",
        "video_prompt": "The person is talking naturally.",
    }
    assert replicate._cost({"duration_seconds": 5, "resolution": "720p"})["cost_usd"] == pytest.approx(0.125)  # noqa: SLF001


def test_heygen_photo_avatar_one_step_flow(monkeypatch):
    from easy_ai_clients.video import _heygen_common as common
    from easy_ai_clients.video._avatar_video._apis import heygen as provider

    calls = []

    def fake_request_json(method, path, payload=None, **kwargs):
        calls.append((method, path, payload))
        if path == "/v3/avatars":
            return {"data": {"avatar_item": {"id": "photo-avatar-1", "status": "completed"}}}
        if path == "/v3/videos":
            return {"data": {"video_id": "video-1", "status": "waiting"}}
        raise AssertionError(path)

    monkeypatch.setattr(common._heygen, "request_json", fake_request_json)

    result = provider.generate_avatar_video(
        image_url="https://example.com/portrait.jpg",
        audio_url="https://example.com/audio.mp3",
        model="heygen_photo_avatar",
        duration_seconds=10,
        sync=False,
    )

    assert result["model"] == "avatar_iv/photo_avatar"
    assert result["request_id"] == "video-1"
    assert result["avatar_id"] == "photo-avatar-1"
    assert result["cost_usd"] == pytest.approx(1.5)
    assert calls[0][1] == "/v3/avatars"
    assert calls[0][2]["type"] == "photo"
    assert calls[0][2]["file"] == {"type": "url", "url": "https://example.com/portrait.jpg"}
    assert calls[1][1] == "/v3/videos"
    assert calls[1][2]["type"] == "avatar"
    assert calls[1][2]["avatar_id"] == "photo-avatar-1"
    assert calls[1][2]["audio_url"] == "https://example.com/audio.mp3"
    assert calls[1][2]["resolution"] == "720p"
    assert calls[1][2]["aspect_ratio"] == "9:16"
    assert "duration_seconds" not in calls[1][2]


def test_replicate_avatar_video_submission_and_result(monkeypatch):
    from easy_ai_clients.video._avatar_video._apis import replicate as provider

    captured = []

    def fake_http_json(method, url, headers=None, payload=None, timeout_seconds=None):
        captured.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "payload": payload,
            }
        )
        if method == "POST":
            return {
                "id": "prediction-1",
                "status": "starting",
                "urls": {"get": "https://api.replicate.com/v1/predictions/prediction-1"},
            }
        return {
            "id": "prediction-1",
            "status": "succeeded",
            "output": "https://replicate.delivery/output.mp4",
            "urls": {"get": "https://api.replicate.com/v1/predictions/prediction-1"},
        }

    monkeypatch.setenv("REPLICATE_API_TOKEN", "test-replicate")
    monkeypatch.setattr(provider, "http_json", fake_http_json)

    result = provider.generate_avatar_video(
        image_url="data:image/png;base64,aW1hZ2U=",
        audio_url="data:audio/mpeg;base64,YXVkaW8=",
        model="replicate_prunaai_p_video_avatar",
        video_prompt="The person is talking naturally.",
        duration_seconds=4,
        sync=True,
    )

    assert result["provider"] == "replicate"
    assert result["model"] == "prunaai/p-video-avatar"
    assert result["status"] == "completed"
    assert result["request_id"] == "prediction-1"
    assert result["video_url"] == "https://replicate.delivery/output.mp4"
    assert result["cost_usd"] == pytest.approx(0.10)
    assert captured[0]["method"] == "POST"
    assert captured[0]["url"].endswith("/v1/models/prunaai/p-video-avatar/predictions")
    assert captured[0]["headers"]["Authorization"] == "Bearer test-replicate"
    assert captured[0]["headers"]["Prefer"] == "wait=5"
    assert captured[0]["payload"]["input"]["image"].startswith("data:image/png")
    assert captured[0]["payload"]["input"]["audio"].startswith("data:audio")
    assert captured[0]["payload"]["input"]["resolution"] == "720p"
    assert captured[0]["payload"]["input"]["video_prompt"] == "The person is talking naturally."
    assert captured[1]["method"] == "GET"


def test_hedra_text_image_and_avatar_payloads(monkeypatch):
    from easy_ai_clients.video import _hedra_common as common
    from easy_ai_clients.video._avatar_video._apis import hedra as avatar_provider
    from easy_ai_clients.video._image_to_video._apis import hedra as image_provider
    from easy_ai_clients.video._text_to_video._apis import hedra as text_provider

    captured = []

    def fake_hedra_json(method, path, api_key, payload=None, timeout_seconds=None):
        captured.append((method, path, payload))
        return {"id": f"hedra-{len(captured)}"}

    monkeypatch.setenv("HEDRA_API_KEY", "test-hedra")
    monkeypatch.setattr(common, "hedra_json", fake_hedra_json)

    text_result = text_provider.generate_text_to_video(
        "A compact product clip.",
        model="grok-video-t2v",
        duration_seconds=5,
        sync=False,
    )
    assert text_result["request_id"] == "hedra-1"
    assert text_result["cost_credits"] == pytest.approx(35)
    assert captured[-1][2]["ai_model_id"] == "827122cd-5fdd-4412-86f2-554f7bb8eef9"

    image_result = image_provider.generate_image_to_video(
        "Animate this.",
        image_url="https://example.com/image.png",
        duration_seconds=6,
        sync=False,
    )
    assert image_result["request_id"] == "hedra-2"
    assert captured[-1][2]["start_keyframe_url"] == "https://example.com/image.png"

    avatar_result = avatar_provider.generate_avatar_video(
        avatar="start-keyframe-id",
        audio_id="audio-id",
        duration_seconds=5,
        sync=False,
    )
    assert avatar_result["request_id"] == "hedra-3"
    assert captured[-1][2]["start_keyframe_id"] == "start-keyframe-id"
    assert captured[-1][2]["audio_id"] == "audio-id"


def test_hedra_v2v_motion_and_video_with_audio_payloads(monkeypatch):
    from easy_ai_clients.video import _hedra_common as common
    from easy_ai_clients.video._motion_control._apis import hedra as motion_provider
    from easy_ai_clients.video._video_to_video._apis import hedra as v2v_provider
    from easy_ai_clients.video._video_with_audio._apis import hedra as audio_provider

    captured = []

    def fake_hedra_json(method, path, api_key, payload=None, timeout_seconds=None):
        captured.append((method, path, payload))
        return {"id": f"hedra-new-{len(captured)}"}

    monkeypatch.setenv("HEDRA_API_KEY", "test-hedra")
    monkeypatch.setattr(common, "hedra_json", fake_hedra_json)

    v2v_result = v2v_provider.generate_video_to_video(
        "Edit the source video.",
        video_id="video-id",
        reference_image_ids=["ref-id"],
        model="kling-o3-standard-reference-v2v",
        duration_seconds=3,
        sync=False,
    )
    assert v2v_result["request_id"] == "hedra-new-1"
    assert v2v_result["cost_credits"] == pytest.approx(90)
    assert captured[-1][2]["type"] == "video_to_video"
    assert captured[-1][2]["video_id"] == "video-id"
    assert captured[-1][2]["reference_image_ids"] == ["ref-id"]

    motion_result = motion_provider.generate_motion_control(
        video_id="motion-id",
        start_keyframe_id="frame-id",
        character_orientation="video",
        duration_seconds=5,
        sync=False,
    )
    assert motion_result["request_id"] == "hedra-new-2"
    assert motion_result["cost_credits"] == pytest.approx(40)
    assert captured[-1][2]["type"] == "motion_control"
    assert captured[-1][2]["video_id"] == "motion-id"
    assert captured[-1][2]["start_keyframe_id"] == "frame-id"
    assert captured[-1][2]["generated_video_inputs"]["character_orientation"] == "video"

    audio_result = audio_provider.generate_video_with_audio(
        video_id="video-id",
        model="video-generation-model-id",
        prompt="Add soft room tone.",
        sync=False,
    )
    assert audio_result["request_id"] == "hedra-new-3"
    assert captured[-1][2]["type"] == "video_with_audio"
    assert captured[-1][2]["video_generation_model_id"] == "video-generation-model-id"
    assert captured[-1][2]["video_id"] == "video-id"


def test_runway_upload_create_avatar_and_avatar_video_custom_flow(monkeypatch, tmp_path):
    from easy_ai_clients.video import _shared
    from easy_ai_clients.video._avatar_video._apis import runway as avatar_provider
    from easy_ai_clients.video._create_avatar._apis import runway as create_provider

    upload_file = tmp_path / "source.mp4"
    upload_file.write_bytes(b"x" * 512)
    upload_captured = {}

    def fake_create_upload(endpoint, payload, api_key, timeout_seconds=None):
        upload_captured.update(endpoint=endpoint, payload=payload, api_key=api_key)
        return {
            "uploadUrl": "https://upload.example.com",
            "fields": {"key": "value"},
            "runwayUri": "runway://uploaded-source",
        }

    class FakeResponse:
        status_code = 204
        text = ""
        reason = "OK"

    def fake_post(url, data=None, files=None, timeout=None):
        upload_captured.update(url=url, data=data, files=list(files or {}), timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr(_shared, "runway_submit", fake_create_upload)
    monkeypatch.setattr(_shared.requests, "post", fake_post)
    assert _shared.runway_upload_file(str(upload_file), "runway-key") == "runway://uploaded-source"
    assert upload_captured["endpoint"] == "/v1/uploads"
    assert upload_captured["files"] == ["file"]

    avatar_captured = {}

    def fake_media_uri(path, url, path_name, url_name, api_key, timeout_seconds=None):
        avatar_captured["media"] = (path, url, path_name, url_name, api_key)
        return "runway://avatar-image"

    def fake_avatar_submit(endpoint, payload, api_key, timeout_seconds=None):
        avatar_captured.update(endpoint=endpoint, payload=payload, api_key=api_key)
        return {"id": "avatar-1", "status": "READY"}

    monkeypatch.setenv("RUNWAYML_API_SECRET", "test-runway")
    monkeypatch.setattr(create_provider, "runway_media_uri", fake_media_uri)
    monkeypatch.setattr(create_provider, "runway_submit", fake_avatar_submit)
    create_result = create_provider.create_avatar(
        image_path="avatar.png",
        name="Support Agent",
        voice="clara",
        personality="Helpful and concise.",
    )

    assert create_result["avatar_id"] == "avatar-1"
    assert avatar_captured["endpoint"] == "/v1/avatars"
    assert avatar_captured["payload"]["referenceImage"] == "runway://avatar-image"
    assert avatar_captured["payload"]["voice"] == {"type": "runway-live-preset", "presetId": "clara"}

    video_captured = {}
    monkeypatch.setattr(create_provider, "create_avatar", lambda **kwargs: {"avatar_id": "avatar-custom"})
    monkeypatch.setattr(avatar_provider, "runway_media_uri", lambda *args, **kwargs: None)

    def fake_video_submit(endpoint, payload, api_key, timeout_seconds=None):
        video_captured.update(endpoint=endpoint, payload=payload, api_key=api_key)
        return {"id": "runway-avatar-video-1"}

    monkeypatch.setattr(avatar_provider, "runway_submit", fake_video_submit)
    result = avatar_provider.generate_avatar_video(
        image_url="https://example.com/avatar.png",
        text="Hello.",
        voice="clara",
        create_avatar=True,
        name="Support Agent",
        personality="Helpful.",
        duration_seconds=6,
        sync=False,
    )

    assert result["request_id"] == "runway-avatar-video-1"
    assert video_captured["payload"]["avatar"] == {"type": "custom", "avatarId": "avatar-custom"}
    assert video_captured["payload"]["speech"]["voice"] == {"type": "preset", "presetId": "clara"}


def test_google_v2v_extension_rejects_unsupported_models_and_parameters():
    from easy_ai_clients.video._video_to_video._apis import google as provider

    prepared = {
        "prompt": "Extend this.",
        "video": "https://example.com/source.mp4",
        "image": None,
        "reference": None,
        "output_path": None,
    }

    with pytest.raises(ValueError, match="only for Veo 3.1"):
        provider._build_payload("veo-3.1-lite-generate-preview", prepared, {})  # noqa: SLF001
    with pytest.raises(ValueError, match="duration_seconds=8"):
        provider._build_payload(provider.DEFAULT_MODEL, prepared, {"duration_seconds": 4})  # noqa: SLF001
    with pytest.raises(ValueError, match="resolution='720p'"):
        provider._build_payload(provider.DEFAULT_MODEL, prepared, {"resolution": "1080p"})  # noqa: SLF001
    with pytest.raises(ValueError, match="number_of_videos=1"):
        provider._build_payload(provider.DEFAULT_MODEL, prepared, {"number_of_videos": 2})  # noqa: SLF001


def test_falai_pricing_estimate_uses_explicit_unit_quantity(monkeypatch):
    from easy_ai_clients.video import _falai_pricing as pricing
    from easy_ai_clients.video._text_to_video._apis import falai as provider

    captured = {}

    def fake_estimate(model, unit_quantity, api_key, timeout_seconds=None):
        captured.update(
            model=model,
            unit_quantity=unit_quantity,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
        )
        return {
            "cost_usd": 1.23,
            "cost_is_estimated": True,
            "cost_source": "fal_pricing_estimate_api",
            "cost_reason": "estimate",
        }

    monkeypatch.setattr(pricing, "require_env", lambda name, provider_name: "fal-key")
    monkeypatch.setattr(pricing, "fal_estimate_unit_price", fake_estimate)

    cost = provider._cost(  # noqa: SLF001
        provider.DEFAULT_MODEL,
        {"billing_unit_quantity": 2, "timeout_seconds": 10},
    )
    payload = provider._build_payload(  # noqa: SLF001
        provider.DEFAULT_MODEL,
        {"prompt": "A test.", "output_path": None},
        {"billing_unit_quantity": 2, "future_parameter": "ok"},
    )
    unavailable = provider._cost(  # noqa: SLF001
        "fal-ai/animatediff-sparsectrl-lcm",
        {},
    )

    assert cost["cost_usd"] == pytest.approx(1.23)
    assert cost["cost_source"] == "fal_pricing_estimate_api"
    assert captured["unit_quantity"] == pytest.approx(2.0)
    assert "billing_unit_quantity" not in payload
    assert payload["future_parameter"] == "ok"
    assert unavailable["cost_source"] == "unavailable"


def test_video_credentials_are_checked_before_network(monkeypatch):
    from easy_ai_clients.video._text_to_video._apis import google as provider

    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
        provider.generate_text_to_video(
            "A short product shot.",
            duration_seconds=4,
            resolution="720p",
            sync=False,
        )


def test_video_result_extractors_accept_provider_shapes():
    from easy_ai_clients.video._shared import extract_video_url, google_extract_video_url
    from easy_ai_clients.video._text_to_video._apis import runway

    assert extract_video_url({"video": {"url": "https://example.com/fal.mp4"}}) == (
        "https://example.com/fal.mp4"
    )
    assert extract_video_url({"output": [{"url": "https://example.com/output.mp4"}]}) == (
        "https://example.com/output.mp4"
    )
    assert google_extract_video_url(
        {
            "response": {
                "generateVideoResponse": {
                    "generatedSamples": [
                        {"video": {"uri": "https://example.com/google.mp4"}}
                    ]
                }
            }
        }
    ) == "https://example.com/google.mp4"
    assert runway._video_url({"output": [{"url": "https://example.com/runway.mp4"}]}) == (  # noqa: SLF001
        "https://example.com/runway.mp4"
    )
