import { pool } from "./db";

export type Ordenacao = "valor_desc" | "valor_asc";

export interface Filtros {
  q?: string;
  descricao?: string;
  produto?: string;
  tipo?: string;
  fabricante?: string;
  ufFornecedor?: string;
  ufOrgao?: string;
  portal?: string;
  dataInicial?: string;
  dataFinal?: string;
  valorMinimo?: string;
  valorMaximo?: string;
  ordenar?: Ordenacao;
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
  uf_fornecedor: string | null;
  eh_fabricante: boolean | null;
  provavel_importador: boolean;
  portal: string | null;
  data_publicacao_pncp: string | null;
  numero_item: number;
  descricao_item: string;
  produto: string | null;
  material_ou_servico: string | null;
  catalogo_codigo: number | null;
  catalogo_nome: string | null;
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
// cnetmobile.estaleiro.serpro.gov.br eh o ComprasNet (nome popular do
// sistema do Serpro) - normaliza pro nome que as pessoas reconhecem.
const PORTAL_EXPR = `
  CASE
    WHEN l.link_sistema_origem IS NULL OR l.link_sistema_origem = '' THEN NULL
    WHEN regexp_replace(l.link_sistema_origem, '^(?:https?://)?(?:www\\.)?([^/]+).*$', '\\1') = 'gov.br'
      THEN 'Compras.gov.br'
    WHEN regexp_replace(l.link_sistema_origem, '^(?:https?://)?(?:www\\.)?([^/]+).*$', '\\1') = 'cnetmobile.estaleiro.serpro.gov.br'
      THEN 'ComprasNet'
    ELSE regexp_replace(l.link_sistema_origem, '^(?:https?://)?(?:www\\.)?([^/]+).*$', '\\1')
  END
`;

// Nao existe CNAE de "importadora" (confirmado - importacao e fluxo
// comercial, nao setor de atividade). O nome do vencedor (ja temos, vem
// direto do PNCP) e o unico indicio viavel - so um heuristico por texto,
// nao um dado oficial cadastral como eh_fabricante.
const IMPORTADOR_EXPR = `r.nome_razao_social ILIKE '%import%'`;

const FROM_JOINS = `
  FROM resultados_item r
  JOIN itens i ON i.id = r.item_id
  JOIN licitacoes l ON l.id = i.licitacao_id
  JOIN orgaos o ON o.id = l.orgao_id
  LEFT JOIN fornecedores fo ON fo.cnpj = r.ni_fornecedor
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
  if (filtros.tipo) {
    params.push(filtros.tipo);
    // r.material_ou_servico (nao i.*): duplicado direto em resultados_item
    // pelo mesmo motivo do uf/data (ver contarResultados/schema.sql).
    condicoes.push(`r.material_ou_servico = $${params.length}`);
  }
  if (filtros.ufOrgao) {
    params.push(filtros.ufOrgao.toUpperCase());
    // r.uf (nao l.uf): duplicado direto em resultados_item pra filtrar sem
    // precisar juntar itens/licitacoes (ver contarResultados/schema.sql).
    condicoes.push(`r.uf = $${params.length}`);
  }
  // "sim" = qualquer um dos dois sinais; "fabricante"/"importador" isolam
  // um sinal especifico (independente do outro estar presente ou nao);
  // "nao" = nenhum dos dois. Nao existe CNAE de "importadora" (importacao
  // e fluxo comercial, nao setor de atividade - confirmado em pesquisa em
  // 2026-08-31), entao o nome do vencedor e o unico sinal viavel pra esse
  // segundo caso.
  if (filtros.fabricante === "sim") {
    condicoes.push(`(fo.eh_fabricante = true OR ${IMPORTADOR_EXPR})`);
  } else if (filtros.fabricante === "fabricante") {
    condicoes.push(`fo.eh_fabricante = true`);
  } else if (filtros.fabricante === "importador") {
    condicoes.push(`${IMPORTADOR_EXPR}`);
  } else if (filtros.fabricante === "nao") {
    condicoes.push(`(fo.eh_fabricante = false AND NOT (${IMPORTADOR_EXPR}))`);
  }
  if (filtros.ufFornecedor) {
    params.push(filtros.ufFornecedor.toUpperCase());
    condicoes.push(`fo.uf = $${params.length}`);
  }
  if (filtros.portal) {
    params.push(`%${filtros.portal}%`);
    condicoes.push(`(${PORTAL_EXPR}) ILIKE $${params.length}`);
  }
  if (filtros.dataInicial) {
    params.push(filtros.dataInicial);
    condicoes.push(`r.data_publicacao_pncp >= $${params.length}`);
  }
  if (filtros.dataFinal) {
    params.push(filtros.dataFinal);
    condicoes.push(`r.data_publicacao_pncp <= $${params.length}`);
  }
  if (filtros.valorMinimo) {
    params.push(filtros.valorMinimo);
    condicoes.push(`r.valor_unitario_homologado >= $${params.length}`);
  }
  if (filtros.valorMaximo) {
    params.push(filtros.valorMaximo);
    condicoes.push(`r.valor_unitario_homologado <= $${params.length}`);
  }

  const where = condicoes.length ? `WHERE ${condicoes.join(" AND ")}` : "";
  return { where, params };
}

function ordenarPor(ordenar: Ordenacao | undefined): string {
  return ordenar === "valor_asc"
    ? "ORDER BY r.valor_unitario_homologado ASC NULLS LAST, r.id DESC"
    : "ORDER BY r.valor_unitario_homologado DESC NULLS LAST, r.id DESC";
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
  fo.uf AS uf_fornecedor,
  fo.eh_fabricante,
  (${IMPORTADOR_EXPR}) AS provavel_importador,
  (${PORTAL_EXPR}) AS portal,
  l.data_publicacao_pncp,
  i.numero_item,
  i.descricao_item,
  i.produto,
  r.material_ou_servico,
  i.catalogo_codigo,
  i.catalogo_nome,
  r.ni_fornecedor,
  r.nome_razao_social,
  r.valor_unitario_homologado,
  r.quantidade_homologada,
  l.link_pncp
`;

// A contagem so precisa dos JOINs que os filtros ativos realmente usam -
// uf/data/valor agora estao direto em resultados_item (ver schema.sql),
// entao a maioria das buscas nem chega a tocar itens/licitacoes/orgaos.
// Sem isso (JOIN fixo com as 4 tabelas sempre) filtrar so por UF chegou a
// levar 2-13s pra contar ~580 mil linhas batendo em 3 tabelas de milhoes
// de linhas a toa - medido em 2026-08-30. Only itens/licitacoes/orgaos
// entram quando descricao/produto (itens), portal (licitacoes) ou q
// (orgaos.razao_social) estao no filtro.
function construirFromContagem(filtros: Omit<Filtros, "pagina" | "porPagina">): string {
  const precisaOrgao = !!filtros.q;
  const precisaLicitacao = precisaOrgao || !!filtros.portal;
  const precisaItem = precisaLicitacao || !!filtros.descricao || !!filtros.produto;
  // "importador" sozinho nao precisa de fo (so olha r.nome_razao_social).
  const precisaFornecedor =
    filtros.fabricante === "sim" ||
    filtros.fabricante === "fabricante" ||
    filtros.fabricante === "nao" ||
    !!filtros.ufFornecedor;

  let from = "FROM resultados_item r";
  if (precisaItem) from += " JOIN itens i ON i.id = r.item_id";
  if (precisaLicitacao) from += " JOIN licitacoes l ON l.id = i.licitacao_id";
  if (precisaOrgao) from += " JOIN orgaos o ON o.id = l.orgao_id";
  if (precisaFornecedor) from += " JOIN fornecedores fo ON fo.cnpj = r.ni_fornecedor";
  return from;
}

async function contarResultados(filtros: Omit<Filtros, "pagina" | "porPagina">, where: string, params: unknown[]): Promise<number> {
  const sql = `SELECT count(*) ${construirFromContagem(filtros)} ${where}`;
  const res = await pool.query(sql, params);
  return parseInt(res.rows[0].count, 10);
}

export async function buscarResultados(filtros: Filtros): Promise<{ linhas: ResultadoLinha[]; total: number }> {
  const { where, params } = montarFiltros(filtros);

  const total = await contarResultados(filtros, where, params);

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
     ${ordenarPor(filtros.ordenar)}
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
     ${ordenarPor(filtros.ordenar)}
     LIMIT $${dataParams.length}`,
    dataParams
  );

  const truncado = res.rows.length > LIMITE_EXPORT;
  return { linhas: (truncado ? res.rows.slice(0, LIMITE_EXPORT) : res.rows) as ResultadoLinha[], truncado };
}
