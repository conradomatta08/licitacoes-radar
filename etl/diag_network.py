"""Diagnostico temporario: compara conectividade do runner do GitHub Actions
com o GitHub (controle, deve sempre funcionar) e com o PNCP (varias
tentativas), pra confirmar se o PNCP bloqueia IPs de nuvem/CI conhecidos.
Nao faz parte do pipeline - apagar depois de usar."""

import time

import httpx

ALVOS = [
    ("github (controle)", "https://api.github.com"),
    ("pncp raiz", "https://pncp.gov.br/"),
    ("pncp api modalidades", "https://pncp.gov.br/api/consulta/v1/modalidades"),
    ("pncp api publicacao", "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao?dataInicial=20260701&dataFinal=20260701&codigoModalidadeContratacao=6&pagina=1&tamanhoPagina=10"),
    ("repositorio dados.gov.br resultado", "https://repositorio.dados.gov.br/seges/comprasgov/diario/comprasGOV-diario-VW_DM_PNCP_ITEM_RESULTADO-latest.csv"),
]

for tentativa in range(1, 4):
    print(f"\n=== tentativa {tentativa} ===")
    for nome, url in ALVOS:
        t0 = time.monotonic()
        try:
            headers = {"Accept": "application/json"}
            if "repositorio" in url:
                headers["Range"] = "bytes=0-500"
            r = httpx.get(url, timeout=15.0, headers=headers)
            dt = round(time.monotonic() - t0, 2)
            print(f"{nome}: OK status={r.status_code} tempo={dt}s bytes={len(r.content)}")
        except Exception as e:
            dt = round(time.monotonic() - t0, 2)
            print(f"{nome}: ERRO {type(e).__name__} tempo={dt}s detalhe={e}")
        time.sleep(1)
