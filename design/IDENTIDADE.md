# Licitarium — Identidade Visual e Notas Históricas

> Documento de referência da identidade do Licitarium: o nome, a marca, o selo,
> os temas — e a fundamentação histórica de cada escolha. Decidido em 2026-07-29.
> A régua do projeto: **fidelidade histórica real, não cenográfica** — cada elemento
> visual corresponde a um artefato ou convenção que existiu.

---

## 1. O nome

**Licitarium** = *licitatio* + *-arium*.

- ***licitatio, -onis*** — latim clássico: "lance, oferta em leilão", do verbo
  *licitari* ("dar lances"). É a raiz direta de "licitação" em português.
- ***-arium*** — sufixo latino para "lugar que contém/guarda": *aquarium*,
  *herbarium*, *granarium*, *tabularium*. A construção não é latim macarrônico:
  segue a fórmula produtiva real da língua.
- Leitura resultante: **"o lugar que guarda as licitações"** — exatamente o que o
  software faz.

Precedente conceitual: o **Tabularium**, arquivo oficial do Estado romano no
Capitólio (78 a.C.), onde se guardavam as *tabulae publicae* — leis, tratados e
atos públicos. O Licitarium é, em espírito, um tabularium municipal de contratações.
(O nome "Tabularium" foi considerado e descartado por colisões com softwares
existentes; ver §8.)

Pronúncia em português: "licitárium". Grafia do produto: **Licitarium**
(capitalização normal em texto corrido); **LICITARIVM** apenas no wordmark (§2).

## 2. O wordmark — LICITARIVM

No wordmark e nas peças da marca, o nome aparece como **LICITARIVM**, com V no
lugar do U.

**Nota histórica.** O alfabeto latino clássico não distinguia U de V: o sinal
**V** representava tanto a vogal /u/ quanto a consoante /w/. A letra U como forma
distinta só se consolida na Idade Moderna. Toda inscrição romana autêntica grafa
AVGVSTVS, IVLIVS, PVBLICVS. LICITARIVM segue a convenção — é o nome como um
lapicida romano o gravaria.

- Tipografia do wordmark: serifada (Georgia como fonte de sistema; aproximação
  acessível da *capitalis monumentalis*, a letra das inscrições monumentais
  romanas, cujo exemplar canônico é a Coluna de Trajano).
- Espaçamento largo (letter-spacing ~0.16em), maiúsculas sempre.
- O **V** recebe a cor de destaque do tema ativo — únio ponto de cor no wordmark.
- Subtítulo institucional (fonte do sistema, sem serifa): "Repositório municipal
  de contratações públicas" ou, na instância, o nome do município configurado.

## 3. O selo — par oficial

Dois artefatos, mesma linguagem, papéis distintos:

| Papel | Artefato | Arquivo |
|---|---|---|
| **Ícone** (exe, atalho, barra de tarefas, janela) | Tabula ansata vermelha com L | `icone-t1.svg`, `icone-t1-16.svg`, `licitarium.ico` |
| **Marca de apresentação** (wizard, tela Sobre, README, splash) | Estandarte (*signum*) | `estandarte-t3.svg` |

### 3.1 O ícone: tabula ansata

Uma **tabula ansata** ("tábua com alças") em vermelho-sinete, com filete interno
claro e **L** capitular ao centro.

**Nota histórica.** A tabula ansata é o formato romano da placa de inscrição
oficial: um retângulo com alças em cauda de andorinha (*ansae*) nas laterais.
Aparece em dedicatórias de edifícios públicos, placas votivas e nos estandartes
militares. Era, literalmente, **o suporte físico do aviso oficial romano** — o
ancestral formal do mural de avisos da prefeitura. Para um repositório de atos
públicos municipais, não existe moldura historicamente mais precisa.

Decisão de design associada: a silhueta (retângulo + alças) é única entre ícones
de aplicativo — barra de tarefas cheia de círculos e quadrados arredondados, e a
tabula se reconhece pela forma antes da cor.

### 3.2 A marca de apresentação: o estandarte

A tabula ansata com as inscrições **LICITARIVM** e **SVB · HASTA · PVBLICA**,
montada numa **hasta** de ponta lanceolada fincada numa linha de solo, com
**MMXXVI** gravado abaixo da linha.

**Notas históricas, elemento por elemento:**

- **A hasta (lança).** Em Roma, o leilão público era anunciado **fincando uma
  lança no chão** — vender *sub hasta*, "sob a lança". A hasta era o símbolo
  jurídico do poder público de alienar bens (espólios de guerra, bens confiscados).
  O termo **sobrevive intacto no direito brasileiro**: "hasta pública" (CPC), e
  na etimologia de "asta" (leilão, italiano) e "subasta" (leilão, espanhol —
  literalmente *sub hasta*). É o elo mais direto entre Roma e a Lei 14.133.
- **A ponta lanceolada e a conteira.** A hasta romana tinha ferro em forma de
  folha (lanceolado) e, na base, o *saurotér* (conteira) — a ponteira que fincava
  a lança no solo. As duas extremidades estão no desenho; a conteira é o detalhe
  que "explica" visualmente a lança fincada.
- **Tabula montada na hasta.** Os estandartes das legiões (*signa militaria*)
  carregavam tabulae ansatas montadas na haste. A combinação tabula + hasta do
  estandarte do Licitarium **é um artefato que existiu**, não uma colagem de
  símbolos.
- **SVB · HASTA · PVBLICA.** "Sob a lança pública" — a fórmula do leilão público
  romano, grafada com V clássico. Funciona como divisa (motto) do produto.
- **Os interpontos (·).** A epigrafia romana separava palavras com pontos a meia
  altura (*interpuncta*), não com espaços. Todos os textos latinos da marca os
  usam.
- **A linha de solo e o exergo MMXXVI.** Na numismática, o **exergo** é o espaço
  sob a linha de base do motivo, onde as casas da moeda gravavam marcas e datas.
  **MMXXVI = 2026**, o ano de fundação do projeto — gravado como uma casa da
  moeda gravaria. É fixo: não muda com versões ou releases.
- **Letras de campo** (usadas na exploração do denário, v3): moedas romanas
  traziam letras soltas no campo ao redor do motivo. Presentes no denário B′
  descartado; não usadas no par final.

### 3.3 Regras de uso do selo

1. O ícone (tabula) e o estandarte não se substituem: tabula = identificação
   compacta; estandarte = apresentação com respiro.
2. Não recolorir, não esticar, não rotacionar; não acrescentar texto dentro da
   tabula do ícone.
3. Os textos do estandarte usam `textLength` no SVG — qualquer edição deve
   preservar o atributo (garante que a inscrição nunca estoure a tabula,
   independente da fonte disponível).
4. O `.ico` é **multi-frame com arte dupla**: frames 256/128/64/48/32 usam a arte
   completa (`icone-t1.svg`); frames 24/16 usam a arte dedicada
   (`icone-t1-16.svg` — sem filete, L branco maior). Regenerar sempre por
   `gerar_ico.py` (Pillow: desenho a 1024 px, redução LANCZOS, SHARPEN nos frames
   ≤24 px, frames do maior para o menor, fundo transparente).

## 4. Cores

| Cor | Hex | Papel na marca | Nota |
|---|---|---|---|
| Vermelho-sinete | `#8b2e2e` | Tabula do ícone, inscrição da divisa | Vermelho de selo/lacre de documento oficial; em Roma, documentos eram autenticados por sinete pessoal pressionado em cera |
| Dourado | `#b08d3e` | Hasta, filetes, detalhes | Bronze/latão dos estandartes e ferragens |
| Pedra clara | `#ded5c2` | Tabula do estandarte | Calcário/mármore das placas epigráficas |
| Tinta | `#2b2115` | Traços e inscrições sobre pedra | Tinta ferrogálica/escura de manuscrito |
| Creme | `#f5efe2` | L do ícone, filetes claros | Pergaminho |

O par selo usa essa paleta fixa, **independente do tema ativo** — a marca não
muda de cor com o tema (exceção: o V do wordmark, §2).

## 5. Os três temas

Selecionáveis nas configurações, persistidos no banco; **Portal é o padrão**
(claro). Implementação: CSS custom properties trocadas por `data-theme` no
`<html>` — um layout, três peles; Pergaminho acrescenta exceções pontuais
(serifa em valores, filete duplo dourado no cabeçalho).

| Tema | Caráter | Fundo | Destaque | Inspiração |
|---|---|---|---|---|
| **Portal** (padrão) | Institucional moderno | `#f8f9fa` claro | Azul `#1351b4` | Linguagem visual gov.br — familiaridade imediata para o servidor público |
| **Pergaminho** | O arquivo | Papel `#f5efe2` | Selo `#8b2e2e` / dourado `#b08d3e` | O acervo histórico; serifas, filetes, materiais da marca |
| **Observatório** | O painel | Escuro `#10151c` | Âmbar `#f0a836` / verde `#2dd4a7` | Radar de dados; números tabulares, KPIs |

Tokens: `--bg --surface --surface2 --text --muted --border --accent --accent-fg
--ok --warn --radius --pill --shadow --mark-v`. KPIs na tela inicial em todos os
temas (herança da direção Observatório, promovida a recurso do produto).

## 6. Tipografia

- **Marca e wordmark**: Georgia (serifada de sistema, presente em todo Windows) —
  aproximação pragmática da capitalis monumentalis sem dependência de webfont.
  No `.ico`, Georgia **Bold** (traço grosso sobrevive à miniatura; a capitalis
  também tinha contraste forte de traço).
- **Interface**: fonte do sistema (`system-ui`/Segoe UI) — legibilidade e zero
  dependência.
- **Números em tabelas e KPIs**: `font-variant-numeric: tabular-nums`.

## 7. Acessibilidade

Padrão WCAG 2.1 AA (mesma régua da família SGCD): contraste mínimo 4.5:1 em
texto sobre fundo nos três temas, foco visível, navegação por teclado, SVGs
decorativos com `aria-hidden`. Verificar contraste ao ajustar qualquer token.

## 8. Explorações descartadas (registro de decisão)

- **Nomes**: RepOrin/LicOrin (amarrados a Orindiúva — projeto virou open-source
  nacional); Cartulário (livro medieval de cópias de documentos — forte, mas
  Licitarium é mais óbvio ao brasileiro); Tabularium (perfeito de significado,
  nome já usado por vários softwares de arquivo); Farol (colide com Farol TCE/SC);
  Index (genérico + bagagem do *Index Librorum Prohibitorum* — conotação de
  censura, oposto de transparência); Mural (colide com mural.co).
- **Selo v1–v3**: selo de cera redondo (imagem **medieval**, não romana — reprovado
  no critério de fidelidade); denário com borda perolada e legenda circular
  (numismática correta, preterido pelo par tabula/estandarte, de forma mais única);
  coluna (genérico "governo"); rolo lacrado (dois elementos disputando 16 px).
- Histórico navegável: `moodboard-v1.html` (direções de tema),
  `prototipo-v2.html` (lista + temas), `selo-v1.html` a `selo-v5.html`
  (evolução do selo), `telas-v1.html` (wizard/detalhe/config).

## 8.1 Tela de abertura (splash)

Composição por tema, montada em `ui/index.html`:

| Tema | Composição |
|---|---|
| Portal (padrão) | Cartão com selo, município e barra |
| Pergaminho | Cartão com estandarte entre filetes duplos dourados |
| Observatório | Selo com anel giratório e a divisa |

- O **selo e o estandarte mantêm as cores da marca em qualquer tema**; só
  fundo, texto e detalhes seguem a paleta ativa. Recolorir a marca por tema
  enfraqueceria a identidade.
- O tema chega pela **URL da janela** (`index.html?tema=…`), lida pelo Python
  no banco antes de abrir: a splash nasce na cor certa, sem piscar.
- A barra reflete **etapas reais** do carregamento (estado → município →
  filtros → primeira lista), nunca um tempo inventado. Piso de 900 ms para a
  splash não piscar quando o acervo abre rápido.
- **Imagem estática do executável** (aparece durante a extração da runtime,
  antes do Python subir): `design/splash.png`, gerada por
  `design/gerar_splash.py` e declarada em `Licitarium.spec`; o app a encerra
  em `main()` via `pyi_splash`.
- Estudos: `design/splash-v1.html` (8 composições) e `design/splash-v2.html`
  (composição × tema).

## 9. Arquivos da identidade

```
design/
  IDENTIDADE.md        ← este documento
  icone-t1.svg         arte oficial do ícone (frames 32px+)
  icone-t1-16.svg      arte dedicada aos frames 16/24px
  estandarte-t3.svg    marca de apresentação (signum)
  licitarium.ico       ícone multi-frame (256/128/64/48/32/24/16)
  gerar_ico.py         gerador do .ico (fonte da verdade da rasterização)
  icone-preview-*.png  provas visuais da última geração
  moodboard-v1.html, prototipo-v2.html, selo-v1..v5.html, telas-v1.html
                       histórico de exploração (não são artes finais)
```
