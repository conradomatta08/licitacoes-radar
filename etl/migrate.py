"""Aplica db/schema.sql (idempotente - cada statement deve poder rodar
repetidas vezes sem erro: CREATE ... IF NOT EXISTS, ALTER ... ADD COLUMN
IF NOT EXISTS, DROP ... IF EXISTS). Rodado automaticamente no inicio de
todo ingest/backfill, pra nao depender do usuario lembrar de migrar."""

from pathlib import Path

from db.connection import get_conn

SCHEMA_PATH = Path(__file__).parent / "db" / "schema.sql"


def run() -> None:
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    # Remove comentarios de linha antes de dividir por ";" - o split e
    # ingenuo e um ";" dentro de um comentario quebraria a divisao.
    sem_comentarios = "\n".join(linha.split("--", 1)[0] for linha in sql.splitlines())
    statements = [s.strip() for s in sem_comentarios.split(";") if s.strip()]
    with get_conn() as conn:
        for statement in statements:
            conn.execute(statement)
        conn.commit()
    print(f"schema aplicado ({len(statements)} statements, idempotente).")


if __name__ == "__main__":
    run()
