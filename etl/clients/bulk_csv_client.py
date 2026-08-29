"""Cliente para os arquivos em lote (CSV) do Compras.gov.br/PNCP, hospedados
em repositorio.dados.gov.br - um dominio estatico separado da API ao vivo do
PNCP. Confirmado por diagnostico em 2026-08-29: esse dominio respondeu
consistentemente (3/3) do GitHub Actions, enquanto a API ao vivo do PNCP
se mostrou instavel mesmo fora daquela janela de teste. Cada arquivo
'diario' traz os registros novos/alterados no dia; 'anual' traz o
acumulado do ano corrente - usado so pra popular o historico na primeira
vez (ver docs/plano)."""

import csv
import io

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

_TIMEOUT = httpx.Timeout(120.0, connect=15.0)


@retry(
    reraise=True,
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=3, max=60),
    retry=retry_if_exception_type(httpx.HTTPStatusError) | retry_if_exception_type(httpx.TransportError),
)
def baixar_csv(url: str) -> list[dict]:
    """Baixa o CSV inteiro e devolve a lista de linhas (dict por linha).
    Os arquivos vao de alguns MB (diario) a algumas dezenas de MB (anual) -
    cabe na memoria sem problema nesse volume."""
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.get(url)
        resp.raise_for_status()
        texto = resp.content.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(texto)))
