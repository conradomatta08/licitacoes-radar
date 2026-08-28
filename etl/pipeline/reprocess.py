"""Reprocessamento diario de licitacoes 'em aberto' (ainda sem resultado).
Reagenda a proxima verificacao com backoff crescente e forca o fetch_items
a rever a lista de itens (pega o caso em que um item passa a ter resultado
depois da primeira consulta). Licitacoes com situacao terminal negativa
(revogada/anulada/cancelada/suspensa) saem da fila em vez de reprocessar
para sempre."""

from db.connection import get_conn
from pipeline import load

_SITUACOES_TERMINAIS = ("revogad", "anulad", "cancelad", "suspensa", "fracassad", "deserta")


def run() -> None:
    with get_conn() as conn:
        pendentes = conn.execute(
            """
            SELECT id, situacao_compra_nome FROM licitacoes
            WHERE existe_resultado = FALSE
              AND (proxima_verificacao_em IS NULL OR proxima_verificacao_em <= now())
            """
        ).fetchall()

        reagendadas = 0
        encerradas = 0
        for licitacao_id, situacao_nome in pendentes:
            situacao = (situacao_nome or "").lower()
            if any(termo in situacao for termo in _SITUACOES_TERMINAIS):
                load.marcar_existe_resultado(conn, licitacao_id)
                encerradas += 1
                continue

            conn.execute("UPDATE licitacoes SET itens_carregados = FALSE WHERE id = %s", (licitacao_id,))
            load.agendar_reverificacao(conn, licitacao_id)
            reagendadas += 1

        conn.commit()
        print(f"reprocess: {reagendadas} licitacoes reagendadas, {encerradas} encerradas por situacao terminal.")


if __name__ == "__main__":
    run()
