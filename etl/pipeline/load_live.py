"""Carrega dados da API ao vivo do PNCP (clients/pncp_live_client.py) no
banco, adaptando o JSON pros mesmos nomes de campo que pipeline/load.py ja
espera (formato dos CSVs em lote) - reaproveita upsert_licitacoes_lote/
upsert_itens_lote/upsert_resultados_lote sem duplicar nada dessa logica.

Ao contrario do fluxo em lote (arquivo -> banco em 3 etapas separadas),
aqui buscamos os itens de cada contratacao logo depois de descobri-la
(um contratacao de cada vez) - o volume por chamada da API ao vivo e
pequeno (nunca as centenas de milhares de linhas de um CSV anual), entao
nao ha risco de estourar memoria acumulando essas listas."""

import httpx

import clients.pncp_live_client as live
from db.connection import get_conn
from pipeline import load


def _adaptar_compra(c: dict, existe_resultado: bool) -> dict:
    orgao = c.get("orgaoEntidade") or {}
    unidade = c.get("unidadeOrgao") or {}
    return {
        "numero_controle_PNCP": c.get("numeroControlePNCP"),
        "orgao_entidade_cnpj": orgao.get("cnpj"),
        "orgao_entidade_razao_social": orgao.get("razaoSocial"),
        "orgao_entidade_poder_id": orgao.get("poderId"),
        "orgao_entidade_esfera_id": orgao.get("esferaId"),
        "unidade_orgao_codigo_unidade": unidade.get("codigoUnidade"),
        "unidade_orgao_nome_unidade": unidade.get("nomeUnidade"),
        "unidade_orgao_uf_sigla": unidade.get("ufSigla"),
        "unidade_orgao_municipio_nome": unidade.get("municipioNome"),
        "unidade_orgao_codigo_ibge": unidade.get("codigoIbge"),
        "ano_compra_pncp": c.get("anoCompra"),
        "sequencial_compra_pncp": c.get("sequencialCompra"),
        "numero_compra": c.get("numeroCompra"),
        "processo": c.get("processo"),
        "codigo_modalidade": c.get("modalidadeId"),
        "modalidade_nome": c.get("modalidadeNome"),
        "modo_disputa_nome_pncp": c.get("modoDisputaNome"),
        "objeto_compra": c.get("objetoCompra"),
        "situacao_compra_id_pncp": c.get("situacaoCompraId"),
        "situacao_compra_nome_pncp": c.get("situacaoCompraNome"),
        "data_publicacao_pncp": c.get("dataPublicacaoPncp"),
        "valor_total_estimado": c.get("valorTotalEstimado"),
        "valor_total_homologado": c.get("valorTotalHomologado"),
        "existe_resultado": existe_resultado,
        "link_sistema_origem": c.get("linkSistemaOrigem"),
    }


def _adaptar_item(it: dict, numero_controle: str) -> dict:
    return {
        "numero_controle_PNCP_compra": numero_controle,
        "numero_item_compra": it.get("numeroItem"),
        "descricao_detalhada": it.get("descricao"),
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
        "numero_controle_PNCP_compra": r.get("numeroControlePNCPCompra"),
        "numero_item_pncp": r.get("numeroItem"),
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
        "data_resultado_pncp": r.get("dataResultado"),
    }


def carregar_periodo_live(data_inicial: str, data_final: str) -> None:
    """data_inicial/data_final: 'AAAAMMDD'. Descobre contratacoes de todas
    as modalidades publicadas nesse periodo, busca os itens de cada uma, e
    os resultados dos itens ja homologados (temResultado=true).

    A API do PNCP e instavel sob uso sustentado (confirmado em 2026-09-09 -
    uma modalidade travou com 502/503 repetidos apos varias chamadas
    seguidas, mesmo com retry). Por isso cada modalidade e cada contratacao
    individual sao isoladas em try/except: uma falha (mesmo apos esgotar as
    tentativas) so pula aquela unidade e loga um aviso, nunca derruba a
    carga inteira - o que ja foi buscado com sucesso ate ali continua
    sendo salvo no fim. Modalidades/contratacoes puladas ficam pendentes
    pra uma proxima execucao (idempotente - roda de novo sem duplicar)."""
    linhas_compra = []
    linhas_item = []
    pendentes_resultado = []  # (cnpj, ano, sequencial, numero_item)
    falhas = 0

    for modalidade in live.MODALIDADES:
        n_modalidade = 0
        try:
            contratacoes = list(live.buscar_contratacoes(data_inicial, data_final, modalidade))
        except (httpx.TransportError, httpx.HTTPStatusError, ValueError) as e:
            falhas += 1
            print(f"  [aviso] modalidade {modalidade}: descoberta falhou ({e}) - pulando pra proxima modalidade")
            continue

        for c in contratacoes:
            numero_controle = c.get("numeroControlePNCP")
            orgao = c.get("orgaoEntidade") or {}
            cnpj, ano, seq = orgao.get("cnpj"), c.get("anoCompra"), c.get("sequencialCompra")
            if not (numero_controle and cnpj and ano and seq):
                continue

            try:
                itens_json = live.buscar_itens(cnpj, ano, seq)
            except (httpx.TransportError, httpx.HTTPStatusError, ValueError) as e:
                falhas += 1
                print(f"  [aviso] itens de {numero_controle} falharam ({e}) - pulando essa contratacao")
                continue

            n_modalidade += 1
            tem_algum_resultado = False
            for it in itens_json:
                linhas_item.append(_adaptar_item(it, numero_controle))
                if it.get("temResultado"):
                    tem_algum_resultado = True
                    pendentes_resultado.append((cnpj, ano, seq, it.get("numeroItem")))

            linhas_compra.append(_adaptar_compra(c, tem_algum_resultado))
        if n_modalidade:
            print(f"  modalidade {modalidade}: {n_modalidade} contratacoes")

    linhas_resultado = []
    for cnpj, ano, seq, numero_item in pendentes_resultado:
        try:
            resultados_json = live.buscar_resultados(cnpj, ano, seq, numero_item)
        except (httpx.TransportError, httpx.HTTPStatusError, ValueError) as e:
            falhas += 1
            print(f"  [aviso] resultado de {cnpj}/{ano}/{seq}/{numero_item} falhou ({e}) - pulando")
            continue
        for r in resultados_json:
            linhas_resultado.append(_adaptar_resultado(r))

    if falhas:
        print(f"  {falhas} chamada(s) falharam e foram puladas (fica pendente pra proxima execucao)")

    with get_conn() as conn:
        cache_licitacao = load.upsert_licitacoes_lote(conn, linhas_compra, {}, {})
        load.upsert_itens_lote(conn, linhas_item, cache_licitacao)
        load.upsert_resultados_lote(conn, linhas_resultado, cache_licitacao)


def reprocessar_pendentes(dias_max: int = 90, limite: int = 500) -> None:
    """Reconsulta o resultado de itens que ainda nao tinham resultado da
    ultima vez (tem_resultado=false), publicados nos ultimos `dias_max`
    dias - cobre o caso de uma licitacao publicada ha 2 semanas que so
    agora foi homologada (o discovery por data de publicacao, sozinho, so
    pega achados no MOMENTO da publicacao). Limitado a `limite` itens por
    execucao pra nao alongar demais o job de 6 em 6 horas."""
    with get_conn() as conn:
        pendentes = conn.execute(
            """
            SELECT l.numero_controle_pncp, l.id, o.cnpj, l.ano_compra, l.sequencial_compra, i.numero_item
            FROM itens i
            JOIN licitacoes l ON l.id = i.licitacao_id
            JOIN orgaos o ON o.id = l.orgao_id
            WHERE i.tem_resultado = false
              AND l.data_publicacao_pncp >= (CURRENT_DATE - %s)
            ORDER BY l.data_publicacao_pncp ASC
            LIMIT %s
            """,
            (dias_max, limite),
        ).fetchall()

        cache_licitacao = {numero_controle: licitacao_id for numero_controle, licitacao_id, *_ in pendentes}

        linhas_resultado = []
        itens_resolvidos = []  # (licitacao_id, numero_item) - pra marcar tem_resultado=true
        for _numero_controle, licitacao_id, cnpj, ano, seq, numero_item in pendentes:
            resultados_json = live.buscar_resultados(cnpj, ano, seq, numero_item)
            if resultados_json:
                itens_resolvidos.append((licitacao_id, numero_item))
                for r in resultados_json:
                    linhas_resultado.append(_adaptar_resultado(r))

        if linhas_resultado:
            load.upsert_resultados_lote(conn, linhas_resultado, cache_licitacao)

        if itens_resolvidos:
            with conn.cursor() as cur:
                cur.executemany(
                    "UPDATE itens SET tem_resultado = true WHERE licitacao_id = %s AND numero_item = %s",
                    itens_resolvidos,
                )
            conn.commit()

        print(f"reprocessamento: {len(pendentes)} itens pendentes verificados, {len(itens_resolvidos)} tinham resultado novo")
