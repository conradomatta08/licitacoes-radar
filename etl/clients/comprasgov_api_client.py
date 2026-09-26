"""Cliente para a API de dados abertos do Compras.gov.br
(dadosabertos.compras.gov.br/modulo-contratacoes), endpoints em lote de
contratacoes, itens e resultados do PNCP (Lei 14.133).

Substitui os arquivos CSV em lote (bulk_csv_client.py), parados desde
15/07/2026, e a API ao vivo do PNCP (pncp_live_client.py), que exige uma
chamada por contratacao/item e ficou inviavel (varias centenas de milhares
de chamadas). Aqui sao poucas dezenas de chamadas por dia, 500 registros
por pagina. Confirmado em 2026-09-26 contra o banco carregado dos CSVs:
14/07 e 16/06 batem 100% (mesmas contratacoes, sem diferenca nenhuma).

Detalhes confirmados empiricamente:
- tamanhoPagina tem que estar entre 10 e 500.
- contratacoes e itens: data final e EXCLUSIVA (faixa [D, D+1) = so o dia
  D; inicial == final devolve zero). Resultados: data final INCLUSIVA
  (faixa [D, D] = so o dia D).
- contratacoes exige codigoModalidade, e o codigo aqui NAO e o do PNCP
  (ex: Dispensa e 6 aqui, 8 no PNCP; Credenciamento e 0).
- itens sao filtrados pela data de inclusao no PNCP, resultados pela data
  do resultado (pode ser bem depois da publicacao da contratacao)."""

import datetime as dt
import time

import httpx

_BASE = "https://dadosabertos.compras.gov.br/modulo-contratacoes"
_TIMEOUT = httpx.Timeout(60.0, connect=15.0)
_TENTATIVAS = 6
_TAMANHO_PAGINA = 500
_PAUSA_ENTRE_CHAMADAS = 0.1

MODALIDADES = list(range(0, 21))


def _get(caminho: str, params: dict) -> dict:
    """404 NAO e tratado como 'sem dados' (a API devolve 200 com total 0
    quando nao ha registros; 404 aparece com parametros invalidos) - assim
    nunca escondemos um buraco. Falha de rede, 5xx, 429 ou corpo invalido
    tentam de novo com backoff e, esgotadas as tentativas, levantam."""
    for tentativa in range(1, _TENTATIVAS + 1):
        try:
            time.sleep(_PAUSA_ENTRE_CHAMADAS)
            resp = httpx.get(f"{_BASE}/{caminho}", params=params, timeout=_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except (httpx.TransportError, httpx.HTTPStatusError, ValueError) as e:
            if tentativa == _TENTATIVAS:
                raise
            espera = min(30, 3 * tentativa)
            print(f"  [aviso] falha em {caminho} {params} (tentativa {tentativa}/{_TENTATIVAS}): {e} - tentando de novo em {espera}s")
            time.sleep(espera)


def _paginar(caminho: str, filtros: dict):
    """Gera todos os registros e confere no fim que a quantidade recebida
    bate com o totalRegistros informado pela API."""
    pagina = 1
    recebidos = 0
    total = 0
    while True:
        corpo = _get(caminho, {"pagina": pagina, "tamanhoPagina": _TAMANHO_PAGINA, **filtros})
        total = corpo.get("totalRegistros") or 0
        registros = corpo.get("resultado") or []
        recebidos += len(registros)
        yield from registros
        if pagina >= (corpo.get("totalPaginas") or 0):
            break
        pagina += 1
    if recebidos != total:
        raise RuntimeError(f"{caminho} {filtros}: recebi {recebidos} registros mas a API informou {total}")


def contratacoes_do_dia(dia: dt.date):
    """Contratacoes publicadas no PNCP em `dia`, de todas as modalidades."""
    inicio = dia.isoformat()
    fim = (dia + dt.timedelta(days=1)).isoformat()
    for modalidade in MODALIDADES:
        yield from _paginar(
            "1_consultarContratacoes_PNCP_14133",
            {"dataPublicacaoPncpInicial": inicio, "dataPublicacaoPncpFinal": fim, "codigoModalidade": modalidade},
        )


def itens_do_dia(dia: dt.date):
    """Itens incluidos no PNCP em `dia`."""
    return _paginar(
        "2_consultarItensContratacoes_PNCP_14133",
        {"dataInclusaoPncpInicial": dia.isoformat(), "dataInclusaoPncpFinal": (dia + dt.timedelta(days=1)).isoformat()},
    )


def resultados_do_dia(dia: dt.date):
    """Resultados de itens registrados no PNCP em `dia` (data final
    inclusiva, ao contrario de contratacoes/itens)."""
    return _paginar(
        "3_consultarResultadoItensContratacoes_PNCP_14133",
        {"dataResultadoPncpInicial": dia.isoformat(), "dataResultadoPncpFinal": dia.isoformat()},
    )
