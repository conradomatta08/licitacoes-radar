"""Entrypoint do workflow incremental via API ao vivo do PNCP - alternativa
a run_ingest.py (baseado no arquivo em lote do Compras.gov.br, que parou de
publicar dados novos em 15/07/2026, ver docs/plano). Roda a cada 6h: busca
contratacoes publicadas nos ultimos DIAS_JANELA dias (sobreposicao
proposital com a execucao anterior - upsert e idempotente, nao duplica) e
reprocessa itens que ainda nao tinham resultado na ultima verificacao.

Mantido lado a lado com run_ingest.py (nao substitui) ate confirmar que a
API ao vivo continua estavel a partir do GitHub Actions - reverter e so
apontar o workflow de volta pra run_ingest.py."""

import datetime as dt

import migrate
from pipeline.load_live import carregar_periodo_live, reprocessar_pendentes

DIAS_JANELA = 4


def main() -> None:
    migrate.run()
    hoje = dt.date.today()
    inicio = hoje - dt.timedelta(days=DIAS_JANELA)
    data_inicial = inicio.strftime("%Y%m%d")
    data_final = hoje.strftime("%Y%m%d")
    print(f"buscando contratacoes de {data_inicial} a {data_final}...")
    carregar_periodo_live(data_inicial, data_final)
    print("reprocessando itens pendentes de resultado...")
    reprocessar_pendentes()


if __name__ == "__main__":
    main()
