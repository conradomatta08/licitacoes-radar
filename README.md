# Radar de Licitações

Rastreia licitações públicas brasileiras via API do [PNCP](https://pncp.gov.br)
para inteligência competitiva: quem venceu, com que CNPJ, a que valor unitário
homologado e quando — com busca e exportação em CSV.

**Fora do escopo desta versão (Fase 1/MVP):** marca ofertada (o PNCP não tem
esse campo em nenhum schema estruturado — confirmado empiricamente, ver
`docs/`), ranking dos 5 primeiros colocados, integração com Compras.gov.br,
e backfill histórico além dos últimos ~4 meses. Cada resultado traz o link
direto pro edital no site do PNCP, pra conferência manual quando precisar.

## Estrutura

- `etl/` — pipeline Python que busca dados na API do PNCP e grava no Postgres.
  Roda via GitHub Actions agendado (`.github/workflows/`), sem custo.
- `web/` — dashboard em Next.js (busca, filtros, exportação CSV), hospedado
  na Vercel.

## Para colocar no ar

Veja [`docs/SETUP.md`](docs/SETUP.md) — passo a passo de criação de contas
(GitHub, Neon, Vercel), sem precisar de experiência técnica prévia.

## Arquitetura

Ver o plano técnico completo em
`C:\Users\conra\.claude\plans\humming-inventing-fern.md` (schema do banco,
endpoints usados, decisões e riscos conhecidos).
