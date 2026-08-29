"""Script de uso unico: preenche a coluna 'produto' (adicionada depois que
os itens ja tinham sido carregados) pra todas as linhas existentes de
'itens' com produto ainda nulo. Daqui pra frente, load.upsert_itens_lote
ja preenche isso na carga normal - rodar este script so faz sentido uma
vez, logo apos aplicar a migracao que criou a coluna."""

import migrate
from db.connection import get_conn
from pipeline.normalize import extrair_produto

_LOTE = 2000


def main() -> None:
    migrate.run()
    atualizados = 0
    with get_conn() as conn:
        while True:
            linhas = conn.execute(
                "SELECT id, descricao_item FROM itens WHERE produto IS NULL ORDER BY id LIMIT %s",
                (_LOTE,),
            ).fetchall()
            if not linhas:
                break

            valores = [(item_id, extrair_produto(descricao)) for item_id, descricao in linhas]
            placeholders = ",".join(["(%s,%s)"] * len(valores))
            params = [v for par in valores for v in par]
            conn.execute(
                f"""
                UPDATE itens AS i SET produto = v.produto
                FROM (VALUES {placeholders}) AS v(id, produto)
                WHERE i.id = v.id::bigint
                """,
                params,
            )
            conn.commit()
            atualizados += len(valores)
            print(f"produto preenchido: {atualizados} itens (até id {linhas[-1][0]})")

    print(f"concluído: {atualizados} itens atualizados")


if __name__ == "__main__":
    main()
