"""Busca a UF e o CNAE de cada CNPJ que ja venceu alguma licitacao na nossa
base, cruzando com a base de Estabelecimentos da Receita Federal (dados
abertos, hospedados em arquivos.receitafederal.gov.br - confirmado via
WebDAV em 2026-08-30, ver docs/plano). UF usada pra avaliar vantagem
logistica (empresa sediada perto do orgao que comprou); CNAE usado pra
sinalizar se a empresa e fabricante (industria de transformacao) e nao so
revendedora.

So guarda CNPJ + UF + CNAE - nao precisamos de endereco completo, nome,
etc pra essa analise. O PNCP nao traz esses dados (confirmado: nenhum
campo de UF/CNAE do fornecedor nos CSVs de resultado), so o CNPJ.

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


_DIVISAO_MIN_FABRICACAO = 10
_DIVISAO_MAX_FABRICACAO = 33


def _eh_cnae_fabricacao(cnae: str) -> bool:
    """Secao C (Industrias de Transformacao) do CNAE 2.0 = divisoes 10 a 33
    (confirmado no IBGE/CONCLA) - divisao e os 2 primeiros digitos do
    codigo (ex: '1113502' -> divisao 11 -> fabricacao de bebidas)."""
    cnae = cnae.strip()
    if len(cnae) < 2 or not cnae[:2].isdigit():
        return False
    divisao = int(cnae[:2])
    return _DIVISAO_MIN_FABRICACAO <= divisao <= _DIVISAO_MAX_FABRICACAO


def _extrair_dados(conteudo_zip: bytes, cnpjs_procurados: set) -> dict:
    """Le o unico CSV dentro do zip em streaming (nunca materializa as
    linhas inteiras) - devolve {cnpj: (uf, cnae_principal, eh_fabricante)}
    so pros CNPJs procurados. eh_fabricante considera o CNAE principal e os
    secundarios (campo com varios codigos separados por virgula)."""
    encontrados: dict = {}
    with zipfile.ZipFile(io.BytesIO(conteudo_zip)) as zf:
        nome_interno = zf.namelist()[0]
        with zf.open(nome_interno) as bruto:
            texto = io.TextIOWrapper(bruto, encoding="latin-1", newline="")
            for linha in csv.reader(texto, delimiter=";", quotechar='"'):
                if len(linha) < 20:
                    continue
                cnpj = linha[0] + linha[1] + linha[2]
                if cnpj not in cnpjs_procurados:
                    continue
                uf = linha[19].strip()
                if not uf:
                    continue
                cnae_principal = linha[11].strip()
                cnaes_secundarios = [c for c in linha[12].split(",") if c.strip()]
                fabricante = _eh_cnae_fabricacao(cnae_principal) or any(_eh_cnae_fabricacao(c) for c in cnaes_secundarios)
                encontrados[cnpj] = (uf, cnae_principal or None, fabricante)
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
            placeholder = ",".join(["(%s,%s,%s,%s)"] * len(lote))
            params = [v for cnpj in lote for v in (cnpj, *pares[cnpj])]
            conn.execute(
                f"""
                INSERT INTO fornecedores (cnpj, uf, cnae_fiscal_principal, eh_fabricante) VALUES {placeholder}
                ON CONFLICT (cnpj) DO UPDATE SET
                    uf = EXCLUDED.uf,
                    cnae_fiscal_principal = EXCLUDED.cnae_fiscal_principal,
                    eh_fabricante = EXCLUDED.eh_fabricante,
                    atualizado_em = now()
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
        encontrados = _extrair_dados(conteudo, faltando)
        print(f"  {len(encontrados)} encontrados nesta parte")
        _salvar(encontrados)
        faltando -= encontrados.keys()

    print(f"concluido: {len(alvo) - len(faltando)}/{len(alvo)} CNPJs com UF encontrada")
    if faltando:
        print(f"nao encontrados ({len(faltando)}): provavelmente CNPJs muito recentes ou baixados/inativos ha muito tempo")


if __name__ == "__main__":
    main()
