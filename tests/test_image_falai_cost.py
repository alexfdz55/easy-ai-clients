"""Offline Fal.ai image cost contract tests."""

from __future__ import annotations

import urllib.parse

import pytest

_ONE_PIXEL_PNG_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def test_fal_pricing_estimate_uses_official_unit_price_payload(monkeypatch):
    from easy_ai_clients import _falai_pricing as pricing

    captured = {}

    def fake_http_json(method, url, headers=None, payload=None, timeout_seconds=None):
        captured.update(
            method=method,
            url=url,
            headers=headers,
            payload=payload,
            timeout_seconds=timeout_seconds,
        )
        return {"total_cost": 0.0042, "currency": "USD"}

    monkeypatch.setattr(pricing, "_http_json", fake_http_json)  # noqa: SLF001

    result = pricing.fal_estimate_unit_price(
        "fal-ai/flux/schnell",
        2,
        "fal-key",
        timeout_seconds=9,
    )

    assert captured["method"] == "POST"
    assert captured["url"] == "https://api.fal.ai/v1/models/pricing/estimate"
    assert captured["headers"]["Authorization"] == "Key fal-key"
    assert captured["payload"] == {
        "estimate_type": "unit_price",
        "endpoints": {"fal-ai/flux/schnell": {"unit_quantity": 2.0}},
    }
    assert captured["timeout_seconds"] == 9
    assert result["cost_usd"] == pytest.approx(0.0042)
    assert result["cost_source"] == "fal_pricing_estimate_api"
    assert result["cost_is_estimated"] is True
    assert result["cost_details"]["pricing_estimate"]["total_cost"] == pytest.approx(0.0042)


def test_falai_generate_saves_estimated_cost_without_forwarding_billing_kwargs(monkeypatch):
    from easy_ai_clients.image._common import falai_utils
    from easy_ai_clients.image._generate._apis import falai as provider

    captured = {}

    class FakeResponse:
        headers = {"x-request-id": "req_header"}

        def json(self):
            return {
                "request_id": "req_123",
                "status_url": "https://queue.fal.run/status",
                "response_url": "https://queue.fal.run/response",
            }

    def fake_estimate(model, values, extra_body, api_key):
        captured["estimate"] = {
            "model": model,
            "values": values,
            "extra_body": dict(extra_body),
            "api_key": api_key,
        }
        return {
            "cost_usd": 0.0042,
            "cost_currency": "USD",
            "cost_is_estimated": True,
            "cost_source": "fal_pricing_estimate_api",
            "cost_details": {"unit_quantity": 2.0},
            "cost_reason": "estimate",
        }

    def fake_submit_queue(model, body, api_key, timeout_seconds):
        captured["submit"] = {
            "model": model,
            "body": dict(body),
            "api_key": api_key,
            "timeout_seconds": timeout_seconds,
        }
        response = FakeResponse()
        return response, response.json()

    monkeypatch.setattr(provider, "get_provider_api_key", lambda *args: "fal-key")
    monkeypatch.setattr(provider, "fal_image_pricing_estimate", fake_estimate)
    monkeypatch.setattr(falai_utils, "_submit_queue", fake_submit_queue)  # noqa: SLF001
    monkeypatch.setattr(
        falai_utils,
        "_poll_completion",  # noqa: SLF001
        lambda **kwargs: (
            {"request_id": "req_123", "images": [{"url": "https://example.com/image.png"}]},
            {"status": "COMPLETED"},
            "",
        ),
    )
    monkeypatch.setattr(
        falai_utils,
        "download_image_as_base64_png",
        lambda *args, **kwargs: "BASE64_IMAGE",
    )

    result = provider.generate(
        "A clean icon.",
        model="fal-ai/flux/schnell",
        num_images=2,
        billing_unit_quantity=2,
        image_size="portrait_16_9",
        timeout_seconds=11,
    )

    assert result["base64"] == "BASE64_IMAGE"
    assert result["request_id"] == "req_123"
    assert result["cost_usd"] == pytest.approx(0.0042)
    assert result["cust_usd"] == pytest.approx(0.0042)
    assert result["cost_source"] == "fal_pricing_estimate_api"
    assert result["cost_is_estimated"] is True
    assert result["cost_details"]["unit_quantity"] == pytest.approx(2.0)
    assert captured["submit"]["body"]["num_images"] == 2
    assert captured["submit"]["body"]["image_size"] == "portrait_16_9"
    assert "billing_unit_quantity" not in captured["submit"]["body"]
    assert "unit_quantity" not in captured["submit"]["body"]
    assert captured["estimate"]["api_key"] == "fal-key"


@pytest.mark.parametrize(
    ("module_path", "operation_name", "call_args"),
    [
        (
            "easy_ai_clients.image._edit._apis.falai",
            "_edit_image",
            ("Edit this image.", _ONE_PIXEL_PNG_DATA_URL),
        ),
        (
            "easy_ai_clients.image._remix._apis.falai",
            "_remix_image",
            ("Remix this image.", [_ONE_PIXEL_PNG_DATA_URL]),
        ),
    ],
)
def test_falai_edit_and_remix_keep_billing_kwargs_out_of_provider_payload(
    monkeypatch,
    module_path,
    operation_name,
    call_args,
):
    provider = pytest.importorskip(module_path)
    captured = {}

    def fake_estimate(model, values, extra_body, api_key):
        captured["estimate"] = {
            "model": model,
            "values": values,
            "extra_body": dict(extra_body),
            "api_key": api_key,
        }
        return {
            "cost_usd": 0.001,
            "cost_is_estimated": True,
            "cost_source": "fal_pricing_estimate_api",
        }

    def fake_image_call(**kwargs):
        captured["image_call"] = kwargs
        return {"ok": True, "cost_metadata": kwargs["cost_metadata"]}

    monkeypatch.setattr(provider, "get_provider_api_key", lambda *args: "fal-key")
    monkeypatch.setattr(provider, "fal_image_pricing_estimate", fake_estimate)
    monkeypatch.setattr(provider, operation_name, fake_image_call)

    operation = provider.edit if operation_name == "_edit_image" else provider.remix
    result = operation(
        *call_args,
        model="fal-ai/flux-pro/kontext",
        billing_unit_quantity=3,
        unit_quantity=4,
        num_images=2,
        timeout_seconds=12,
    )

    extra_body = captured["image_call"]["extra_body"]
    assert result["cost_metadata"]["cost_source"] == "fal_pricing_estimate_api"
    assert extra_body["num_images"] == 2
    assert "billing_unit_quantity" not in extra_body
    assert "unit_quantity" not in extra_body
    assert captured["estimate"]["values"]["billing_unit_quantity"] == 3
    assert captured["estimate"]["api_key"] == "fal-key"


def test_fal_pricing_estimate_reports_unavailable_on_lookup_failure(monkeypatch):
    from easy_ai_clients import _falai_pricing as pricing

    def broken_estimate(*args, **kwargs):
        raise RuntimeError("pricing down")

    monkeypatch.setattr(pricing, "fal_estimate_unit_price", broken_estimate)

    result = pricing.fal_pricing_estimate(
        "fal-ai/flux/schnell",
        {"billing_unit_quantity": 1},
        api_key="fal-key",
    )

    assert result["cost_usd"] == pytest.approx(0.0)
    assert result["cost_source"] == "unavailable"
    assert result["cost_is_estimated"] is True
    assert "pricing down" in result["cost_details"]["cost_lookup_error"]


def test_falai_billable_units_header_prices_the_real_cost(monkeypatch):
    """fal informa lo FACTURADO en `x-fal-billable-units`; se tarifa con la API oficial.

    Medido 2026-09-09 con gpt-image-2.5: la misma escena 720×1280 costó 0.0039 unidades
    con un prompt corto y 0.0241 con el prompt real y dos referencias. Una tabla por
    resolución no puede saberlo; el header sí.
    """
    from easy_ai_clients.image._common import falai_utils
    from easy_ai_clients.image._generate._apis import falai as provider

    captured = {}

    class FakeResponse:
        headers = {"x-request-id": "req_header"}

        def json(self):
            return {
                "request_id": "req_123",
                "status_url": "https://queue.fal.run/status",
                "response_url": "https://queue.fal.run/response",
            }

    def fake_unit_price(model, units, api_key, timeout_seconds=None):
        captured["priced"] = {"model": model, "units": units, "api_key": api_key}
        return {"cost_usd": 0.0241, "pricing_estimate": {"total_cost": 0.0241}}

    monkeypatch.setattr(provider, "get_provider_api_key", lambda *args: "fal-key")
    monkeypatch.setattr(
        provider,
        "fal_image_pricing_estimate",
        lambda *args: {"cost_usd": 0.0100, "cost_is_estimated": True, "cost_source": "fal_pricing_estimate_api"},
    )
    monkeypatch.setattr(falai_utils, "fal_estimate_unit_price", fake_unit_price)
    monkeypatch.setattr(
        falai_utils, "_submit_queue", lambda **kwargs: (FakeResponse(), FakeResponse().json())  # noqa: SLF001
    )
    monkeypatch.setattr(
        falai_utils,
        "_poll_completion",  # noqa: SLF001
        lambda **kwargs: (
            {"request_id": "req_123", "images": [{"url": "https://example.com/image.png"}]},
            {"status": "COMPLETED"},
            "",
            {"x-fal-billable-units": "0.0241", "x-fal-request-id": "req_123"},
        ),
    )
    monkeypatch.setattr(falai_utils, "download_image_as_base64_png", lambda *a, **k: "BASE64")

    result = provider.generate("A scene.", model="openai/gpt-image-2.5/flare/edit", timeout_seconds=11)

    assert captured["priced"] == {"model": "openai/gpt-image-2.5/flare/edit", "units": pytest.approx(0.0241), "api_key": "fal-key"}
    assert result["cost_usd"] == pytest.approx(0.0241)
    assert result["cust_usd"] == pytest.approx(0.0241)
    assert result["cost_source"] == "fal_billable_units"
    assert result["cost_is_estimated"] is False
    assert result["cost_details"]["billable_units"] == pytest.approx(0.0241)


def test_billable_units_fall_back_to_the_estimate_when_pricing_fails(monkeypatch):
    from easy_ai_clients.image._common import falai_utils

    def broken(*args, **kwargs):
        raise RuntimeError("pricing down")

    monkeypatch.setattr(falai_utils, "fal_estimate_unit_price", broken)
    estimate = {"cost_usd": 0.01, "cost_is_estimated": True, "cost_source": "fal_pricing_estimate_api"}
    out = falai_utils.billable_units_cost(
        model="openai/gpt-image-2", headers={"x-fal-billable-units": "0.0072"}, api_key="k",
        timeout_seconds=5, cost_metadata=estimate,
    )
    assert out["cost_usd"] == 0.01
    assert out["cost_source"] == "fal_pricing_estimate_api"
    assert out["cost_details"]["billable_units"] == pytest.approx(0.0072)
    assert "billable_units_pricing_error" in out["cost_details"]
    # Sin header no cambia nada.
    assert falai_utils.billable_units_cost(model="m", headers={}, api_key="k", timeout_seconds=5, cost_metadata=estimate) is estimate


def test_falai_submit_queue_appends_fal_webhook_query(monkeypatch):
    from easy_ai_clients.image._common import falai_utils

    captured = {}

    class FakeResponse:
        def json(self):
            return {
                "request_id": "req-hook-1",
                "status_url": "https://queue.fal.run/status",
                "response_url": "https://queue.fal.run/response",
            }

    def fake_request(method, url, headers=None, json=None, timeout_seconds=None):
        captured.update(
            method=method,
            url=url,
            headers=headers,
            json=json,
            timeout_seconds=timeout_seconds,
        )
        return FakeResponse()

    monkeypatch.setattr(falai_utils, "request", fake_request)

    _, payload = falai_utils._submit_queue(  # noqa: SLF001
        model="fal-ai/flux/schnell",
        body={"prompt": "A clean icon."},
        api_key="fal-key",
        timeout_seconds=9,
        webhook_url="https://example.com/hook?token=a b",
    )

    parsed = urllib.parse.urlsplit(captured["url"])
    query = urllib.parse.parse_qs(parsed.query)
    assert captured["method"] == "POST"
    assert parsed.path.endswith("/fal-ai/flux/schnell")
    assert query["fal_webhook"] == ["https://example.com/hook?token=a b"]
    assert payload["request_id"] == "req-hook-1"


def test_falai_image_on_submitted_exception_is_not_swallowed(monkeypatch):
    from easy_ai_clients import image
    from easy_ai_clients.image._common import falai_utils
    from easy_ai_clients.image._generate._apis import falai as provider

    class FakeResponse:
        headers = {}

    monkeypatch.setattr(provider, "get_provider_api_key", lambda *args: "fal-key")
    monkeypatch.setattr(
        provider,
        "fal_image_pricing_estimate",
        lambda *args: {"cost_usd": 0.0, "cost_is_estimated": True, "cost_source": "unavailable"},
    )
    monkeypatch.setattr(
        falai_utils,
        "_submit_queue",  # noqa: SLF001
        lambda **kwargs: (
            FakeResponse(),
            {
                "request_id": "req-callback-1",
                "status_url": "https://queue.fal.run/status",
                "response_url": "https://queue.fal.run/response",
            },
        ),
    )
    monkeypatch.setattr(
        falai_utils,
        "_poll_completion",  # noqa: SLF001
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("poll should not run after callback failure")),
    )

    receipts = []
    expected = RuntimeError("stop waiting from callback")

    def on_submitted(receipt):
        receipts.append(receipt)
        raise expected

    with pytest.raises(RuntimeError) as raised:
        image.generate("A clean icon.", api="falai", on_submitted=on_submitted)

    assert raised.value is expected
    assert receipts and receipts[0]["request_id"] == "req-callback-1"


def test_falai_image_submission_skips_submit_post(monkeypatch):
    from easy_ai_clients.image._common import falai_utils
    from easy_ai_clients.image._generate._apis import falai as provider

    captured = {}

    monkeypatch.setattr(provider, "get_provider_api_key", lambda *args: "fal-key")
    monkeypatch.setattr(
        provider,
        "fal_image_pricing_estimate",
        lambda *args: {"cost_usd": 0.0, "cost_is_estimated": True, "cost_source": "unavailable"},
    )
    monkeypatch.setattr(
        falai_utils,
        "_submit_queue",  # noqa: SLF001
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("submit must be skipped when submission is provided")),
    )

    def fake_poll_completion(**kwargs):
        captured["submission"] = kwargs["submission"]
        return (
            {"request_id": "req-reused-1", "images": [{"url": "https://example.com/image.png"}]},
            {"status": "COMPLETED"},
            "",
            {},
        )

    monkeypatch.setattr(falai_utils, "_poll_completion", fake_poll_completion)  # noqa: SLF001
    monkeypatch.setattr(falai_utils, "download_image_as_base64_png", lambda *a, **k: "BASE64_IMAGE")

    result = provider.generate(
        "A clean icon.",
        submission={
            "request_id": "req-reused-1",
            "status_url": "https://queue.fal.run/status",
            "response_url": "https://queue.fal.run/response",
        },
    )

    assert captured["submission"]["request_id"] == "req-reused-1"
    assert result["request_id"] == "req-reused-1"
    assert result["base64"] == "BASE64_IMAGE"
