"""Entrypoint do workflow incremental (.github/workflows/ingest-incremental.yml),
via API de dados abertos do Compras.gov.br. Roda a cada 6h: recarrega os
ultimos DIAS_JANELA dias (sobreposicao proposital - o upsert e idempotente e
cobre execucoes perdidas e registros que chegam atrasados). Resultados de
licitacoes antigas entram pela data do resultado, nao pela da publicacao,
entao a janela tambem os captura."""

import datetime as dt
import sys

import migrate
from pipeline.load_comprasgov import carregar_periodo

DIAS_JANELA = 5


def main() -> None:
    migrate.run()
    hoje = dt.date.today()
    inicio = hoje - dt.timedelta(days=DIAS_JANELA)
    print(f"incremental comprasgov: {inicio.isoformat()} ate {hoje.isoformat()}")
    falhas = carregar_periodo(inicio, hoje)
    if falhas:
        print("FALHAS: " + ", ".join(f"{fase} {dia.isoformat()}" for fase, dia in falhas))
        sys.exit(1)


if __name__ == "__main__":
    main()
