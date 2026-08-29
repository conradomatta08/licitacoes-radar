"""Orquestra o carregamento de um 'snapshot' (diario ou anual) dos arquivos
em lote do Compras.gov.br: baixa os 3 CSVs (compra, item, resultado) e
carrega no banco, nessa ordem - item e resultado dependem da licitacao/item
correspondente ja existir na tabela.

Mantem caches em memoria (numero_controle_pncp -> licitacao_id,
(numero_controle_pncp, numero_item) -> item_id, cnpj -> orgao_id, etc) pra
evitar um SELECT por linha - essencial pra rodar num tempo razoavel com
dezenas de milhares de linhas por arquivo."""

import datetime as dt

import config
from clients.bulk_csv_client import baixar_csv
from db.connection import get_conn
from pipeline import load
from pipeline.normalize import parse_date, parse_int

_COMMIT_A_CADA = 1000


def _carregar_compras(conn, periodo: str, cutoff: dt.date | None) -> dict:
    url = config.url_csv(periodo, "VW_FT_PNCP_COMPRA")
    linhas = baixar_csv(url)
    cache_licitacao: dict = {}
    cache_orgao: dict = {}
    cache_unidade: dict = {}
    processadas = 0
    for i, row in enumerate(linhas, start=1):
        if cutoff is not None:
            data_pub = parse_date(row.get("data_publicacao_pncp"))
            if data_pub is not None and data_pub < cutoff:
                continue
        licitacao_id = load.upsert_licitacao_csv(conn, row, cache_orgao, cache_unidade)
        if licitacao_id is not None:
            cache_licitacao[row.get("numero_controle_PNCP")] = licitacao_id
            processadas += 1
        if i % _COMMIT_A_CADA == 0:
            conn.commit()
    conn.commit()
    print(f"compras ({periodo}): {processadas}/{len(linhas)} linhas carregadas")
    return cache_licitacao


def _carregar_itens(conn, periodo: str, cache_licitacao: dict) -> dict:
    url = config.url_csv(periodo, "VW_FT_PNCP_COMPRA_ITEM")
    linhas = baixar_csv(url)
    load.preload_licitacao_ids(conn, (r.get("numero_controle_PNCP_compra") for r in linhas), cache_licitacao)
    cache_item: dict = {}
    processadas = 0
    for i, row in enumerate(linhas, start=1):
        item_id = load.upsert_item_csv(conn, row, cache_licitacao)
        if item_id is not None:
            numero_controle = row.get("numero_controle_PNCP_compra")
            numero_item = parse_int(row.get("numero_item_compra"))
            cache_item[(numero_controle, numero_item)] = item_id
            processadas += 1
        if i % _COMMIT_A_CADA == 0:
            conn.commit()
    conn.commit()
    print(f"itens ({periodo}): {processadas}/{len(linhas)} linhas carregadas")
    return cache_item


def _carregar_resultados(conn, periodo: str, cache_licitacao: dict, cache_item: dict) -> None:
    url = config.url_csv(periodo, "VW_DM_PNCP_ITEM_RESULTADO")
    linhas = baixar_csv(url)
    load.preload_licitacao_ids(conn, (r.get("numero_controle_PNCP_compra") for r in linhas), cache_licitacao)
    for i, row in enumerate(linhas, start=1):
        load.upsert_resultado_csv(conn, row, cache_licitacao, cache_item)
        if i % _COMMIT_A_CADA == 0:
            conn.commit()
    conn.commit()
    print(f"resultados ({periodo}): {len(linhas)} linhas processadas")


def carregar_snapshot(periodo: str, cutoff: dt.date | None = None) -> None:
    with get_conn() as conn:
        cache_licitacao = _carregar_compras(conn, periodo, cutoff)
        cache_item = _carregar_itens(conn, periodo, cache_licitacao)
        _carregar_resultados(conn, periodo, cache_licitacao, cache_item)
