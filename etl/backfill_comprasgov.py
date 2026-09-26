"""Backfill via API de dados abertos do Compras.gov.br.

Uso: python backfill_comprasgov.py AAAA-MM-DD-inicio [AAAA-MM-DD-fim [fases]]
Sem data final vai ate hoje. `fases` (opcional, separadas por virgula:
contratacoes,itens,resultados) permite rodar so parte. Idempotente - pode rodar de novo pro mesmo
periodo sem duplicar nada. Termina com codigo 1 se algum dia/fase falhou,
listando quais (ver pipeline.load_comprasgov.carregar_periodo)."""

import datetime as dt
import sys

import migrate
from pipeline.load_comprasgov import carregar_periodo


def main() -> None:
    migrate.run()
    inicio = dt.date.fromisoformat(sys.argv[1])
    fim = dt.date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else dt.date.today()
    print(f"backfill comprasgov: {inicio.isoformat()} ate {fim.isoformat()}")
    fases = tuple(sys.argv[3].split(",")) if len(sys.argv) > 3 else ("contratacoes", "itens", "resultados")
    falhas = carregar_periodo(inicio, fim, fases)
    if falhas:
        print("FALHAS (rodar de novo): " + ", ".join(f"{fase} {dia.isoformat()}" for fase, dia in falhas))
        sys.exit(1)
    print("backfill comprasgov concluido sem falhas")


if __name__ == "__main__":
    main()
