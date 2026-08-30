"""Orquestra o carregamento de um 'snapshot' dos arquivos em lote do
Compras.gov.br: baixa os 3 CSVs (compra, item, resultado) e carrega no
banco, nessa ordem - item e resultado dependem da licitacao/item
correspondente ja existir na tabela.

Tudo em streaming (nunca acumula um arquivo inteiro em memoria) e em lote
(varias linhas por INSERT) - ver pipeline.load e clients.bulk_csv_client."""

import datetime as dt

import config
from clients.bulk_csv_client import baixar_csv
from db.connection import get_conn
from pipeline import load
from pipeline.normalize import parse_date


def _filtrar_por_data(linhas, cutoff: dt.date):
    for row in linhas:
        data_pub = parse_date(row.get("data_publicacao_pncp"))
        if data_pub is None or data_pub >= cutoff:
            yield row


def carregar_snapshot_urls(url_compra: str, url_item: str, url_resultado: str, cutoff: dt.date | None = None) -> None:
    """Carrega um snapshot a partir de URLs explicitas (usado pro backfill,
    que precisa combinar o arquivo do ano corrente com arquivos de anos
    anteriores - formatos de URL diferentes, ver config.url_csv_ano)."""
    with get_conn() as conn:
        compras = baixar_csv(url_compra)
        if cutoff is not None:
            compras = _filtrar_por_data(compras, cutoff)
        cache_orgao: dict = {}
        cache_unidade: dict = {}
        cache_licitacao = load.upsert_licitacoes_lote(conn, compras, cache_orgao, cache_unidade)

        itens = baixar_csv(url_item)
        load.upsert_itens_lote(conn, itens, cache_licitacao)

        resultados = baixar_csv(url_resultado)
        load.upsert_resultados_lote(conn, resultados, cache_licitacao)


def carregar_snapshot(periodo: str, cutoff: dt.date | None = None) -> None:
    """periodo: 'diario' | 'mensal' | 'anual' (ano corrente, arquivo
    '-latest')."""
    carregar_snapshot_urls(
        config.url_csv(periodo, "VW_FT_PNCP_COMPRA"),
        config.url_csv(periodo, "VW_FT_PNCP_COMPRA_ITEM"),
        config.url_csv(periodo, "VW_DM_PNCP_ITEM_RESULTADO"),
        cutoff,
    )


def carregar_snapshot_ano(ano: int, cutoff: dt.date | None = None) -> None:
    """Carrega o arquivo de historico completo de um ano especifico
    (2021-2025) - formato de URL diferente do 'anual' (ano corrente)."""
    carregar_snapshot_urls(
        config.url_csv_ano(ano, "VW_FT_PNCP_COMPRA"),
        config.url_csv_ano(ano, "VW_FT_PNCP_COMPRA_ITEM"),
        config.url_csv_ano(ano, "VW_DM_PNCP_ITEM_RESULTADO"),
        cutoff,
    )
