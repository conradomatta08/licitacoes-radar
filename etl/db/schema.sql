-- Radar de Licitações — schema do banco (Fase 1 / MVP)
-- Fonte de dados: arquivos em lote (CSV) do Compras.gov.br/PNCP, hospedados
-- em repositorio.dados.gov.br (mais confiavel que a API ao vivo do PNCP,
-- ver plano). "marca" não existe em nenhum campo estruturado do PNCP
-- (confirmado no schema oficial IncluirCompraItemResultadoDTO e nos CSVs).

CREATE TABLE IF NOT EXISTS orgaos (
  id SERIAL PRIMARY KEY,
  cnpj VARCHAR(14) UNIQUE NOT NULL,
  razao_social TEXT,
  poder_id VARCHAR(5),
  esfera_id VARCHAR(5)
);

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
  raw_payload JSONB,
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
  material_ou_servico VARCHAR(2),
  quantidade NUMERIC,
  unidade_medida TEXT,
  valor_unitario_estimado NUMERIC(18, 4),
  valor_total_estimado NUMERIC(18, 2),
  situacao_item_id INT,
  situacao_item_nome TEXT,
  tem_resultado BOOLEAN NOT NULL DEFAULT FALSE,
  raw_payload JSONB,
  criado_em TIMESTAMP NOT NULL DEFAULT now(),
  UNIQUE (licitacao_id, numero_item)
);

-- Núcleo do produto: o(s) vencedor(es) homologado(s) de cada item.
-- Normalmente 1 linha por item, mas em Registro de Preços pode haver mais de um
-- fornecedor homologado (ordem_classificacao_srp indica a posição).
CREATE TABLE IF NOT EXISTS resultados_item (
  id BIGSERIAL PRIMARY KEY,
  item_id BIGINT NOT NULL REFERENCES itens(id),
  sequencial_resultado INT NOT NULL,
  ni_fornecedor VARCHAR(20),
  tipo_pessoa VARCHAR(4),
  nome_razao_social TEXT,
  valor_unitario_homologado NUMERIC(18, 4),
  valor_total_homologado NUMERIC(18, 2),
  quantidade_homologada NUMERIC,
  ordem_classificacao_srp INT,
  situacao_resultado_id INT,
  situacao_resultado_nome TEXT,
  data_resultado DATE,
  raw_payload JSONB,
  criado_em TIMESTAMP NOT NULL DEFAULT now(),
  UNIQUE (item_id, sequencial_resultado)
);
CREATE INDEX IF NOT EXISTS idx_resultados_cnpj ON resultados_item (ni_fornecedor);
CREATE INDEX IF NOT EXISTS idx_resultados_nome ON resultados_item USING gin (to_tsvector('simple', coalesce(nome_razao_social, '')));
