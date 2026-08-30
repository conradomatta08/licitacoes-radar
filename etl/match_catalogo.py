"""Casa o campo 'produto' de cada item com o catálogo oficial (CATMAT PDM
para materiais, CATSER item para serviços) por similaridade de texto
(pg_trgm) - roda uma vez por combinação distinta de (produto, tipo), não
por item, pra ser rápido (dezenas de milhares de combinações em vez de
centenas de milhares de itens). Resultado é uma correspondência
aproximada, não o código realmente usado na compra (o PNCP não registra
isso - ver comentário em db/schema.sql).

Uso: python match_catalogo.py"""

import migrate
from db.connection import get_conn

_LIMIAR_SIMILARIDADE = 0.3
_LOTE_CASAMENTO = 300
_LOTE_ATUALIZACAO = 1000


def _casar_lote(conn, tabela: str, coluna_nome: str, coluna_codigo: str, produtos: list[str]) -> dict:
    """Pra cada produto do lote, acha (via LATERAL JOIN, indice GIST) a
    linha mais parecida na tabela de catalogo - uma so consulta pro lote
    inteiro, nao uma por produto."""
    placeholders = ",".join(["(%s)"] * len(produtos))
    sql = f"""
        SELECT p.produto, m.{coluna_codigo}, m.{coluna_nome}, similarity(m.{coluna_nome}, p.produto) AS sim
        FROM (VALUES {placeholders}) AS p(produto)
        LEFT JOIN LATERAL (
            SELECT {coluna_codigo}, {coluna_nome}
            FROM {tabela}
            ORDER BY {coluna_nome} <-> p.produto
            LIMIT 1
        ) m ON true
    """
    linhas = conn.execute(sql, produtos).fetchall()
    resultado = {}
    for produto, codigo, nome, sim in linhas:
        if sim is not None and sim >= _LIMIAR_SIMILARIDADE:
            resultado[produto] = (codigo, nome, sim)
        else:
            resultado[produto] = (None, None, sim)
    return resultado


def _casar_todos(conn, tabela: str, coluna_nome: str, coluna_codigo: str, produtos: list[str]) -> dict:
    resultado: dict = {}
    for i in range(0, len(produtos), _LOTE_CASAMENTO):
        lote = produtos[i : i + _LOTE_CASAMENTO]
        resultado.update(_casar_lote(conn, tabela, coluna_nome, coluna_codigo, lote))
        print(f"  {tabela}: {min(i + _LOTE_CASAMENTO, len(produtos))}/{len(produtos)} produtos casados")
    return resultado


def _aplicar_em_itens(conn, tipo: str, matches: dict) -> None:
    chaves = list(matches.keys())
    for i in range(0, len(chaves), _LOTE_ATUALIZACAO):
        lote_chaves = chaves[i : i + _LOTE_ATUALIZACAO]
        valores = [(produto, *matches[produto]) for produto in lote_chaves]
        placeholders = ",".join(["(%s,%s::int,%s,%s::real)"] * len(valores))
        params = [v for linha in valores for v in linha]
        conn.execute(
            f"""
            UPDATE itens AS it SET
                catalogo_codigo = v.codigo,
                catalogo_nome = v.nome,
                catalogo_similaridade = v.sim
            FROM (VALUES {placeholders}) AS v(produto, codigo, nome, sim)
            WHERE it.produto = v.produto AND it.material_ou_servico = %s
            """,
            params + [tipo],
        )
        conn.commit()


def main() -> None:
    migrate.run()
    with get_conn() as conn:
        for tipo, tabela, coluna_nome, coluna_codigo in [
            ("M", "catalogo_material_pdm", "nome_pdm", "codigo_pdm"),
            ("S", "catalogo_servico_item", "nome_servico", "codigo_servico"),
        ]:
            produtos = [
                r[0]
                for r in conn.execute(
                    "SELECT DISTINCT produto FROM itens WHERE produto IS NOT NULL AND material_ou_servico = %s",
                    (tipo,),
                ).fetchall()
            ]
            print(f"tipo={tipo}: {len(produtos)} produtos distintos")
            matches = _casar_todos(conn, tabela, coluna_nome, coluna_codigo, produtos)
            _aplicar_em_itens(conn, tipo, matches)
            com_match = sum(1 for c, _, _ in matches.values() if c is not None)
            print(f"tipo={tipo}: {com_match}/{len(matches)} produtos com correspondência (similaridade >= {_LIMIAR_SIMILARIDADE})")

    print("concluído")


if __name__ == "__main__":
    main()
