"""Async video reference preservation and pass-through tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest


def test_falai_image_to_video_sync_uses_returned_urls_and_preserves_submission(monkeypatch):
    from easy_ai_clients.video._image_to_video._apis import falai as provider

    captured = {}

    def fake_submit(model, payload, api_key, timeout_seconds=None):
        return {
            "request_id": "fal-sync-1",
            "status_url": "https://queue.example/status/fal-sync-1",
            "response_url": "https://queue.example/result/fal-sync-1",
        }

    def fake_wait(model, request_id, api_key, **kwargs):
        captured.update(model=model, request_id=request_id, api_key=api_key, kwargs=kwargs)
        return {
            "status": {"status": "COMPLETED"},
            "response": {"video": {"url": "https://cdn.example/video.mp4"}},
        }

    monkeypatch.setenv("FAL_KEY", "fal-key")
    monkeypatch.setattr(provider, "fal_submit", fake_submit)
    monkeypatch.setattr(provider, "fal_wait_for_result", fake_wait)

    result = provider.generate_image_to_video(
        "Slow push-in.",
        image_url="https://example.com/input.png",
        model="fal-ai/future/image-to-video",
        sync=True,
    )

    assert captured["kwargs"]["status_url"] == "https://queue.example/status/fal-sync-1"
    assert captured["kwargs"]["response_url"] == "https://queue.example/result/fal-sync-1"
    assert result["video_url"] == "https://cdn.example/video.mp4"
    assert result["status_url"] == "https://queue.example/status/fal-sync-1"
    assert result["response_url"] == "https://queue.example/result/fal-sync-1"
    assert result["raw_response"]["submission"]["request_id"] == "fal-sync-1"
    assert result["raw_response"]["response"]["video"]["url"] == "https://cdn.example/video.mp4"


def test_falai_image_to_video_async_returns_provider_urls(monkeypatch):
    from easy_ai_clients.video._image_to_video._apis import falai as provider

    monkeypatch.setenv("FAL_KEY", "fal-key")
    monkeypatch.setattr(
        provider,
        "fal_submit",
        lambda *args, **kwargs: {
            "request_id": "fal-async-1",
            "status_url": "https://queue.example/status/fal-async-1",
            "response_url": "https://queue.example/result/fal-async-1",
        },
    )

    result = provider.generate_image_to_video(
        "Animate.",
        image_url="https://example.com/input.png",
        sync=False,
    )

    assert result["status"] == "submitted"
    assert result["request_id"] == "fal-async-1"
    assert result["status_url"] == "https://queue.example/status/fal-async-1"
    assert result["response_url"] == "https://queue.example/result/fal-async-1"


def test_public_falai_helpers_pass_explicit_urls(monkeypatch):
    from easy_ai_clients import video
    from easy_ai_clients.video._image_to_video._apis import falai as provider

    captured = {}

    def fake_status(model, request_id, api_key, timeout_seconds=None, status_url=None, poll_url=None):
        captured["status_url"] = status_url
        return {"status": "IN_PROGRESS"}

    def fake_result(
        model,
        request_id,
        api_key,
        timeout_seconds=None,
        response_url=None,
        result_url=None,
    ):
        captured["response_url"] = response_url
        return {"video": {"url": "https://cdn.example/final.mp4"}}

    monkeypatch.setenv("FAL_KEY", "fal-key")
    monkeypatch.setattr(provider, "fal_get_status", fake_status)
    monkeypatch.setattr(provider, "fal_get_result", fake_result)

    status = video.get_status(
        "image_to_video",
        "fal-1",
        api="falai",
        model="fal-ai/any/image-to-video",
        status_url="https://queue.example/exact-status",
    )
    result = video.get_result(
        "image_to_video",
        "fal-1",
        api="falai",
        model="fal-ai/any/image-to-video",
        response_url="https://queue.example/exact-result",
    )

    assert status["status"] == "running"
    assert captured["status_url"] == "https://queue.example/exact-status"
    assert captured["response_url"] == "https://queue.example/exact-result"
    assert result["video_url"] == "https://cdn.example/final.mp4"


def test_avatar_falai_helpers_resolve_model_aliases(monkeypatch):
    from easy_ai_clients import video
    from easy_ai_clients.video._avatar_video._apis import falai as provider

    captured = []

    def fake_status(model, request_id, api_key, timeout_seconds=None, status_url=None, poll_url=None):
        captured.append(model)
        return {"status": "COMPLETED"}

    def fake_result(
        model,
        request_id,
        api_key,
        timeout_seconds=None,
        response_url=None,
        result_url=None,
    ):
        captured.append(model)
        return {"video": {"url": "https://cdn.example/avatar.mp4"}}

    monkeypatch.setenv("FAL_KEY", "fal-key")
    monkeypatch.setattr(provider, "fal_get_status", fake_status)
    monkeypatch.setattr(provider, "fal_get_result", fake_result)

    status = video.get_status(
        "avatar_video",
        "fal-avatar-1",
        api="falai",
        model="fal_omnihuman_v1_5",
    )
    result = video.get_result(
        "avatar_video",
        "fal-avatar-1",
        api="falai",
        model="fal_omnihuman_v1_5",
    )

    assert status["model"] == "fal-ai/bytedance/omnihuman/v1.5"
    assert result["model"] == "fal-ai/bytedance/omnihuman/v1.5"
    assert result["video_url"] == "https://cdn.example/avatar.mp4"
    assert captured == [
        "fal-ai/bytedance/omnihuman/v1.5",
        "fal-ai/bytedance/omnihuman/v1.5",
    ]


def test_falai_helpers_fall_back_to_reconstructed_urls(monkeypatch):
    from easy_ai_clients.video import _shared

    captured = []

    def fake_http_json(method, url, headers=None, payload=None, timeout_seconds=None):
        captured.append(url)
        return {"status": "COMPLETED", "video": {"url": "https://cdn.example/out.mp4"}}

    monkeypatch.setattr(_shared, "http_json", fake_http_json)

    _shared.fal_get_status("fal-ai/future/video", "req 1", "key")
    _shared.fal_get_result("fal-ai/future/video", "req 1", "key")

    assert captured[0].endswith("/fal-ai/future/video/requests/req%201/status?logs=1")
    assert captured[1].endswith("/fal-ai/future/video/requests/req%201/response")


def test_provider_poll_urls_are_not_shadowed_by_reconstructed_fallbacks():
    from easy_ai_clients.video import _shared
    from easy_ai_clients.video import _together_common as together
    from easy_ai_clients.video import _xai_video_common as xai

    fal_refs = _shared.fal_async_refs(
        {"poll_url": "https://queue.example/poll/fal-1"},
        "fal-ai/future/video",
        "fal-1",
    )
    runway_refs = _shared.runway_async_refs(
        {"poll_url": "https://api.dev.runwayml.com/v1/tasks/runway-1/poll"},
        "runway-1",
    )
    together_refs = together.async_refs(
        {"poll_url": "https://api.together.xyz/v1/videos/together-1/poll"},
        "together-1",
    )
    xai_refs = xai.async_refs(
        {"poll_url": "https://api.x.ai/v1/videos/xai-1/poll"},
        "xai-1",
    )

    assert fal_refs["poll_url"] == "https://queue.example/poll/fal-1"
    assert "status_url" not in fal_refs
    assert runway_refs["poll_url"] == "https://api.dev.runwayml.com/v1/tasks/runway-1/poll"
    assert "task_url" not in runway_refs
    assert together_refs["poll_url"] == "https://api.together.xyz/v1/videos/together-1/poll"
    assert "task_url" not in together_refs
    assert xai_refs["poll_url"] == "https://api.x.ai/v1/videos/xai-1/poll"
    assert "task_url" not in xai_refs


def test_falai_image_to_video_provider_native_kwargs_are_forwarded():
    from easy_ai_clients.video._image_to_video._apis import falai as provider

    payload = provider._build_payload(  # noqa: SLF001
        "fal-ai/ltx-2-19b/distilled/image-to-video",
        {
            "prompt": "Animate this.",
            "image": "https://example.com/input.png",
            "output_path": None,
        },
        {
            "camera_lora": "push_in",
            "use_multiscale": True,
            "video_output_type": "mp4",
            "interpolation_direction": "forward",
        },
    )

    assert payload["camera_lora"] == "push_in"
    assert payload["use_multiscale"] is True
    assert payload["video_output_type"] == "mp4"
    assert payload["interpolation_direction"] == "forward"


FALAI_OPERATION_CASES = [
    (
        "easy_ai_clients.video._text_to_video._apis.falai",
        "generate_text_to_video",
        {"prompt": "A shot."},
    ),
    (
        "easy_ai_clients.video._image_to_video._apis.falai",
        "generate_image_to_video",
        {"prompt": "A shot.", "image_url": "https://example.com/image.png"},
    ),
    (
        "easy_ai_clients.video._video_to_video._apis.falai",
        "generate_video_to_video",
        {"prompt": "A shot.", "video_url": "https://example.com/source.mp4"},
    ),
    (
        "easy_ai_clients.video._motion_control._apis.falai",
        "generate_motion_control",
        {
            "image_url": "https://example.com/character.png",
            "video_url": "https://example.com/motion.mp4",
            "character_orientation": "image",
            "duration_seconds": 5,
        },
    ),
    (
        "easy_ai_clients.video._avatar_video._apis.falai",
        "generate_avatar_video",
        {
            "image_url": "https://example.com/avatar.png",
            "audio_url": "https://example.com/audio.wav",
        },
    ),
    (
        "easy_ai_clients.video._image_lipsync._apis.falai",
        "generate_image_lipsync",
        {
            "image_url": "https://example.com/avatar.png",
            "audio_url": "https://example.com/audio.wav",
        },
    ),
    (
        "easy_ai_clients.video._video_lipsync._apis.falai",
        "generate_video_lipsync",
        {
            "video_url": "https://example.com/source.mp4",
            "audio_url": "https://example.com/audio.wav",
        },
    ),
]


@pytest.mark.parametrize(("module_name", "function_name", "call_kwargs"), FALAI_OPERATION_CASES)
def test_falai_operations_forward_webhook_and_call_on_submitted(
    monkeypatch,
    module_name,
    function_name,
    call_kwargs,
):
    import importlib

    provider = importlib.import_module(module_name)
    captured = {}
    receipts = []

    monkeypatch.setenv("FAL_KEY", "fal-key")

    def fake_submit(model, payload, api_key, timeout_seconds=None, webhook_url=None):
        captured["webhook_url"] = webhook_url
        return {
            "request_id": "fal-webhook-1",
            "status_url": "https://queue.example/status/fal-webhook-1",
            "response_url": "https://queue.example/response/fal-webhook-1",
        }

    monkeypatch.setattr(provider, "fal_submit", fake_submit)

    result = getattr(provider, function_name)(
        sync=False,
        webhook_url="https://notice.example/fal",
        on_submitted=receipts.append,
        **call_kwargs,
    )

    assert captured["webhook_url"] == "https://notice.example/fal"
    assert receipts and receipts[0]["request_id"] == "fal-webhook-1"
    assert result["request_id"] == "fal-webhook-1"


@pytest.mark.parametrize(("module_name", "function_name", "call_kwargs"), FALAI_OPERATION_CASES)
def test_falai_operations_reuse_submission_without_post(
    monkeypatch,
    module_name,
    function_name,
    call_kwargs,
):
    import importlib

    provider = importlib.import_module(module_name)
    seen = {}

    monkeypatch.setenv("FAL_KEY", "fal-key")
    monkeypatch.setattr(
        provider,
        "fal_submit",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("fal_submit should not be called when submission is provided")
        ),
    )

    def fake_wait(model, request_id, api_key, **kwargs):
        seen.update(model=model, request_id=request_id, kwargs=kwargs)
        return {
            "status": {"status": "COMPLETED"},
            "response": {"video_url": "https://cdn.example/reused.mp4"},
        }

    monkeypatch.setattr(provider, "fal_wait_for_result", fake_wait)

    result = getattr(provider, function_name)(
        sync=True,
        submission={
            "request_id": "fal-reused-1",
            "status_url": "https://queue.example/status/fal-reused-1",
            "response_url": "https://queue.example/response/fal-reused-1",
        },
        **call_kwargs,
    )

    assert seen["request_id"] == "fal-reused-1"
    assert seen["kwargs"]["status_url"] == "https://queue.example/status/fal-reused-1"
    assert seen["kwargs"]["response_url"] == "https://queue.example/response/fal-reused-1"
    assert result["request_id"] == "fal-reused-1"
    assert result["video_url"] == "https://cdn.example/reused.mp4"


@pytest.mark.parametrize(("module_name", "function_name", "call_kwargs"), FALAI_OPERATION_CASES)
def test_falai_operation_sync_paths_use_returned_refs(
    monkeypatch,
    module_name,
    function_name,
    call_kwargs,
):
    import importlib

    provider = importlib.import_module(module_name)
    captured = {}

    monkeypatch.setenv("FAL_KEY", "fal-key")
    monkeypatch.setattr(
        provider,
        "fal_submit",
        lambda *args, **kwargs: {
            "request_id": "fal-op-1",
            "status_url": "https://queue.example/status/fal-op-1",
            "response_url": "https://queue.example/response/fal-op-1",
        },
    )

    def fake_wait(model, request_id, api_key, **kwargs):
        captured.update(kwargs)
        return {"status": {"status": "COMPLETED"}, "response": {"video_url": "https://cdn.example/op.mp4"}}

    monkeypatch.setattr(provider, "fal_wait_for_result", fake_wait)

    result = getattr(provider, function_name)(sync=True, **call_kwargs)

    assert captured["status_url"] == "https://queue.example/status/fal-op-1"
    assert captured["response_url"] == "https://queue.example/response/fal-op-1"
    assert result["status_url"] == "https://queue.example/status/fal-op-1"
    assert result["response_url"] == "https://queue.example/response/fal-op-1"
    assert result["video_url"] == "https://cdn.example/op.mp4"


@pytest.mark.parametrize(("module_name", "function_name", "call_kwargs"), FALAI_OPERATION_CASES)
def test_falai_operation_helpers_accept_explicit_urls_and_fallback(
    monkeypatch,
    module_name,
    function_name,
    call_kwargs,
):
    import importlib

    provider = importlib.import_module(module_name)
    captured = {"status": [], "result": []}

    def fake_status(model, request_id, api_key, timeout_seconds=None, status_url=None, poll_url=None):
        captured["status"].append(status_url)
        return {"status": "COMPLETED"}

    def fake_result(
        model,
        request_id,
        api_key,
        timeout_seconds=None,
        response_url=None,
        result_url=None,
    ):
        captured["result"].append(response_url)
        return {"video_url": "https://cdn.example/result.mp4"}

    monkeypatch.setenv("FAL_KEY", "fal-key")
    monkeypatch.setattr(provider, "fal_get_status", fake_status)
    monkeypatch.setattr(provider, "fal_get_result", fake_result)

    provider.get_generation_status("req-1", model="fal-ai/generic/video", status_url="https://exact/status")
    provider.get_generation_status("req-1", model="fal-ai/generic/video")
    provider.get_generation_result("req-1", model="fal-ai/generic/video", response_url="https://exact/result")
    provider.get_generation_result("req-1", model="fal-ai/generic/video")

    assert captured["status"][0] == "https://exact/status"
    assert captured["status"][1].endswith("/fal-ai/generic/video/requests/req-1/status?logs=1")
    assert captured["result"][0] == "https://exact/result"
    assert captured["result"][1].endswith("/fal-ai/generic/video/requests/req-1/response")


def test_public_video_dispatcher_does_not_swallow_on_submitted_exception(monkeypatch):
    from easy_ai_clients import video
    from easy_ai_clients.video._image_to_video._apis import falai as provider

    expected = RuntimeError("stop waiting from callback")

    monkeypatch.setenv("FAL_KEY", "fal-key")
    monkeypatch.setattr(
        provider,
        "fal_submit",
        lambda *args, **kwargs: {
            "request_id": "fal-stop-1",
            "status_url": "https://queue.example/status/fal-stop-1",
            "response_url": "https://queue.example/response/fal-stop-1",
        },
    )
    monkeypatch.setattr(
        provider,
        "fal_wait_for_result",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("poll should not run after callback failure")
        ),
    )

    with pytest.raises(RuntimeError) as raised:
        video.image_to_video(
            "Animate this.",
            image="https://example.com/input.png",
            api="falai",
            on_submitted=lambda receipt: (_ for _ in ()).throw(expected),
        )

    assert raised.value is expected


def test_runway_task_url_is_preserved_used_and_upload_secrets_redacted(monkeypatch):
    from easy_ai_clients.video._text_to_video._apis import runway as provider

    captured = {}

    monkeypatch.setenv("RUNWAYML_API_SECRET", "runway-key")
    monkeypatch.setattr(
        provider,
        "runway_submit",
        lambda *args, **kwargs: {
            "id": "task-1",
            "task_url": "https://api.dev.runwayml.com/v1/tasks/task-1?view=safe",
            "uploadUrl": "https://signed.example/upload?X-Amz-Signature=secret",
            "fields": {"policy": "secret"},
        },
    )

    def fake_wait(task_id, api_key, **kwargs):
        captured.update(kwargs)
        return {"status": "SUCCEEDED", "output": ["https://cdn.example/runway.mp4"]}

    monkeypatch.setattr(provider, "runway_wait_for_task", fake_wait)

    result = provider.generate_text_to_video("A shot.", model="gen4.5", duration=1, sync=True)

    assert captured["task_url"] == "https://api.dev.runwayml.com/v1/tasks/task-1?view=safe"
    assert result["task_url"] == "https://api.dev.runwayml.com/v1/tasks/task-1?view=safe"
    assert result["raw_response"]["submission"]["uploadUrl"] == "[redacted]"
    assert result["raw_response"]["submission"]["fields"] == "[redacted]"

    status_seen = {}

    def fake_get(task_id, api_key, **kwargs):
        status_seen.update(kwargs)
        return {"status": "RUNNING"}

    monkeypatch.setattr(provider, "runway_get_task", fake_get)
    provider.get_generation_status("task-1", task_url="https://api.dev.runwayml.com/v1/tasks/exact")
    assert status_seen["task_url"] == "https://api.dev.runwayml.com/v1/tasks/exact"


def test_google_operation_url_is_preserved_and_download_uses_api_headers(monkeypatch):
    from easy_ai_clients.video._text_to_video._apis import google as provider

    captured = {}

    monkeypatch.setenv("GOOGLE_API_KEY", "google-key")
    monkeypatch.setattr(
        provider,
        "http_json",
        lambda *args, **kwargs: {
            "name": "operations/op-1",
            "operation_url": "https://generativelanguage.googleapis.com/v1beta/operations/op-1",
        },
    )

    submitted = provider.generate_text_to_video("A shot.", sync=False, duration_seconds=4)
    assert submitted["operation_name"] == "operations/op-1"
    assert submitted["operation_url"] == "https://generativelanguage.googleapis.com/v1beta/operations/op-1"

    def fake_get(operation_name, api_key, timeout_seconds=None, operation_url=None):
        captured["operation_url"] = operation_url
        return {
            "done": True,
            "response": {
                "generateVideoResponse": {
                    "generatedSamples": [{"video": {"uri": "https://files.example/google.mp4"}}]
                }
            },
        }

    monkeypatch.setattr(provider, "google_get_operation", fake_get)
    result = provider.get_generation_result(
        "operations/op-1",
        operation_url="https://generativelanguage.googleapis.com/v1beta/operations/exact",
    )
    assert captured["operation_url"] == "https://generativelanguage.googleapis.com/v1beta/operations/exact"
    assert result["video_url"] == "https://files.example/google.mp4"

    download_seen = {}
    monkeypatch.setattr(
        provider,
        "download_file",
        lambda url, output_path, headers=None: download_seen.update(headers=headers) or output_path,
    )
    provider.download_generation(video_url="https://files.example/google.mp4", output_path="out.mp4")
    assert download_seen["headers"]["x-goog-api-key"] == "google-key"


def test_replicate_prediction_url_is_preserved(monkeypatch):
    from easy_ai_clients import video
    from easy_ai_clients.video._avatar_video._apis import replicate as provider

    captured = []

    def fake_http_json(method, url, headers=None, payload=None, timeout_seconds=None):
        captured.append(url)
        return {
            "id": "prediction-1",
            "status": "succeeded",
            "output": "https://replicate.delivery/output.mp4",
            "urls": {"get": "https://api.replicate.com/v1/predictions/prediction-1"},
        }

    monkeypatch.setenv("REPLICATE_API_TOKEN", "replicate-key")
    monkeypatch.setattr(provider, "http_json", fake_http_json)

    status = video.get_status(
        "avatar_video",
        "prediction-1",
        api="replicate",
        model="replicate_prunaai_p_video_avatar",
        task_url="https://api.replicate.com/v1/predictions/exact",
    )
    result = video.get_result(
        "avatar_video",
        "prediction-1",
        api="replicate",
        model="replicate_prunaai_p_video_avatar",
        task_url="https://api.replicate.com/v1/predictions/exact",
    )

    assert status["status"] == "completed"
    assert result["video_url"] == "https://replicate.delivery/output.mp4"
    assert captured == [
        "https://api.replicate.com/v1/predictions/exact",
        "https://api.replicate.com/v1/predictions/exact",
    ]


def test_hedra_common_preserves_and_reuses_status_refs(monkeypatch):
    from easy_ai_clients.video import _hedra_common as common

    calls = []

    def fake_json(method, path, api_key, payload=None, timeout_seconds=None):
        calls.append((method, path))
        if method == "POST":
            return {"id": "hedra-1", "status_url": "https://api.hedra.com/web-app/public/generations/hedra-1/status"}
        return {"status": "complete", "download_url": "https://cdn.example/hedra.mp4"}

    monkeypatch.setenv("HEDRA_API_KEY", "hedra-key")
    monkeypatch.setattr(common, "hedra_json", fake_json)

    model_data = {"id": "model-id", "name": "Model", "operation": "text_to_video"}
    returned = common.submit_generation(
        {"type": "video"},
        False,
        None,
        model_data,
        {"cost_reason": "none", "cost_credits": 0, "credit_source": "none"},
        {},
    )

    assert returned[1] == "hedra-1"
    assert returned[-1]["status_url"].endswith("/generations/hedra-1/status")

    seen = {}

    def fake_status(generation_id, api_key, **kwargs):
        seen.update(kwargs)
        return {"status": "complete", "download_url": "https://cdn.example/hedra.mp4"}

    monkeypatch.setattr(common, "hedra_get_generation_status", fake_status)
    raw, refs = common.fetch_generation_status("hedra-1", {"status_url": "https://exact/hedra-status"})
    assert raw["status"] == "complete"
    assert seen["status_url"] == "https://exact/hedra-status"
    assert refs["status_url"] == "https://exact/hedra-status"


def test_hedra_common_calls_on_submitted_and_reuses_submission_without_post(monkeypatch):
    from easy_ai_clients.video import _hedra_common as common

    calls = []
    receipts = []

    def fake_json(method, path, api_key, payload=None, timeout_seconds=None):
        calls.append(method)
        return {"id": "hedra-hook-1", "status_url": "https://api.hedra.com/web-app/public/generations/hedra-hook-1/status"}

    monkeypatch.setenv("HEDRA_API_KEY", "hedra-key")
    monkeypatch.setattr(common, "hedra_json", fake_json)
    monkeypatch.setattr(
        common,
        "hedra_wait_for_result",
        lambda generation_id, api_key, **kwargs: {
            "status": "complete",
            "download_url": f"https://cdn.example/{generation_id}.mp4",
        },
    )

    model_data = {"id": "model-id", "name": "Model", "operation": "avatar_video"}
    submitted = common.submit_generation(
        {"type": "video"},
        False,
        None,
        model_data,
        {"cost_reason": "none", "cost_credits": 0, "credit_source": "none"},
        {"on_submitted": receipts.append},
    )

    assert calls == ["POST"]
    assert receipts and receipts[0]["id"] == "hedra-hook-1"
    assert submitted[1] == "hedra-hook-1"

    calls.clear()
    reused = common.submit_generation(
        {"type": "video"},
        True,
        None,
        model_data,
        {"cost_reason": "none", "cost_credits": 0, "credit_source": "none"},
        {"submission": {"id": "hedra-reused-1"}},
    )

    assert calls == []
    assert reused[1] == "hedra-reused-1"
    assert reused[2] == "completed"
    assert reused[3] == "https://cdn.example/hedra-reused-1.mp4"


def test_hedra_avatar_and_video_with_audio_reject_webhook_url_before_submit(monkeypatch):
    from easy_ai_clients.video import _hedra_common as common
    from easy_ai_clients.video._avatar_video._apis import hedra as avatar_provider
    from easy_ai_clients.video._video_with_audio._apis import hedra as audio_provider

    monkeypatch.setenv("HEDRA_API_KEY", "hedra-key")
    monkeypatch.setattr(
        common,
        "hedra_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("submit POST should not run when webhook_url is provided")
        ),
    )

    with pytest.raises(ValueError, match="does not support webhook_url"):
        avatar_provider.generate_avatar_video(
            start_keyframe_url="https://example.com/avatar.png",
            audio_id="audio-1",
            sync=False,
            webhook_url="https://notice.example/hedra",
        )

    with pytest.raises(ValueError, match="does not support webhook_url"):
        audio_provider.generate_video_with_audio(
            video_id="video-1",
            model="model-1",
            sync=False,
            webhook_url="https://notice.example/hedra",
        )


def test_public_video_dispatcher_does_not_swallow_hedra_on_submitted_exception(monkeypatch):
    from easy_ai_clients import video
    from easy_ai_clients.video import _hedra_common as common

    expected = RuntimeError("stop hedra after submit")

    monkeypatch.setenv("HEDRA_API_KEY", "hedra-key")
    monkeypatch.setattr(
        common,
        "hedra_json",
        lambda method, path, api_key, payload=None, timeout_seconds=None: {"id": "hedra-stop-1"},
    )

    with pytest.raises(RuntimeError) as raised:
        video.avatar_video(
            avatar="start-keyframe-id",
            api="hedra",
            audio_id="audio-id",
            sync=False,
            on_submitted=lambda _receipt: (_ for _ in ()).throw(expected),
        )

    assert raised.value is expected


def test_heygen_together_and_xai_common_helpers_echo_async_refs(monkeypatch):
    from easy_ai_clients.video import _heygen_common as heygen
    from easy_ai_clients.video import _together_common as together
    from easy_ai_clients.video import _xai_video_common as xai

    monkeypatch.setattr(
        heygen._heygen,
        "request_json",
        lambda *args, **kwargs: {"data": {"status": "completed", "video_url": "https://cdn.example/h.mp4"}},
    )
    heygen_status = heygen.get_video("video-1", task_url="https://api.heygen.com/v3/videos/video-1")
    assert heygen_status["task_url"] == "https://api.heygen.com/v3/videos/video-1"

    together_seen = {}
    monkeypatch.setenv("TOGETHER_API_KEY", "together-key")
    monkeypatch.setattr(
        together,
        "http_json",
        lambda method, url, **kwargs: together_seen.update(url=url)
        or {"status": "completed", "video_url": "https://cdn.example/t.mp4"},
    )
    together_status = together.get_video("t-1", task_url="https://api.together.xyz/v1/videos/t-1")
    assert together_seen["url"] == "https://api.together.xyz/v1/videos/t-1"
    assert together.async_refs(together_status, "t-1")["task_url"].endswith("/videos/t-1")

    xai_seen = {}
    monkeypatch.setenv("XAI_API_KEY", "xai-key")
    monkeypatch.setattr(
        xai,
        "http_json",
        lambda method, url, **kwargs: xai_seen.update(url=url)
        or {"status": "done", "video_url": "https://cdn.example/x.mp4"},
    )
    xai_status = xai.get_video("x-1", task_url="https://api.x.ai/v1/videos/x-1")
    assert xai_seen["url"] == "https://api.x.ai/v1/videos/x-1"
    assert xai.async_refs(xai_status, "x-1")["task_url"].endswith("/videos/x-1")


def test_video_download_requires_output_path_for_direct_video_url():
    from easy_ai_clients import video

    result = video.download(
        "text_to_video",
        video_url="https://cdn.example/video.mp4",
        api="falai",
    )

    assert result["status"] == "failed"
    assert "output_path is required" in result["warnings"]


def test_huggingface_sync_false_is_documented_noop(monkeypatch):
    from easy_ai_clients.video._text_to_video._apis import huggingface as provider

    response = SimpleNamespace(
        headers={"content-type": "application/json", "x-request-id": "hf-1"},
        content=b"",
    )

    monkeypatch.setenv("HUGGINGFACE_API_KEY", "hf-key")
    monkeypatch.setattr(provider, "request", lambda *args, **kwargs: response)
    monkeypatch.setattr(provider, "response_json", lambda response: {"video_url": "https://cdn.example/hf.mp4"})

    result = provider.generate_text_to_video("A shot.", sync=False)

    assert result["status"] == "completed"
    assert "does not create an async job" in result["warnings"]
    assert result["video_url"] == "https://cdn.example/hf.mp4"
