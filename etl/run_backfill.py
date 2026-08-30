"""Entrypoint do backfill histórico (.github/workflows/backfill.yml, ou
rodado manualmente). Carrega o histórico completo a partir de
config.DATA_INICIO_HISTORICO: os arquivos de anos fechados anteriores ao
ano corrente (histórico completo de cada ano) e o arquivo do ano corrente
('-latest'), cada um filtrado pela mesma data de início. Idempotente -
pode ser rodado de novo sem duplicar nada."""

import datetime as dt

import migrate
from config import DATA_INICIO_HISTORICO
from pipeline.load_snapshot import carregar_snapshot, carregar_snapshot_ano


def main() -> None:
    migrate.run()
    print(f"backfill: carregando licitações publicadas a partir de {DATA_INICIO_HISTORICO}")

    ano_atual = dt.date.today().year
    for ano in range(DATA_INICIO_HISTORICO.year, ano_atual):
        print(f"--- ano {ano} (arquivo histórico completo) ---")
        carregar_snapshot_ano(ano, cutoff=DATA_INICIO_HISTORICO)

    print(f"--- ano corrente {ano_atual} (arquivo 'anual', mais recente) ---")
    carregar_snapshot("anual", cutoff=DATA_INICIO_HISTORICO)


if __name__ == "__main__":
    main()
