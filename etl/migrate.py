"""Aplica db/schema.sql (idempotente - so CREATE TABLE/INDEX IF NOT EXISTS).
Rodado automaticamente no inicio de todo ingest/reprocess, pra nao depender
do usuario lembrar de rodar uma migracao manual."""

from pathlib import Path

from db.connection import get_conn

SCHEMA_PATH = Path(__file__).parent / "db" / "schema.sql"


def run() -> None:
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    with get_conn() as conn:
        for statement in statements:
            conn.execute(statement)
        conn.commit()
    print(f"schema aplicado ({len(statements)} statements, idempotente).")


if __name__ == "__main__":
    run()
