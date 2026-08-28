"""Entrypoint do workflow incremental (.github/workflows/ingest-incremental.yml).
Roda a cada 4-6h: aplica o schema, descobre licitacoes novas, busca itens e
busca resultados - nessa ordem, cada etapa com seu proprio orcamento de tempo."""

import migrate
from pipeline import discover, fetch_items, fetch_resultados


def main() -> None:
    migrate.run()
    discover.run()
    fetch_items.run()
    fetch_resultados.run()


if __name__ == "__main__":
    main()
