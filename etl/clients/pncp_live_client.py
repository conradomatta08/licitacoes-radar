"""Cliente para a API ao vivo do PNCP (pncp.gov.br/api/consulta e
pncp.gov.br/api/pncp) - alternativa ao arquivo em lote do Compras.gov.br
(bulk_csv_client.py), que parou de publicar dados novos em 15/07/2026
(confirmado em 2026-09-08 - ver docs/plano). A API ao vivo foi evitada no
inicio do projeto por instabilidade relatada a partir de IPs de nuvem, mas
testada de novo em 2026-09-08 rodando via GitHub Actions e respondeu
normalmente (HTTP 200 de primeira). Mantemos o cliente em lote intacto
como fallback caso essa instabilidade volte.

codigoModalidadeContratacao e obrigatorio nos endpoints de consulta - nao
da pra pedir "tudo" de uma vez, precisa iterar por modalidade (confirmado
empiricamente). tamanhoPagina tem que ser entre 10 e 50 (confirmado
empiricamente - 5 da 400 "must be >= 10", 100 da 400 "Tamanho de pagina
invalido")."""

import time

import httpx

_BASE_CONSULTA = "https://pncp.gov.br/api/consulta/v1"
_BASE_PNCP = "https://pncp.gov.br/api/pncp/v1"
_TIMEOUT = httpx.Timeout(60.0, connect=15.0)
_TENTATIVAS = 5
_TAMANHO_PAGINA = 50
# Pausa fixa antes de cada chamada - reduz a frequencia de "429 Too Many
# Requests" (confirmado acontecendo bastante em 2026-09-09 num loop sem
# pausa nenhuma entre paginas) em vez de so reagir depois de ja apanhar.
_PAUSA_ENTRE_CHAMADAS = 0.6

# Modalidades de contratacao do PNCP (GET /v1/modalidades, tambem publico) -
# fixo aqui porque a lista quase nunca muda (ver docs/plano).
MODALIDADES = list(range(1, 20))


def _get(url: str, params: dict):
    """Devolve o corpo ja decodificado (dict/list) de uma resposta 2xx, ou
    None se o servidor confirmou "nao existe" (404) - nesse caso nao
    adianta tentar de novo. Falha de rede, 5xx OU corpo vazio/invalido
    (confirmado na pratica: a conexao as vezes cai no meio da resposta e o
    servidor ainda assim fecha com 200, sem corpo - vira JSONDecodeError)
    contam como falha transitoria e tentam de novo com backoff."""
    for tentativa in range(1, _TENTATIVAS + 1):
        try:
            time.sleep(_PAUSA_ENTRE_CHAMADAS)
            resp = httpx.get(url, params=params, timeout=_TIMEOUT, follow_redirects=True)
            # 204 = "sem registros" (modalidade sem contratacoes no dia,
            # confirmado em 26/09/2026) - nao e falha, nao adianta repetir.
            if resp.status_code in (204, 404):
                return None
            resp.raise_for_status()
            return resp.json()
        except (httpx.TransportError, httpx.HTTPStatusError, ValueError) as e:
            if tentativa == _TENTATIVAS:
                raise
            limitado = isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 429
            # 429 = limite de requisicoes do PNCP (confirmado em 15/09/2026
            # durante ~1.100 consultas seguidas): espera bem mais que nos
            # outros erros, senao as 5 tentativas se esgotam no mesmo minuto.
            espera = min(90, 20 * tentativa) if limitado else min(20, 3 * tentativa)
            print(f"  [aviso] falha ao chamar {url} {params} (tentativa {tentativa}/{_TENTATIVAS}): {e} - tentando de novo em {espera}s")
            time.sleep(espera)


def buscar_contratacoes(data_inicial: str, data_final: str, modalidade: int):
    """data_inicial/data_final: 'AAAAMMDD'. Gera dicts de contratacao (a
    paginacao e automatica) pra uma modalidade e janela de datas."""
    pagina = 1
    while True:
        corpo = _get(
            f"{_BASE_CONSULTA}/contratacoes/publicacao",
            {
                "dataInicial": data_inicial,
                "dataFinal": data_final,
                "codigoModalidadeContratacao": modalidade,
                "pagina": pagina,
                "tamanhoPagina": _TAMANHO_PAGINA,
            },
        )
        if corpo is None:
            return
        for item in corpo.get("data", []):
            yield item
        if pagina >= corpo.get("totalPaginas", 0):
            return
        pagina += 1


def buscar_contratacao(cnpj: str, ano: int, sequencial: int) -> dict | None:
    """Detalhe de uma contratacao (mesmo formato dos itens de
    buscar_contratacoes). Usa /api/consulta, nao /api/pncp - o segundo
    responde 301 sem corpo pra esse caminho (confirmado em 2026-09-26)."""
    return _get(f"{_BASE_CONSULTA}/orgaos/{cnpj}/compras/{ano}/{sequencial}", {})


def buscar_itens(cnpj: str, ano: int, sequencial: int) -> list[dict]:
    corpo = _get(f"{_BASE_PNCP}/orgaos/{cnpj}/compras/{ano}/{sequencial}/itens", {})
    return corpo if corpo is not None else []


def buscar_resultados(cnpj: str, ano: int, sequencial: int, numero_item: int) -> list[dict]:
    corpo = _get(f"{_BASE_PNCP}/orgaos/{cnpj}/compras/{ano}/{sequencial}/itens/{numero_item}/resultados", {})
    return corpo if corpo is not None else []
