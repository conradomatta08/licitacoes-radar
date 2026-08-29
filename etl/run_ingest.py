"""Entrypoint do workflow incremental (.github/workflows/ingest-incremental.yml).
Roda a cada 6h: aplica o schema e carrega o snapshot 'diario' (registros
novos/alterados no dia) do Compras.gov.br."""

import migrate
from pipeline.load_snapshot import carregar_snapshot


def main() -> None:
    migrate.run()
    carregar_snapshot("diario")


if __name__ == "__main__":
    main()
