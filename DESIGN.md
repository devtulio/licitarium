# Licitarium — Design (ARQUITETURA FECHADA 2026-07-29 — reservada para implementação)

> Repositório local de contratações públicas municipais, espelhando o PNCP.
> Desktop, open-source (MIT), qualquer prefeitura. Piloto: Orindiúva-SP.

## 1. Decisões fechadas

| Tema | Decisão |
|---|---|
| Nome | **Licitarium** (*licitatio* + *-arium*, "lugar que guarda licitações") |
| Escopo de dados | Contratações, Contratos, Atas de RP, PCA — só metadados + link (sem anexos) |
| Plataforma | Desktop Windows: Python + pywebview (WebView2) + SQLite, exe via PyInstaller |
| Sync | Incremental ao abrir + catch-up desde última execução; botão "Sincronizar agora" |
| Distribuição | GitHub público, MIT, release com exe; DOI Zenodo |

## 2. Fatos da API que moldam o desenho

Fonte: `https://pncp.gov.br/api/consulta` (spec OpenAPI verificada em 2026-07-29).

- **Filtro por município (`codigoMunicipioIbge`) só existe em `/v1/contratacoes/*`.**
  Contratos, atas e PCA só filtram por CNPJ do órgão.
- **`/v1/contratacoes/*` exige `codigoModalidadeContratacao`** — loop obrigatório pelas
  modalidades da Lei 14.133 (tabela de códigos embutida no código).
- Todos os 4 tipos têm endpoint `/atualizacao` (por data de atualização global) —
  sync incremental sem janela retroativa artificial.
- Paginação: contratações máx. 50/página; contratos/atas/PCA máx. 500/página.
- Janelas de data fatiadas por ano (limite de range da API); volume municipal é pequeno.

## 3. Sync em 2 fases

```
Fase 1 — CONTRATAÇÕES (chave: município)
  para cada modalidade:
    GET /v1/contratacoes/atualizacao
        ?codigoMunicipioIbge=X &dataInicial=lastSync &dataFinal=hoje
    upsert por numeroControlePNCP

Descoberta de órgãos:
  CNPJs distintos das contratações → tabela orgaos (INSERT OR IGNORE)
  (usuário pode adicionar CNPJ manualmente — ex.: câmara que nunca licitou por lá)

Fase 2 — CONTRATOS / ATAS / PCA (chave: CNPJ do órgão)
  para cada órgão ativo:
    GET /v1/contratos/atualizacao?cnpjOrgao=...
    GET /v1/atas/atualizacao?cnpj=...
    GET /v1/pca/atualizacao?cnpj=...
```

- **Estado**: `last_sync_<tipo>` em `config`; upsert idempotente → recomeço seguro após falha.
- **Bootstrap** (primeira execução): mesma máquina, janela 2021-01-01 → hoje
  (PNCP existe desde ago/2021), com barra de progresso.
- **Robustez**: retry 3× com backoff em 429/5xx/timeout; falha em um tipo não
  bloqueia os demais; resultado em `sync_log`; API fora do ar → app funciona
  normal com dados locais + aviso.
- **Concorrência**: uma thread de sync por vez (lock); UI nunca bloqueia —
  abre com dados locais na hora, sync roda atrás com banner de progresso.

## 4. Esquema SQLite

```sql
config        (chave TEXT PK, valor TEXT)          -- municipio_ibge, last_sync_*, tema…
orgaos        (cnpj TEXT PK, razao_social TEXT, ativo INT, origem TEXT)  -- descoberto|manual
contratacoes  (numero_controle TEXT PK, ano INT, sequencial INT,
               orgao_cnpj TEXT, orgao_nome TEXT, unidade TEXT,
               modalidade_id INT, modalidade_nome TEXT, situacao TEXT,
               objeto TEXT, valor_estimado REAL, valor_homologado REAL,
               data_publicacao TEXT, data_atualizacao TEXT,
               raw TEXT, sync_em TEXT)
contratos     (numero_controle TEXT PK, contratacao_controle TEXT,
               orgao_cnpj TEXT, fornecedor_ni TEXT, fornecedor_nome TEXT,
               objeto TEXT, valor_global REAL,
               vigencia_inicio TEXT, vigencia_fim TEXT,
               data_publicacao TEXT, data_atualizacao TEXT, raw TEXT, sync_em TEXT)
atas          (numero_controle TEXT PK, contratacao_controle TEXT, orgao_cnpj TEXT,
               vigencia_inicio TEXT, vigencia_fim TEXT,
               data_atualizacao TEXT, raw TEXT, sync_em TEXT)
pca_itens     (orgao_cnpj TEXT, ano INT, sequencial INT,
               categoria TEXT, descricao TEXT, valor REAL, raw TEXT,
               PRIMARY KEY (orgao_cnpj, ano, sequencial))
sync_log      (id INTEGER PK, iniciado_em TEXT, tipo TEXT,
               janela_ini TEXT, janela_fim TEXT, registros INT,
               status TEXT, erro TEXT)
```

Princípio: **`raw` (JSON completo do PNCP) é a fonte da verdade**; colunas são
projeção para filtro/listagem. Campo novo na UI = reprojetar do raw, sem re-baixar.
Índices: datas, modalidade, situação, orgao_cnpj. Busca textual: `LIKE` no objeto
(volume municipal; FTS5 só se precisar).

O banco é **cache reconstruível** — perdeu/corrompeu, re-bootstrap resolve.
Sem sistema de backup próprio (diferente da família, onde o dado é produzido localmente).

## 5. Processo e ponte Python↔UI

Um processo, sem servidor HTTP (sem waitress, porta, firewall):

```python
webview.create_window("Licitarium", "ui/index.html", js_api=Api())
```

```python
class Api:
    listar(tipo, filtros, pagina)    # SELECT paginado → JSON
    detalhe(tipo, numero_controle)   # raw completo
    sincronizar()                    # dispara thread de sync
    status_sync()
    get_config() / set_config(...)
    municipios(texto)                # autocomplete na tabela IBGE embutida
    exportar_csv(tipo, filtros)      # diálogo salvar nativo
```

Progresso do sync empurrado para a UI via `window.evaluate_js("onSyncProgress(...)")`.

## 6. UI (ui/index.html, single-file)

- **4 abas**: Contratações | Contratos | Atas | PCA. Lista paginada com filtros:
  ano, modalidade, situação, órgão, busca no objeto.
- **Detalhe**: painel com campos principais + link oficial
  `pncp.gov.br/app/editais/{cnpj}/{ano}/{sequencial}` (abre no navegador padrão).
- **Sync**: banner de status, botão "Sincronizar agora", histórico (sync_log).
- **Wizard de primeira execução**: UF → município (autocomplete, tabela IBGE
  embutida `ui/municipios.json`, ~5570 municípios) → "baixar histórico desde 2021?".
- **Config**: município (trocar = confirmação + re-bootstrap), órgãos (CNPJs), tema.
- Acessibilidade WCAG 2.1 AA (padrão da casa). Sem login — desktop single-user,
  dado 100% público.

## 7. Layout do repositório

```
Licitarium/
  licitarium.py        # entry: janela + classe Api
  pncp.py              # cliente da API de consulta + motor de sync
  ui/index.html        # UI completa (CSS/JS inline)
  ui/municipios.json   # tabela IBGE (código, nome, UF)
  tests/               # pytest: sync com HTTP mockado, upsert, catch-up
  Licitarium.spec      # PyInstaller (onefile, windowed, ícone)
  .github/workflows/   # CI: testes em push; build do exe anexado ao release por tag
  README.md  LICENSE(MIT)  CHANGELOG.md  MANUAL.html
```

Dados do usuário em `%LOCALAPPDATA%\Licitarium\licitarium.db`
(exe pode estar em pasta sem escrita).

## 8. Fora do escopo (por ora)

Anexos/PDFs · FTS5 · multi-município na mesma instância · auto-update ·
assinatura de código (SmartScreen documentado no README) · cruzamento com SGCD/SGCA.

## 9. Decisões finais (2026-07-29)

1. **Dependências**: só stdlib (`urllib.request` + helper com retry/backoff). Única dep externa: `pywebview`.
2. **Export CSV**: na v1.
3. **PCA**: fica para v1.1 (schema `pca_itens` já previsto; v1 lança com contratações + contratos + atas).
4. **Identidade visual**: própria, independente da família — ver §10.

## 10. Identidade visual (fechada 2026-07-29)

> Documentação completa, incluindo as notas históricas de cada escolha
> (hasta pública, tabula ansata, signum, exergo, interpontos, V clássico):
> **`design/IDENTIDADE.md`** — leitura obrigatória antes de mexer na marca.

- **3 temas selecionáveis** nas configurações, todos via CSS custom properties +
  `data-theme` no `<html>` (persistido em `config`):
  - **Portal** (claro, azul institucional #1351b4) — **padrão**
  - **Pergaminho** (claro, papel #f5efe2 / tinta #2b2115 / selo #8b2e2e / dourado #b08d3e, serifas)
  - **Observatório** (escuro, #10151c / âmbar #f0a836 / verde #2dd4a7)
- **Marca constante nos 3 temas**: wordmark **LICITARIVM** (Georgia/serif,
  letter-spacing largo, "V" romano na cor de destaque do tema). Subtítulo com
  município configurado. Selo circular como ícone do app (a desenhar para o .ico).
- **KPIs na tela inicial** (contratações, R$ homologado no ano, contratos vigentes)
  em todos os temas — herança da direção Observatório.
- Componentes tematizáveis por token: `--bg --surface --surface2 --text --muted
  --border --accent --accent-fg --ok --warn --radius --pill --shadow`.
  Pergaminho diferencia por tokens extras (serifa em valores/KPIs, filete duplo
  dourado no header) via `[data-theme="pergaminho"]` — exceções pontuais, não tema paralelo.
- **Selo (fechado, v5)**: par **T1 + T3** com gramática romana autêntica
  (capitais, interpontos, hasta pública — *sub hasta vendere* —, tabula ansata, exergo):
  - **Ícone**: tabula ansata vermelha com L (`design/icone-t1.svg`); `.ico` multi-frame
    gerado por `design/gerar_ico.py` (Pillow, 1024px→LANCZOS, maior→menor, transparente):
    frames 256–32 com arte completa (Georgia bold), 24/16 com frame dedicado
    (`design/icone-t1-16.svg` — sem filete, L branco 38, SHARPEN pós-redução).
  - **Marca de apresentação**: estandarte/signum (`design/estandarte-t3.svg`) — tabula
    com LICITARIVM / SVB·HASTA·PVBLICA montada na hasta, MMXXVI no exergo (ano de
    fundação, fixo). Textos com `textLength` — não estouram a tabula em fonte alguma.
    Usos: wizard, tela Sobre, README, splash.
- **Telas prototipadas** (`design/telas-v1.html`, temas + navegação testados):
  wizard de primeira execução (estandarte + UF/município + opção de histórico),
  detalhe de contratação (meta-grid, itens, Ver no PNCP, Exportar CSV),
  configurações (cards de tema, município com aviso de re-bootstrap, órgãos
  monitorados com origem descoberto/manual, Sobre).
- Histórico da exploração: `design/moodboard-v1.html` (direções),
  `design/prototipo-v2.html` (lista principal + temas), `design/selo-v1..v5.html` (selo).
