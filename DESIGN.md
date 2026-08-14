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
  Assimetria reconferida contra a API real em 2026-08-14: `/contratacoes/*`
  responde `400 "Tamanho de página inválido"` já em 100, enquanto
  `/contratos/atualizacao` e `/atas/atualizacao` devolvem 500 registros numa
  página só. Trocar os dois números de lugar quebra a fase 1 em silêncio,
  por isso há teste que os fixa.
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
- **Robustez**: retry 5× com backoff em 429/5xx/timeout; falha em um tipo não
  bloqueia os demais; resultado em `sync_log`; API fora do ar → app funciona
  normal com dados locais + aviso.
- **Falha parcial (1.36.0)**: `_baixar` devolve `(rótulo, registros, erro)` —
  a consulta que esgota as tentativas não derruba as irmãs. Quem chama grava
  o que veio e levanta `PncpErro` **no fim**, para que `last_sync_<tipo>` não
  avance sobre janela que nunca foi baixada. Antes disso, uma janela ruim
  entre as 78 da fase 1 jogava fora todo o resto da passada.
- **Concorrência**: uma thread de sync por vez (lock); UI nunca bloqueia —
  abre com dados locais na hora, sync roda atrás com banner de progresso.
- **Paralelismo (1.1.x)**: as três fases baixam com até 4 conexões (`_baixar`
  na 1 e 2, executor próprio na 3). Só as *requisições* vão para as threads —
  a gravação fica na conexão de quem chamou. Em paralelo o pacing de 0,5 s é
  dispensado: quem regula o ritmo passa a ser o número de conexões.
  Medido contra a API real: 4 conexões sem pacing fazem 13 consultas em 0,9 s
  sem nenhum 429, enquanto a versão sequencial com pacing levava 38 s.
  O recuo por 429 usa **janela de tempo** (`JANELA_BLOQUEIOS`), nunca contador
  acumulado: o portal oscila (502/503 e 429 em rajada, sem relação com a nossa
  taxa), e um contador que só cresce desligava o paralelismo para sempre.
  **Remedição de 2026-08-14** (madrugada): o "nenhum 429" acima não se
  sustenta mais — 13 de 60 requisições voltaram 429 numa thread só, e o
  intervalo entre elas não explicou o padrão (0,5 s deu 3/12; 1,0 s deu 5/12;
  1,5 s deu 5/12; 2,0 s e 3,0 s deram 0/12), o que confirma a rajada como
  humor do portal, não como função da nossa taxa. Nenhuma resposta trouxe
  cabeçalho `Retry-After`, então o backoff do código é sempre o de fallback.
  Na mesma noite o mesmo endpoint alternou entre responder em 0,3 s e devolver
  `500 "Erro na comunicação com o banco de dados"` depois de 60 s.
  **Consequência de desenho**: não adianta calibrar pacing contra um número
  que não é nosso — a defesa é tolerar a consulta perdida (falha parcial,
  acima) e reler a escada de recuo entre levas curtas dentro de `_baixar`,
  em vez de fixar a concorrência uma vez para a fase inteira.
- **Municípios de referência (1.3.0)**: `referencia` (0/1) e `municipio_ibge`
  em `contratacoes` e `itens`, mais a tabela `municipios_referencia`. Para
  esses municípios roda **só a fase 1**; os itens saem na fase 3 junto com os
  próprios. Tudo que representa o município — KPIs, abas do acervo, filtros,
  `descobrir_orgaos`, PCA e os relatórios oficiais — filtra `referencia=0`;
  só o banco de preços e o relatório de Pesquisa de Preços enxergam os dois.
  A blindagem é testada em `tests/test_referencia.py`, que inclusive lê o HTML
  gerado. Motivação e medições: `design/BRIEFING-precos-referencia.md`.
  O `raw` do item de referência é mantido (medido: 25,5 MB de JSON para cinco
  vizinhos) — descartá-lo economizaria pouco e quebraria o princípio de que
  o JSON bruto é a fonte da verdade. O que o município ocupa de fato em disco
  é esse JSON vezes `pncp.FATOR_DISCO` (1,78, medido): é assim que a lista de
  municípios de referência e o aviso de volume dizem o tamanho, já que
  `dbstat` não existe na build do SQLite que acompanha o Python.
- **Revisita de itens**: `data_atualizacao` da contratação muda por motivo
  cosmético e não implica item alterado — `_itens_pendentes` compara a data de
  cada item antes de pedir o resultado. Item inalterado é pulado inteiro, e
  não regravado: `_upsert_item` é INSERT OR REPLACE e apagaria o preço
  homologado se fosse regravado sem o resultado em mãos.

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
das contratações/contratos/atas (volume municipal não pede mais que isso). Nos
**itens**, `LIKE` não servia — "papel a4" não acha "PAPEL SULFITE A4" — então
entrou **FTS5** (`itens_fts`, external content sobre `itens`, sincronizada por
triggers) com prefixo obrigatório por palavra. Banco anterior à 1.1.0 reconstrói
o índice na primeira abertura.

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

## 6. UI (ui/, três arquivos)

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
- **Regras de interface travadas por teste** (`tests-e2e/interface.spec.js`,
  desde a 1.38.0). São medições sobre a tela renderizada, porque token, tema
  e composição de transparência só se encontram no navegador:
  contraste ≥ 4,5:1 nos **quatro** temas · piso de 11 px (exceção: rótulo de
  eixo dentro do SVG, 10,5 px) · todo campo com nome acessível, nunca só
  `placeholder` · cards de uma fileira com o mesmo número de linhas visíveis.
- **Verde e vermelho são afirmação, não direção.** `.up`/`.down` só valem
  onde subir *significa* melhor (economia). Para valor gasto vale `.dir`:
  a seta carrega a direção em tinta neutra. Pintar "gastamos 73% a mais" de
  verde era o programa dizendo o que o dado não diz.
- **Âmbar custa: só marca o que tem consequência.** `.aviso` (cor de alerta)
  é para o que a pessoa precisa observar — trocar de município apaga o
  acervo; o limite legal desatualizado produz alerta de fracionamento errado.
  Texto que só explica o que o card faz usa `.ajuda` (tinta neutra). Quando
  todo texto auxiliar sai em âmbar, o âmbar deixa de significar alguma coisa.
- **Ao medir a tela, esperar a transição fechar.** `body` anima `background`
  e `color` por 250 ms; `getComputedStyle` no meio disso devolve o valor
  interpolado e produz razão de contraste que na tela parada não existe.
  Mesma família de armadilha: o Chrome devolve cor em `rgb()` (0–255) **e**
  em `color(srgb …)` (0–1) — ler as duas com a mesma régua acusou 71 falhas
  onde havia 18.
- Nasceu single-file; na 1.1.0 virou `index.html` + `estilo.css` + `app.js`,
  quando o arquivo passou de 1.700 linhas. Para **por aí**: `app.js` continua
  um script clássico. Fatiar em ES modules exigiria `type="module"`, e o
  pywebview abre o index por caminho de arquivo — CORS bloqueia módulo em
  `file://` e a janela abriria em branco.

## 7. Layout do repositório

```
Licitarium/
  licitarium.py        # entry: janela + classe Api
  pncp.py              # cliente da API de consulta + motor de sync
  ui/index.html        # marcação
  ui/estilo.css        # três peles por data-theme
  ui/app.js            # lógica + ponte com o Python
  ui/municipios.json   # tabela IBGE (código, nome, UF)
  tests/               # pytest: sync com HTTP mockado, upsert, catch-up
  Licitarium.spec      # PyInstaller (onefile, windowed, ícone)
  .github/workflows/   # CI: testes em push; build do exe anexado ao release por tag
  README.md  LICENSE(MIT)  CHANGELOG.md  MANUAL.html
```

Dados do usuário em `%LOCALAPPDATA%\Licitarium\licitarium.db`
(exe pode estar em pasta sem escrita).

## 8. Fora do escopo (por ora)

Anexos/PDFs · multi-município na mesma instância · auto-update ·
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
