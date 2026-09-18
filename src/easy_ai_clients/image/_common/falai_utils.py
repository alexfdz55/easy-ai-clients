"""Helpers compartilhados para integração com a fal.ai.

Concentra a submissão por fila (``queue.fal.run``), o polling assíncrono do
status, o download das imagens resultantes e a extração de texto dos endpoints
de visão. Cada operação pública (``generate``, ``edit``, ``remix``, ``analyze``)
consome este módulo para reutilizar autenticação, detecção de bloqueio e
tratamento de erros.

Última atualização: 2026-04-24
"""

from __future__ import annotations

import time

from ..._error_utils import request_id_of
from ..._falai_pricing import fal_estimate_unit_price
from .http_utils import request
from .image_utils import image_to_data_url
from .provider_utils import (
    detect_block,
    download_image_as_base64_png,
    extract_request_id,
    join_warnings,
    provider_error_to_warning,
    response_json,
)

_FAL_QUEUE_BASE = "https://queue.fal.run"
_TERMINAL_SUCCESS = {"COMPLETED", "OK"}
_TERMINAL_FAILURE = {"FAILED", "ERROR", "CANCELED", "CANCELLED", "REJECTED"}
_POLL_INTERVAL_SECONDS = 2.0

# Modelos de edit que aceitam apenas uma imagem no campo `image_url`.
_EDIT_SINGLE_IMAGE_MODELS = frozenset(
    {
        "fal-ai/flux-pro/kontext",
        "fal-ai/flux-pro/kontext/max",
        "fal-ai/flux-pro/v1/fill",
        "fal-ai/flux-lora/inpaint",
        "fal-ai/reve/edit",
        "fal-ai/bria/fibo-edit/edit",
    }
)

# Modelos de edit que suportam máscara pública convertida para polaridade de inpaint.
_EDIT_MASK_MODELS = frozenset(
    {
        "fal-ai/flux-pro/v1/fill",
        "fal-ai/flux-lora/inpaint",
    }
)


def _auth_headers(api_key):
    """Retorna os cabeçalhos padrão da fal.ai com a chave de API."""

    return {"Authorization": f"Key {api_key}"}


def _submit_queue(*, model, body, api_key, timeout_seconds):
    """Submete a requisição inicial para a fila da fal.ai.

    ### Parâmetros:
        model: Identificador público do modelo, por exemplo ``fal-ai/flux/dev``.
        body: Payload JSON já montado para o modelo alvo.
        api_key: Credencial resolvida a partir de ``FAL_KEY``.
        timeout_seconds: Timeout da chamada HTTP.

    ### Retorna:
        Tupla ``(response, payload)`` com a resposta HTTP e o JSON parseado.
    """

    response = request(
        "POST",
        f"{_FAL_QUEUE_BASE}/{model}",
        headers={**_auth_headers(api_key), "Content-Type": "application/json"},
        json=body,
        timeout_seconds=timeout_seconds,
    )
    return response, response_json(response)


def _poll_completion(*, submission, api_key, timeout_seconds):
    """Aguarda a conclusão de uma tarefa submetida e devolve o payload final.

    ### Parâmetros:
        submission: Payload retornado pelo POST inicial (com ``status_url`` e ``response_url``).
        api_key: Credencial da fal.ai.
        timeout_seconds: Deadline total para o polling.

    ### Retorna:
        Tupla ``(final_payload, last_status, error, final_headers)``. ``final_payload``
        é ``None`` em falha e ``error`` traz a mensagem pública. ``final_headers`` são
        os headers da resposta final (chaves em minúsculas): a fal informa ali a
        quantidade faturada real (``x-fal-billable-units``).
    """

    status_url = submission.get("status_url")
    response_url = submission.get("response_url")
    if not status_url or not response_url:
        return None, submission, "fal.ai did not return queue URLs for the request.", {}

    deadline = time.time() + timeout_seconds
    last_status = dict(submission)
    while time.time() < deadline:
        status_response = request(
            "GET",
            str(status_url),
            headers=_auth_headers(api_key),
            timeout_seconds=timeout_seconds,
        )
        last_status = response_json(status_response)
        status = str(last_status.get("status") or "").upper()
        if status in _TERMINAL_SUCCESS:
            final_response = request(
                "GET",
                str(response_url),
                headers=_auth_headers(api_key),
                timeout_seconds=timeout_seconds,
            )
            return response_json(final_response), last_status, "", _response_headers(final_response)
        if status in _TERMINAL_FAILURE:
            error_detail = (
                last_status.get("error")
                or last_status.get("detail")
                or f"fal.ai request ended with status {status}."
            )
            return None, last_status, str(error_detail), {}
        time.sleep(_POLL_INTERVAL_SECONDS)
    return None, last_status, "fal.ai polling reached the configured timeout.", {}


def _response_headers(response):
    """Headers de uma resposta HTTP como dict com chaves em minúsculas (ou ``{}``)."""

    try:
        return {str(k).lower(): str(v) for k, v in dict(response.headers).items()}
    except Exception:  # noqa: BLE001
        return {}


BILLABLE_UNITS_HEADER = "x-fal-billable-units"


def billable_units_cost(*, model, headers, api_key, timeout_seconds, cost_metadata=None):
    """Custo REAL a partir da quantidade faturada que a fal devolve no resultado.

    A fal informa ``x-fal-billable-units`` na resposta final; para modelos cobrados
    por token (gpt-image) esse número varia com o prompt e as referências, então uma
    tabela por resolução sempre erra (medido: a mesma cena 720×1280 custou $0.0039 com
    um prompt curto e $0.0241 com o prompt real e duas referências). A quantidade é
    convertida em dólares pela API oficial de preços da fal (``unit_price``), que é a
    mesma tarifa do painel. Se o header não vier ou a API falhar, devolve o
    ``cost_metadata`` recebido (a estimativa de antes), anotando as unidades quando
    existirem.
    """

    raw = (headers or {}).get(BILLABLE_UNITS_HEADER)
    try:
        units = float(raw)
    except (TypeError, ValueError):
        return cost_metadata
    if units <= 0:
        return cost_metadata
    base = dict(cost_metadata or {})
    details = dict(base.get("cost_details") or {})
    details["billable_units"] = units
    try:
        priced = fal_estimate_unit_price(
            model, units, api_key, timeout_seconds=timeout_seconds
        )
    except Exception as exc:  # noqa: BLE001
        details["billable_units_pricing_error"] = str(exc)[:200]
        base["cost_details"] = details
        return base
    return {
        "cost_usd": float(priced["cost_usd"]),
        "cost_currency": "USD",
        "cost_is_estimated": False,
        "cost_source": "fal_billable_units",
        "cost_reason": (
            "fal.ai reported the billed quantity in x-fal-billable-units; priced with "
            "the official pricing API at the account's unit rate."
        ),
        "cost_details": {**details, "pricing_estimate": priced.get("pricing_estimate")},
    }


def _extract_image_url(payload):
    """Extrai a primeira URL de imagem de um payload da fal.ai."""

    if not isinstance(payload, dict):
        return ""
    images = payload.get("images")
    if isinstance(images, list) and images:
        first = images[0]
        if isinstance(first, dict) and first.get("url"):
            return str(first["url"])
    image = payload.get("image")
    if isinstance(image, dict) and image.get("url"):
        return str(image["url"])
    return ""


def _cost_result_kwargs(cost_metadata):
    """Convert normalized cost metadata into image result builder kwargs."""

    if not isinstance(cost_metadata, dict):
        return {}
    details = {}
    if isinstance(cost_metadata.get("cost_details"), dict):
        details.update(cost_metadata["cost_details"])
    if cost_metadata.get("cost_reason"):
        details.setdefault("cost_reason", cost_metadata["cost_reason"])
    if cost_metadata.get("pricing_estimate") is not None:
        details.setdefault("pricing_estimate", cost_metadata["pricing_estimate"])
    return {
        "cust_usd": cost_metadata.get("cost_usd") or 0.0,
        "cost_source": cost_metadata.get("cost_source") or "unavailable",
        "cost_is_estimated": bool(cost_metadata.get("cost_is_estimated", True)),
        "cost_details": details,
    }


def _run_image_job(
    *,
    model,
    body,
    api_key,
    timeout_seconds,
    build_result,
    operation,
    preprocess_warnings="",
    cost_metadata=None,
):
    """Executa o ciclo completo submit → poll → download para operações de imagem."""

    # Declarados fuera del `try`: si algo falla después del submit, el id ya existe y el
    # `except` lo tiene que devolver. Antes se perdía y el error quedaba sin id.
    submit_request_id = ""
    request_id = ""
    try:
        submit_response, submit_payload = _submit_queue(
            model=model,
            body=body,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
        )
        submit_request_id = extract_request_id(submit_response, submit_payload)

        polled = _poll_completion(
            submission=submit_payload,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
        )
        final_payload, last_status, error = polled[0], polled[1], polled[2]
        final_headers = polled[3] if len(polled) > 3 else {}
        request_id = (
            extract_request_id(payload=final_payload or last_status or {})
            or submit_request_id
        )

        if final_payload is None:
            return build_result(
                warnings=join_warnings(
                    preprocess_warnings,
                    error or "fal.ai request did not complete successfully.",
                ),
                request_id=request_id,
            )
        cost_metadata = billable_units_cost(
            model=model,
            headers=final_headers,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            cost_metadata=cost_metadata,
        )

        blocked = detect_block(final_payload, operation=operation)
        if blocked is not None:
            return build_result(
                warnings=join_warnings(preprocess_warnings, blocked.warning),
                request_id=request_id or blocked.request_id,
            )

        image_url = _extract_image_url(final_payload)
        if not image_url:
            return build_result(
                warnings=join_warnings(
                    preprocess_warnings,
                    "fal.ai did not return a downloadable image payload.",
                ),
                request_id=request_id,
            )

        return build_result(
            base64_value=download_image_as_base64_png(
                image_url,
                timeout_seconds=timeout_seconds,
            ),
            warnings=preprocess_warnings,
            request_id=request_id,
            **_cost_result_kwargs(cost_metadata),
        )
    except Exception as exc:
        return build_result(
            warnings=join_warnings(preprocess_warnings, provider_error_to_warning(exc)),
            request_id=request_id or submit_request_id or request_id_of(exc),
        )


def generate_image(
    *,
    api_key,
    prepared,
    model,
    output_format,
    timeout_seconds,
    build_result,
    seed=None,
    extra_body=None,
    cost_metadata=None,
):
    """Executa a geração text-to-image em um modelo da fal.ai.

    ### Parâmetros:
        api_key: Credencial resolvida via ``FAL_KEY``.
        prepared: Entrada normalizada de ``generate`` com o prompt final.
        model: Identificador público do modelo na fal.ai.
        output_format: ``png`` ou ``jpeg`` encaminhado ao provedor.
        timeout_seconds: Timeout total da execução.
        build_result: Construtor do contrato público de imagem.
        seed: Semente opcional para reprodutibilidade.

    ### Retorna:
        Dict no contrato normalizado de ``generate``.
    """

    body = {"prompt": prepared.prompt, "output_format": output_format}
    if seed is not None:
        body["seed"] = seed
    if extra_body:
        body.update(extra_body)
    return _run_image_job(
        model=model,
        body=body,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        build_result=build_result,
        operation="generate",
        cost_metadata=cost_metadata,
    )


def _build_edit_body(*, model, prepared, output_format, seed, extra_body=None):
    """Monta o corpo da requisição de ``edit`` conforme a família do modelo."""

    input_image_data_url = image_to_data_url(prepared.image)
    body = {"prompt": prepared.prompt, "output_format": output_format}
    if seed is not None:
        body["seed"] = seed
    if model in _EDIT_SINGLE_IMAGE_MODELS:
        body["image_url"] = input_image_data_url
    else:
        body["image_urls"] = [input_image_data_url]
    if prepared.mask is not None and model in _EDIT_MASK_MODELS:
        mask_data_url = image_to_data_url(prepared.mask)
        body["mask_url"] = mask_data_url
    if extra_body:
        body.update(extra_body)
    return body


def edit_image(
    *,
    api_key,
    prepared,
    model,
    output_format,
    timeout_seconds,
    build_result,
    seed=None,
    extra_body=None,
    cost_metadata=None,
):
    """Executa a edição image+prompt em um modelo da fal.ai.

    ### Parâmetros:
        api_key: Credencial resolvida via ``FAL_KEY``.
        prepared: Entrada normalizada de ``edit``.
        model: Identificador público do modelo na fal.ai.
        output_format: ``png`` ou ``jpeg`` encaminhado ao provedor.
        timeout_seconds: Timeout total da execução.
        build_result: Construtor do contrato público de imagem.
        seed: Semente opcional.

    ### Retorna:
        Dict no contrato normalizado de ``edit``. Quando uma máscara é fornecida
        e o modelo não suporta inpainting via máscara, o aviso é propagado por
        ``warnings`` e a edição segue sem máscara.
    """

    warnings = prepared.preprocess_warnings
    if prepared.mask is not None and model not in _EDIT_MASK_MODELS:
        warnings = join_warnings(
            warnings,
            f"fal.ai model `{model}` does not accept an uploaded mask; the mask was ignored.",
        )
    body = _build_edit_body(
        model=model,
        prepared=prepared,
        output_format=output_format,
        seed=seed,
        extra_body=extra_body,
    )
    return _run_image_job(
        model=model,
        body=body,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        build_result=build_result,
        operation="edit",
        preprocess_warnings=warnings,
        cost_metadata=cost_metadata,
    )


def remix_image(
    *,
    api_key,
    prepared,
    model,
    output_format,
    timeout_seconds,
    build_result,
    seed=None,
    extra_body=None,
    cost_metadata=None,
):
    """Executa a geração guiada por referências na fal.ai.

    Os modelos da fal.ai que suportam ``remix`` recebem uma lista de imagens via
    ``image_urls``. Quando ``base_image`` é informado, ele vira a primeira
    referência, mantendo o comportamento de âncora usado por outros provedores.

    ### Parâmetros:
        api_key: Credencial resolvida via ``FAL_KEY``.
        prepared: Entrada normalizada de ``remix``.
        model: Identificador público do modelo.
        output_format: ``png`` ou ``jpeg`` encaminhado ao provedor.
        timeout_seconds: Timeout total da execução.
        build_result: Construtor do contrato público de imagem.
        seed: Semente opcional.

    ### Retorna:
        Dict no contrato normalizado de ``remix``.
    """

    references = list(prepared.reference_images)
    if prepared.base_image is not None:
        references = [prepared.base_image, *references]
    image_urls = [image_to_data_url(asset) for asset in references]

    body = {
        "prompt": prepared.prompt,
        "image_urls": image_urls,
        "output_format": output_format,
    }
    if seed is not None:
        body["seed"] = seed
    if extra_body:
        body.update(extra_body)
    return _run_image_job(
        model=model,
        body=body,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        build_result=build_result,
        operation="remix",
        cost_metadata=cost_metadata,
    )


def analyze_image(
    *,
    api_key,
    prepared,
    model,
    timeout_seconds,
    build_result,
    vision_endpoint="fal-ai/any-llm/vision",
    extra_body=None,
):
    """Executa análise de imagem via endpoint multimodal da fal.ai.

    O endpoint público é sempre o mesmo (``fal-ai/any-llm/vision``) e a escolha
    do modelo subjacente é feita pelo campo ``model`` no corpo da requisição.

    ### Parâmetros:
        api_key: Credencial resolvida via ``FAL_KEY``.
        prepared: Entrada normalizada de ``analyze``.
        model: Identificador do modelo VLM subjacente (ex.: ``google/gemini-2.5-flash``).
        timeout_seconds: Timeout total da execução.
        build_result: Construtor do contrato público de ``analyze``.
        vision_endpoint: Endpoint da fal.ai usado para o roteamento VLM.

    ### Retorna:
        Dict no contrato normalizado de ``analyze``.
    """

    submit_request_id = ""
    request_id = ""
    try:
        image_data_url = image_to_data_url(prepared.image)
        body = {
            "prompt": prepared.prompt,
            "image_urls": [image_data_url],
            "model": model,
        }
        if extra_body:
            body.update(extra_body)
        submit_response, submit_payload = _submit_queue(
            model=vision_endpoint,
            body=body,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
        )
        submit_request_id = extract_request_id(submit_response, submit_payload)

        polled = _poll_completion(
            submission=submit_payload,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
        )
        final_payload, last_status, error = polled[0], polled[1], polled[2]
        request_id = (
            extract_request_id(payload=final_payload or last_status or {})
            or submit_request_id
        )

        if final_payload is None:
            return build_result(
                request_id=request_id,
                input_text=prepared.prompt,
                output=error or "fal.ai request did not complete successfully.",
            )

        blocked = detect_block(final_payload, operation="analyze")
        if blocked is not None:
            return build_result(
                request_id=request_id or blocked.request_id,
                input_text=prepared.prompt,
                output=blocked.warning,
            )

        output_text = (
            final_payload.get("output")
            or final_payload.get("response")
            or final_payload.get("text")
            or ""
        )
        if not output_text:
            output_text = "fal.ai vision endpoint did not return textual output."

        return build_result(
            request_id=request_id,
            input_text=prepared.prompt,
            output=str(output_text).strip(),
        )
    except Exception as exc:
        return build_result(
            request_id=request_id or submit_request_id or request_id_of(exc),
            input_text=prepared.prompt,
            output=provider_error_to_warning(exc),
        )
