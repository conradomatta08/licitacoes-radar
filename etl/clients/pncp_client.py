"""Cliente HTTP para a API publica do PNCP.

Endpoints e comportamento validados manualmente em 2026-08-28 (ver
docs em C:\\Users\\conra\\.claude\\plans\\humming-inventing-fern.md):

- Descoberta de licitacoes fica em /api/consulta (CONSULTA_BASE_URL).
- Itens e resultados de item ficam em /api/pncp (PNCP_BASE_URL), apesar de
  essa base tambem hospedar a API de manutencao (GET e publico, sem token).
- 404 em /itens ou /itens/{n}/resultados significa "nao ha dado" (o orgao
  nao itemizou, ou o item ainda nao tem resultado) - NAO e erro transiente,
  nao deve fazer retry, deve virar lista vazia.
- A API ja se mostrou instavel (503 em rajada) - todo GET tem retry/backoff.
"""

import time

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import CONSULTA_BASE_URL, PNCP_BASE_URL, REQUEST_DELAY_SECONDS

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class PncpNotFound(Exception):
    """404 - recurso nao existe (nao e erro transiente)."""


def _client() -> httpx.Client:
    return httpx.Client(timeout=_TIMEOUT, headers={"Accept": "application/json"})


@retry(
    reraise=True,
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type(httpx.HTTPStatusError) | retry_if_exception_type(httpx.TransportError),
)
def _get(url: str, params: dict | None = None) -> httpx.Response:
    time.sleep(REQUEST_DELAY_SECONDS)
    with _client() as client:
        resp = client.get(url, params=params)
        if resp.status_code == 404:
            raise PncpNotFound(url)
        resp.raise_for_status()
        return resp


def _get_json_or_default(url: str, params: dict | None, default):
    try:
        return _get(url, params).json()
    except PncpNotFound:
        return default


def listar_contratacoes_publicadas(data_inicial: str, data_final: str, modalidade: int, pagina: int, tamanho_pagina: int) -> dict:
    """data_inicial/data_final no formato AAAAMMDD. Retorna o envelope de paginacao completo."""
    url = f"{CONSULTA_BASE_URL}/v1/contratacoes/publicacao"
    params = {
        "dataInicial": data_inicial,
        "dataFinal": data_final,
        "codigoModalidadeContratacao": modalidade,
        "pagina": pagina,
        "tamanhoPagina": tamanho_pagina,
    }
    resp = _get(url, params)
    return resp.json()


def listar_contratacoes_atualizadas(data_inicial: str, data_final: str, modalidade: int, pagina: int, tamanho_pagina: int) -> dict:
    url = f"{CONSULTA_BASE_URL}/v1/contratacoes/atualizacao"
    params = {
        "dataInicial": data_inicial,
        "dataFinal": data_final,
        "codigoModalidadeContratacao": modalidade,
        "pagina": pagina,
        "tamanhoPagina": tamanho_pagina,
    }
    resp = _get(url, params)
    return resp.json()


def listar_itens(cnpj: str, ano: int, sequencial: int) -> list[dict]:
    url = f"{PNCP_BASE_URL}/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/itens"
    return _get_json_or_default(url, None, [])


def listar_resultados_item(cnpj: str, ano: int, sequencial: int, numero_item: int) -> list[dict]:
    url = f"{PNCP_BASE_URL}/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/itens/{numero_item}/resultados"
    return _get_json_or_default(url, None, [])
