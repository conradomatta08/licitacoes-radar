"""Upserts no Postgres a partir das linhas dos CSVs em lote do
Compras.gov.br (repositorio.dados.gov.br). Cada funcao upsert_*_csv recebe
uma linha (dict) vinda de clients.bulk_csv_client.baixar_csv - as chaves
sao os nomes exatos das colunas do CSV, confirmados manualmente em
2026-08-29 (ver plano).

Os caches (dict) sao opcionais: quando fornecidos, evitam um SELECT por
linha pra resolver orgao_id/licitacao_id/item_id ja resolvidos antes na
mesma execucao - essencial pra rodar num tempo razoavel com dezenas de
milhares de linhas por arquivo."""

import json

import psycopg

import config
from pipeline.normalize import clean_cnpj, parse_bool, parse_date, parse_decimal, parse_int


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


def upsert_licitacao_csv(conn: psycopg.Connection, row: dict, cache_orgao: dict | None = None, cache_unidade: dict | None = None) -> int | None:
    numero_controle = row.get("numero_controle_PNCP")
    if not numero_controle:
        return None

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

    result = conn.execute(
        """
        INSERT INTO licitacoes (
            numero_controle_pncp, orgao_id, unidade_id, ano_compra, sequencial_compra,
            numero_compra, processo, modalidade_id, modalidade_nome, modo_disputa_nome,
            objeto_compra, situacao_compra_id, situacao_compra_nome, uf,
            data_publicacao_pncp, valor_total_estimado, valor_total_homologado,
            existe_resultado, link_pncp, link_sistema_origem, raw_payload, atualizado_em
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now())
        ON CONFLICT (numero_controle_pncp) DO UPDATE SET
            situacao_compra_id = EXCLUDED.situacao_compra_id,
            situacao_compra_nome = EXCLUDED.situacao_compra_nome,
            valor_total_estimado = EXCLUDED.valor_total_estimado,
            valor_total_homologado = EXCLUDED.valor_total_homologado,
            existe_resultado = EXCLUDED.existe_resultado,
            raw_payload = EXCLUDED.raw_payload,
            atualizado_em = now()
        RETURNING id
        """,
        (
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
            json.dumps(row, ensure_ascii=False),
        ),
    ).fetchone()
    return result[0] if result else None


def _licitacao_id(conn: psycopg.Connection, numero_controle_pncp: str) -> int | None:
    row = conn.execute(
        "SELECT id FROM licitacoes WHERE numero_controle_pncp = %s", (numero_controle_pncp,)
    ).fetchone()
    return row[0] if row else None


def preload_licitacao_ids(conn: psycopg.Connection, numeros_controle, cache: dict) -> None:
    """Busca em uma unica consulta os licitacao_id de todos os
    numero_controle_pncp ainda nao presentes no cache, evitando um SELECT
    por linha quando o arquivo de itens/resultados referencia licitacoes
    de fora do proprio arquivo de compras (ex: item alterado de uma
    licitacao publicada em dia anterior)."""
    faltantes = list({n for n in numeros_controle if n and n not in cache})
    if not faltantes:
        return
    rows = conn.execute(
        "SELECT numero_controle_pncp, id FROM licitacoes WHERE numero_controle_pncp = ANY(%s)",
        (faltantes,),
    ).fetchall()
    for numero_controle, licitacao_id in rows:
        cache[numero_controle] = licitacao_id


def _item_id(conn: psycopg.Connection, licitacao_id: int, numero_item: int) -> int | None:
    row = conn.execute(
        "SELECT id FROM itens WHERE licitacao_id = %s AND numero_item = %s", (licitacao_id, numero_item)
    ).fetchone()
    return row[0] if row else None


def upsert_item_csv(conn: psycopg.Connection, row: dict, cache_licitacao: dict | None = None) -> int | None:
    numero_controle = row.get("numero_controle_PNCP_compra")
    numero_item = parse_int(row.get("numero_item_compra"))
    if not numero_controle or numero_item is None:
        return None

    if cache_licitacao is not None:
        # O cache ja foi pre-carregado em lote (preload_licitacao_ids) - uma
        # ausencia aqui e definitiva, nao vale a pena checar de novo no banco.
        licitacao_id = cache_licitacao.get(numero_controle)
    else:
        licitacao_id = _licitacao_id(conn, numero_controle)
    if licitacao_id is None:
        # Licitacao fora do escopo carregado (ex: filtrada pela janela do backfill).
        return None

    descricao = row.get("descricao_detalhada") or row.get("descricao_resumida")

    result = conn.execute(
        """
        INSERT INTO itens (
            licitacao_id, numero_item, descricao_item, material_ou_servico, quantidade,
            unidade_medida, valor_unitario_estimado, valor_total_estimado,
            situacao_item_id, situacao_item_nome, tem_resultado, raw_payload
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (licitacao_id, numero_item) DO UPDATE SET
            situacao_item_id = EXCLUDED.situacao_item_id,
            situacao_item_nome = EXCLUDED.situacao_item_nome,
            tem_resultado = EXCLUDED.tem_resultado,
            raw_payload = EXCLUDED.raw_payload
        RETURNING id
        """,
        (
            licitacao_id,
            numero_item,
            descricao,
            row.get("material_ou_servico"),
            parse_decimal(row.get("quantidade")),
            row.get("unidade_medida"),
            parse_decimal(row.get("valor_unitario_estimado")),
            parse_decimal(row.get("valor_total")),
            parse_int(row.get("situacao_compra_item")),
            row.get("situacao_compra_item_nome"),
            parse_bool(row.get("tem_resultado")) or False,
            json.dumps(row, ensure_ascii=False),
        ),
    ).fetchone()
    return result[0] if result else None


def upsert_resultado_csv(conn: psycopg.Connection, row: dict, cache_licitacao: dict | None = None, cache_item: dict | None = None) -> None:
    numero_controle = row.get("numero_controle_PNCP_compra")
    numero_item = parse_int(row.get("numero_item_pncp"))
    if not numero_controle or numero_item is None:
        return

    if cache_licitacao is not None:
        licitacao_id = cache_licitacao.get(numero_controle)
    else:
        licitacao_id = _licitacao_id(conn, numero_controle)
    if licitacao_id is None:
        return

    if cache_item is not None:
        # O item pode nao ter vindo no arquivo de itens do mesmo periodo
        # (ex: resultado alterado sem o item ter sido re-exportado) - uma
        # ausencia no cache ja populado significa isso, sem checar de novo.
        item_id = cache_item.get((numero_controle, numero_item))
    else:
        item_id = _item_id(conn, licitacao_id, numero_item)
    if item_id is None:
        return

    sequencial_resultado = parse_int(row.get("sequencial_resultado")) or 1

    conn.execute(
        """
        INSERT INTO resultados_item (
            item_id, sequencial_resultado, ni_fornecedor, tipo_pessoa, nome_razao_social,
            valor_unitario_homologado, valor_total_homologado, quantidade_homologada,
            ordem_classificacao_srp, situacao_resultado_id, situacao_resultado_nome,
            data_resultado, raw_payload
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (item_id, sequencial_resultado) DO UPDATE SET
            valor_unitario_homologado = EXCLUDED.valor_unitario_homologado,
            valor_total_homologado = EXCLUDED.valor_total_homologado,
            quantidade_homologada = EXCLUDED.quantidade_homologada,
            situacao_resultado_id = EXCLUDED.situacao_resultado_id,
            situacao_resultado_nome = EXCLUDED.situacao_resultado_nome,
            raw_payload = EXCLUDED.raw_payload
        """,
        (
            item_id,
            sequencial_resultado,
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
            json.dumps(row, ensure_ascii=False),
        ),
    )
