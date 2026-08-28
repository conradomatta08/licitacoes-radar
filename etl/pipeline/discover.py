"""Descobre licitacoes novas: itera modalidade x dia (nao da pra pedir um
range grande de uma vez - so "Pregao - Eletronico" teve 307 registros em
2 dias, nacionalmente, no teste manual de 2026-08-28). Checkpoint por
modalidade permite retomar de onde parou."""

import datetime as dt

import config
from clients import pncp_client
from db.connection import get_conn
from pipeline import load
from time_budget import Deadline


def _daterange(inicio: dt.date, fim: dt.date):
    dia = inicio
    while dia <= fim:
        yield dia
        dia += dt.timedelta(days=1)


def run() -> None:
    deadline = Deadline(config.MAX_RUNTIME_SECONDS)
    hoje = dt.date.today()
    inicio_padrao = hoje - dt.timedelta(days=config.JANELA_HISTORICO_DIAS)

    with get_conn() as conn:
        for modalidade_id in config.MODALIDADES:
            if deadline.expired():
                print("Orcamento de tempo esgotado, parando discover.")
                break

            chave = f"modalidade={modalidade_id}"
            ultima = load.get_checkpoint(conn, "discover", chave)
            inicio = (ultima + dt.timedelta(days=1)) if ultima else inicio_padrao
            if inicio > hoje:
                continue

            for dia in _daterange(inicio, hoje):
                if deadline.expired():
                    break

                data_str = dia.strftime("%Y%m%d")
                pagina = 1
                while True:
                    if deadline.expired():
                        break
                    envelope = pncp_client.listar_contratacoes_publicadas(
                        data_str, data_str, modalidade_id, pagina, config.TAMANHO_PAGINA
                    )
                    registros = envelope.get("data", [])
                    for contratacao in registros:
                        load.upsert_licitacao(conn, contratacao)
                    conn.commit()

                    total_paginas = envelope.get("totalPaginas", 1)
                    print(f"modalidade={modalidade_id} dia={data_str} pagina={pagina}/{total_paginas} registros={len(registros)}")
                    if pagina >= total_paginas or not registros:
                        break
                    pagina += 1

                load.set_checkpoint(conn, "discover", chave, dia)
                conn.commit()

    print("discover concluido (ou pausado pelo orcamento de tempo).")


if __name__ == "__main__":
    run()
