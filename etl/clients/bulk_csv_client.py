"""Cliente para os arquivos em lote (CSV) do Compras.gov.br/PNCP, hospedados
em repositorio.dados.gov.br - um dominio estatico separado da API ao vivo do
PNCP. Confirmado por diagnostico em 2026-08-29: esse dominio respondeu
consistentemente (3/3) do GitHub Actions, enquanto a API ao vivo do PNCP
se mostrou instavel mesmo fora daquela janela de teste. Cada arquivo
'diario' traz os registros novos/alterados no dia; 'anual' traz o
acumulado do ano corrente; os arquivos por ano (2021-2025) trazem o
historico completo daquele ano - usados so pra popular o historico
(ver docs/plano).

A conexao com esse servidor cai com frequencia (confirmado na pratica -
2 quedas num arquivo de so 1.6MB), o que inviabiliza reiniciar o download
do zero a cada queda pros arquivos de alguns GB dos anos completos. Por
isso baixa pra um arquivo local com suporte a retomar de onde parou
(Range request, que o servidor confirmadamente suporta) antes de fazer
qualquer parsing."""

import csv
import os
import tempfile
import time

import httpx

_TIMEOUT = httpx.Timeout(120.0, connect=15.0)
_TENTATIVAS_DOWNLOAD = 40
_PASTA_TEMP = os.path.join(tempfile.gettempdir(), "licitacoes-radar-downloads")


def _tamanho_remoto(url: str) -> int | None:
    """Descobre o tamanho total do arquivo via HEAD, pra confirmar se um
    arquivo parcial local ja esta completo (ver uso em _baixar_para_arquivo)."""
    try:
        resp = httpx.head(url, timeout=_TIMEOUT, follow_redirects=True)
        resp.raise_for_status()
        content_length = resp.headers.get("Content-Length")
        return int(content_length) if content_length is not None else None
    except (httpx.TransportError, httpx.HTTPStatusError, ValueError):
        return None


def _baixar_para_arquivo(url: str, caminho: str) -> None:
    os.makedirs(_PASTA_TEMP, exist_ok=True)
    for tentativa in range(1, _TENTATIVAS_DOWNLOAD + 1):
        recebido = os.path.getsize(caminho) if os.path.exists(caminho) else 0
        headers = {"Range": f"bytes={recebido}-"} if recebido > 0 else {}
        try:
            with httpx.stream("GET", url, timeout=_TIMEOUT, follow_redirects=True, headers=headers) as resp:
                if resp.status_code == 416 and recebido > 0:
                    # "Range Not Satisfiable" pedindo a partir do fim do
                    # arquivo local geralmente significa que o download ja
                    # terminou (nao ha mais bytes depois do que ja temos).
                    # Confirma com o tamanho real antes de aceitar isso -
                    # se o arquivo remoto mudou de tamanho, descarta o
                    # parcial local e recomeca do zero.
                    total_remoto = _tamanho_remoto(url)
                    if total_remoto == recebido:
                        return
                    if total_remoto is not None:
                        os.remove(caminho)
                        recebido = 0
                if recebido > 0 and resp.status_code == 200:
                    # servidor nao suportou o Range (nao deveria acontecer,
                    # ja confirmamos que suporta, mas por seguranca) -
                    # reinicia do zero.
                    recebido = 0
                resp.raise_for_status()
                modo = "ab" if recebido > 0 else "wb"
                with open(caminho, modo) as f:
                    for chunk in resp.iter_bytes():
                        f.write(chunk)
            return
        except (httpx.TransportError, httpx.HTTPStatusError) as e:
            if tentativa == _TENTATIVAS_DOWNLOAD:
                raise
            espera = min(15, 2 * tentativa)
            recebido_agora = os.path.getsize(caminho) if os.path.exists(caminho) else 0
            print(
                f"  [aviso] queda ao baixar {url} (tentativa {tentativa}/{_TENTATIVAS_DOWNLOAD}, "
                f"{recebido_agora} bytes recebidos até agora): {e} - retomando em {espera}s"
            )
            time.sleep(espera)


def baixar_csv(url: str):
    """Baixa o CSV pra um arquivo temporario local (retomando de onde
    parou se a conexao cair) e devolve as linhas em streaming a partir do
    arquivo - nunca materializa o conteudo inteiro em memoria, essencial
    pros arquivos de item dos anos completos (2-4GB)."""
    nome_arquivo = "".join(c if c.isalnum() else "_" for c in url) + ".csv"
    caminho = os.path.join(_PASTA_TEMP, nome_arquivo)
    try:
        _baixar_para_arquivo(url, caminho)
        with open(caminho, encoding="utf-8-sig", newline="") as f:
            leitor = csv.reader(f)
            try:
                cabecalho = next(leitor)
            except StopIteration:
                return
            for valores in leitor:
                if not valores:
                    continue
                yield dict(zip(cabecalho, valores))
    finally:
        if os.path.exists(caminho):
            os.remove(caminho)
