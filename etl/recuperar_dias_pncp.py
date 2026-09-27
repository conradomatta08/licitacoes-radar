"""Recupera dias inteiros pelo API ao vivo do PNCP quando a fonte principal
(Compras.gov.br) veio incompleta.

Uso: python recuperar_dias_pncp.py AAAA-MM-DD [AAAA-MM-DD ...]
Idempotente e retomavel (ver pipeline.load_live.recuperar_dia). Depois de
recuperar, rode a fase de resultados do Compras.gov.br do dia em diante:
python backfill_comprasgov.py AAAA-MM-DD hoje resultados"""

import datetime as dt
import sys

import migrate
from pipeline.load_live import recuperar_dia


def main() -> None:
    migrate.run()
    for arg in sys.argv[1:]:
        recuperar_dia(dt.date.fromisoformat(arg))
    print("recuperacao concluida")


if __name__ == "__main__":
    main()
