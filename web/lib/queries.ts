import { pool } from "./db";

export interface Filtros {
  q?: string;
  descricao?: string;
  produto?: string;
  uf?: string;
  portal?: string;
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
  portal: string | null;
  data_publicacao_pncp: string | null;
  numero_item: number;
  descricao_item: string;
  produto: string | null;
  ni_fornecedor: string;
  nome_razao_social: string;
  valor_unitario_homologado: number | null;
  quantidade_homologada: number | null;
  link_pncp: string;
}

// Extrai um nome de portal a partir da URL do sistema de origem
// (link_sistema_origem) - o campo "Fonte" do PNCP em si mostra sempre
// "Compras.gov.br" (canal de integracao com o PNCP, nao o portal
// especifico), entao nao serve pra identificar onde a licitacao tramitou;
// link_sistema_origem eh o que realmente varia (site proprio do orgao,
// ComprasNet, etc). Quando vazio, nao da pra saber - fica "Nao encontrado"
// no app. "www.gov.br/compras" (sem protocolo, como o Compras.gov.br as
// vezes exporta) vira "gov.br" pelo regex, entao normalizamos esse caso.
const PORTAL_EXPR = `
  CASE
    WHEN l.link_sistema_origem IS NULL OR l.link_sistema_origem = '' THEN NULL
    WHEN regexp_replace(l.link_sistema_origem, '^(?:https?://)?(?:www\\.)?([^/]+).*$', '\\1') = 'gov.br'
      THEN 'Compras.gov.br'
    ELSE regexp_replace(l.link_sistema_origem, '^(?:https?://)?(?:www\\.)?([^/]+).*$', '\\1')
  END
`;

const FROM_JOINS = `
  FROM resultados_item r
  JOIN itens i ON i.id = r.item_id
  JOIN licitacoes l ON l.id = i.licitacao_id
  JOIN orgaos o ON o.id = l.orgao_id
`;

function montarFiltros(filtros: Omit<Filtros, "pagina" | "porPagina">) {
  const condicoes: string[] = [];
  const params: unknown[] = [];

  if (filtros.q) {
    params.push(`%${filtros.q}%`);
    const idx = params.length;
    condicoes.push(`(r.nome_razao_social ILIKE $${idx} OR r.ni_fornecedor ILIKE $${idx} OR o.razao_social ILIKE $${idx})`);
  }
  if (filtros.descricao) {
    params.push(`%${filtros.descricao}%`);
    condicoes.push(`i.descricao_item ILIKE $${params.length}`);
  }
  if (filtros.produto) {
    params.push(`%${filtros.produto}%`);
    condicoes.push(`i.produto ILIKE $${params.length}`);
  }
  if (filtros.uf) {
    params.push(filtros.uf.toUpperCase());
    condicoes.push(`l.uf = $${params.length}`);
  }
  if (filtros.portal) {
    params.push(`%${filtros.portal}%`);
    condicoes.push(`(${PORTAL_EXPR}) ILIKE $${params.length}`);
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

const SELECT_COLUNAS = `
  r.id AS resultado_id,
  l.id AS licitacao_id,
  l.numero_controle_pncp,
  l.objeto_compra,
  o.razao_social AS orgao_nome,
  l.uf,
  u.municipio,
  l.modalidade_nome,
  (${PORTAL_EXPR}) AS portal,
  l.data_publicacao_pncp,
  i.numero_item,
  i.descricao_item,
  i.produto,
  r.ni_fornecedor,
  r.nome_razao_social,
  r.valor_unitario_homologado,
  r.quantidade_homologada,
  l.link_pncp
`;

const ORDER_BY = "ORDER BY l.data_publicacao_pncp DESC NULLS LAST, r.id DESC";

export async function buscarResultados(filtros: Filtros): Promise<{ linhas: ResultadoLinha[]; total: number }> {
  const { where, params } = montarFiltros(filtros);

  const totalRes = await pool.query(`SELECT count(*) ${FROM_JOINS} ${where}`, params);
  const total = parseInt(totalRes.rows[0].count, 10);

  const dataParams = [...params];
  dataParams.push(filtros.porPagina);
  const limitIdx = dataParams.length;
  dataParams.push((filtros.pagina - 1) * filtros.porPagina);
  const offsetIdx = dataParams.length;

  const dataRes = await pool.query(
    `SELECT ${SELECT_COLUNAS}
     ${FROM_JOINS}
     LEFT JOIN unidades_orgao u ON u.id = l.unidade_id
     ${where}
     ${ORDER_BY}
     LIMIT $${limitIdx} OFFSET $${offsetIdx}`,
    dataParams
  );

  return { linhas: dataRes.rows as ResultadoLinha[], total };
}

// Exportação (CSV/XLSX): mesmos filtros, sem paginação. Limitada por
// segurança - com filtros mais específicos dá pra exportar o recorte
// inteiro; sem filtro, o teto evita uma consulta/arquivo gigantes demais
// pra uma função serverless.
const LIMITE_EXPORT = 200_000;

export async function buscarResultadosParaExport(filtros: Omit<Filtros, "pagina" | "porPagina">): Promise<{ linhas: ResultadoLinha[]; truncado: boolean }> {
  const { where, params } = montarFiltros(filtros);
  const dataParams = [...params, LIMITE_EXPORT + 1];

  const res = await pool.query(
    `SELECT ${SELECT_COLUNAS}
     ${FROM_JOINS}
     LEFT JOIN unidades_orgao u ON u.id = l.unidade_id
     ${where}
     ${ORDER_BY}
     LIMIT $${dataParams.length}`,
    dataParams
  );

  const truncado = res.rows.length > LIMITE_EXPORT;
  return { linhas: (truncado ? res.rows.slice(0, LIMITE_EXPORT) : res.rows) as ResultadoLinha[], truncado };
}
