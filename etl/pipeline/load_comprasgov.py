"""Carrega no banco os dados da API de dados abertos do Compras.gov.br
(clients/comprasgov_api_client.py), adaptando o JSON pros mesmos nomes de
campo que pipeline/load.py ja espera (colunas dos CSVs em lote) - reaproveita
upsert_licitacoes_lote/upsert_itens_lote/upsert_resultados_lote sem duplicar
nada dessa logica.

Um dia por vez, nesta ordem: contratacoes publicadas no dia, itens
incluidos no dia, resultados registrados no dia. Itens e resultados podem
pertencer a contratacoes de dias anteriores (o resultado normalmente sai
dias ou semanas depois da publicacao) - por isso o id da licitacao e
resolvido no banco, nao so pelo que foi carregado no proprio dia."""

import datetime as dt
import re
import time

import httpx

from clients import comprasgov_api_client as api
from clients import pncp_live_client as pncp
from db.connection import get_conn
from pipeline import load
from pipeline.normalize import parse_int

_LOTE_CONSULTA = 5000


def _adaptar_compra(c: dict) -> dict:
    return {
        "numero_controle_PNCP": c.get("numeroControlePNCP"),
        "orgao_entidade_cnpj": c.get("orgaoEntidadeCnpj"),
        "orgao_entidade_razao_social": c.get("orgaoEntidadeRazaoSocial"),
        "orgao_entidade_poder_id": c.get("orgaoEntidadePoderId"),
        "orgao_entidade_esfera_id": c.get("orgaoEntidadeEsferaId"),
        "unidade_orgao_codigo_unidade": c.get("unidadeOrgaoCodigoUnidade"),
        "unidade_orgao_nome_unidade": c.get("unidadeOrgaoNomeUnidade"),
        "unidade_orgao_uf_sigla": c.get("unidadeOrgaoUfSigla"),
        "unidade_orgao_municipio_nome": c.get("unidadeOrgaoMunicipioNome"),
        "unidade_orgao_codigo_ibge": c.get("unidadeOrgaoCodigoIbge"),
        "ano_compra_pncp": c.get("anoCompraPncp"),
        "sequencial_compra_pncp": c.get("sequencialCompraPncp"),
        "numero_compra": c.get("numeroCompra"),
        "processo": c.get("processo"),
        "codigo_modalidade": c.get("codigoModalidade"),
        "modalidade_nome": c.get("modalidadeNome"),
        "modo_disputa_nome_pncp": c.get("modoDisputaNomePncp"),
        "objeto_compra": c.get("objetoCompra"),
        "situacao_compra_id_pncp": c.get("situacaoCompraIdPncp"),
        "situacao_compra_nome_pncp": c.get("situacaoCompraNomePncp"),
        "data_publicacao_pncp": c.get("dataPublicacaoPncp"),
        "valor_total_estimado": c.get("valorTotalEstimado"),
        "valor_total_homologado": c.get("valorTotalHomologado"),
        "existe_resultado": c.get("existeResultado"),
        "link_sistema_origem": None,
    }


def _adaptar_item(it: dict) -> dict:
    return {
        "numero_controle_PNCP_compra": it.get("numeroControlePNCPCompra") or it.get("idContratacaoPNCP"),
        "numero_item_compra": it.get("numeroItemCompra"),
        "descricao_detalhada": it.get("descricaodetalhada"),
        "descricao_resumida": it.get("descricaoResumida"),
        "material_ou_servico": it.get("materialOuServico"),
        "quantidade": it.get("quantidade"),
        "unidade_medida": it.get("unidadeMedida"),
        "valor_unitario_estimado": it.get("valorUnitarioEstimado"),
        "valor_total": it.get("valorTotal"),
        "situacao_compra_item": it.get("situacaoCompraItem"),
        "situacao_compra_item_nome": it.get("situacaoCompraItemNome"),
        "tem_resultado": it.get("temResultado"),
    }


def _adaptar_resultado(r: dict) -> dict:
    return {
        "numero_controle_PNCP_compra": r.get("numeroControlePNCPCompra") or r.get("idContratacaoPNCP"),
        "numero_item_pncp": r.get("numeroItemPncp"),
        "sequencial_resultado": r.get("sequencialResultado"),
        "ni_fornecedor": r.get("niFornecedor"),
        "tipo_pessoa": r.get("tipoPessoa"),
        "nome_razao_social_fornecedor": r.get("nomeRazaoSocialFornecedor"),
        "valor_unitario_homologado": r.get("valorUnitarioHomologado"),
        "valor_total_homologado": r.get("valorTotalHomologado"),
        "quantidade_homologada": r.get("quantidadeHomologada"),
        "ordem_classificacao_srp": r.get("ordemClassificacaoSrp"),
        "situacao_compra_item_resultado_id": r.get("situacaoCompraItemResultadoId"),
        "situacao_compra_item_resultado_nome": r.get("situacaoCompraItemResultadoNome"),
        "data_resultado_pncp": r.get("dataResultadoPncp"),
    }


def _completar_cache(conn, cache_licitacao: dict, numeros) -> None:
    """Acrescenta ao cache os ids das licitacoes que ja estao no banco
    (carregadas em dias anteriores) e ainda nao estao no cache."""
    faltando = [n for n in set(numeros) if n and n not in cache_licitacao]
    for i in range(0, len(faltando), _LOTE_CONSULTA):
        parte = faltando[i : i + _LOTE_CONSULTA]
        linhas = conn.execute(
            "SELECT numero_controle_pncp, id FROM licitacoes WHERE numero_controle_pncp = ANY(%s)", (parte,)
        ).fetchall()
        cache_licitacao.update(dict(linhas))


def _marcar_com_resultado(conn, resultados: list, cache_licitacao: dict) -> None:
    """Itens/licitacoes que ganharam resultado valido (situacao 1 =
    Informado) depois de terem sido carregados sem resultado."""
    pares = set()
    for r in resultados:
        if r["situacao_compra_item_resultado_id"] not in (1, "1"):
            continue
        licitacao_id = cache_licitacao.get(r["numero_controle_PNCP_compra"])
        numero_item = r["numero_item_pncp"]
        if licitacao_id is not None and numero_item is not None:
            pares.add((licitacao_id, int(numero_item)))
    if not pares:
        return
    ids = [p[0] for p in pares]
    numeros = [p[1] for p in pares]
    conn.execute(
        """
        UPDATE itens i SET tem_resultado = true
        FROM unnest(%s::bigint[], %s::int[]) AS v(lic, num)
        WHERE i.licitacao_id = v.lic AND i.numero_item = v.num AND i.tem_resultado = false
        """,
        (ids, numeros),
    )
    conn.execute(
        "UPDATE licitacoes SET existe_resultado = true WHERE id = ANY(%s) AND existe_resultado = false",
        (list(set(ids)),),
    )
    conn.commit()


def _carregar_contratacoes(dia: dt.date, cache_orgao: dict, cache_unidade: dict) -> None:
    with get_conn() as conn:
        compras = [_adaptar_compra(c) for c in api.contratacoes_do_dia(dia)]
        load.upsert_licitacoes_lote(conn, compras, cache_orgao, cache_unidade)


_TENTATIVAS_VERIFICACAO = 3
_LOTE_PLANO_B = 100


def _contar_itens_presentes(conn, chaves: list) -> int:
    return conn.execute(
        """
        SELECT count(*) FROM unnest(%s::text[], %s::int[]) v(c, n)
        JOIN licitacoes l ON l.numero_controle_pncp = v.c
        JOIN itens i ON i.licitacao_id = l.id AND i.numero_item = v.n
        """,
        ([c for c, _ in chaves], [n for _, n in chaves]),
    ).fetchone()[0]


def _contar_resultados(conn, chaves: list) -> tuple:
    """(presentes, esperados): esperados = resultados da fonte cujo item ja
    esta no banco (os demais pertencem a contratacoes fora do banco e sao
    ignorados de proposito); presentes = quantos desses ja estao gravados."""
    return conn.execute(
        """
        SELECT count(r.id), count(*) FROM unnest(%s::text[], %s::int[], %s::int[]) v(c, n, s)
        JOIN licitacoes l ON l.numero_controle_pncp = v.c
        JOIN itens i ON i.licitacao_id = l.id AND i.numero_item = v.n
        LEFT JOIN resultados_item r ON r.item_id = i.id AND r.sequencial_resultado = v.s
        """,
        ([c for c, _, _ in chaves], [n for _, n, _ in chaves], [s for _, _, s in chaves]),
    ).fetchone()


_PADRAO_NUMERO_CONTROLE = re.compile(r"^(\d{14})-1-(\d+)/(\d{4})$")


def _mapa_modalidade(conn) -> dict:
    """{modalidade_nome: codigo} no padrao do Compras.gov.br (o usado por
    todas as licitacoes carregadas dos CSVs e desta fonte), tirado do
    proprio banco (codigo mais frequente por nome antes do buraco). O PNCP
    usa outros codigos pra mesma modalidade (ex: Dispensa e 8 no PNCP, 6
    aqui)."""
    linhas = conn.execute(
        """
        SELECT DISTINCT ON (modalidade_nome) modalidade_nome, modalidade_id
        FROM (
            SELECT modalidade_nome, modalidade_id, count(*) n FROM licitacoes
            WHERE data_publicacao_pncp < '2026-07-16' AND modalidade_id IS NOT NULL
            GROUP BY 1, 2
        ) t ORDER BY modalidade_nome, n DESC
        """
    ).fetchall()
    return dict(linhas)


def _buscar_contratacoes_faltantes(itens: list, cache_orgao: dict, cache_unidade: dict) -> None:
    """Plano B: a fonte as vezes tem itens de contratacoes que ela mesma nao
    devolve no endpoint de contratacoes (confirmado em 15/09/2026: 1.109 de
    1.345). Busca o cabecalho no PNCP, uma chamada por contratacao, so das
    que faltam.

    Nao mantem conexao aberta durante as buscas (levam minutos): o banco
    derruba conexoes paradas (idle-in-transaction timeout e queda de SSL,
    ambos confirmados em 15/09/2026). Cada gravacao abre a sua."""
    from pipeline.load_live import _adaptar_compra as adaptar_pncp

    cache: dict = {}
    with get_conn() as conn:
        _completar_cache(conn, cache, (i["numero_controle_PNCP_compra"] for i in itens))
        mapa = _mapa_modalidade(conn)
    faltando = sorted({i["numero_controle_PNCP_compra"] for i in itens} - set(cache))
    validas = [n for n in faltando if n and _PADRAO_NUMERO_CONTROLE.match(n)]
    if not validas:
        return
    print(f"  plano B: buscando {len(validas)} contratacoes no PNCP (a fonte principal nao as tem)")
    linhas = []
    obtidas = nao_encontradas = erros = 0
    for n in validas:
        cnpj, seq, ano = _PADRAO_NUMERO_CONTROLE.match(n).groups()
        try:
            c = pncp.buscar_contratacao(cnpj, int(ano), int(seq))
        except (httpx.TransportError, httpx.HTTPStatusError, ValueError):
            erros += 1
            continue
        if not c:
            nao_encontradas += 1
            continue
        linha = adaptar_pncp(c, bool(c.get("existeResultado")))
        linha["codigo_modalidade"] = mapa.get(c.get("modalidadeNome"))
        linhas.append(linha)
        obtidas += 1
        if len(linhas) >= _LOTE_PLANO_B:
            with get_conn() as conn:
                load.upsert_licitacoes_lote(conn, linhas, cache_orgao, cache_unidade)
            linhas = []
    if linhas:
        with get_conn() as conn:
            load.upsert_licitacoes_lote(conn, linhas, cache_orgao, cache_unidade)
    print(f"  plano B: {obtidas} obtidas, {nao_encontradas} nao existem no PNCP, {erros} com erro")


def _carregar_itens(dia: dt.date) -> None:
    itens = [_adaptar_item(it) for it in api.itens_do_dia(dia)]
    validos = [i for i in itens if _PADRAO_NUMERO_CONTROLE.match(i["numero_controle_PNCP_compra"] or "")]
    orfaos = len(itens) - len(validos)
    if orfaos:
        # A fonte as vezes manda itens sem nenhuma referencia a contratacao
        # ("-1-/", sem CNPJ) - confirmado em 03 e 04/09/2026 (8.804 de
        # 13.257 itens em 04/09). Nao ha como liga-los a uma licitacao.
        print(f"  [aviso] {orfaos} de {len(itens)} itens vieram da fonte sem referencia a contratacao - nao ha como carrega-los")
    chaves = sorted(
        {
            (i["numero_controle_PNCP_compra"], parse_int(i["numero_item_compra"]))
            for i in validos
            if parse_int(i["numero_item_compra"]) is not None
        }
    )
    for tentativa in range(1, _TENTATIVAS_VERIFICACAO + 1):
        with get_conn() as conn:
            cache_licitacao: dict = {}
            _completar_cache(conn, cache_licitacao, (i["numero_controle_PNCP_compra"] for i in itens))
            load.upsert_itens_lote(conn, itens, cache_licitacao)
            ausentes = len(chaves) - _contar_itens_presentes(conn, chaves)
        print(f"  verificacao itens: {ausentes} ausentes de {len(chaves)} unicos (tentativa {tentativa})")
        if ausentes == 0:
            return
        if tentativa == 1:
            _buscar_contratacoes_faltantes(itens, {}, {})
    raise RuntimeError(f"itens de {dia.isoformat()}: {ausentes} continuam ausentes apos {_TENTATIVAS_VERIFICACAO} tentativas")


def _carregar_resultados(dia: dt.date) -> None:
    resultados = [_adaptar_resultado(r) for r in api.resultados_do_dia(dia)]
    chaves = sorted(
        {
            (r["numero_controle_PNCP_compra"], parse_int(r["numero_item_pncp"]), parse_int(r["sequencial_resultado"]) or 1)
            for r in resultados
            if r["numero_controle_PNCP_compra"] and parse_int(r["numero_item_pncp"]) is not None
        }
    )
    with get_conn() as conn:
        for tentativa in range(1, _TENTATIVAS_VERIFICACAO + 1):
            cache_licitacao: dict = {}
            _completar_cache(conn, cache_licitacao, (r["numero_controle_PNCP_compra"] for r in resultados))
            load.upsert_resultados_lote(conn, resultados, cache_licitacao)
            _marcar_com_resultado(conn, resultados, cache_licitacao)
            presentes, esperados = _contar_resultados(conn, chaves)
            print(f"  verificacao resultados: {esperados - presentes} ausentes de {esperados} com item no banco (tentativa {tentativa})")
            if presentes == esperados:
                return
        raise RuntimeError(f"resultados de {dia.isoformat()}: {esperados - presentes} continuam ausentes apos {_TENTATIVAS_VERIFICACAO} tentativas")


def carregar_periodo(inicio: dt.date, fim: dt.date, fases_desejadas=("contratacoes", "itens", "resultados")) -> list:
    """Carrega [inicio, fim] em tres fases sobre o periodo inteiro -
    contratacoes, depois itens, depois resultados - porque um item/resultado
    de um dia pode pertencer a uma contratacao publicada em outro dia do
    periodo, e ela precisa ja estar no banco. Um dia/fase que falhe (mesmo
    apos as tentativas do cliente) nao derruba o resto: devolve a lista de
    (fase, dia) que falharam pra rodar de novo."""
    dias = [inicio + dt.timedelta(days=i) for i in range((fim - inicio).days + 1)]
    cache_orgao: dict = {}
    cache_unidade: dict = {}
    falhas = []
    fases = (
        ("contratacoes", lambda d: _carregar_contratacoes(d, cache_orgao, cache_unidade)),
        ("itens", _carregar_itens),
        ("resultados", _carregar_resultados),
    )
    for nome_fase, carregar in fases:
        if nome_fase not in fases_desejadas:
            continue
        print(f"=== fase: {nome_fase} ===")
        for dia in dias:
            print(f"--- {nome_fase} {dia.isoformat()} ---")
            t0 = time.time()
            try:
                carregar(dia)
                print(f"  ({time.time() - t0:.0f}s)")
            except Exception as e:
                falhas.append((nome_fase, dia))
                print(f"  [ERRO] {nome_fase} {dia.isoformat()} falhou: {type(e).__name__}: {e}")
    return falhas
