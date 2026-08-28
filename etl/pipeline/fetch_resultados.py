"""Busca o resultado homologado (vencedor) de cada item marcado como
tem_resultado=TRUE e ainda nao carregado. No final, marca existe_resultado=TRUE
na licitacao so quando TODOS os itens conhecidos ja foram resolvidos - uma
licitacao pode ser homologada aos poucos, item por item."""

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
            SELECT i.id, o.cnpj, l.ano_compra, l.sequencial_compra, i.numero_item
            FROM itens i
            JOIN licitacoes l ON l.id = i.licitacao_id
            JOIN orgaos o ON o.id = l.orgao_id
            WHERE i.tem_resultado = TRUE AND i.resultado_carregado = FALSE
            ORDER BY i.id
            """
        ).fetchall()

        processados = 0
        for item_id, cnpj, ano, sequencial, numero_item in pendentes:
            if deadline.expired():
                print("Orcamento de tempo esgotado, parando fetch_resultados.")
                break

            resultados = pncp_client.listar_resultados_item(cnpj, ano, sequencial, numero_item)
            for resultado in resultados:
                load.upsert_resultado(conn, item_id, resultado)
            load.marcar_resultado_carregado(conn, item_id)
            conn.commit()
            processados += 1

        licitacoes_completas = conn.execute(
            """
            SELECT DISTINCT l.id
            FROM licitacoes l
            WHERE l.existe_resultado = FALSE
              AND l.itens_carregados = TRUE
              AND NOT EXISTS (
                  SELECT 1 FROM itens i
                  WHERE i.licitacao_id = l.id AND i.tem_resultado = TRUE AND i.resultado_carregado = FALSE
              )
              AND EXISTS (
                  SELECT 1 FROM itens i JOIN resultados_item r ON r.item_id = i.id
                  WHERE i.licitacao_id = l.id
              )
            """
        ).fetchall()
        for (licitacao_id,) in licitacoes_completas:
            load.marcar_existe_resultado(conn, licitacao_id)
        conn.commit()

        print(f"fetch_resultados: {processados}/{len(pendentes)} itens processados, {len(licitacoes_completas)} licitacoes concluidas.")


if __name__ == "__main__":
    run()
