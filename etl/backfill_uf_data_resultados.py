"""Backfill unico: popula resultados_item.uf/data_publicacao_pncp (colunas
duplicadas de licitacoes, adicionadas pra acelerar os filtros mais comuns
do dashboard - ver comentario em db/schema.sql) pras ~2.8 milhoes de linhas
que ja existiam antes dessas colunas. Dai em diante, pipeline/load.py ja
populo isso na carga. Em lotes (nao um UPDATE gigante so) pra nao segurar
uma transacao enorme contra o Neon.

Uso: python backfill_uf_data_resultados.py"""

import migrate
from db.connection import get_conn

_TAMANHO_LOTE = 20_000


def main() -> None:
    migrate.run()
    total = 0
    cursor_id = 0
    with get_conn() as conn:
        while True:
            # Percorre por faixa de id (nao "WHERE uf IS NULL") de proposito:
            # se a licitacao de origem tambem tiver uf/data nulos, a linha
            # continuaria null apos o UPDATE e um filtro por "ainda esta
            # null" reseleciona ela pra sempre - por id sempre avanca.
            cur = conn.execute(
                """
                WITH alvo AS (
                    SELECT r.id
                    FROM resultados_item r
                    WHERE r.id > %s
                    ORDER BY r.id
                    LIMIT %s
                )
                UPDATE resultados_item r
                SET uf = l.uf, data_publicacao_pncp = l.data_publicacao_pncp
                FROM alvo, itens i, licitacoes l
                WHERE r.id = alvo.id AND i.id = r.item_id AND l.id = i.licitacao_id
                RETURNING r.id
                """,
                (cursor_id, _TAMANHO_LOTE),
            )
            ids = [row[0] for row in cur.fetchall()]
            conn.commit()
            if not ids:
                break
            cursor_id = max(ids)
            total += len(ids)
            print(f"  {total} linhas atualizadas (ate id={cursor_id})...")
            if len(ids) < _TAMANHO_LOTE:
                break
    print(f"concluido: {total} linhas atualizadas")


if __name__ == "__main__":
    main()
