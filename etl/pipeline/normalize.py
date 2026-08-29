"""Normalizacao defensiva: dado publicado por milhares de orgaos diferentes
vem com qualidade heterogenea (CNPJ mal formatado, datas ausentes, etc).
Nenhuma funcao aqui deve lancar excecao por dado malformado - retornar None
e deixar o registro seguir incompleto, nunca derrubar o lote inteiro."""

import re
from datetime import date, datetime

from dateutil import parser as dateutil_parser


def clean_cnpj(value) -> str | None:
    if not value:
        return None
    digits = "".join(c for c in str(value) if c.isdigit())
    return digits if digits else None


def parse_date(value) -> date | None:
    if not value:
        return None
    try:
        return dateutil_parser.parse(str(value)).date()
    except (ValueError, OverflowError):
        return None


def parse_datetime(value) -> datetime | None:
    if not value:
        return None
    try:
        return dateutil_parser.parse(str(value))
    except (ValueError, OverflowError):
        return None


def parse_decimal(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def parse_int(value):
    """Os CSVs em lote as vezes exportam inteiros como '6.0' - passa por
    float() primeiro pra aceitar os dois formatos."""
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def parse_bool(value):
    if value is None or value == "":
        return None
    s = str(value).strip().lower()
    if s in ("true", "1", "sim", "t"):
        return True
    if s in ("false", "0", "nao", "não", "f"):
        return False
    return None


# As descricoes de item do CATMAT/CATSER seguem o padrao "<Nome Padrao>
# <atributo1>: <valor1>, <atributo2>: <valor2>, ..." - o produto e o texto
# antes do primeiro atributo reconhecido. Testado em 2026-08-29 contra uma
# amostra real: da bons resultados pra a maioria dos casos (Notebook, Touca,
# Cunha Odontologica, Vergalhao, Disjuntor, nomes de medicamento, etc).
# Excecao conhecida e aceita: quando o nome padrao e generico e o atributo
# "tipo" da a classificacao mais especifica (ex: "Estabilizador Tensao ...
# tipo: nobreak"), o produto extraido fica no nivel generico ("Estabilizador
# Tensao"), nao no especifico ("Nobreak") - nao ha regra mecanica que acerte
# os dois padroes ao mesmo tempo (decisao registrada em conversa com o
# usuario: prioriza o nome do cabecalho, mais confiavel no geral).
_ATRIBUTOS_DESCRICAO = [
    "tipo", "material", "cor", "tamanho", "capacidade", "aplicação", "aplicacao",
    "diâmetro", "diametro", "comprimento", "largura", "altura", "espessura",
    "tensão", "tensao", "potência", "potencia", "voltagem", "corrente nominal",
    "característica", "caracteristica", "características adicionais", "caracteristicas adicionais",
    "unidade de fornecimento", "unidade fornecimento", "peso", "volume", "quantidade",
    "concentração", "concentracao", "forma farmacêutica", "forma farmaceutica", "uso",
    "referência", "referencia", "modelo", "marca", "acabamento", "formato", "gramatura",
    "composição", "composicao", "sabor", "embalagem", "apresentação", "apresentacao",
    "revestimento", "funcionamento", "padrão", "padrao", "frequência", "frequencia",
    "alimentação", "alimentacao", "bateria", "autonomia", "garantia", "fixação", "fixacao",
    "conectividade", "resolução", "resolucao", "memória", "memoria", "processador",
    "sistema operacional", "tela", "interatividade", "armazenamento",
]
_PADRAO_ATRIBUTO = re.compile(
    r"\b(" + "|".join(re.escape(a) for a in sorted(_ATRIBUTOS_DESCRICAO, key=len, reverse=True)) + r")\w*\s*[:\*]",
    re.IGNORECASE,
)


def extrair_produto(descricao: str | None) -> str | None:
    """Extrai o nome do produto/serviço a partir da descrição estruturada
    do item (ver módulo acima pra explicação da heurística e limitações)."""
    if not descricao:
        return None
    match = _PADRAO_ATRIBUTO.search(descricao)
    cabecalho = descricao[: match.start()] if match else descricao
    cabecalho = cabecalho.strip(" -,:;")
    if not cabecalho:
        return None
    # Descrições às vezes repetem o nome 2x ("Fio Guia Fio Guia") - se a
    # primeira metade das palavras é idêntica à segunda, usa só a primeira.
    palavras = cabecalho.split()
    metade = len(palavras) // 2
    if metade > 0 and palavras[:metade] == palavras[metade : metade * 2]:
        cabecalho = " ".join(palavras[:metade])
    return cabecalho.upper()[:120]
