"""Entrypoint do workflow diario (.github/workflows/reprocess-pending.yml).
Revisita licitacoes ainda sem resultado homologado, respeitando o backoff
de reverificacao."""

import migrate
from pipeline import fetch_items, fetch_resultados, reprocess


def main() -> None:
    migrate.run()
    reprocess.run()
    fetch_items.run()
    fetch_resultados.run()


if __name__ == "__main__":
    main()
