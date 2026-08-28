import psycopg

from config import DATABASE_URL


def get_conn() -> psycopg.Connection:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL nao configurada (env var ausente)")
    return psycopg.connect(DATABASE_URL, autocommit=False)
