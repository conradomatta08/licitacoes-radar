"""Upserts no Postgres. Cada funcao recebe uma conexao psycopg ja aberta
(a transacao/commit e responsabilidade de quem chama, em pipeline/discover.py
etc) e o payload bruto (dict) vindo direto da API do PNCP."""

import json

import psycopg

import config
from pipeline.normalize import clean_cnpj, parse_date, parse_datetime, parse_decimal


def upsert_orgao(conn: psycopg.Connection, orgao_entidade: dict) -> int | None:
    cnpj = clean_cnpj(orgao_entidade.get("cnpj"))
    if not cnpj:
        return None
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
        (cnpj, orgao_entidade.get("razaoSocial"), orgao_entidade.get("poderId"), orgao_entidade.get("esferaId")),
    ).fetchone()
    return row[0] if row else None


def upsert_unidade(conn: psycopg.Connection, orgao_id: int | None, unidade_orgao: dict) -> int | None:
    if orgao_id is None:
        return None
    codigo = unidade_orgao.get("codigoUnidade")
    if not codigo:
        return None
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
        (
            orgao_id,
            codigo,
            unidade_orgao.get("nomeUnidade"),
            unidade_orgao.get("ufSigla"),
            unidade_orgao.get("municipioNome"),
            unidade_orgao.get("codigoIbge"),
        ),
    ).fetchone()
    return row[0] if row else None


def upsert_licitacao(conn: psycopg.Connection, contratacao: dict) -> int:
    orgao_entidade = contratacao.get("orgaoEntidade") or {}
    unidade_orgao = contratacao.get("unidadeOrgao") or {}

    orgao_id = upsert_orgao(conn, orgao_entidade)
    unidade_id = upsert_unidade(conn, orgao_id, unidade_orgao)

    cnpj = clean_cnpj(orgao_entidade.get("cnpj"))
    ano = contratacao.get("anoCompra")
    sequencial = contratacao.get("sequencialCompra")
    link = config.link_pncp(cnpj, ano, sequencial) if cnpj and ano and sequencial else None

    row = conn.execute(
        """
        INSERT INTO licitacoes (
            numero_controle_pncp, orgao_id, unidade_id, ano_compra, sequencial_compra,
            numero_compra, processo, modalidade_id, modalidade_nome, modo_disputa_nome,
            objeto_compra, situacao_compra_id, situacao_compra_nome, uf,
            data_publicacao_pncp, data_abertura_proposta, data_encerramento_proposta,
            valor_total_estimado, valor_total_homologado, link_pncp, link_sistema_origem,
            raw_payload, atualizado_em
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now()
        )
        ON CONFLICT (numero_controle_pncp) DO UPDATE SET
            situacao_compra_id = EXCLUDED.situacao_compra_id,
            situacao_compra_nome = EXCLUDED.situacao_compra_nome,
            valor_total_estimado = EXCLUDED.valor_total_estimado,
            valor_total_homologado = EXCLUDED.valor_total_homologado,
            raw_payload = EXCLUDED.raw_payload,
            atualizado_em = now()
        RETURNING id
        """,
        (
            contratacao.get("numeroControlePNCP"),
            orgao_id,
            unidade_id,
            ano,
            sequencial,
            contratacao.get("numeroCompra"),
            contratacao.get("processo"),
            contratacao.get("modalidadeId"),
            contratacao.get("modalidadeNome"),
            contratacao.get("modoDisputaNome"),
            contratacao.get("objetoCompra"),
            contratacao.get("situacaoCompraId"),
            contratacao.get("situacaoCompraNome"),
            unidade_orgao.get("ufSigla"),
            parse_date(contratacao.get("dataPublicacaoPncp")),
            parse_datetime(contratacao.get("dataAberturaProposta")),
            parse_datetime(contratacao.get("dataEncerramentoProposta")),
            parse_decimal(contratacao.get("valorTotalEstimado")),
            parse_decimal(contratacao.get("valorTotalHomologado")),
            link,
            contratacao.get("linkSistemaOrigem"),
            json.dumps(contratacao, ensure_ascii=False),
        ),
    ).fetchone()
    return row[0]


def marcar_itens_carregados(conn: psycopg.Connection, licitacao_id: int) -> None:
    conn.execute("UPDATE licitacoes SET itens_carregados = TRUE WHERE id = %s", (licitacao_id,))


def upsert_item(conn: psycopg.Connection, licitacao_id: int, item: dict) -> int:
    row = conn.execute(
        """
        INSERT INTO itens (
            licitacao_id, numero_item, descricao_item, material_ou_servico, quantidade,
            unidade_medida, valor_unitario_estimado, valor_total_estimado,
            situacao_item_id, situacao_item_nome, tem_resultado, raw_payload
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (licitacao_id, numero_item) DO UPDATE SET
            situacao_item_id = EXCLUDED.situacao_item_id,
            situacao_item_nome = EXCLUDED.situacao_item_nome,
            tem_resultado = EXCLUDED.tem_resultado,
            raw_payload = EXCLUDED.raw_payload
        RETURNING id
        """,
        (
            licitacao_id,
            item.get("numeroItem"),
            item.get("descricao"),
            item.get("materialOuServico"),
            parse_decimal(item.get("quantidade")),
            item.get("unidadeMedida"),
            parse_decimal(item.get("valorUnitarioEstimado")),
            parse_decimal(item.get("valorTotal")),
            item.get("situacaoCompraItem"),
            item.get("situacaoCompraItemNome"),
            bool(item.get("temResultado")),
            json.dumps(item, ensure_ascii=False),
        ),
    ).fetchone()
    return row[0]


def marcar_resultado_carregado(conn: psycopg.Connection, item_id: int) -> None:
    conn.execute("UPDATE itens SET resultado_carregado = TRUE WHERE id = %s", (item_id,))


def upsert_resultado(conn: psycopg.Connection, item_id: int, resultado: dict) -> None:
    conn.execute(
        """
        INSERT INTO resultados_item (
            item_id, sequencial_resultado, ni_fornecedor, tipo_pessoa, nome_razao_social,
            valor_unitario_homologado, valor_total_homologado, quantidade_homologada,
            ordem_classificacao_srp, situacao_resultado_id, situacao_resultado_nome,
            data_resultado, raw_payload
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
            resultado.get("sequencialResultado"),
            clean_cnpj(resultado.get("niFornecedor")) or resultado.get("niFornecedor"),
            resultado.get("tipoPessoa"),
            resultado.get("nomeRazaoSocialFornecedor"),
            parse_decimal(resultado.get("valorUnitarioHomologado")),
            parse_decimal(resultado.get("valorTotalHomologado")),
            parse_decimal(resultado.get("quantidadeHomologada")),
            resultado.get("ordemClassificacaoSrp"),
            resultado.get("situacaoCompraItemResultadoId"),
            resultado.get("situacaoCompraItemResultadoNome"),
            parse_date(resultado.get("dataResultado")),
            json.dumps(resultado, ensure_ascii=False),
        ),
    )


def marcar_existe_resultado(conn: psycopg.Connection, licitacao_id: int) -> None:
    conn.execute("UPDATE licitacoes SET existe_resultado = TRUE WHERE id = %s", (licitacao_id,))


def agendar_reverificacao(conn: psycopg.Connection, licitacao_id: int) -> None:
    row = conn.execute("SELECT tentativas_verificacao FROM licitacoes WHERE id = %s", (licitacao_id,)).fetchone()
    tentativa = (row[0] if row else 0)
    dias_lista = config.REPROCESS_BACKOFF_DIAS
    dias = dias_lista[min(tentativa, len(dias_lista) - 1)]
    conn.execute(
        """
        UPDATE licitacoes
        SET proxima_verificacao_em = now() + (%s::text || ' days')::interval,
            tentativas_verificacao = tentativas_verificacao + 1
        WHERE id = %s
        """,
        (dias, licitacao_id),
    )


def get_checkpoint(conn: psycopg.Connection, tipo: str, chave: str):
    row = conn.execute(
        "SELECT ultima_data_processada FROM ingestao_checkpoints WHERE tipo = %s AND chave = %s",
        (tipo, chave),
    ).fetchone()
    return row[0] if row else None


def set_checkpoint(conn: psycopg.Connection, tipo: str, chave: str, ultima_data_processada, status: str = "em_andamento") -> None:
    conn.execute(
        """
        INSERT INTO ingestao_checkpoints (tipo, chave, ultima_data_processada, status, atualizado_em)
        VALUES (%s, %s, %s, %s, now())
        ON CONFLICT (tipo, chave) DO UPDATE SET
            ultima_data_processada = EXCLUDED.ultima_data_processada,
            status = EXCLUDED.status,
            atualizado_em = now()
        """,
        (tipo, chave, ultima_data_processada, status),
    )
