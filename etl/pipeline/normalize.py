"""Normalizacao defensiva: dado publicado por milhares de orgaos diferentes
vem com qualidade heterogenea (CNPJ mal formatado, datas ausentes, etc).
Nenhuma funcao aqui deve lancar excecao por dado malformado - retornar None
e deixar o registro seguir incompleto, nunca derrubar o lote inteiro."""

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
