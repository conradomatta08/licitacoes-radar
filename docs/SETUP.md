# Passo a passo para colocar o Radar de Licitações no ar

Este guia assume que você não tem nenhuma conta ainda. São 4 contas gratuitas
e leva uns 20-30 minutos. Siga na ordem.

## 1. GitHub (guarda o código)

1. Acesse `github.com/signup` e crie uma conta gratuita.
2. Crie um repositório novo, público, chamado `licitacoes-radar` (botão verde
   "New" na página inicial do GitHub).
3. Suba o código deste projeto pra esse repositório (peça ajuda pra fazer isso
   na primeira vez — é um `git push`).

## 2. Neon (o banco de dados)

1. Acesse `neon.tech` e clique em **"Sign up with GitHub"** (assim você não
   precisa criar mais uma senha).
2. Crie um projeto novo. Pode aceitar os valores padrão (nome, região).
3. No painel do projeto, procure **"Connection Details"** / **"Connection
   string"**. Copie o valor — é algo como
   `postgresql://usuario:senha@ep-exemplo.neon.tech/neondb?sslmode=require`.
   Isso é o `DATABASE_URL` que vamos usar nos próximos passos.

## 3. Configurar o GitHub para rodar a coleta de dados sozinho

1. No repositório `licitacoes-radar` no GitHub, vá em **Settings → Secrets and
   variables → Actions**.
2. Clique em **"New repository secret"**.
   - Nome: `DATABASE_URL`
   - Valor: cole a connection string do Neon (passo 2.3)
3. Salve.
4. Vá na aba **Actions** do repositório. Você vai ver dois workflows:
   "Ingestão incremental (PNCP)" (já programado pra rodar sozinho a cada 6h)
   e "Backfill histórico (Compras.gov.br)" (só manual).
5. Pra popular o banco pela primeira vez com o histórico, clique em
   **"Backfill histórico (Compras.gov.br)" → "Run workflow" → "Run
   workflow"** (botão verde). Leva só alguns minutos — bem mais rápido que
   uma coleta ao vivo, porque baixa um arquivo pronto em vez de consultar
   licitação por licitação.
6. Depois disso, a "Ingestão incremental" já mantém tudo atualizado sozinha.

## 4. Vercel (o site/dashboard)

1. Acesse `vercel.com` e clique em **"Sign up with GitHub"**.
2. Clique em **"Add New… → Project"** e escolha o repositório
   `licitacoes-radar`.
3. Em **"Root Directory"**, clique em "Edit" e selecione a pasta `web`
   (importante — o projeto Next.js fica dentro dela, não na raiz).
4. Em **"Environment Variables"**, adicione:
   - Nome: `DATABASE_URL`
   - Valor: a mesma connection string do Neon (passo 2.3)
   - Nome: `AUTH_SECRET`
   - Valor: uma string aleatória longa, só pra essa variável (gere uma em
     [passwordsgenerator.net](https://passwordsgenerator.net) ou rode
     `openssl rand -hex 32` no terminal) — nunca reaproveite em outro lugar.
   - Nome: `AUTH_USERS`
   - Valor: uma pessoa por par `usuario:senha`, separados por vírgula, ex:
     `maria:S3nh4Forte!,joao:Outr4Senha#`. Só quem estiver aqui consegue
     entrar no dashboard.
5. Clique em **"Deploy"**. Em 1-2 minutos a Vercel te dá um link
   (algo como `licitacoes-radar.vercel.app`) — esse é o endereço do seu
   dashboard. Ele vai pedir usuário e senha (uma das combinações que você
   colocou em `AUTH_USERS`) antes de mostrar qualquer dado.

### Adicionando/removendo uma pessoa depois

Vá em **Settings → Environment Variables** no projeto da Vercel, edite o
valor de `AUTH_USERS` (adicione ou remova o par `usuario:senha` da pessoa) e
clique em **"Redeploy"** no último deployment — sem isso a mudança não
entra em vigor. Trocar a senha de alguém funciona do mesmo jeito.

## Pronto

A partir daqui:
- O GitHub Actions vai manter o banco atualizado sozinho, sem você precisar
  fazer nada.
- Toda vez que o banco for atualizado, o dashboard na Vercel já reflete os
  dados novos automaticamente (ele consulta o banco a cada visita).
- Se quiser acompanhar se a coleta está rodando sem erro, volte na aba
  **Actions** do GitHub de vez em quando e veja se as últimas execuções
  aparecem com um ✔️ verde.

## Rodando localmente (opcional, pra testar antes de publicar)

Se quiser rodar no seu computador antes de publicar:

```bash
# Pipeline de coleta (precisa de Python 3.12+)
cd etl
pip install -r requirements.txt
set DATABASE_URL=postgresql://... # (no Windows PowerShell: $env:DATABASE_URL="...")
python run_ingest.py
```

```bash
# Dashboard (precisa de Node.js 20+)
cd web
npm install
echo DATABASE_URL=postgresql://... > .env.local
echo AUTH_SECRET=qualquer-string-aleatoria-para-teste-local >> .env.local
echo AUTH_USERS=teste:teste123 >> .env.local
npm run dev
# abra http://localhost:3000 e entre com usuario "teste" / senha "teste123"
```
