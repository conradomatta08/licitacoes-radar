import { notFound } from "next/navigation";
import { buscarLicitacaoDetalhe } from "../../../lib/queries";

function formatarMoeda(valor: number | null) {
  if (valor === null || valor === undefined) return "—";
  return Number(valor).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function formatarData(valor: string | null) {
  if (!valor) return "—";
  return new Date(valor).toLocaleDateString("pt-BR", { timeZone: "UTC" });
}

export default async function LicitacaoDetalhePage({ params }: { params: { id: string } }) {
  const id = parseInt(params.id, 10);
  if (Number.isNaN(id)) notFound();

  const detalhe = await buscarLicitacaoDetalhe(id);
  if (!detalhe) notFound();

  return (
    <main>
      <a href="/">&larr; Voltar à busca</a>
      <h1>{detalhe.objeto_compra}</h1>
      <p className="subtitulo">
        {detalhe.orgao_nome} · {detalhe.municipio ?? "—"}/{detalhe.uf ?? "—"} · {detalhe.modalidade_nome ?? "—"}
      </p>
      {detalhe.link_pncp && (
        <p>
          <a href={detalhe.link_pncp} target="_blank" rel="noreferrer">
            Ver edital completo no PNCP
          </a>
        </p>
      )}

      <table>
        <thead>
          <tr>
            <th>Item</th>
            <th>Descrição</th>
            <th>Vencedor</th>
            <th>CNPJ</th>
            <th>Valor unitário homologado</th>
            <th>Data do resultado</th>
          </tr>
        </thead>
        <tbody>
          {detalhe.itens.map((item) => (
            <tr key={item.id}>
              <td>{item.numero_item}</td>
              <td>{item.descricao_item}</td>
              <td>{item.vencedor_nome ?? "—"}</td>
              <td>{item.vencedor_cnpj ?? "—"}</td>
              <td>{formatarMoeda(item.valor_unitario_homologado)}</td>
              <td>{formatarData(item.data_resultado)}</td>
            </tr>
          ))}
          {detalhe.itens.length === 0 && (
            <tr>
              <td colSpan={6}>Itens ainda não carregados para esta licitação.</td>
            </tr>
          )}
        </tbody>
      </table>
    </main>
  );
}
