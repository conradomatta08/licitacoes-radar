import { NextRequest, NextResponse } from "next/server";
import { buscarResultados } from "../../../lib/queries";

// pg devolve colunas DATE como objetos Date (nao string) - String(date) direto
// produz o formato verboso do JS ("Wed Feb 21 2024 00:00:00 GMT..."), ruim
// pra abrir no Excel. Formata como YYYY-MM-DD.
function formatarDataIso(valor: unknown): string {
  if (!valor) return "";
  const data = valor instanceof Date ? valor : new Date(String(valor));
  if (Number.isNaN(data.getTime())) return "";
  return data.toISOString().slice(0, 10);
}

export async function GET(req: NextRequest) {
  const sp = req.nextUrl.searchParams;
  const filtros = {
    q: sp.get("q") ?? undefined,
    uf: sp.get("uf") ?? undefined,
    dataInicial: sp.get("dataInicial") ?? undefined,
    dataFinal: sp.get("dataFinal") ?? undefined,
    pagina: Math.max(1, parseInt(sp.get("pagina") ?? "1", 10) || 1),
    porPagina: 50,
  };

  const { linhas, total } = await buscarResultados(filtros);

  if (sp.get("format") === "csv") {
    const header = "empresa,cnpj,orgao,uf,municipio,item,valor_unitario_homologado,data_resultado,link_pncp\n";
    const corpo = linhas
      .map((l) =>
        [
          l.nome_razao_social,
          l.ni_fornecedor,
          l.orgao_nome,
          l.uf,
          l.municipio,
          l.descricao_item,
          l.valor_unitario_homologado,
          formatarDataIso(l.data_resultado),
          l.link_pncp,
        ]
          .map((v) => `"${String(v ?? "").replace(/"/g, '""')}"`)
          .join(",")
      )
      .join("\n");

    return new NextResponse(header + corpo, {
      headers: {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": "attachment; filename=licitacoes.csv",
      },
    });
  }

  return NextResponse.json({ linhas, total });
}
