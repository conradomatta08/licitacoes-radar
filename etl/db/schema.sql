-- Radar de Licitações — schema do banco (Fase 1 / MVP)
-- Fonte de dados: arquivos em lote (CSV) do Compras.gov.br/PNCP, hospedados
-- em repositorio.dados.gov.br (mais confiavel que a API ao vivo do PNCP,
-- ver plano). "marca" não existe em nenhum campo estruturado do PNCP
-- (confirmado no schema oficial IncluirCompraItemResultadoDTO e nos CSVs).

-- pg_trgm acelera busca por trecho (ILIKE '%...%'), usada nos filtros de
-- empresa/descrição do dashboard - um índice B-tree comum não serve pra isso.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS orgaos (
  id SERIAL PRIMARY KEY,
  cnpj VARCHAR(14) UNIQUE NOT NULL,
  razao_social TEXT,
  poder_id VARCHAR(5),
  esfera_id VARCHAR(5)
);
CREATE INDEX IF NOT EXISTS idx_orgaos_razao_social_trgm ON orgaos USING gin (razao_social gin_trgm_ops);

CREATE TABLE IF NOT EXISTS unidades_orgao (
  id SERIAL PRIMARY KEY,
  orgao_id INT NOT NULL REFERENCES orgaos(id),
  codigo_unidade VARCHAR(20) NOT NULL,
  nome_unidade TEXT,
  uf CHAR(2),
  municipio TEXT,
  codigo_ibge VARCHAR(10),
  UNIQUE (orgao_id, codigo_unidade)
);

CREATE TABLE IF NOT EXISTS licitacoes (
  id BIGSERIAL PRIMARY KEY,
  numero_controle_pncp VARCHAR(40) UNIQUE NOT NULL,
  orgao_id INT REFERENCES orgaos(id),
  unidade_id INT REFERENCES unidades_orgao(id),
  ano_compra INT,
  sequencial_compra INT,
  numero_compra VARCHAR(30),
  processo VARCHAR(50),
  modalidade_id INT,
  modalidade_nome TEXT,
  modo_disputa_nome TEXT,
  objeto_compra TEXT,
  situacao_compra_id INT,
  situacao_compra_nome TEXT,
  uf CHAR(2),
  data_publicacao_pncp DATE,
  valor_total_estimado NUMERIC(18, 2),
  valor_total_homologado NUMERIC(18, 2),
  existe_resultado BOOLEAN,
  link_pncp TEXT,
  link_sistema_origem TEXT,
  criado_em TIMESTAMP NOT NULL DEFAULT now(),
  atualizado_em TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_licitacoes_uf ON licitacoes (uf);
CREATE INDEX IF NOT EXISTS idx_licitacoes_data_pub ON licitacoes (data_publicacao_pncp);

CREATE TABLE IF NOT EXISTS itens (
  id BIGSERIAL PRIMARY KEY,
  licitacao_id BIGINT NOT NULL REFERENCES licitacoes(id),
  numero_item INT NOT NULL,
  descricao_item TEXT,
  produto TEXT,
  material_ou_servico VARCHAR(2),
  quantidade NUMERIC,
  unidade_medida TEXT,
  valor_unitario_estimado NUMERIC(18, 4),
  valor_total_estimado NUMERIC(18, 2),
  situacao_item_id INT,
  situacao_item_nome TEXT,
  tem_resultado BOOLEAN NOT NULL DEFAULT FALSE,
  criado_em TIMESTAMP NOT NULL DEFAULT now(),
  UNIQUE (licitacao_id, numero_item)
);
-- CREATE TABLE IF NOT EXISTS não adiciona coluna em tabela já existente -
-- precisa do ALTER explícito pra bases que já tinham 'itens' antes desta coluna.
ALTER TABLE itens ADD COLUMN IF NOT EXISTS produto TEXT;
CREATE INDEX IF NOT EXISTS idx_itens_produto_trgm ON itens USING gin (produto gin_trgm_ops);
-- Indexar descricao_item (texto longo, livre) em trigram custava 84MB -
-- mais que o dobro do dado em si - e quase estourou os 512MB do plano
-- gratuito do Neon. 'produto' (extraido de descricao_item, bem mais curto)
-- cobre a maioria das buscas por um custo bem menor (10MB) - a busca por
-- descrição completa segue funcionando, só sem esse índice (sequential
-- scan, mais lenta, mas aceitável pro volume atual).
DROP INDEX IF EXISTS idx_itens_descricao_trgm;

-- Classificação por correspondência aproximada (pg_trgm) contra o catálogo
-- oficial (ver tabelas catalogo_* abaixo) - não é o código usado de fato na
-- compra (o PNCP não registra isso), é o item do catálogo mais parecido com
-- o texto de 'produto'. catalogo_similaridade guarda o grau de semelhança
-- (0 a 1) usado no casamento, pra transparência/depuração.
ALTER TABLE itens ADD COLUMN IF NOT EXISTS catalogo_codigo INT;
ALTER TABLE itens ADD COLUMN IF NOT EXISTS catalogo_nome TEXT;
ALTER TABLE itens ADD COLUMN IF NOT EXISTS catalogo_similaridade REAL;

-- Núcleo do produto: o(s) vencedor(es) homologado(s) de cada item.
-- Normalmente 1 linha por item, mas em Registro de Preços pode haver mais de um
-- fornecedor homologado (ordem_classificacao_srp indica a posição).
CREATE TABLE IF NOT EXISTS resultados_item (
  id BIGSERIAL PRIMARY KEY,
  item_id BIGINT NOT NULL REFERENCES itens(id),
  sequencial_resultado INT NOT NULL,
  ni_fornecedor TEXT,
  tipo_pessoa VARCHAR(4),
  nome_razao_social TEXT,
  valor_unitario_homologado NUMERIC(18, 4),
  valor_total_homologado NUMERIC(18, 2),
  quantidade_homologada NUMERIC,
  ordem_classificacao_srp INT,
  situacao_resultado_id INT,
  situacao_resultado_nome TEXT,
  data_resultado DATE,
  criado_em TIMESTAMP NOT NULL DEFAULT now(),
  UNIQUE (item_id, sequencial_resultado)
);
CREATE INDEX IF NOT EXISTS idx_resultados_cnpj ON resultados_item (ni_fornecedor);
CREATE INDEX IF NOT EXISTS idx_resultados_nome_trgm ON resultados_item USING gin (nome_razao_social gin_trgm_ops);
DROP INDEX IF EXISTS idx_resultados_nome;

-- Catálogo oficial (CATMAT/CATSER), espelhado de dadosabertos.compras.gov.br
-- (modulo-material/modulo-servico) - tabelas de referência pequenas
-- (~20 mil e ~3 mil linhas), sincronizadas raramente por
-- etl/sync_catalogo_oficial.py (o catálogo quase não muda). Usadas só pra
-- casar com 'produto' via similaridade de texto (etl/match_catalogo.py) -
-- ver comentário em itens.catalogo_codigo.
CREATE TABLE IF NOT EXISTS catalogo_material_pdm (
  codigo_pdm INT PRIMARY KEY,
  nome_pdm TEXT NOT NULL,
  codigo_classe INT,
  nome_classe TEXT,
  codigo_grupo INT,
  nome_grupo TEXT
);
CREATE INDEX IF NOT EXISTS idx_catalogo_material_pdm_gist ON catalogo_material_pdm USING gist (nome_pdm gist_trgm_ops);

-- UF de cada CNPJ vencedor, cruzado com a base de Estabelecimentos da
-- Receita Federal (dados abertos) - usado pra avaliar vantagem logística
-- (empresa sediada perto do órgão comprador). Só guarda UF (não endereço
-- completo, não precisamos de mais que isso). Populada/atualizada por
-- etl/sync_fornecedores.py - o PNCP não traz esse dado, só o CNPJ.
CREATE TABLE IF NOT EXISTS fornecedores (
  cnpj VARCHAR(14) PRIMARY KEY,
  uf CHAR(2),
  atualizado_em TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS catalogo_servico_item (
  codigo_servico INT PRIMARY KEY,
  nome_servico TEXT NOT NULL,
  codigo_classe INT,
  nome_classe TEXT,
  codigo_grupo INT,
  nome_grupo TEXT,
  codigo_divisao INT,
  nome_divisao TEXT,
  codigo_secao INT,
  nome_secao TEXT
);
CREATE INDEX IF NOT EXISTS idx_catalogo_servico_item_gist ON catalogo_servico_item USING gist (nome_servico gist_trgm_ops);
