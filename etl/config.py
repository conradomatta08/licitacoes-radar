import datetime as dt
import os

REPOSITORIO_BASE_URL = "https://repositorio.dados.gov.br/seges/comprasgov"

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Escopo do historico coberto pelo backfill (etl/run_backfill.py) - decisao
# do usuario em 2026-08-29 apos avaliar custo de armazenamento no Neon
# (plano Launch, pago por uso). Licitacoes publicadas antes dessa data sao
# ignoradas mesmo se aparecerem nos arquivos anuais/por ano.
DATA_INICIO_HISTORICO = dt.date(2025, 1, 1)


def url_csv(periodo: str, view: str) -> str:
    """periodo: 'diario' | 'mensal' | 'anual'. view: nome da view, ex.
    VW_FT_PNCP_COMPRA, VW_FT_PNCP_COMPRA_ITEM, VW_DM_PNCP_ITEM_RESULTADO."""
    return f"{REPOSITORIO_BASE_URL}/{periodo}/comprasGOV-{periodo}-{view}-latest.csv"


def url_csv_ano(ano: int, view: str) -> str:
    """Arquivo com o historico completo de um ano especifico (2021-2025),
    sem o sufixo '-latest' e numa subpasta por ano - formato diferente do
    arquivo 'anual' (que so cobre o ano corrente)."""
    return f"{REPOSITORIO_BASE_URL}/anual/{ano}/comprasGOV-anual-{view}-{ano}.csv"


def link_pncp(cnpj: str, ano: int, sequencial: int) -> str:
    return f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{sequencial}"
