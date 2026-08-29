"""Entrypoint do backfill inicial (.github/workflows/backfill.yml, disparado
manualmente). Carrega o snapshot 'anual' (acumulado do ano corrente),
filtrando pela janela definida em config.JANELA_HISTORICO_DIAS."""

import datetime as dt

import config
import migrate
from pipeline.load_snapshot import carregar_snapshot


def main() -> None:
    migrate.run()
    cutoff = dt.date.today() - dt.timedelta(days=config.JANELA_HISTORICO_DIAS)
    print(f"backfill: carregando licitacoes publicadas a partir de {cutoff}")
    carregar_snapshot("anual", cutoff=cutoff)


if __name__ == "__main__":
    main()
