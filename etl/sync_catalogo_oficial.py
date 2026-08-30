"""Sincroniza as tabelas de referência do catálogo oficial (CATMAT PDM e
CATSER item) a partir da API pública dadosabertos.compras.gov.br. Roda
raramente (o catálogo muda pouco) - não faz parte do ingest diário. Uso:
  python sync_catalogo_oficial.py"""

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

import migrate
from db.connection import get_conn

_BASE_URL = "https://dadosabertos.compras.gov.br"
_TAMANHO_PAGINA = 500
_LOTE = 1000


@retry(
    reraise=True,
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=3, max=60),
    retry=retry_if_exception_type(httpx.HTTPStatusError) | retry_if_exception_type(httpx.TransportError),
)
def _buscar_pagina(caminho: str, pagina: int) -> dict:
    with httpx.Client(timeout=30) as client:
        resp = client.get(f"{_BASE_URL}{caminho}", params={"pagina": pagina, "tamanhoPagina": _TAMANHO_PAGINA})
        resp.raise_for_status()
        return resp.json()


def _baixar_tudo(caminho: str) -> list[dict]:
    linhas: list[dict] = []
    pagina = 1
    while True:
        dados = _buscar_pagina(caminho, pagina)
        linhas.extend(dados["resultado"])
        if pagina >= dados.get("totalPaginas", 0) or not dados["resultado"]:
            break
        pagina += 1
    return linhas


def _inserir_em_lotes(conn, tabela: str, colunas: list[str], linhas: list[tuple]) -> None:
    conn.execute(f"TRUNCATE {tabela}")
    n = len(colunas)
    placeholder_linha = "(" + ",".join(["%s"] * n) + ")"
    for i in range(0, len(linhas), _LOTE):
        lote = linhas[i : i + _LOTE]
        values_sql = ",".join([placeholder_linha] * len(lote))
        params = [v for linha in lote for v in linha]
        conn.execute(f"INSERT INTO {tabela} ({','.join(colunas)}) VALUES {values_sql}", params)
        conn.commit()


def _sem_duplicatas(tuplas: list[tuple]) -> list[tuple]:
    """A API pagina sem garantir unicidade entre paginas (o mesmo codigo as
    vezes repete) - mantem so a primeira ocorrencia de cada codigo (1a
    coluna da tupla, sempre a chave primaria aqui)."""
    vistos: dict = {}
    for t in tuplas:
        vistos.setdefault(t[0], t)
    return list(vistos.values())


def sync_material(conn) -> None:
    linhas = _baixar_tudo("/modulo-material/3_consultarPdmMaterial")
    tuplas = _sem_duplicatas([
        (r["codigoPdm"], r["nomePdm"], r.get("codigoClasse"), r.get("nomeClasse"), r.get("codigoGrupo"), r.get("nomeGrupo"))
        for r in linhas
        if r.get("codigoPdm") is not None
    ])
    _inserir_em_lotes(
        conn,
        "catalogo_material_pdm",
        ["codigo_pdm", "nome_pdm", "codigo_classe", "nome_classe", "codigo_grupo", "nome_grupo"],
        tuplas,
    )
    print(f"catalogo_material_pdm: {len(tuplas)} linhas")


def sync_servico(conn) -> None:
    linhas = _baixar_tudo("/modulo-servico/6_consultarItemServico")
    tuplas = _sem_duplicatas([
        (
            r["codigoServico"],
            r["nomeServico"],
            r.get("codigoClasse"),
            r.get("nomeClasse"),
            r.get("codigoGrupo"),
            r.get("nomeGrupo"),
            r.get("codigoDivisao"),
            r.get("nomeDivisao"),
            r.get("codigoSecao"),
            r.get("nomeSecao"),
        )
        for r in linhas
        if r.get("codigoServico") is not None
    ])
    _inserir_em_lotes(
        conn,
        "catalogo_servico_item",
        [
            "codigo_servico", "nome_servico", "codigo_classe", "nome_classe", "codigo_grupo", "nome_grupo",
            "codigo_divisao", "nome_divisao", "codigo_secao", "nome_secao",
        ],
        tuplas,
    )
    print(f"catalogo_servico_item: {len(tuplas)} linhas")


def main() -> None:
    migrate.run()
    with get_conn() as conn:
        sync_material(conn)
        sync_servico(conn)


if __name__ == "__main__":
    main()
