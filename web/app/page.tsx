import { buscarResultados, Ordenacao } from "../lib/queries";
import { sair } from "./login/actions";

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
    tipo: searchParams.tipo,
    fabricante: searchParams.fabricante,
    ufFornecedor: searchParams.ufFornecedor,
    ufOrgao: searchParams.ufOrgao,
    portal: searchParams.portal,
    dataInicial: searchParams.dataInicial,
    dataFinal: searchParams.dataFinal,
    valorMinimo: searchParams.valorMinimo,
    valorMaximo: searchParams.valorMaximo,
    ordenar: (searchParams.ordenar as Ordenacao | undefined) ?? "valor_desc",
    pagina,
    porPagina: POR_PAGINA,
  };

  const { linhas, total } = await buscarResultados(filtros);
  const totalPaginas = Math.max(1, Math.ceil(total / POR_PAGINA));

  const paramsBase = new URLSearchParams();
  if (searchParams.q) paramsBase.set("q", searchParams.q);
  if (searchParams.descricao) paramsBase.set("descricao", searchParams.descricao);
  if (searchParams.produto) paramsBase.set("produto", searchParams.produto);
  if (searchParams.tipo) paramsBase.set("tipo", searchParams.tipo);
  if (searchParams.fabricante) paramsBase.set("fabricante", searchParams.fabricante);
  if (searchParams.ufFornecedor) paramsBase.set("ufFornecedor", searchParams.ufFornecedor);
  if (searchParams.ufOrgao) paramsBase.set("ufOrgao", searchParams.ufOrgao);
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
  const filtrosAtivos = Object.keys(searchParams).filter(
    (k) => !["pagina"].includes(k) && searchParams[k]
  ).length;

  return (
    <main>
      <header className="topo">
        <form action={sair} className="sair-form">
          <button type="submit" className="link-sair">Sair</button>
        </form>
        <h1>Análise de Mercado</h1>
        <p className="marca">À Frente Soluções</p>
        <p className="subtitulo">Vencedores homologados no site PNCP.</p>
      </header>

      <form className="painel-filtros" method="get">
        <div className="grade-filtros">
          <div className="campo">
            <label htmlFor="q">Empresa ou CNPJ</label>
            <input id="q" type="text" name="q" placeholder="Nome ou CNPJ" defaultValue={searchParams.q ?? ""} />
          </div>
          <div className="campo">
            <label htmlFor="descricao">Descrição</label>
            <input
              id="descricao"
              type="text"
              name="descricao"
              placeholder="Trecho da descrição do item"
              defaultValue={searchParams.descricao ?? ""}
            />
          </div>
          <div className="campo">
            <label htmlFor="produto">Produto/Serviço</label>
            <input
              id="produto"
              type="text"
              name="produto"
              placeholder="Ex: notebook, nobreak"
              defaultValue={searchParams.produto ?? ""}
            />
          </div>
          <div className="campo">
            <label htmlFor="tipo">Tipo</label>
            <select id="tipo" name="tipo" defaultValue={searchParams.tipo ?? ""}>
              <option value="">Material e serviço</option>
              <option value="M">Material</option>
              <option value="S">Serviço</option>
            </select>
          </div>
          <div className="campo">
            <label htmlFor="fabricante">Fabricante</label>
            <select id="fabricante" name="fabricante" defaultValue={searchParams.fabricante ?? ""}>
              <option value="">Todos</option>
              <option value="sim">Só fabricantes</option>
              <option value="nao">Só não fabricantes</option>
            </select>
          </div>
          <div className="campo campo-uf">
            <label htmlFor="ufFornecedor">UF Fornecedor</label>
            <input
              id="ufFornecedor"
              type="text"
              name="ufFornecedor"
              placeholder="UF"
              maxLength={2}
              defaultValue={searchParams.ufFornecedor ?? ""}
            />
          </div>
          <div className="campo campo-uf">
            <label htmlFor="ufOrgao">UF Órgão</label>
            <input
              id="ufOrgao"
              type="text"
              name="ufOrgao"
              placeholder="UF"
              maxLength={2}
              defaultValue={searchParams.ufOrgao ?? ""}
            />
          </div>
          <div className="campo">
            <label htmlFor="portal">Portal</label>
            <input id="portal" type="text" name="portal" placeholder="Ex: gov.br" defaultValue={searchParams.portal ?? ""} />
          </div>
          <div className="campo">
            <label htmlFor="ordenar">Ordenar por</label>
            <select id="ordenar" name="ordenar" defaultValue={searchParams.ordenar ?? "valor_desc"}>
              <option value="valor_desc">Maior valor primeiro</option>
              <option value="valor_asc">Menor valor primeiro</option>
            </select>
          </div>

          <div className="campo">
            <label htmlFor="dataInicial">Data inicial</label>
            <input id="dataInicial" type="date" name="dataInicial" defaultValue={searchParams.dataInicial ?? ""} />
          </div>
          <div className="campo">
            <label htmlFor="dataFinal">Data final</label>
            <input id="dataFinal" type="date" name="dataFinal" defaultValue={searchParams.dataFinal ?? ""} />
          </div>
          <div className="campo">
            <label htmlFor="valorMinimo">Valor mínimo (R$)</label>
            <input
              id="valorMinimo"
              type="number"
              name="valorMinimo"
              placeholder="0,00"
              step="0.01"
              min={0}
              defaultValue={searchParams.valorMinimo ?? ""}
            />
          </div>
          <div className="campo">
            <label htmlFor="valorMaximo">Valor máximo (R$)</label>
            <input
              id="valorMaximo"
              type="number"
              name="valorMaximo"
              placeholder="0,00"
              step="0.01"
              min={0}
              defaultValue={searchParams.valorMaximo ?? ""}
            />
          </div>
        </div>
        <div className="acoes-filtros">
          {filtrosAtivos > 0 && <a href="/" className="limpar-filtros">Limpar filtros</a>}
          <button type="submit">Buscar</button>
        </div>
      </form>

      <div className="resumo">
        <span className="contagem">{total.toLocaleString("pt-BR")} resultados</span>
        <div className="exportar">
          <a href={csvHref}>⬇ CSV</a>
          <a href={xlsxHref}>⬇ XLSX (até 50 mil linhas)</a>
        </div>
      </div>

      <div className="table-wrapper">
        <table>
          <colgroup>
            <col style={{ width: "11%" }} />
            <col style={{ width: "8%" }} />
            <col style={{ width: "5%" }} />
            <col style={{ width: "5%" }} />
            <col style={{ width: "8%" }} />
            <col style={{ width: "5%" }} />
            <col style={{ width: "8%" }} />
            <col style={{ width: "8%" }} />
            <col style={{ width: "4%" }} />
            <col style={{ width: "9%" }} />
            <col style={{ width: "4%" }} />
            <col style={{ width: "6%" }} />
            <col style={{ width: "8%" }} />
            <col style={{ width: "6%" }} />
            <col style={{ width: "5%" }} />
          </colgroup>
          <thead>
            <tr>
              <th>Empresa vencedora</th>
              <th>CNPJ</th>
              <th>UF Fornecedor</th>
              <th>Fabricante</th>
              <th>Órgão</th>
              <th>UF Órgão</th>
              <th>Portal</th>
              <th>Produto/Serviço</th>
              <th>Tipo</th>
              <th>CATMAT/CATSER</th>
              <th>Item</th>
              <th>Descrição</th>
              <th>Valor homologado</th>
              <th>Divulgação PNCP</th>
              <th>Edital</th>
            </tr>
          </thead>
          <tbody>
            {linhas.map((l) => (
              <tr key={l.resultado_id}>
                <td title={l.nome_razao_social}>{l.nome_razao_social}</td>
                <td className="col-mono">{l.ni_fornecedor}</td>
                <td>
                  {l.uf_fornecedor ? <span className="badge">{l.uf_fornecedor}</span> : "—"}
                </td>
                <td>{l.eh_fabricante === true ? "Sim" : l.eh_fabricante === false ? "Não" : "—"}</td>
                <td title={l.orgao_nome}>{l.orgao_nome}</td>
                <td>
                  <span className="badge">{l.uf}</span>
                </td>
                <td>{l.portal ?? "Não encontrado"}</td>
                <td title={l.produto ?? undefined}>{l.produto ?? "—"}</td>
                <td>{l.material_ou_servico === "M" ? "Material" : l.material_ou_servico === "S" ? "Serviço" : "—"}</td>
                <td title={l.catalogo_nome ?? undefined}>{l.catalogo_codigo ?? "—"}</td>
                <td className="col-mono">{l.numero_item}</td>
                <td title={l.descricao_item}>{l.descricao_item}</td>
                <td className="col-mono">{formatarMoeda(l.valor_unitario_homologado)}</td>
                <td>{formatarData(l.data_publicacao_pncp)}</td>
                <td>
                  <a href={l.link_pncp} target="_blank" rel="noreferrer" title="Ver no PNCP">
                    PNCP ↗
                  </a>
                </td>
              </tr>
            ))}
            {linhas.length === 0 && (
              <tr>
                <td colSpan={15}>Nenhum resultado encontrado para esses filtros.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

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
          {searchParams.tipo && <input type="hidden" name="tipo" value={searchParams.tipo} />}
          {searchParams.fabricante && <input type="hidden" name="fabricante" value={searchParams.fabricante} />}
          {searchParams.ufFornecedor && <input type="hidden" name="ufFornecedor" value={searchParams.ufFornecedor} />}
          {searchParams.ufOrgao && <input type="hidden" name="ufOrgao" value={searchParams.ufOrgao} />}
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
