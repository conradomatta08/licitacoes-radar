"""Backfill unico: popula resultados_item.material_ou_servico (duplicado
de itens, pro filtro Material/Servico do dashboard nao precisar de JOIN -
ver comentario em db/schema.sql) pras linhas que ja existiam antes dessa
coluna. Dai em diante, pipeline/load.py ja popula isso na carga.

Uso: python backfill_material_ou_servico.py"""

import migrate
from db.connection import get_conn

_TAMANHO_LOTE = 20_000


def main() -> None:
    migrate.run()
    total = 0
    cursor_id = 0
    with get_conn() as conn:
        while True:
            # Por faixa de id (nao "WHERE material_ou_servico IS NULL") -
            # mesmo motivo do backfill_uf_data_resultados.py: garante
            # progresso mesmo se a origem tambem estiver nula.
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
                SET material_ou_servico = i.material_ou_servico
                FROM alvo, itens i
                WHERE r.id = alvo.id AND i.id = r.item_id
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
