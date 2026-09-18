"""Offline tests: failed provider calls keep the provider request id.

Without the id a failure cannot be traced back to the provider's dashboard. These tests
pin down that the id survives each path where it used to be dropped, and that errors
without an id keep exactly the shape they always had.
"""

from __future__ import annotations

import io
import urllib.error

import httpx
import pytest


class _HeaderError(Exception):
    def __init__(self, message, headers):
        super().__init__(message)
        self.response = type("Response", (), {"headers": headers})()


def test_build_error_without_an_id_keeps_todays_keys():
    from easy_ai_clients._error_utils import build_error

    error = build_error(RuntimeError("boom"), provider="falai", operation="edit", model="m")

    assert error == {
        "type": "RuntimeError",
        "message": "boom",
        "provider": "falai",
        "operation": "edit",
        "model": "m",
    }


def test_the_id_is_found_through_the_cause_chain():
    from easy_ai_clients._error_utils import build_error, request_id_of

    try:
        try:
            raise _HeaderError("HTTP 401", {"request-id": "rid-1"})
        except _HeaderError as low_level:
            raise RuntimeError("Failed to synthesize chunk") from low_level
    except RuntimeError as wrapped:
        assert request_id_of(wrapped) == "rid-1"
        assert build_error(wrapped, provider="elevenlabs")["request_id"] == "rid-1"


def test_attach_error_fills_an_empty_top_level_id():
    from easy_ai_clients._error_utils import attach_error

    exc = RuntimeError("failed")
    exc.request_id = "req-9"
    output = attach_error({"request_id": ""}, exc, provider="falai")
    assert output["request_id"] == "req-9"
    assert output["error"]["request_id"] == "req-9"

    kept = attach_error({"request_id": "keep"}, RuntimeError("x"), provider="falai")
    assert kept["request_id"] == "keep"
    assert kept["error"]["request_id"] == "keep"


def test_fal_image_failure_after_submit_keeps_the_submit_id(monkeypatch):
    # The real case: the job was submitted (so fal already has an id) and then a status
    # or response call failed with an HTTP error. That id used to be thrown away.
    from easy_ai_clients import image
    from easy_ai_clients.image._common import falai_utils
    from easy_ai_clients.image._common.errors import ProviderResponseError
    from easy_ai_clients.image._generate._apis import falai as provider

    class FakeResponse:
        headers = {}

        def json(self):
            return {
                "request_id": "req_123",
                "status_url": "https://queue.fal.run/x/requests/req_123/status",
                "response_url": "https://queue.fal.run/x/requests/req_123",
            }

    def fake_submit_queue(model, body, api_key, timeout_seconds):
        response = FakeResponse()
        return response, response.json()

    def failing_poll(**kwargs):
        raise ProviderResponseError(
            "Provider request failed with status 422.",
            status_code=422,
            response_text='{"detail": "unprocessable"}',
        )

    monkeypatch.setattr(provider, "get_provider_api_key", lambda *args: "fal-key")
    monkeypatch.setattr(provider, "fal_image_pricing_estimate", lambda *args, **kwargs: {})
    monkeypatch.setattr(falai_utils, "_submit_queue", fake_submit_queue)  # noqa: SLF001
    monkeypatch.setattr(falai_utils, "_poll_completion", failing_poll)  # noqa: SLF001

    result = image.generate("A clean icon.", model="fal-ai/flux/schnell", api="falai")

    assert result["base64"] == ""
    assert result["request_id"] == "req_123"
    assert result["error"]["request_id"] == "req_123"


def test_a_failed_http_request_carries_the_fal_request_id(monkeypatch):
    from easy_ai_clients.image._common import http_utils
    from easy_ai_clients.image._common.errors import ProviderResponseError

    def reply(headers):
        def fake_request(self, method, url, **kwargs):
            return httpx.Response(
                422,
                headers=headers,
                text='{"detail": "bad"}',
                request=httpx.Request(method, url),
            )

        return fake_request

    monkeypatch.setattr(httpx.Client, "request", reply({"x-fal-request-id": "fal-9"}))
    with pytest.raises(ProviderResponseError) as caught:
        http_utils.request("POST", "https://queue.fal.run/fal-ai/x", max_attempts=1)
    assert caught.value.request_id == "fal-9"
    assert caught.value.status_code == 422
    assert caught.value.headers["x-fal-request-id"] == "fal-9"

    # Without the header, a fal queue URL still names the request.
    monkeypatch.setattr(httpx.Client, "request", reply({}))
    with pytest.raises(ProviderResponseError) as caught:
        http_utils.request(
            "GET", "https://queue.fal.run/fal-ai/x/requests/abc/status", max_attempts=1
        )
    assert caught.value.request_id == "abc"


def test_extract_request_id_prefers_the_fal_header():
    from easy_ai_clients.image._common.provider_utils import extract_request_id

    response = type("R", (), {"headers": {"x-fal-request-id": "fal-1", "x-request-id": "gw-1"}})()
    assert extract_request_id(response) == "fal-1"


def test_video_http_errors_keep_their_message_and_add_the_id(monkeypatch):
    from easy_ai_clients.video import _shared

    url = "https://queue.fal.run/fal-ai/wan/requests/abc/response"

    def fake_urlopen(request, timeout=None):
        raise urllib.error.HTTPError(
            url, 422, "Unprocessable", {}, io.BytesIO(b'{"detail": "bad"}')
        )

    monkeypatch.setattr(_shared.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(RuntimeError) as caught:
        _shared.http_json("GET", url)

    # Same text as before (retry decisions read it), now with the id and the status.
    assert str(caught.value) == f'HTTP 422 from {url}: {{"detail": "bad"}}'
    assert isinstance(caught.value, _shared.ProviderJobError)
    assert caught.value.request_id == "abc"
    assert caught.value.status_code == 422


def test_fal_wait_for_result_failures_carry_the_id(monkeypatch):
    from easy_ai_clients.video import _shared

    monkeypatch.setattr(_shared, "fal_get_status", lambda *args, **kwargs: {"status": "FAILED"})
    with pytest.raises(RuntimeError) as failed:
        _shared.fal_wait_for_result("fal-ai/wan", "req-7", "key", timeout_seconds=5)
    assert failed.value.request_id == "req-7"
    assert "fal.ai generation req-7 ended with status" in str(failed.value)

    monkeypatch.setattr(_shared, "fal_get_status", lambda *args, **kwargs: {"status": "IN_PROGRESS"})
    monkeypatch.setattr(_shared.time, "sleep", lambda seconds: None)
    with pytest.raises(TimeoutError) as timed_out:
        _shared.fal_wait_for_result("fal-ai/wan", "req-8", "key", timeout_seconds=0.01)
    assert timed_out.value.request_id == "req-8"


def test_elevenlabs_speech_reports_the_id_of_each_chunk(monkeypatch):
    from easy_ai_clients.audio._synthesize._apis import elevenlabs

    finalized = {}

    def fake_finalize(records, cost_usd):
        finalized["records"] = records
        return {"base64": "AAA", "cost_usd": cost_usd}

    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setattr(
        elevenlabs,
        "_generate_chunk",
        lambda *args, **kwargs: [{"character_cost": 10, "request_id": "tts-1"}],
    )
    monkeypatch.setattr(elevenlabs, "_finalize_synthesis_output", fake_finalize)

    result = elevenlabs.generate("Hola.", model="eleven_flash_v2_5")

    assert result["request_id"] == "tts-1"
    assert result["request_ids"] == ["tts-1"]
    assert all("request_id" not in record for record in finalized["records"])
    assert elevenlabs._response_request_id({"request-id": "tts-2"}) == "tts-2"  # noqa: SLF001
    assert elevenlabs._response_request_id(None) == ""  # noqa: SLF001
