"""Backfill unico via API ao vivo do PNCP - cobre o periodo em que o
arquivo em lote do Compras.gov.br ficou parado sem publicar (15/07/2026 em
diante, confirmado em 2026-09-08, ver docs/plano). Dia a dia (nao o
periodo inteiro de uma vez so) pra dar visibilidade de progresso e permitir
retomar de onde parou em caso de falha - pode demorar horas (cada
contratacao custa pelo menos 1 chamada de API pros itens, mais 1 por item
ja homologado).

Uso: python backfill_live.py [AAAA-MM-DD-inicio [AAAA-MM-DD-fim]]
Sem argumento comeca em 2026-07-15 (ver DATA_INICIO_GAP) e vai ate hoje.
Idempotente - pode rodar de novo pro mesmo periodo sem duplicar nada."""

import datetime as dt
import sys

import migrate
from pipeline.load_live import carregar_periodo_live

DATA_INICIO_GAP = dt.date(2026, 7, 15)


def main() -> None:
    migrate.run()
    inicio = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else DATA_INICIO_GAP
    fim = dt.date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else dt.date.today()
    print(f"backfill live: {inicio.isoformat()} ate {fim.isoformat()}")

    dia = inicio
    while dia <= fim:
        data_str = dia.strftime("%Y%m%d")
        print(f"--- {dia.isoformat()} ---")
        carregar_periodo_live(data_str, data_str)
        dia += dt.timedelta(days=1)
    print("backfill live concluido")


if __name__ == "__main__":
    main()
