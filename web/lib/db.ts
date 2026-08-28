import { Pool } from "pg";

declare global {
  // eslint-disable-next-line no-var
  var _pgPool: Pool | undefined;
}

// Neon (produção) exige SSL; um Postgres local de desenvolvimento normalmente
// não tem SSL habilitado e rejeita a negociação - então só exigimos SSL
// quando o host não é local.
function precisaSsl(connectionString: string | undefined): boolean {
  if (!connectionString) return false;
  try {
    const host = new URL(connectionString).hostname;
    return host !== "localhost" && host !== "127.0.0.1";
  } catch {
    return true;
  }
}

// Reaproveita a pool entre requisições em dev (hot reload) e em ambientes
// serverless que reciclam a mesma instância.
export const pool =
  global._pgPool ??
  new Pool({
    connectionString: process.env.DATABASE_URL,
    ssl: precisaSsl(process.env.DATABASE_URL) ? { rejectUnauthorized: false } : false,
    max: 5,
  });

if (process.env.NODE_ENV !== "production") {
  global._pgPool = pool;
}
