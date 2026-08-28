import { pool } from "./db";

export interface Filtros {
  q?: string;
  uf?: string;
  dataInicial?: string;
  dataFinal?: string;
  pagina: number;
  porPagina: number;
}

export interface ResultadoLinha {
  resultado_id: number;
  licitacao_id: number;
  numero_controle_pncp: string;
  objeto_compra: string;
  orgao_nome: string;
  uf: string;
  municipio: string;
  modalidade_nome: string;
  data_publicacao_pncp: string | null;
  data_resultado: string | null;
  numero_item: number;
  descricao_item: string;
  ni_fornecedor: string;
  nome_razao_social: string;
  valor_unitario_homologado: number | null;
  quantidade_homologada: number | null;
  link_pncp: string;
}

function montarFiltros(filtros: Filtros) {
  const condicoes: string[] = [];
  const params: unknown[] = [];

  if (filtros.q) {
    params.push(`%${filtros.q}%`);
    const idx = params.length;
    condicoes.push(`(r.nome_razao_social ILIKE $${idx} OR r.ni_fornecedor ILIKE $${idx} OR o.razao_social ILIKE $${idx})`);
  }
  if (filtros.uf) {
    params.push(filtros.uf.toUpperCase());
    condicoes.push(`l.uf = $${params.length}`);
  }
  if (filtros.dataInicial) {
    params.push(filtros.dataInicial);
    condicoes.push(`l.data_publicacao_pncp >= $${params.length}`);
  }
  if (filtros.dataFinal) {
    params.push(filtros.dataFinal);
    condicoes.push(`l.data_publicacao_pncp <= $${params.length}`);
  }

  const where = condicoes.length ? `WHERE ${condicoes.join(" AND ")}` : "";
  return { where, params };
}

export async function buscarResultados(filtros: Filtros): Promise<{ linhas: ResultadoLinha[]; total: number }> {
  const { where, params } = montarFiltros(filtros);

  const totalRes = await pool.query(
    `SELECT count(*) FROM resultados_item r
     JOIN itens i ON i.id = r.item_id
     JOIN licitacoes l ON l.id = i.licitacao_id
     JOIN orgaos o ON o.id = l.orgao_id
     ${where}`,
    params
  );
  const total = parseInt(totalRes.rows[0].count, 10);

  const dataParams = [...params];
  dataParams.push(filtros.porPagina);
  const limitIdx = dataParams.length;
  dataParams.push((filtros.pagina - 1) * filtros.porPagina);
  const offsetIdx = dataParams.length;

  const dataRes = await pool.query(
    `SELECT
        r.id AS resultado_id,
        l.id AS licitacao_id,
        l.numero_controle_pncp,
        l.objeto_compra,
        o.razao_social AS orgao_nome,
        l.uf,
        u.municipio,
        l.modalidade_nome,
        l.data_publicacao_pncp,
        r.data_resultado,
        i.numero_item,
        i.descricao_item,
        r.ni_fornecedor,
        r.nome_razao_social,
        r.valor_unitario_homologado,
        r.quantidade_homologada,
        l.link_pncp
     FROM resultados_item r
     JOIN itens i ON i.id = r.item_id
     JOIN licitacoes l ON l.id = i.licitacao_id
     JOIN orgaos o ON o.id = l.orgao_id
     LEFT JOIN unidades_orgao u ON u.id = l.unidade_id
     ${where}
     ORDER BY r.data_resultado DESC NULLS LAST, r.id DESC
     LIMIT $${limitIdx} OFFSET $${offsetIdx}`,
    dataParams
  );

  return { linhas: dataRes.rows as ResultadoLinha[], total };
}

export interface ItemDetalhe {
  id: number;
  numero_item: number;
  descricao_item: string;
  vencedor_nome: string | null;
  vencedor_cnpj: string | null;
  valor_unitario_homologado: number | null;
  data_resultado: string | null;
}

export interface LicitacaoDetalhe {
  id: number;
  objeto_compra: string;
  orgao_nome: string;
  municipio: string | null;
  uf: string | null;
  modalidade_nome: string | null;
  link_pncp: string | null;
  itens: ItemDetalhe[];
}

export async function buscarLicitacaoDetalhe(id: number): Promise<LicitacaoDetalhe | null> {
  const licRes = await pool.query(
    `SELECT l.id, l.objeto_compra, o.razao_social AS orgao_nome, u.municipio, l.uf, l.modalidade_nome, l.link_pncp
     FROM licitacoes l
     JOIN orgaos o ON o.id = l.orgao_id
     LEFT JOIN unidades_orgao u ON u.id = l.unidade_id
     WHERE l.id = $1`,
    [id]
  );
  if (licRes.rows.length === 0) return null;
  const lic = licRes.rows[0];

  const itensRes = await pool.query(
    `SELECT i.id, i.numero_item, i.descricao_item, r.nome_razao_social AS vencedor_nome,
            r.ni_fornecedor AS vencedor_cnpj, r.valor_unitario_homologado, r.data_resultado
     FROM itens i
     LEFT JOIN resultados_item r ON r.item_id = i.id
     WHERE i.licitacao_id = $1
     ORDER BY i.numero_item`,
    [id]
  );

  return { ...lic, itens: itensRes.rows } as LicitacaoDetalhe;
}
