# Radar de Licitações

Rastreia licitações públicas brasileiras (dados do PNCP) para inteligência
competitiva: quem venceu, com que CNPJ, a que valor unitário homologado e
quando — com busca e exportação em CSV.

**Fonte de dados**: arquivos CSV em lote publicados diariamente pelo
Compras.gov.br em `repositorio.dados.gov.br` — não a API ao vivo do PNCP,
que se mostrou instável demais pra depender dela em produção (ver
`docs/` e o plano técnico). Esses arquivos são o canal oficial pensado
justamente para consumo automatizado.

**Fora do escopo desta versão (Fase 1/MVP):** marca ofertada (o PNCP não tem
esse campo em nenhum schema estruturado — confirmado empiricamente), ranking
dos 5 primeiros colocados, integração com Compras.gov.br além dos arquivos
em lote. Cada resultado traz o link direto pro edital no site do PNCP, pra
conferência manual quando precisar.

## Estrutura

- `etl/` — pipeline Python que baixa os CSVs em lote e grava no Postgres.
  Roda via GitHub Actions agendado (`.github/workflows/ingest-incremental.yml`,
  a cada 6h) e um backfill manual (`backfill.yml`), sem custo.
- `web/` — dashboard em Next.js (busca, filtros, exportação CSV), hospedado
  na Vercel.

## Para colocar no ar

Veja [`docs/SETUP.md`](docs/SETUP.md) — passo a passo de criação de contas
(GitHub, Neon, Vercel), sem precisar de experiência técnica prévia.

## Arquitetura

Ver o plano técnico completo em
`C:\Users\conra\.claude\plans\humming-inventing-fern.md` (schema do banco,
endpoints usados, decisões e riscos conhecidos).
