import ExcelJS from "exceljs";
import { NextRequest, NextResponse } from "next/server";
import { buscarResultados, buscarResultadosParaExport, Ordenacao, ResultadoLinha } from "../../../lib/queries";

export const maxDuration = 60;

// pg devolve colunas DATE como objetos Date (nao string) - String(date) direto
// produz o formato verboso do JS ("Wed Feb 21 2024 00:00:00 GMT..."), ruim
// pra abrir no Excel. Formata como YYYY-MM-DD.
function formatarDataIso(valor: unknown): string {
  if (!valor) return "";
  const data = valor instanceof Date ? valor : new Date(String(valor));
  if (Number.isNaN(data.getTime())) return "";
  return data.toISOString().slice(0, 10);
}

function lerFiltros(sp: URLSearchParams) {
  return {
    q: sp.get("q") ?? undefined,
    descricao: sp.get("descricao") ?? undefined,
    produto: sp.get("produto") ?? undefined,
    uf: sp.get("uf") ?? undefined,
    portal: sp.get("portal") ?? undefined,
    dataInicial: sp.get("dataInicial") ?? undefined,
    dataFinal: sp.get("dataFinal") ?? undefined,
    valorMinimo: sp.get("valorMinimo") ?? undefined,
    valorMaximo: sp.get("valorMaximo") ?? undefined,
    ordenar: (sp.get("ordenar") as Ordenacao | null) ?? undefined,
  };
}

const COLUNAS_EXPORT: { titulo: string; valor: (l: ResultadoLinha) => string | number }[] = [
  { titulo: "Empresa vencedora", valor: (l) => l.nome_razao_social ?? "" },
  { titulo: "CNPJ/CPF", valor: (l) => l.ni_fornecedor ?? "" },
  { titulo: "Órgão", valor: (l) => l.orgao_nome ?? "" },
  { titulo: "UF", valor: (l) => l.uf ?? "" },
  { titulo: "Município", valor: (l) => l.municipio ?? "" },
  { titulo: "Portal", valor: (l) => l.portal ?? "Não encontrado" },
  { titulo: "Produto", valor: (l) => l.produto ?? "" },
  { titulo: "CATMAT/CATSER", valor: (l) => (l.catalogo_codigo ? `${l.catalogo_codigo} - ${l.catalogo_nome}` : "") },
  { titulo: "Descrição do item", valor: (l) => l.descricao_item ?? "" },
  { titulo: "Valor unitário homologado", valor: (l) => (l.valor_unitario_homologado ?? "") as number },
  { titulo: "Data de divulgação no PNCP", valor: (l) => formatarDataIso(l.data_publicacao_pncp) },
  { titulo: "Link PNCP", valor: (l) => l.link_pncp ?? "" },
];

function gerarCsv(linhas: ResultadoLinha[]): string {
  const header = COLUNAS_EXPORT.map((c) => c.titulo).join(",") + "\n";
  const corpo = linhas
    .map((l) => COLUNAS_EXPORT.map((c) => `"${String(c.valor(l) ?? "").replace(/"/g, '""')}"`).join(","))
    .join("\n");
  return header + corpo;
}

async function gerarXlsx(linhas: ResultadoLinha[]): Promise<Buffer> {
  const workbook = new ExcelJS.Workbook();
  const sheet = workbook.addWorksheet("Licitações");
  sheet.columns = COLUNAS_EXPORT.map((c) => ({ header: c.titulo, key: c.titulo, width: 28 }));
  for (const l of linhas) {
    sheet.addRow(COLUNAS_EXPORT.map((c) => c.valor(l)));
  }
  const buffer = await workbook.xlsx.writeBuffer();
  return Buffer.from(buffer);
}

// Exportação em XLSX é bem mais pesada em memória/CPU que CSV por linha
// (monta o workbook inteiro antes de gerar o arquivo), então usa um teto
// mais conservador pra rodar com folga dentro do tempo de uma função
// serverless.
const LIMITE_XLSX = 50_000;

export async function GET(req: NextRequest) {
  const sp = req.nextUrl.searchParams;
  const format = sp.get("format");

  if (format === "csv" || format === "xlsx") {
    const filtros = lerFiltros(sp);
    const { linhas, truncado } = await buscarResultadosParaExport(filtros);

    if (format === "csv") {
      const aviso = truncado ? "-parcial-primeiras-200mil-linhas" : "";
      return new NextResponse(gerarCsv(linhas), {
        headers: {
          "Content-Type": "text/csv; charset=utf-8",
          "Content-Disposition": `attachment; filename=licitacoes${aviso}.csv`,
        },
      });
    }

    const linhasXlsx = linhas.slice(0, LIMITE_XLSX);
    const buffer = await gerarXlsx(linhasXlsx);
    const aviso = linhasXlsx.length < linhas.length || truncado ? "-parcial" : "";
    return new NextResponse(buffer, {
      headers: {
        "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "Content-Disposition": `attachment; filename=licitacoes${aviso}.xlsx`,
      },
    });
  }

  const filtros = {
    ...lerFiltros(sp),
    pagina: Math.max(1, parseInt(sp.get("pagina") ?? "1", 10) || 1),
    porPagina: 50,
  };
  const { linhas, total } = await buscarResultados(filtros);
  return NextResponse.json({ linhas, total });
}
