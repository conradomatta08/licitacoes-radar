"""Busca os itens de cada licitacao ainda nao itemizada. 404 vira lista
vazia (varios orgaos nao itemizam via API, so publicam o PDF do edital)."""

import config
from clients import pncp_client
from db.connection import get_conn
from pipeline import load
from time_budget import Deadline


def run() -> None:
    deadline = Deadline(config.MAX_RUNTIME_SECONDS)

    with get_conn() as conn:
        pendentes = conn.execute(
            """
            SELECT l.id, o.cnpj, l.ano_compra, l.sequencial_compra
            FROM licitacoes l
            JOIN orgaos o ON o.id = l.orgao_id
            WHERE l.itens_carregados = FALSE
            ORDER BY l.id
            """
        ).fetchall()

        processados = 0
        for licitacao_id, cnpj, ano, sequencial in pendentes:
            if deadline.expired():
                print("Orcamento de tempo esgotado, parando fetch_items.")
                break

            itens = pncp_client.listar_itens(cnpj, ano, sequencial)
            for item in itens:
                load.upsert_item(conn, licitacao_id, item)
            load.marcar_itens_carregados(conn, licitacao_id)
            conn.commit()
            processados += 1

        print(f"fetch_items: {processados}/{len(pendentes)} licitacoes processadas.")


if __name__ == "__main__":
    run()
