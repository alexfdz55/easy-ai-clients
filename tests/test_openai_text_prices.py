"""Preços de texto da OpenAI para o GPT-6.

A tabela casa o modelo por substring: sem linha própria, o gpt-6 não casa com nenhuma chave
e a chamada direta à OpenAI reporta custo 0, sem aviso.
"""

from __future__ import annotations

import pytest

from easy_ai_clients.text._apis.openai import _calcular_custo, _resolver_preco_modelo


def test_gpt_6_has_its_own_text_price() -> None:
    luna, _ = _resolver_preco_modelo("gpt-6-luna", {})
    assert luna == {"input": 0.10, "cached_input": 0.01, "output": 0.50}
    sol, _ = _resolver_preco_modelo("gpt-6-sol", {})
    assert sol == {"input": 2.0, "cached_input": 0.20, "output": 10.0}


def test_batch_and_flex_cost_half() -> None:
    flex, _ = _resolver_preco_modelo("gpt-6-luna", {}, service_tier="flex")
    assert flex == {"input": 0.05, "cached_input": 0.005, "output": 0.25}
    batch, _ = _resolver_preco_modelo("gpt-6-sol", {}, service_tier="batch")
    assert batch == {"input": 1.0, "cached_input": 0.10, "output": 5.0}


def test_gpt_6_cost_is_not_zero() -> None:
    usage = {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000}
    assert _calcular_custo("gpt-6-luna", usage) == pytest.approx(0.60)
