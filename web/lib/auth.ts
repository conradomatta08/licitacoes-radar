// Login proprio do dashboard - restringe o acesso as pessoas cadastradas
// em AUTH_USERS (nao ha cadastro de conta pelo site, e um allow-list fixo
// combinado com a empresa). Sessao e um cookie assinado com HMAC (Web
// Crypto, compativel com o runtime de middleware do Next.js) em vez de
// guardar sessao em algum lugar - sem estado nenhum pra manter.

const CODIFICADOR = new TextEncoder();
const NOME_COOKIE = "sessao";
const DURACAO_SESSAO_SEGUNDOS = 30 * 24 * 60 * 60; // 30 dias

function paraHex(buffer: ArrayBuffer): string {
  return Array.from(new Uint8Array(buffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

async function assinar(mensagem: string): Promise<string> {
  const segredo = process.env.AUTH_SECRET;
  if (!segredo) {
    throw new Error("AUTH_SECRET nao configurada (env var ausente)");
  }
  const chave = await crypto.subtle.importKey(
    "raw",
    CODIFICADOR.encode(segredo),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const assinatura = await crypto.subtle.sign("HMAC", chave, CODIFICADOR.encode(mensagem));
  return paraHex(assinatura);
}

export async function criarCookieSessao(usuario: string): Promise<string> {
  const expira = Math.floor(Date.now() / 1000) + DURACAO_SESSAO_SEGUNDOS;
  const carga = `${usuario}.${expira}`;
  return `${carga}.${await assinar(carga)}`;
}

export async function validarCookieSessao(valor: string | undefined): Promise<boolean> {
  if (!valor) return false;
  const partes = valor.split(".");
  if (partes.length !== 3) return false;
  const [usuario, expiraTexto, assinaturaRecebida] = partes;
  const expira = Number(expiraTexto);
  if (!usuario || !Number.isFinite(expira) || expira < Math.floor(Date.now() / 1000)) return false;
  const assinaturaEsperada = await assinar(`${usuario}.${expiraTexto}`);
  return assinaturaEsperada === assinaturaRecebida;
}

function credenciaisCadastradas(): Map<string, string> {
  const bruto = process.env.AUTH_USERS ?? "";
  const mapa = new Map<string, string>();
  for (const par of bruto.split(",")) {
    const [usuario, senha] = par.split(":").map((v) => v?.trim());
    if (usuario && senha) mapa.set(usuario, senha);
  }
  return mapa;
}

export function verificarCredenciais(usuario: string, senha: string): boolean {
  if (!usuario || !senha) return false;
  return credenciaisCadastradas().get(usuario) === senha;
}

// Diagnostico temporario (nao expoe senha) - remover depois de confirmar
// que AUTH_USERS esta configurada corretamente na Vercel.
export function usuariosCadastrados(): string[] {
  return Array.from(credenciaisCadastradas().keys());
}

export { NOME_COOKIE };
