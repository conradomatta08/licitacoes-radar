"""Upserts no Postgres a partir das linhas dos CSVs em lote do
Compras.gov.br (repositorio.dados.gov.br). As chaves dos dicts de linha
sao os nomes exatos das colunas do CSV, confirmados manualmente em
2026-08-29 (ver plano).

licitacoes/itens/resultados_item sao gravados em lote (varias linhas por
INSERT, nao uma por vez) E em streaming (nunca acumulam o arquivo inteiro
em memoria - o arquivo anual tem centenas de milhares de linhas e ja
estourou memoria numa versao anterior que fazia list(linhas) primeiro).
orgaos/unidades_orgao continuam linha a linha porque sao poucos (centenas)
e quase sempre resolvidos pelo cache depois das primeiras linhas."""

import psycopg

import config
from pipeline.normalize import clean_cnpj, extrair_produto, parse_bool, parse_date, parse_decimal, parse_int

_TAMANHO_LOTE = 1000


def upsert_orgao(conn: psycopg.Connection, cnpj_raw, razao_social, poder_id, esfera_id, cache: dict | None = None) -> int | None:
    cnpj = clean_cnpj(cnpj_raw)
    if not cnpj:
        return None
    if cache is not None and cnpj in cache:
        return cache[cnpj]
    row = conn.execute(
        """
        INSERT INTO orgaos (cnpj, razao_social, poder_id, esfera_id)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (cnpj) DO UPDATE SET
            razao_social = EXCLUDED.razao_social,
            poder_id = EXCLUDED.poder_id,
            esfera_id = EXCLUDED.esfera_id
        RETURNING id
        """,
        (cnpj, razao_social, poder_id, esfera_id),
    ).fetchone()
    orgao_id = row[0] if row else None
    if cache is not None and orgao_id is not None:
        cache[cnpj] = orgao_id
    return orgao_id


def upsert_unidade(conn: psycopg.Connection, orgao_id, codigo_unidade, nome_unidade, uf, municipio, codigo_ibge, cache: dict | None = None) -> int | None:
    if orgao_id is None or not codigo_unidade:
        return None
    chave = (orgao_id, codigo_unidade)
    if cache is not None and chave in cache:
        return cache[chave]
    row = conn.execute(
        """
        INSERT INTO unidades_orgao (orgao_id, codigo_unidade, nome_unidade, uf, municipio, codigo_ibge)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (orgao_id, codigo_unidade) DO UPDATE SET
            nome_unidade = EXCLUDED.nome_unidade,
            uf = EXCLUDED.uf,
            municipio = EXCLUDED.municipio,
            codigo_ibge = EXCLUDED.codigo_ibge
        RETURNING id
        """,
        (orgao_id, codigo_unidade, nome_unidade, uf, municipio, codigo_ibge),
    ).fetchone()
    unidade_id = row[0] if row else None
    if cache is not None and unidade_id is not None:
        cache[chave] = unidade_id
    return unidade_id


def _inserir_lote(conn: psycopg.Connection, sql_insert: str, sql_conflito: str, n_colunas: int, linhas_por_chave: dict) -> dict:
    """Monta e roda um unico INSERT com varias linhas de VALUES (uma por
    chave em linhas_por_chave) e devolve {chave: id} na mesma ordem."""
    if not linhas_por_chave:
        return {}
    chaves = list(linhas_por_chave.keys())
    placeholder_linha = "(" + ",".join(["%s"] * n_colunas) + ")"
    values_sql = ",".join([placeholder_linha] * len(chaves))
    sql = f"{sql_insert} VALUES {values_sql} {sql_conflito} RETURNING id"
    params = [v for chave in chaves for v in linhas_por_chave[chave]]
    ids = [r[0] for r in conn.execute(sql, params).fetchall()]
    return dict(zip(chaves, ids))


_LICITACAO_INSERT = """
    INSERT INTO licitacoes (
        numero_controle_pncp, orgao_id, unidade_id, ano_compra, sequencial_compra,
        numero_compra, processo, modalidade_id, modalidade_nome, modo_disputa_nome,
        objeto_compra, situacao_compra_id, situacao_compra_nome, uf,
        data_publicacao_pncp, valor_total_estimado, valor_total_homologado,
        existe_resultado, link_pncp, link_sistema_origem
    )
"""
_LICITACAO_CONFLITO = """
    ON CONFLICT (numero_controle_pncp) DO UPDATE SET
        situacao_compra_id = EXCLUDED.situacao_compra_id,
        situacao_compra_nome = EXCLUDED.situacao_compra_nome,
        valor_total_estimado = EXCLUDED.valor_total_estimado,
        valor_total_homologado = EXCLUDED.valor_total_homologado,
        existe_resultado = EXCLUDED.existe_resultado,
        atualizado_em = now()
"""


def upsert_licitacoes_lote(conn: psycopg.Connection, linhas, cache_orgao: dict, cache_unidade: dict) -> dict:
    """linhas: iteravel de dicts (streaming - nao precisa ser uma list).
    Resolve orgao/unidade linha a linha (barato, cache-backed) e grava as
    licitacoes em lotes de _TAMANHO_LOTE. Devolve {numero_controle_pncp:
    licitacao_id}."""
    resultado: dict = {}
    lote: dict = {}
    total = 0
    for row in linhas:
        total += 1
        numero_controle = row.get("numero_controle_PNCP")
        if not numero_controle:
            continue

        orgao_id = upsert_orgao(
            conn,
            row.get("orgao_entidade_cnpj"),
            row.get("orgao_entidade_razao_social"),
            row.get("orgao_entidade_poder_id"),
            row.get("orgao_entidade_esfera_id"),
            cache_orgao,
        )
        unidade_id = upsert_unidade(
            conn,
            orgao_id,
            row.get("unidade_orgao_codigo_unidade"),
            row.get("unidade_orgao_nome_unidade"),
            row.get("unidade_orgao_uf_sigla"),
            row.get("unidade_orgao_municipio_nome"),
            row.get("unidade_orgao_codigo_ibge"),
            cache_unidade,
        )

        cnpj = clean_cnpj(row.get("orgao_entidade_cnpj"))
        ano = parse_int(row.get("ano_compra_pncp"))
        sequencial = parse_int(row.get("sequencial_compra_pncp"))
        link = config.link_pncp(cnpj, ano, sequencial) if cnpj and ano and sequencial else None

        lote[numero_controle] = (
            numero_controle,
            orgao_id,
            unidade_id,
            ano,
            sequencial,
            row.get("numero_compra"),
            row.get("processo"),
            parse_int(row.get("codigo_modalidade")),
            row.get("modalidade_nome"),
            row.get("modo_disputa_nome_pncp"),
            row.get("objeto_compra"),
            parse_int(row.get("situacao_compra_id_pncp")),
            row.get("situacao_compra_nome_pncp"),
            row.get("unidade_orgao_uf_sigla"),
            parse_date(row.get("data_publicacao_pncp")),
            parse_decimal(row.get("valor_total_estimado")),
            parse_decimal(row.get("valor_total_homologado")),
            parse_bool(row.get("existe_resultado")),
            link,
            row.get("link_sistema_origem"),
        )
        if len(lote) >= _TAMANHO_LOTE:
            resultado.update(_inserir_lote(conn, _LICITACAO_INSERT, _LICITACAO_CONFLITO, 20, lote))
            conn.commit()
            lote = {}
    if lote:
        resultado.update(_inserir_lote(conn, _LICITACAO_INSERT, _LICITACAO_CONFLITO, 20, lote))
        conn.commit()
    print(f"compras: {len(resultado)}/{total} linhas carregadas")
    return resultado


_ITEM_INSERT = """
    INSERT INTO itens (
        licitacao_id, numero_item, descricao_item, produto, material_ou_servico, quantidade,
        unidade_medida, valor_unitario_estimado, valor_total_estimado,
        situacao_item_id, situacao_item_nome, tem_resultado
    )
"""
_ITEM_CONFLITO = """
    ON CONFLICT (licitacao_id, numero_item) DO UPDATE SET
        produto = EXCLUDED.produto,
        situacao_item_id = EXCLUDED.situacao_item_id,
        situacao_item_nome = EXCLUDED.situacao_item_nome,
        tem_resultado = EXCLUDED.tem_resultado
"""


def upsert_itens_lote(conn: psycopg.Connection, linhas, cache_licitacao: dict) -> None:
    """Nao devolve um cache dos itens gravados (ao contrario de
    upsert_licitacoes_lote) de proposito: os arquivos anuais tem milhoes de
    itens, e um dict {chave: item_id} nessa escala (testado: 2.9M entradas
    em 2025) e o suficiente pra derrubar o processo por falta de memoria
    (confirmado em 2026-08-30 - backfill morreu sem traceback no meio do
    arquivo de itens de 2026). upsert_resultados_lote resolve o item_id
    direto no banco, em lote, quando precisar."""
    lote: dict = {}
    total = 0
    carregados = 0
    for row in linhas:
        total += 1
        numero_controle = row.get("numero_controle_PNCP_compra")
        numero_item = parse_int(row.get("numero_item_compra"))
        if not numero_controle or numero_item is None:
            continue
        licitacao_id = cache_licitacao.get(numero_controle)
        if licitacao_id is None:
            continue

        descricao = row.get("descricao_detalhada") or row.get("descricao_resumida")
        lote[(numero_controle, numero_item)] = (
            licitacao_id,
            numero_item,
            descricao,
            extrair_produto(descricao),
            row.get("material_ou_servico"),
            parse_decimal(row.get("quantidade")),
            row.get("unidade_medida"),
            parse_decimal(row.get("valor_unitario_estimado")),
            parse_decimal(row.get("valor_total")),
            parse_int(row.get("situacao_compra_item")),
            row.get("situacao_compra_item_nome"),
            parse_bool(row.get("tem_resultado")) or False,
        )
        if len(lote) >= _TAMANHO_LOTE:
            carregados += len(_inserir_lote(conn, _ITEM_INSERT, _ITEM_CONFLITO, 12, lote))
            conn.commit()
            lote = {}
    if lote:
        carregados += len(_inserir_lote(conn, _ITEM_INSERT, _ITEM_CONFLITO, 12, lote))
        conn.commit()
    print(f"itens: {carregados}/{total} linhas carregadas")


_RESULTADO_INSERT = """
    INSERT INTO resultados_item (
        item_id, sequencial_resultado, ni_fornecedor, tipo_pessoa, nome_razao_social,
        valor_unitario_homologado, valor_total_homologado, quantidade_homologada,
        ordem_classificacao_srp, situacao_resultado_id, situacao_resultado_nome,
        data_resultado, uf, data_publicacao_pncp, material_ou_servico
    )
"""
_RESULTADO_CONFLITO = """
    ON CONFLICT (item_id, sequencial_resultado) DO UPDATE SET
        valor_unitario_homologado = EXCLUDED.valor_unitario_homologado,
        valor_total_homologado = EXCLUDED.valor_total_homologado,
        quantidade_homologada = EXCLUDED.quantidade_homologada,
        situacao_resultado_id = EXCLUDED.situacao_resultado_id,
        situacao_resultado_nome = EXCLUDED.situacao_resultado_nome,
        uf = EXCLUDED.uf,
        data_publicacao_pncp = EXCLUDED.data_publicacao_pncp,
        material_ou_servico = EXCLUDED.material_ou_servico
"""


def _resolver_itens(conn: psycopg.Connection, pares: list) -> dict:
    """pares: lista de (licitacao_id, numero_item). Resolve, em lote via
    indice UNIQUE(licitacao_id, numero_item), o item_id junto com uf/data
    de publicacao da licitacao e material_ou_servico do item (duplicados em
    resultados_item - ver schema.sql) - tudo numa unica consulta em vez de
    depender de um cache em memoria com todo o arquivo de itens (essa era a
    causa da falta de memoria - ver upsert_itens_lote)."""
    if not pares:
        return {}
    unicos = list(set(pares))
    placeholder = ",".join(["(%s,%s)"] * len(unicos))
    params = [v for par in unicos for v in par]
    linhas = conn.execute(
        f"""
        SELECT i.licitacao_id, i.numero_item, i.id, l.uf, l.data_publicacao_pncp, i.material_ou_servico
        FROM itens i
        JOIN licitacoes l ON l.id = i.licitacao_id
        WHERE (i.licitacao_id, i.numero_item) IN ({placeholder})
        """,
        params,
    ).fetchall()
    return {
        (lic_id, num_item): (item_id, uf, data_pub, mat_serv)
        for lic_id, num_item, item_id, uf, data_pub, mat_serv in linhas
    }


def upsert_resultados_lote(conn: psycopg.Connection, linhas, cache_licitacao: dict) -> None:
    lote: dict = {}
    total = 0
    processados = 0
    for row in linhas:
        total += 1
        numero_controle = row.get("numero_controle_PNCP_compra")
        numero_item = parse_int(row.get("numero_item_pncp"))
        if not numero_controle or numero_item is None:
            continue
        licitacao_id = cache_licitacao.get(numero_controle)
        if licitacao_id is None:
            continue

        sequencial_resultado = parse_int(row.get("sequencial_resultado")) or 1
        lote[(licitacao_id, numero_item, sequencial_resultado)] = (
            clean_cnpj(row.get("ni_fornecedor")) or row.get("ni_fornecedor"),
            row.get("tipo_pessoa"),
            row.get("nome_razao_social_fornecedor"),
            parse_decimal(row.get("valor_unitario_homologado")),
            parse_decimal(row.get("valor_total_homologado")),
            parse_decimal(row.get("quantidade_homologada")),
            parse_int(row.get("ordem_classificacao_srp")),
            parse_int(row.get("situacao_compra_item_resultado_id")),
            row.get("situacao_compra_item_resultado_nome"),
            parse_date(row.get("data_resultado_pncp")),
        )
        if len(lote) >= _TAMANHO_LOTE:
            processados += _gravar_lote_resultados(conn, lote)
            conn.commit()
            lote = {}
    if lote:
        processados += _gravar_lote_resultados(conn, lote)
        conn.commit()
    print(f"resultados: {processados}/{total} linhas processadas")


def _gravar_lote_resultados(conn: psycopg.Connection, lote: dict) -> int:
    pares = [(lic_id, num_item) for (lic_id, num_item, _seq) in lote.keys()]
    itens_resolvidos = _resolver_itens(conn, pares)
    linhas_finais = {}
    for (lic_id, num_item, seq), valores in lote.items():
        resolvido = itens_resolvidos.get((lic_id, num_item))
        if resolvido is None:
            # O item pode nao ter vindo no arquivo de itens do mesmo periodo
            # (ex: resultado alterado sem o item ter sido re-exportado).
            continue
        item_id, uf, data_pub, mat_serv = resolvido
        linhas_finais[(item_id, seq)] = (item_id, seq) + valores + (uf, data_pub, mat_serv)
    if not linhas_finais:
        return 0
    _inserir_lote(conn, _RESULTADO_INSERT, _RESULTADO_CONFLITO, 15, linhas_finais)
    return len(linhas_finais)
