"""Cliente de geracao texto->texto para a Responses API da OpenAI.

Ultima atualizacao: 2026-04-23
"""

from requests import exceptions as requests_exceptions

from ..post_processing import (
    atualizar_custo_no_resultado as _atualizar_custo_no_resultado,
)
from ..post_processing import (
    calcular_custo_tokens as _calcular_custo_tokens,
)
from ..post_processing import (
    extrair_request_id as _extrair_request_id,
)
from ..post_processing import (
    extrair_texto_openai_responses as _extrair_texto_openai_responses,
)
from ..post_processing import (
    montar_resultado as _montar_resultado,
)
from ..post_processing import (
    normalizar_resultado_publico as _normalizar_resultado_publico,
)
from ..post_processing import (
    normalizar_uso as _normalizar_uso,
)
from ..pre_processing import (
    obter_chave_api as _obter_chave_api,
)
from ..pre_processing import (
    remover_nulos as _remover_nulos,
)
from ..pre_processing import (
    requisicao_json as _requisicao_json,
)
from ._shared import (
    OPENAI_RESPONSES_PARAMETERS,
)
from ._shared import (
    execute_json_request as _execute_json_request,
)
from ._shared import (
    normalize_reasoning_value as _normalize_reasoning_value,
)
from ._shared import (
    validate_kwargs as _validate_kwargs,
)

_PRECOS_MODELOS = {
    # Preço oficial da OpenAI em 2026-09-23; batch e flex custam a metade.
    "gpt-6-sol": {
        "standard": {
            "short": {"input": 2.0, "cached_input": 0.20, "output": 10.0},
        },
        "batch": {
            "short": {"input": 1.0, "cached_input": 0.10, "output": 5.0},
        },
        "flex": {
            "short": {"input": 1.0, "cached_input": 0.10, "output": 5.0},
        },
    },
    "gpt-6-luna": {
        "standard": {
            "short": {"input": 0.10, "cached_input": 0.01, "output": 0.50},
        },
        "batch": {
            "short": {"input": 0.05, "cached_input": 0.005, "output": 0.25},
        },
        "flex": {
            "short": {"input": 0.05, "cached_input": 0.005, "output": 0.25},
        },
    },
    "gpt-5.4-pro": {
        "standard": {
            "short": {"input": 30.0, "output": 180.0},
            "long": {"input": 60.0, "output": 270.0},
        },
        "batch": {
            "short": {"input": 15.0, "output": 90.0},
            "long": {"input": 30.0, "output": 135.0},
        },
        "flex": {
            "short": {"input": 15.0, "output": 90.0},
            "long": {"input": 30.0, "output": 135.0},
        },
    },
    "gpt-5.4-mini": {
        "standard": {
            "short": {"input": 0.75, "cached_input": 0.075, "output": 4.5},
        },
        "batch": {
            "short": {"input": 0.375, "cached_input": 0.0375, "output": 2.25},
        },
        "flex": {
            "short": {"input": 0.375, "cached_input": 0.0375, "output": 2.25},
        },
        "priority": {
            "short": {"input": 1.50, "cached_input": 0.15, "output": 9.0},
        },
    },
    "gpt-5.4-nano": {
        "standard": {
            "short": {"input": 0.20, "cached_input": 0.02, "output": 1.25},
        },
        "batch": {
            "short": {"input": 0.10, "cached_input": 0.01, "output": 0.625},
        },
        "flex": {
            "short": {"input": 0.10, "cached_input": 0.01, "output": 0.625},
        },
    },
    "gpt-5.4": {
        "standard": {
            "short": {"input": 2.5, "cached_input": 0.25, "output": 15.0},
            "long": {"input": 5.0, "cached_input": 0.50, "output": 22.5},
        },
        "batch": {
            "short": {"input": 1.25, "cached_input": 0.13, "output": 7.5},
            "long": {"input": 2.5, "cached_input": 0.25, "output": 11.25},
        },
        "flex": {
            "short": {"input": 1.25, "cached_input": 0.13, "output": 7.5},
            "long": {"input": 2.5, "cached_input": 0.25, "output": 11.25},
        },
        "priority": {
            "short": {"input": 5.0, "cached_input": 0.50, "output": 30.0},
        },
    },
    "gpt-5.3-chat-latest": {
        "short": {"input": 1.75, "cached_input": 0.175, "output": 14.0},
    },
    "gpt-5.3-codex": {
        "short": {"input": 1.75, "cached_input": 0.175, "output": 14.0},
    },
    "gpt-5.2-pro": {
        "short": {"input": 21.0, "output": 168.0},
    },
    "gpt-5.2": {
        "short": {"input": 1.75, "cached_input": 0.175, "output": 14.0},
    },
    "gpt-5.1": {
        "short": {"input": 1.25, "cached_input": 0.125, "output": 10.0},
    },
    "gpt-5": {
        "short": {"input": 1.25, "cached_input": 0.125, "output": 10.0},
    },
    "gpt-5-mini": {
        "short": {"input": 0.25, "cached_input": 0.025, "output": 2.0},
    },
    "gpt-5-nano": {
        "short": {"input": 0.05, "cached_input": 0.005, "output": 0.4},
    },
    "gpt-4.1": {
        "short": {"input": 2.0, "cached_input": 0.5, "output": 8.0},
    },
    "gpt-4.1-mini": {
        "short": {"input": 0.4, "cached_input": 0.1, "output": 1.6},
    },
    "gpt-4.1-nano": {
        "short": {"input": 0.1, "cached_input": 0.025, "output": 0.4},
    },
    "gpt-4o": {
        "short": {"input": 2.5, "cached_input": 1.25, "output": 10.0},
    },
    "gpt-4o-mini": {
        "short": {"input": 0.15, "cached_input": 0.075, "output": 0.6},
    },
}
_CHAVES_MODELOS_ORDENADAS = sorted(_PRECOS_MODELOS, key=len, reverse=True)


def generate(
    input_text,
    instruction=None,
    model="gpt-5-nano",
    **kwargs,
):
    """Generate text with OpenAI Responses. Full details: text/docs/openai.md."""
    _validate_kwargs(
        provider="openai",
        api="responses",
        model=model,
        kwargs=kwargs,
        supported_parameters=OPENAI_RESPONSES_PARAMETERS,
    )
    chave = _obter_chave_api("OPENAI_API_KEY")
    parametros = dict(kwargs)
    if "reasoning" in parametros:
        parametros["reasoning"] = _normalize_reasoning_value(parametros["reasoning"])

    corpo = _montar_corpo_responses(
        input_text=input_text,
        instruction=instruction,
        model=model,
        parametros_extras=parametros,
    )
    headers = {
        "Authorization": f"Bearer {chave}",
        "Content-Type": "application/json",
    }
    resposta_json, resposta_http = _execute_json_request(
        method="POST",
        url="https://api.openai.com/v1/responses",
        headers=headers,
        payload=corpo,
        stream_kind="openai_responses",
    )
    uso = _normalizar_uso(resposta_json.get("usage") or {})
    resultado = _montar_resultado(
        provider="openai",
        model=model,
        input_text=input_text,
        instruction=instruction,
        output_text=_extrair_texto_openai_responses(resposta_json),
        request_id=_extrair_request_id(resposta_json, resposta_http),
        usage=uso,
    )
    custo = _calcular_custo(
        modelo=model,
        uso=uso,
        service_tier=corpo.get("service_tier"),
    )
    _atualizar_custo_no_resultado(resultado, custo, origem="usage_x_pricing_page")
    return _normalizar_resultado_publico(resultado)


def list_models(api_key=None, timeout=180):
    """Lista os modelos atualmente expostos para a conta da OpenAI."""
    chave = _obter_chave_api("OPENAI_API_KEY", api_key=api_key)
    resposta_json, _ = _requisicao_json(
        metodo="GET",
        url="https://api.openai.com/v1/models",
        headers={"Authorization": f"Bearer {chave}"},
        timeout=timeout,
    )
    return resposta_json.get("data") or []


def update_cost(resultado):
    """Atualiza `cost_usd` consultando a resposta persistida da OpenAI."""
    resposta_json = None
    request_id = resultado.get("request_id")
    uso = resultado.get("usage") or {}
    if request_id:
        try:
            chave = _obter_chave_api("OPENAI_API_KEY")
            resposta_json, _ = _requisicao_json(
                metodo="GET",
                url=f"https://api.openai.com/v1/responses/{request_id}",
                headers={"Authorization": f"Bearer {chave}"},
            )
            uso = _normalizar_uso(resposta_json.get("usage") or uso)
            resultado["usage"] = uso
            if resposta_json.get("model"):
                resultado["model"] = resposta_json.get("model")
            if resposta_json.get("service_tier"):
                resultado["service_tier"] = resposta_json.get("service_tier")
        except (RuntimeError, requests_exceptions.RequestException):
            pass

    custo = _calcular_custo(
        modelo=resultado.get("model"),
        uso=uso,
        service_tier=resultado.get("service_tier"),
    )
    _atualizar_custo_no_resultado(resultado, custo, origem="usage_x_pricing_page")
    if resposta_json and not resultado.get("output_text"):
        resultado["output_text"] = _extrair_texto_openai_responses(resposta_json)
    return resultado


def _montar_reasoning(reasoning):
    """Monta o objeto `reasoning` a partir do nivel simplificado do wrapper."""
    effort = _normalizar_opcional(reasoning)
    if not effort:
        return None
    return {"effort": effort}


def _montar_corpo_responses(
    input_text,
    instruction=None,
    model=None,
    parametros_extras=None,
):
    """Monta o corpo da Responses API."""
    corpo = _remover_nulos(
        {
            "model": model,
            "instructions": instruction,
            "input": input_text,
        }
    )
    if parametros_extras:
        corpo.update(_remover_nulos(parametros_extras))
    return corpo


def _calcular_custo(modelo, uso, service_tier=None):
    """Calcula o custo em USD usando `usage` e a tabela publica da OpenAI."""
    precos, usa_multiplicador = _resolver_preco_modelo(modelo, uso, service_tier)
    if not precos:
        return 0.0

    custo = _calcular_custo_tokens(uso, precos)
    if not usa_multiplicador:
        return custo

    multiplicador = _resolver_multiplicador_service_tier(service_tier)
    return custo * multiplicador


def _resolver_preco_modelo(modelo, uso, service_tier=None):
    """Resolve a tabela de precos adequada ao modelo informado."""
    modelo_normalizado = (modelo or "").lower()
    for chave in _CHAVES_MODELOS_ORDENADAS:
        if chave not in modelo_normalizado:
            continue

        tabela = _PRECOS_MODELOS[chave]
        if _tabela_tem_tiers_explicitos(tabela):
            tabela_tier = _resolver_tabela_service_tier(tabela, service_tier)
            if "long" in tabela_tier and _usa_contexto_longo(modelo_normalizado, uso):
                return tabela_tier["long"], False
            return tabela_tier.get("short"), False

        if "long" in tabela and _usa_contexto_longo(modelo_normalizado, uso):
            return tabela["long"], True
        return tabela.get("short"), True
    return None, False


def _usa_contexto_longo(modelo, uso):
    """Retorna se o request cai na faixa de contexto longo da tabela."""
    if "gpt-5.4" not in modelo:
        return False
    input_tokens = (uso or {}).get("input_tokens", 0) or 0
    return input_tokens > 270000


def _resolver_multiplicador_service_tier(service_tier):
    """Retorna o multiplicador de preco do tier utilizado."""
    tier = (_normalizar_opcional(service_tier) or "").lower()
    if tier == "flex":
        return 0.5
    if tier == "priority":
        return 2.0
    return 1.0


def _tabela_tem_tiers_explicitos(tabela):
    """Retorna se a tabela do modelo ja traz precos por `service_tier`."""
    return any(chave in tabela for chave in ("standard", "batch", "flex", "priority"))


def _resolver_tabela_service_tier(tabela, service_tier):
    """Resolve a faixa de preco do tier informado usando tabela explicita."""
    tier = (_normalizar_opcional(service_tier) or "standard").lower()
    return tabela.get(tier) or tabela.get("standard") or {}


def _normalizar_opcional(valor):
    """Normaliza strings opcionais do wrapper simplificado."""
    if valor is None:
        return None
    valor = str(valor).strip()
    if not valor or valor.lower() == "none":
        return None
    return valor
