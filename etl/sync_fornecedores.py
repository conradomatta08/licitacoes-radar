"""Busca a UF de cada CNPJ que ja venceu alguma licitacao na nossa base,
cruzando com a base de Estabelecimentos da Receita Federal (dados abertos,
hospedados em arquivos.receitafederal.gov.br - confirmado via WebDAV em
2026-08-30, ver docs/plano). Usado pra avaliar vantagem logistica (empresa
sediada perto do orgao que comprou).

So guarda CNPJ + UF - nao precisamos de endereco completo, nome, etc pra
essa analise. O PNCP nao traz esse dado (confirmado: nenhum campo de UF do
fornecedor nos CSVs de resultado), so o CNPJ.

A pasta de dados muda de nome todo mes (formato YYYY-MM) - descoberta
automaticamente via WebDAV PROPFIND, pega sempre a mais recente. Cada
parte (Estabelecimentos0..9.zip) tem ~370MB e cobre uma fatia arbitraria
do cadastro nacional inteiro (nao filtrada por UF nem por CNPJ) - por isso
precisamos baixar as 10 partes pra ter certeza de achar todos os CNPJs
que procuramos. O servidor nao suporta Range (testado, devolve 500), entao
uma queda no meio do download reinicia aquela parte do zero - aceitavel,
sao so ~370MB por parte (bem menor que os arquivos do PNCP).

Idempotente e re-executavel: pode rodar de novo (ex: mensalmente, quando a
Receita publica uma base nova) pra achar fornecedores que apareceram desde
a ultima vez - so refaz o download e upsert, sem duplicar nada.

Uso: python sync_fornecedores.py"""

import csv
import io
import re
import zipfile

import httpx

import migrate
from db.connection import get_conn

_TOKEN = "YggdBLfdninEJX9"
_BASE_URL = f"https://arquivos.receitafederal.gov.br/public.php/dav/files/{_TOKEN}"
_AUTH = (_TOKEN, "")
_TIMEOUT = httpx.Timeout(300.0, connect=15.0)
_TENTATIVAS = 5
_LOTE_SALVAR = 5000


def _pasta_mais_recente() -> str:
    resp = httpx.request("PROPFIND", f"{_BASE_URL}/", auth=_AUTH, headers={"Depth": "1"}, timeout=_TIMEOUT)
    resp.raise_for_status()
    pastas = re.findall(r"/(\d{4}-\d{2})/</d:href>", resp.text)
    if not pastas:
        raise RuntimeError("nao encontrou nenhuma pasta AAAA-MM no compartilhamento da Receita Federal")
    return max(pastas)


def _baixar_zip(pasta: str, indice: int) -> bytes:
    url = f"{_BASE_URL}/{pasta}/Estabelecimentos{indice}.zip"
    for tentativa in range(1, _TENTATIVAS + 1):
        try:
            resp = httpx.get(url, auth=_AUTH, timeout=_TIMEOUT, follow_redirects=True)
            resp.raise_for_status()
            return resp.content
        except (httpx.TransportError, httpx.HTTPStatusError) as e:
            if tentativa == _TENTATIVAS:
                raise
            print(f"  [aviso] falha ao baixar Estabelecimentos{indice}.zip (tentativa {tentativa}/{_TENTATIVAS}): {e}")


def _extrair_ufs(conteudo_zip: bytes, cnpjs_procurados: set) -> dict:
    """Le o unico CSV dentro do zip em streaming (nunca materializa as
    linhas inteiras) - devolve {cnpj: uf} so pros CNPJs procurados."""
    encontrados: dict = {}
    with zipfile.ZipFile(io.BytesIO(conteudo_zip)) as zf:
        nome_interno = zf.namelist()[0]
        with zf.open(nome_interno) as bruto:
            texto = io.TextIOWrapper(bruto, encoding="latin-1", newline="")
            for linha in csv.reader(texto, delimiter=";", quotechar='"'):
                if len(linha) < 20:
                    continue
                cnpj = linha[0] + linha[1] + linha[2]
                if cnpj in cnpjs_procurados:
                    uf = linha[19].strip()
                    if uf:
                        encontrados[cnpj] = uf
    return encontrados


def _cnpjs_alvo() -> set:
    with get_conn() as conn:
        linhas = conn.execute(
            "SELECT DISTINCT ni_fornecedor FROM resultados_item "
            "WHERE tipo_pessoa = 'PJ' AND length(ni_fornecedor) = 14"
        ).fetchall()
    return {r[0] for r in linhas}


def _salvar(pares: dict) -> None:
    if not pares:
        return
    chaves = list(pares.keys())
    with get_conn() as conn:
        for i in range(0, len(chaves), _LOTE_SALVAR):
            lote = chaves[i : i + _LOTE_SALVAR]
            placeholder = ",".join(["(%s,%s)"] * len(lote))
            params = [v for cnpj in lote for v in (cnpj, pares[cnpj])]
            conn.execute(
                f"""
                INSERT INTO fornecedores (cnpj, uf) VALUES {placeholder}
                ON CONFLICT (cnpj) DO UPDATE SET uf = EXCLUDED.uf, atualizado_em = now()
                """,
                params,
            )
            conn.commit()


def main() -> None:
    migrate.run()
    alvo = _cnpjs_alvo()
    print(f"CNPJs a localizar: {len(alvo)}")

    pasta = _pasta_mais_recente()
    print(f"usando base da Receita Federal de {pasta}")

    faltando = set(alvo)
    for i in range(10):
        if not faltando:
            print("todos os CNPJs ja foram encontrados, parando antes da parte", i)
            break
        print(f"Estabelecimentos{i}.zip ({len(faltando)} CNPJs ainda faltando)...")
        conteudo = _baixar_zip(pasta, i)
        encontrados = _extrair_ufs(conteudo, faltando)
        print(f"  {len(encontrados)} encontrados nesta parte")
        _salvar(encontrados)
        faltando -= encontrados.keys()

    print(f"concluido: {len(alvo) - len(faltando)}/{len(alvo)} CNPJs com UF encontrada")
    if faltando:
        print(f"nao encontrados ({len(faltando)}): provavelmente CNPJs muito recentes ou baixados/inativos ha muito tempo")


if __name__ == "__main__":
    main()
