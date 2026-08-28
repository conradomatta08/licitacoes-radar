import os

CONSULTA_BASE_URL = "https://pncp.gov.br/api/consulta"
PNCP_BASE_URL = "https://pncp.gov.br/api/pncp"

# GET /v1/modalidades (https://pncp.gov.br/api/pncp/v1/modalidades) confirmado
# publico em 2026-08-28. Hardcoded aqui pra nao depender de mais uma chamada
# de rede a cada execucao do pipeline.
MODALIDADES = {
    1: "Leilão - Eletrônico",
    2: "Diálogo Competitivo",
    3: "Concurso",
    4: "Concorrência - Eletrônica",
    5: "Concorrência - Presencial",
    6: "Pregão - Eletrônico",
    7: "Pregão - Presencial",
    8: "Dispensa",
    9: "Inexigibilidade",
    10: "Manifestação de Interesse",
    11: "Pré-qualificação",
    12: "Credenciamento",
    13: "Leilão - Presencial",
    14: "Inaplicabilidade da Licitação",
    15: "Chamada pública",
    16: "Concorrência – Eletrônica Internacional",
    17: "Concorrência – Presencial Internacional",
    18: "Pregão – Eletrônico Internacional",
    19: "Pregão – Presencial Internacional",
}

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Fase 1: recorte de ~4 meses pra validar antes do backfill nacional completo.
JANELA_HISTORICO_DIAS = int(os.environ.get("JANELA_HISTORICO_DIAS", "120"))

TAMANHO_PAGINA = int(os.environ.get("TAMANHO_PAGINA", "50"))  # minimo aceito pela API e 10

# Cada execucao do GitHub Actions tem um limite de tempo; paramos de pedir mais
# paginas/itens quando esse orcamento estoura, e continuamos na proxima execucao
# a partir do checkpoint salvo.
MAX_RUNTIME_SECONDS = int(os.environ.get("MAX_RUNTIME_SECONDS", str(5 * 60 * 60)))  # 5h

# Delay entre chamadas HTTP, pra nao martelar uma API que ja se mostrou instavel.
REQUEST_DELAY_SECONDS = float(os.environ.get("REQUEST_DELAY_SECONDS", "0.3"))

# Backoff de reprocessamento de licitacoes "em aberto" (sem resultado ainda).
REPROCESS_BACKOFF_DIAS = [3, 7, 15, 30, 60]

def link_pncp(cnpj: str, ano: int, sequencial: int) -> str:
    return f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{sequencial}"
