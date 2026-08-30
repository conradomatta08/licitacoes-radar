import { buscarResultados, Ordenacao } from "../lib/queries";

const POR_PAGINA = 50;

function formatarMoeda(valor: number | null) {
  if (valor === null || valor === undefined) return "—";
  return Number(valor).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function formatarData(valor: string | null) {
  if (!valor) return "—";
  return new Date(valor).toLocaleDateString("pt-BR", { timeZone: "UTC" });
}

// Paginação com janela deslizante: sempre mostra a primeira e a última
// página, mais uma janela ao redor da página atual, com "..." nos vãos.
// Evita renderizar milhares de números quando há muitas páginas.
function gerarPaginas(atual: number, total: number, janela = 2): (number | "...")[] {
  const paginas = new Set<number>([1, total]);
  for (let i = atual - janela; i <= atual + janela; i++) {
    if (i >= 1 && i <= total) paginas.add(i);
  }
  const ordenadas = Array.from(paginas).sort((a, b) => a - b);

  const resultado: (number | "...")[] = [];
  let anterior: number | null = null;
  for (const p of ordenadas) {
    if (anterior !== null && p - anterior > 1) resultado.push("...");
    resultado.push(p);
    anterior = p;
  }
  return resultado;
}

export default async function Home({
  searchParams,
}: {
  searchParams: { [key: string]: string | undefined };
}) {
  const pagina = Math.max(1, parseInt(searchParams.pagina ?? "1", 10) || 1);
  const filtros = {
    q: searchParams.q,
    descricao: searchParams.descricao,
    produto: searchParams.produto,
    uf: searchParams.uf,
    portal: searchParams.portal,
    dataInicial: searchParams.dataInicial,
    dataFinal: searchParams.dataFinal,
    valorMinimo: searchParams.valorMinimo,
    valorMaximo: searchParams.valorMaximo,
    ordenar: (searchParams.ordenar as Ordenacao | undefined) ?? "data",
    pagina,
    porPagina: POR_PAGINA,
  };

  const { linhas, total } = await buscarResultados(filtros);
  const totalPaginas = Math.max(1, Math.ceil(total / POR_PAGINA));

  const paramsBase = new URLSearchParams();
  if (searchParams.q) paramsBase.set("q", searchParams.q);
  if (searchParams.descricao) paramsBase.set("descricao", searchParams.descricao);
  if (searchParams.produto) paramsBase.set("produto", searchParams.produto);
  if (searchParams.uf) paramsBase.set("uf", searchParams.uf);
  if (searchParams.portal) paramsBase.set("portal", searchParams.portal);
  if (searchParams.dataInicial) paramsBase.set("dataInicial", searchParams.dataInicial);
  if (searchParams.dataFinal) paramsBase.set("dataFinal", searchParams.dataFinal);
  if (searchParams.valorMinimo) paramsBase.set("valorMinimo", searchParams.valorMinimo);
  if (searchParams.valorMaximo) paramsBase.set("valorMaximo", searchParams.valorMaximo);
  if (searchParams.ordenar) paramsBase.set("ordenar", searchParams.ordenar);
  const baseQs = paramsBase.toString();

  const csvHref = `/api/licitacoes?${baseQs}${baseQs ? "&" : ""}format=csv`;
  const xlsxHref = `/api/licitacoes?${baseQs}${baseQs ? "&" : ""}format=xlsx`;
  const hrefPagina = (n: number) => `/?${baseQs}${baseQs ? "&" : ""}pagina=${n}`;
  const paginasVisiveis = gerarPaginas(pagina, totalPaginas);

  return (
    <main>
      <h1>Análise de Mercado - À Frente Soluções</h1>
      <p className="subtitulo">Vencedores homologados no site PNCP.</p>

      <form className="filtros" method="get">
        <input type="text" name="q" placeholder="Empresa ou CNPJ" defaultValue={searchParams.q ?? ""} />
        <input
          type="text"
          name="descricao"
          placeholder="Descrição do produto/serviço"
          defaultValue={searchParams.descricao ?? ""}
        />
        <input
          type="text"
          name="produto"
          placeholder="Produto (ex: notebook, nobreak)"
          defaultValue={searchParams.produto ?? ""}
        />
        <input type="text" name="uf" placeholder="UF" maxLength={2} defaultValue={searchParams.uf ?? ""} />
        <input type="text" name="portal" placeholder="Portal" defaultValue={searchParams.portal ?? ""} />
        <input type="date" name="dataInicial" defaultValue={searchParams.dataInicial ?? ""} />
        <input type="date" name="dataFinal" defaultValue={searchParams.dataFinal ?? ""} />
        <input
          type="number"
          name="valorMinimo"
          placeholder="Valor mínimo (R$)"
          step="0.01"
          min={0}
          defaultValue={searchParams.valorMinimo ?? ""}
        />
        <input
          type="number"
          name="valorMaximo"
          placeholder="Valor máximo (R$)"
          step="0.01"
          min={0}
          defaultValue={searchParams.valorMaximo ?? ""}
        />
        <select name="ordenar" defaultValue={searchParams.ordenar ?? "data"}>
          <option value="data">Mais recente</option>
          <option value="valor_desc">Maior valor primeiro</option>
          <option value="valor_asc">Menor valor primeiro</option>
        </select>
        <button type="submit">Buscar</button>
      </form>

      <div className="resumo">
        <span>{total.toLocaleString("pt-BR")} resultados</span>
        <a href={csvHref}>Exportar tudo (CSV)</a>
        <a href={xlsxHref}>Exportar tudo (XLSX, até 50 mil linhas)</a>
      </div>

      <table>
        <thead>
          <tr>
            <th>Empresa vencedora</th>
            <th>CNPJ</th>
            <th>Órgão</th>
            <th>UF</th>
            <th>Portal</th>
            <th>Produto</th>
            <th>Descrição</th>
            <th>Valor unitário homologado</th>
            <th>Data de divulgação no PNCP</th>
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
              <td>{l.portal ?? "Não encontrado"}</td>
              <td>{l.produto ?? "—"}</td>
              <td>{l.descricao_item}</td>
              <td>{formatarMoeda(l.valor_unitario_homologado)}</td>
              <td>{formatarData(l.data_publicacao_pncp)}</td>
              <td>
                <a href={l.link_pncp} target="_blank" rel="noreferrer">
                  Ver no PNCP
                </a>
              </td>
            </tr>
          ))}
          {linhas.length === 0 && (
            <tr>
              <td colSpan={10}>Nenhum resultado encontrado para esses filtros.</td>
            </tr>
          )}
        </tbody>
      </table>

      <div className="paginacao">
        {pagina > 1 && <a href={hrefPagina(pagina - 1)}>&larr; Anterior</a>}
        {paginasVisiveis.map((p, idx) =>
          p === "..." ? (
            <span key={`reticencias-${idx}`} className="reticencias">
              …
            </span>
          ) : (
            <a key={p} href={hrefPagina(p)} className={p === pagina ? "pagina-atual" : ""}>
              {p}
            </a>
          )
        )}
        {pagina < totalPaginas && <a href={hrefPagina(pagina + 1)}>Próxima &rarr;</a>}

        <form className="ir-para-pagina" method="get">
          {searchParams.q && <input type="hidden" name="q" value={searchParams.q} />}
          {searchParams.descricao && <input type="hidden" name="descricao" value={searchParams.descricao} />}
          {searchParams.produto && <input type="hidden" name="produto" value={searchParams.produto} />}
          {searchParams.uf && <input type="hidden" name="uf" value={searchParams.uf} />}
          {searchParams.portal && <input type="hidden" name="portal" value={searchParams.portal} />}
          {searchParams.dataInicial && <input type="hidden" name="dataInicial" value={searchParams.dataInicial} />}
          {searchParams.dataFinal && <input type="hidden" name="dataFinal" value={searchParams.dataFinal} />}
          {searchParams.valorMinimo && <input type="hidden" name="valorMinimo" value={searchParams.valorMinimo} />}
          {searchParams.valorMaximo && <input type="hidden" name="valorMaximo" value={searchParams.valorMaximo} />}
          {searchParams.ordenar && <input type="hidden" name="ordenar" value={searchParams.ordenar} />}
          <label>
            Ir para página
            <input type="number" name="pagina" min={1} max={totalPaginas} defaultValue={pagina} />
          </label>
          <button type="submit">Ir</button>
        </form>
      </div>
    </main>
  );
}
