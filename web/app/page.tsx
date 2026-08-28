import { buscarResultados } from "../lib/queries";

const POR_PAGINA = 50;

function formatarMoeda(valor: number | null) {
  if (valor === null || valor === undefined) return "—";
  return Number(valor).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function formatarData(valor: string | null) {
  if (!valor) return "—";
  return new Date(valor).toLocaleDateString("pt-BR", { timeZone: "UTC" });
}

export default async function Home({
  searchParams,
}: {
  searchParams: { [key: string]: string | undefined };
}) {
  const pagina = Math.max(1, parseInt(searchParams.pagina ?? "1", 10) || 1);
  const filtros = {
    q: searchParams.q,
    uf: searchParams.uf,
    dataInicial: searchParams.dataInicial,
    dataFinal: searchParams.dataFinal,
    pagina,
    porPagina: POR_PAGINA,
  };

  const { linhas, total } = await buscarResultados(filtros);
  const totalPaginas = Math.max(1, Math.ceil(total / POR_PAGINA));

  const paramsBase = new URLSearchParams();
  if (searchParams.q) paramsBase.set("q", searchParams.q);
  if (searchParams.uf) paramsBase.set("uf", searchParams.uf);
  if (searchParams.dataInicial) paramsBase.set("dataInicial", searchParams.dataInicial);
  if (searchParams.dataFinal) paramsBase.set("dataFinal", searchParams.dataFinal);
  const baseQs = paramsBase.toString();

  const csvHref = `/api/licitacoes?${baseQs}${baseQs ? "&" : ""}pagina=${pagina}&format=csv`;
  const prevHref = `/?${baseQs}${baseQs ? "&" : ""}pagina=${pagina - 1}`;
  const nextHref = `/?${baseQs}${baseQs ? "&" : ""}pagina=${pagina + 1}`;

  return (
    <main>
      <h1>Radar de Licitações</h1>
      <p className="subtitulo">
        Vencedores homologados no PNCP — CNPJ, valor unitário e data. Sem dados de marca (o PNCP não
        registra esse campo estruturado); use o link para o edital quando precisar conferir.
      </p>

      <form className="filtros" method="get">
        <input type="text" name="q" placeholder="Empresa ou CNPJ" defaultValue={searchParams.q ?? ""} />
        <input type="text" name="uf" placeholder="UF" maxLength={2} defaultValue={searchParams.uf ?? ""} />
        <input type="date" name="dataInicial" defaultValue={searchParams.dataInicial ?? ""} />
        <input type="date" name="dataFinal" defaultValue={searchParams.dataFinal ?? ""} />
        <button type="submit">Buscar</button>
      </form>

      <div className="resumo">
        <span>{total.toLocaleString("pt-BR")} resultados</span>
        <a href={csvHref}>Exportar CSV (página atual)</a>
      </div>

      <table>
        <thead>
          <tr>
            <th>Empresa vencedora</th>
            <th>CNPJ</th>
            <th>Órgão</th>
            <th>UF</th>
            <th>Item</th>
            <th>Valor unitário homologado</th>
            <th>Data do resultado</th>
            <th>Licitação</th>
          </tr>
        </thead>
        <tbody>
          {linhas.map((l) => (
            <tr key={l.resultado_id}>
              <td>{l.nome_razao_social}</td>
              <td>{l.ni_fornecedor}</td>
              <td>{l.orgao_nome}</td>
              <td>{l.uf}</td>
              <td>{l.descricao_item}</td>
              <td>{formatarMoeda(l.valor_unitario_homologado)}</td>
              <td>{formatarData(l.data_resultado)}</td>
              <td>
                <a href={`/licitacao/${l.licitacao_id}`}>Todos os itens</a>
                {" · "}
                <a href={l.link_pncp} target="_blank" rel="noreferrer">
                  PNCP
                </a>
              </td>
            </tr>
          ))}
          {linhas.length === 0 && (
            <tr>
              <td colSpan={8}>Nenhum resultado encontrado para esses filtros.</td>
            </tr>
          )}
        </tbody>
      </table>

      <div className="paginacao">
        {pagina > 1 && <a href={prevHref}>&larr; Anterior</a>}
        <span>
          Página {pagina} de {totalPaginas}
        </span>
        {pagina < totalPaginas && <a href={nextHref}>Próxima &rarr;</a>}
      </div>
    </main>
  );
}
