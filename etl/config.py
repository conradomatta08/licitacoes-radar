import os

REPOSITORIO_BASE_URL = "https://repositorio.dados.gov.br/seges/comprasgov"

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Usado so no backfill inicial (arquivo "anual"): ignora licitacoes publicadas
# antes desse numero de dias atras, pra manter o escopo da Fase 1 controlado.
JANELA_HISTORICO_DIAS = int(os.environ.get("JANELA_HISTORICO_DIAS", "120"))


def url_csv(periodo: str, view: str) -> str:
    """periodo: 'diario' | 'mensal' | 'anual'. view: nome da view, ex.
    VW_FT_PNCP_COMPRA, VW_FT_PNCP_COMPRA_ITEM, VW_DM_PNCP_ITEM_RESULTADO."""
    return f"{REPOSITORIO_BASE_URL}/{periodo}/comprasGOV-{periodo}-{view}-latest.csv"


def link_pncp(cnpj: str, ano: int, sequencial: int) -> str:
    return f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{sequencial}"
