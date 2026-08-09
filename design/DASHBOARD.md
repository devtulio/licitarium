# Painel — decisões de desenho

O Painel é a primeira tela do programa. Cada número dele vira decisão de quem
assina processo, então as escolhas abaixo são regra, não estilo.

## Por que quatro vistas, e não uma tela só

Quatro perguntas diferentes, quatro leituras diferentes:

| Vista | Pergunta | Não serve para |
|---|---|---|
| **Execução** | como está o ano | achar padrão |
| **Análise** | o que mudou e onde concentra | decidir o que fazer hoje |
| **Vigilância** | o que exige ação agora | medir desempenho |
| **Economia** | quanto foi economizado, e onde | acompanhar o andamento do ano |

Amontoar as quatro numa página só produziria a tela que ninguém lê.

**Os alertas ficam acima das subabas**, sempre visíveis: alerta que só aparece
depois de escolher a subaba certa não alerta ninguém. Cada chip leva à lista
já filtrada — pelo exercício e órgão do Painel, e pelo que o alerta contou,
não por "toda a modalidade" ou por nada (achado em 2026-08-07: dois dos
quatro chips não filtravam nada — o parâmetro de modalidade nunca era lido, e
o de "processo parado" nunca existiu; os outros dois filtravam por corrida
entre o reset da troca de aba e o religamento do filtro, que só "funcionava"
porque a segunda consulta costumava vencer a primeira). O de limite anual
filtra pelos **objetos exatos** que estouraram (`agrupamento_objeto`, mesma
função SQL do agrupamento do medidor — ver `licitarium.py`), não pela
modalidade Dispensa inteira.

**"Vigentes" e "vence em 60 dias" são filtros diferentes** (achado em
2026-08-07, o mesmo usuário que pegou o item acima: 25 no alerta, 50 na
lista). O alerta conta contratos/atas com vigência numa janela **fechada**
de 60 dias; "Vigentes" não tem teto — mostra todo contrato ainda ativo,
inclusive um vencendo daqui a um ano. O chip agora liga uma caixa própria
(**Vence em 60 dias**), independente de Vigentes. O mesmo alerta aparece em
dois lugares (chip do Painel e chip no topo das listas, calculado por
`Api._kpis`) — os dois usavam o filtro errado, os dois foram corrigidos.

**Contrato e ata não dividem mais o mesmo chip** (achado logo em seguida,
mesmo dia). "25 contratos/atas vencem" levava só a uma tela — a query já
soma as duas tabelas, mas a lista é de uma tabela só, então metade da
contagem nunca tinha como aparecer. Viraram dois chips, um por tabela, cada
um com sua contagem (`alertas.vencendo_contratos`/`vencendo_atas`,
`_kpis.vencendo_60_contratos`/`vencendo_60_atas`). Os cards do Painel
também passaram a ter **largura padronizada** (`grid-template-columns:
repeat(auto-fit, minmax(200px, 1fr))`): antes cada um só media o próprio
texto, e o card do limite anual (frase longa) ficava bem mais largo que o
de propostas abertas (frase curta) na mesma fileira.

**Altura também precisou de ajuste à parte** (mesmo dia, achado pelo
usuário sobre a captura da correção acima): largura ficou igual, mas
altura não — o card do limite anual quebra em duas linhas dentro de
200px e ficava mais alto que os de uma linha só. `align-items:stretch`
é o padrão do grid e deveria igualar sozinho; **não igualou**, medido
duas vezes (inclusive forçando a propriedade). Causa: `.chip` é
`<button>`, elemento de formulário, e form controls resistem a esticar
em flex/grid — a UA stylesheet dá `min-height:min-content` implícito que
vence o `stretch` do pai. Correção: `height:100%` explícito no `.chip`.
Teste em `painel.spec.js` ("chips ficam com a mesma altura...") mede a
`getBoundingClientRect().height` dos quatro chips.

**O piso de 200px não sobrevive aos 5 alertas ao mesmo tempo** (achado
seguinte, ainda 2026-08-08, sobre print real com todos os alertas
ativos). `<main>` tem `max-width:1000px`; com o padding do conteúdo, a
área útil do `.chips` é ~956px na largura padrão. Cinco colunas de 200px
+ gap precisam de 1032px — não cabe. `auto-fit` respondeu do jeito certo
para o algoritmo (não é bug do grid): computou o máximo de colunas de
≥200px que cabem (4), e o 5º chip (o de "sem resultado", por ser o
último a entrar no HTML) quebrou sozinho pra uma segunda linha, com três
células vazias ao lado dele — mais estranho visualmente do que a
diferença de altura que motivou o post anterior. Piso baixado para
**160px**: `5×160 + 4×8(gap) = 832px`, cabe até a largura mínima da
janela (`min_size=(900,600)` no `webview.create_window`, `licitarium.py`
— abaixo disso o usuário não redimensiona de jeito nenhum). Teste em
`painel.spec.js` ("os 5 alertas possíveis cabem numa linha só...") monta
os 5 alertas via `window.__painel` e mede a viewport no mínimo absoluto.

**Terceiro round, mesmo print do usuário: `.chip.aviso` ficava 8px mais
baixo que os irmãos, com a MESMA altura** (por isso o teste de altura
não pegava — height igual, position diferente). Causa: colisão de
nome de classe. Existe uma `.aviso` genérica no CSS (texto de aviso sob
campo de formulário) com `margin-top:8px`; os dois chips de vencimento
têm `class="chip aviso"` e herdavam essa margem sem eu perceber, porque
nunca é óbvio que duas seções bem distantes do arquivo compartilham uma
classe. `.chip.aviso { margin-top:0 }` resolve — a especificidade do
composto (duas classes) já venceria a `.aviso` sozinha de qualquer jeito,
o problema era só a declaração faltando. **Lição**: `height` igual não
prova alinhamento; teste teria de medir `y`, não só `height` — o de
altura ficou como está (pega quebra de linha), o de posição é novo
("chip.aviso não herda margin-top...").

**Auditoria de design completa (2026-08-08) achou colisão de texto na
Agenda.** `grafAgenda` já tinha anti-colisão (limiar fixo de 120px entre
centros de rótulo), mas não contava a largura real do texto — um nome de até
22 caracteres, mais o sufixo " +N" de grupo, passa dos 120px sozinho, então
dois vizinhos "aprovados" pelo limiar ainda se tocavam. No acervo real, os
grupos de 11 e 12 fornecedores em dias 8 e 23 reproduziam isso toda vez.
Trocado por rastrear a borda direita real do último rótulo desenhado
(`direitaUltimoRotulo`) e calcular quantos caracteres cabem no espaço livre
até ali, cortando mais quando o vizinho está perto e pulando o rótulo (nunca
desenhando um coto ilegível) quando não sobra espaço para pelo menos 3
caracteres. `PX_POR_CHAR = 6.4` é estimativa para maiúsculas em 11px — não é
medição de DOM (o gerador produz string, não manipula nós vivos), então o
teste mede a caixa real renderizada (`getBoundingClientRect()` de cada
`text.val`), não o número de caracteres.

## Regras dos gráficos

Seguem o método de `dataviz` (skill), com a paleta validada pelo script de seis
checks — banda de luminosidade, piso de croma, separação sob daltonismo,
piso de visão normal e contraste contra a superfície.

- **Um eixo só.** Nunca dois eixos y. Estimado e homologado dividem a mesma
  escala; deságio é gráfico próprio.
- **Escala a partir do zero**, com passos de 1, 2, 2,5 ou 5 vezes uma potência
  de dez — eixo com marcas em "1,7 mi" e "3,3 mi" ninguém compara de cabeça.
- **Cor nunca sozinha.** Toda série tem rótulo direto ou legenda; os selos de
  prazo trazem o número de dias junto da cor.
- **Nenhuma pizza.** Para parte-todo com mais de três fatias, barra ordenada é
  lida certo; pizza não.
- **Emphasis em vez de categórico** quando uma série é o assunto: no acumulado
  plurianual, o ano corrente é o único colorido; os anteriores ficam no cinza
  de de-ênfase.
- **`<title>` em cada marca** — é o tooltip nativo, funciona offline e sai da
  impressão sem sujeira.
- **A marca sob o cursor acende; as irmãs recuam** (`fill-opacity: .38`, 150 ms).
  Sem isso, o `<title>` diz o número mas não diz de qual retângulo ele veio.
  **O realce é do desenho, nunca do dado**: barra não muda de tamanho, porque a
  marca vale o valor que representa. Cresce só o que é ponto — círculo da agenda,
  seta de estouro —, onde o tamanho não codifica nada. Nenhuma animação de
  entrada: o painel redesenha a cada troca de exercício e de subaba.
  A regra que esmaece as irmãs usa `:has()` e vive **separada** da que acende a
  marca — onde o seletor não existir, ela é descartada sozinha e o realce
  continua de pé.
- **Tooltip próprio, não o `<title>` nativo.** O navegador demora ~1s para
  mostrar `<title>` e não segue o cursor; `mostrarTt`/`dtip` (painel.js)
  substituem por um rótulo instantâneo, com o valor em destaque (Strong) e o
  rótulo secundário — a hierarquia que a skill `dataviz` pede. Cada marca leva
  `data-tip-v`/`data-tip-l`; um único listener delegado no `#painel` cobre
  todos os gráficos de barra/célula/ponto, porque `#painel` sobrevive ao
  redesenho — só o `innerHTML` dos cartões troca.
- **Corte vertical nos dois gráficos de linha** (execução acumulada,
  concentração de fornecedores): a pergunta vira "o que valia neste ponto",
  com uma linha por série no tooltip — nunca é preciso mirar os 2px da linha,
  o retângulo de captura cobre toda a área do gráfico. `grafSeries` e
  `grafConcentracao` devolvem `{ html, ligar }` em vez de string pura;
  `ligar(container)` prende os listeners ao SVG recém-inserido, reaproveitando
  as mesmas funções de escala do desenho — sem duplicar a matemática.
  O ponto e o rótulo do "estado padrão" (mês corrente, 10º fornecedor)
  continuam sempre visíveis em repouso — é o direto-label que vale sem hover
  nenhum; o corte os esconde enquanto ativo e devolve ao sair.
  O retângulo de captura (`[data-cross-hit]`) fica **fora** das regras gerais
  de realce — ele é invisível de propósito, "acender" a própria captura não
  informaria nada.
- **Vazio é vazio.** Sem dado, o cartão diz o que falta; nunca desenha zero.

### Paleta

As cores de série vivem em `ui/estilo.css` (`--s1…--s4`, `--seq1…--seq5`), com
**uma paleta por tema** — cada uma validada contra a própria superfície pelo
script dos seis checks:

| Tema | Séries | Rampa |
|---|---|---|
| Portal | azul, laranja, aqua, amarelo | azul, claro → escuro |
| Pergaminho | terracota, ocre, verde, ardósia | sépia, claro → escuro |
| Observatório | azul, laranja, verde, ocre (tons escuros) | azul, escuro → claro |

O Pergaminho não podia herdar o azul do Portal: sobre papel sépia ele lê como
corpo estranho. Mas quatro tons quentes não se separam sob daltonismo — daí a
ardósia fria na quarta posição, que é o que faz a paleta passar nos checks.

A rampa do Observatório tem degraus mais espaçados que a do tema claro: sobre
fundo escuro, dois azuis próximos viram a mesma cor e o mapa de calor deixa de
informar. Passo mínimo de luminosidade entre vizinhos: 0,066.

**O que não muda com o tema é o significado**: dentro de um gráfico, a mesma
posição de série é sempre a mesma cor, e nenhuma paleta usa cor sozinha para
identificar.

## O que cada número é (e não é)

- **Homologado** é `valor_homologado`, puro. O resumo executivo usa
  `COALESCE(homologado, estimado)` para não zerar processo em andamento; no
  painel isso faria a barra "homologado" mostrar como pago o que ainda é
  estimativa. Foi um defeito real, pego por teste.
- **Deságio** só considera contratações com estimado > 0 **e** homologado.
- **Funil**: as quatro etapas contam o mesmo conjunto — contratações do
  exercício escolhido. "Com resultado" é contratação com ao menos um item
  homologado; "vigentes" são os contratos **dessas** contratações, não todos os
  vigentes do acervo (o que fazia a última barra superar a primeira).
- **Medidor de limite** soma dispensas **por objeto**, agrupado pelas duas
  primeiras palavras significativas da descrição (`pca_builder.chave_agrupamento`
  com `palavras=2`). Agrupar por `unidade` não servia: o campo do PNCP traz o
  nome do órgão, e no acervo do piloto todas as dispensas caíam numa linha só.
  Com três palavras, "PAPEL A4" e "PAPEL A4 SULFITE" viram objetos distintos e
  o limite deixa de somar o que a lei manda somar; com uma, "MATERIAL" engole
  meio acervo. O enquadramento final é juízo do gestor — termômetro, não
  veredito.
- **Comparação com o ano anterior** usa o mesmo período quando o exercício está
  em curso. Comparar acumulado parcial com ano fechado mede o calendário.
- **Concentração** usa contratos do exercício, por fornecedor. A linha
  tracejada é a distribuição perfeitamente igual.

## Largura

Cada gráfico é desenhado **na largura medida do seu cartão** e redesenhado num
`ResizeObserver`. Com `viewBox` fixo e `preserveAspectRatio`, o SVG escalava
mantendo proporção e sobrava faixa morta dos dois lados — em monitor largo,
metade do cartão era vazio. Vista oculta tem largura zero: por isso o desenho
também acontece ao trocar de subaba.

## Desempenho (medido, não estimado)

Num acervo sintético de 114 MB — 3.360 contratações e 25 mil itens, com `raw`
do tamanho real:

| etapa | custo |
|---|---|
| `dados_painel` sem filtro | 121 ms |
| `dados_painel` com filtro de órgão | 167 ms |
| montar as três vistas + desenhar | 2 ms |
| `VACUUM` do acervo | 620 ms, **bloqueando toda leitura** |

Daí três regras:

- **Trocar de subaba não consulta o banco.** As três vistas já estão montadas;
  trocar é mostrar.
- **A compactação exige desperdício real** (5% do arquivo e ao menos 2.000
  páginas). O limiar antigo, de 200 páginas, disparava em quase toda
  sincronização e congelava a tela por meio segundo sem motivo aparente.
- **Consulta com JOIN qualifica a coluna.** `contratacoes` e `itens` têm as
  duas `orgao_cnpj`: sem o prefixo, filtrar por órgão derruba a consulta inteira
  com *ambiguous column name* — e o painel não abre, o que na tela parece
  travamento.

## Impressão

`🖨 Imprimir` gera **A3 paisagem**, uma vista por página. O SVG enviado ao
documento é o mesmo que está na tela — redesenhar no Python seria uma segunda
implementação para divergir da primeira. `print-color-adjust: exact` impede o
navegador de "economizar tinta" e devolver barras cinzentas; por ser vetorial,
a saída não tem resolução de tela, e sim a da impressora.

**Achado do usuário (2026-08-08, corrigido na v1.14.4): a impressão sempre
saía em pergaminho**, mesmo com outro tema ativo. Três overrides
independentes forçavam isso: um `@media print` em `_css()` que sobrescrevia
`:root` inteiro com a paleta do Pergaminho (afetava todos os relatórios
tabulares); `background:#fff`/`#faf6ec` hardcoded no `@media print` de
`_pagina()`; e `CSS_PAINEL` com as cores de série (`--s1`..`--s4`,
`--seq1`..`--seq5`) e a superfície dos cards fixas no Pergaminho, ignorando o
`tema` recebido. O motivo original — "tema escuro não faz sentido impresso"
— não se sustentava: Portal também é claro e saía errado. Correção: os três
pontos agora derivam do `tema` passado (`_css_painel(tema)` substituiu a
constante `CSS_PAINEL`); a impressão acompanha o que está na tela, inclusive
o Observatório escuro, se for essa a escolha do usuário.

## Resumo Executivo: os mesmos gráficos do Painel (2026-08-08)

Pedido do usuário: o relatório "Resumo Executivo" (`gerar(tipo="executivo")`)
tinha cartões e tabelas, sem gráfico nenhum — a evolução mensal era uma
`<span>` com `width` calculado à mão dentro de uma célula de tabela, um
truque de antes do Painel existir. Reformulado para reaproveitar:

- **A mesma consulta.** `gerar()` chamava `dados_executivo` (achatada);
  agora chama `dados_painel`, cujo campo `execucao` já é exatamente o
  `d.execucao` que `ui/painel.js:vistaExecucao` usa na tela — mesmos
  números, uma consulta a mais que o relatório não paga em lugar nenhum
  crítico de latência.
- **O mesmo layout.** Hero com sparkline + 3 cartões KPI (`.f-4`), duas
  colunas de gráfico (`.f-21`: mês × modalidade), tabelas de detalhe
  abaixo — é a estrutura de `vistaExecucao`, só que impressa de uma vez em
  vez de desenhada por JS.
- **Os mesmos gráficos, portados para Python.** `grafMeses` e `grafBarras`
  de `ui/painel.js` viraram `_grafico_meses`/`_grafico_barras` em
  `relatorios.py` — SVG escrito à mão dos dois lados, sem depender de JS
  no documento impresso (o HTML do relatório precisa se bastar sozinho, e
  não carrega `painel.js`). `_escala()` é a mesma régua de eixo redondo
  (1/2/2,5/5×10ⁿ) dos dois lados.
- **CSS reaproveitado.** `_css_painel(tema)` (a mesma função do painel
  impresso em A3) também virou o `estilo_extra` do executivo — `.hero`,
  `.kpiv`, `.rot`, `.val`, `.eixo`, `.leg` já existiam, prontos.

As tabelas de detalhe (modalidade completa, evolução mês a mês, maiores
fornecedores, vigências a vencer) continuam abaixo dos gráficos, sem corte —
um documento oficial precisa do número exato, o gráfico é para o primeiro
olhar.

## Os outros três relatórios (2026-08-08)

Levantamento pedido pelo usuário sobre os relatórios que ainda não tinham
gráfico nenhum — três achados, os três corrigidos na mesma sessão:

- **Fracionamento** já tinha, na tabela, tudo que o medidor de limite do
  Painel (`grafLimites`) precisa (`%` de cada unidade sobre o teto do art.
  75). Portado como `_grafico_limites` — mesma barra cheia = limite, mesma
  troca de "874% do limite" (esconderia a gravidade numa barra do tamanho
  da de 100%) por "×o limite" acima de 100%.
- **Preços** descrevia dispersão só em texto ("desvio padrão, coeficiente
  de variação, amostra dispersa..."). `_grafico_dispersao` é uma caixa de
  Tukey (mín–Q1–mediana–Q3–máx, média marcada à parte) construída a partir
  do que `resumo_estatistico` já calculava — nenhuma consulta nova, só
  parou de esconder o número em prosa.
- **Minuta do PCA** já calculava a curva ABC (`pca_builder.classificar_abc`,
  dentro de `listar_minuta`, usada pela tela de Montar PCA) e nunca
  mostrava a classe no documento — corrigido com uma coluna e um resumo,
  sem cálculo novo nenhum.

Padrão que se repete nos três: o número ou o cálculo já existia em algum
lugar do programa (tela, consulta, ou os dois); o achado nunca foi "falta
uma estatística", foi "a estatística existe e não aparece no documento".

## Auditoria de design (2026-08-08)

Primeira auditoria completa, nível profissional: 21+ screenshots (6 abas × 3
temas + estados de borda — janela mínima, densidade expandida, modal, filtros
ativos), cada achado visual conferido contra o código-fonte antes de entrar
no relatório (dois candidatos caíram nessa conferência: um eixo do gráfico de
deságio "sem rótulo" que só estava cortado fora do print, e uma "borda azul"
de KPI que era o cursor do mouse do Playwright atravessando a tela, não um
estado de hover real). Achados, por prioridade:

| # | Achado | Onde | Corrigido em |
|---|---|---|---|
| C1 | Rótulos da agenda se sobrepunham em dias lotados | Painel · Vigilância | 1.14.0 |
| M1 | Fornecedor/objeto truncado sem `title` | Painel + Contratos | 1.14.0 |
| M2 | Barra de filtros quebrava sem folga vertical | Contratações, Preços | 1.14.0 |
| M3 | Chip "parado" com o mesmo ícone dos de vencimento | Painel · Vigilância | 1.14.1 |
| M4 | Área clicável dos filtros de caixinha = altura do texto | barra de filtros | 1.14.1 |
| m1 | Número do hero quebrava em duas linhas na janela mínima | Painel · Execução | 1.14.1 |
| m2 | Coluna Objeto crescia sem limite na largura Expandida | listas de tabela | 1.14.1 |
| m3 | Filtros que mudam o cálculo sem hierarquia visual | aba Preços | 1.14.1 |

Todos os oito, corrigidos e liberados. Cada fix tem teste E2E que morde sem a
correção (`git diff` revertido, teste roda, falha; correção volta, teste
passa) — não só passa com a correção presente.

## Três achados do usuário na aba Preços (2026-08-08)

- **Rótulos do gráfico de dispersão sobrepostos** (mediana/média perto uma
  da outra): mesma família do C1 acima, resolvida do mesmo jeito — quando
  não cabem lado a lado, empilha em duas fileiras (`_grafico_dispersao`,
  `relatorios.py`) em vez de cortar texto (aqui não sobra caractere pra
  cortar, diferente da agenda). **Correção do passo em 1.15.4**: as
  fileiras usavam 22px de distância, que cabe só a linha do nome — o
  bloco nome+valor inteiro (14px entre as duas linhas) ainda vazava pra
  fileira vizinha (print real: "média" quase colado em "mediana"). Passo
  virou 28px, igual ao vão já usado dentro da mesma fileira.
- **Unidade de medida agora classifica a pesquisa inteira**
  (`Api.classificar_por_unidade`, `licitarium.py`): antes o seletor só
  filtrava a lista visível — a estatística (`estatisticas_preco`) sempre
  rodou sobre o conjunto de descartes gravado, não sobre o filtro da tela,
  então escolher uma unidade não bastava. A correção roda numa transação
  só sobre o mesmo recorte (termo/ano/origem) de `estatisticas_preco`, não
  só a página que a tela mostra — sem isso, uma busca com centenas de
  itens exigiria trocar de página várias vezes pra pegar todos.
- **Teto da lista em Expandida, de 1.400px pra 1.600px**: achado real de
  monitor comum (a margem visível em 1.400px parecia "não estar usando a
  tela"). Medido contra o vão-depois-do-texto que o m2 corrigiu (ver
  tabela acima) — são a mesma folga, só que a subida de um número reduz a
  margem de fora e aumenta o vão de dentro, não tem valor que zere os
  dois. 1.600px é o meio-termo medido, não uma correção completa: quem
  quiser mais folga ainda vai ver alguma margem em monitor muito largo.
  **Substituído pela regra abaixo** — o usuário comparou Painel × lista na
  mesma janela e viu que o teto próprio da lista já não fazia sentido.

## Largura da página: regra global, não teto fixo (2026-08-08)

O ajuste acima (1.600px) resolvia a lista sozinha, mas o usuário comparou
Painel e Contratações lado a lado, na mesma janela Expandida: o Painel
(`<main>` sem teto) ia até a borda; a lista parava em 1.600px e sobrava uma
faixa vazia que o Painel não tinha. Pediu a regra explícita: **Compacta =
metade da largura da janela, Expandida = a janela inteira** — para as duas
telas, não um número de pixels escolhido por medição.

- `main { max-width:max(50vw, 1000px); }` — 50% da janela em Compacta,
  com piso de 1.000px. Sem o piso, a janela mínima do pywebview (900px,
  `licitarium.py`) derrubaria o conteúdo útil para 450px — menos do que a
  barra de filtros e os 5 chips de alerta do Painel precisam para caber
  numa linha só (teste `os 5 alertas possíveis cabem numa linha só`,
  `painel.spec.js`). O piso só pesa abaixo de ~2.000px de janela.
- `[data-largura="expandida"] main { max-width:none; }` — 100%, sem
  mudança (já era assim).
- **A lista perdeu o teto próprio** (`[data-largura="expandida"] .lista`,
  1.400px→1.600px→removido): agora só segue o `<main>`, igual ao Painel.
  O vão depois do texto do Objeto que o achado m2 apontou volta a existir
  em monitor muito largo — decisão que passou a ser explícita do usuário
  (largura = tela toda), não escondida atrás de um teto arbitrário.

## Pesquisa de preços: seleção opt-in em vez de opt-out (2026-08-08)

Pedido do usuário, três achados: (1) a busca abria com tudo marcado —
comparar por um subconjunto (ex.: só "maço") exigia desmarcar item por
item; (2) faltava um jeito rápido de marcar tudo de volta; (3) MAÇO e MÇ
eram grupos de unidade diferentes (faltava "Maço" em
`UNIDADES_SINONIMAS`, `licitarium.py`).

**Modelo novo**: nova tabela `precos_selecionados` (termo, item_id — sem
motivo). Um item nunca marcado não aparece em lugar nenhum; um item
marcado e depois tirado vira `precos_descartes` (aí sim com motivo — foi
visto e recusado, não só nunca escolhido). As duas tabelas ficam
mutuamente exclusivas por construção: marcar sempre limpa um descarte
anterior do mesmo item (`Api.selecionar_preco`), e "Restaurar todos"
agora **seleciona** de novo cada item descartado, não só apaga o registro
(o antigo `restaurar_preco` sozinho deixava o item fora da conta mesmo
"restaurado" — achado ao migrar o modelo).

`estatisticas_preco` ganhou `incluidos` (lista vazia explícita ≠ `None` —
vazia é "nada selecionado ainda", `None` é "sem filtro", útil pra chamada
legada/testes). `relatorios.dados_precos` lê `precos_selecionados` direto
do banco pelo termo (mesmo padrão que já usava pra `precos_descartes`) —
o relatório sai sobre o que a tela mostrava, sem precisar que a UI passe
a lista.

`classificar_por_unidade` (v1.15.2) foi revisado: antes escrevia descarte
com motivo "embalagem" pra tudo que não batia com a unidade escolhida —
sob o modelo antigo (tudo dentro por padrão) fazia sentido, mas sob o
novo vira barulho no relatório (centenas de "sem justificativa" pra itens
que nunca foram considerados). Agora só popula a seleção com quem bate.

**Corrida real, achada rodando os testes**: `carregarLista()` chamava
`mostrarResumoPrecos()` sem `await`, que por sua vez recarregava a
seleção do banco — a lista podia desenhar as linhas ANTES do Set de
seleção estar populado, lendo tudo como não-marcado até o próximo
redesenho. Benigno no modelo antigo (Set vazio = "nada excluído" = tudo
marcado, coincidia com o padrão certo na maioria dos casos); maligno no
novo (Set vazio = "nada selecionado" = tudo desmarcado, mascarando
justamente os testes que verificavam seleção pré-carregada). Corrigido
movendo o carregamento de descartes/seleção pra dentro de
`carregarLista()`, com `await`, antes de desenhar qualquer linha.

## Contador e três seletores por critério (2026-08-08)

Pedido do usuário, depois do levantamento de filtros da v1.16.0 (contador
visível, unidade acumulando, fornecedor, faixa de valor, texto contido —
os cinco itens do levantamento).

**`total` em `estatisticas_preco`**: computado sempre, sem olhar seleção
nem descarte — via uma consulta `COUNT(*)` própria com
`_where_pesquisa_precos`, antes dos filtros de `incluidos`/`excluidos`
entrarem. Presente nos quatro caminhos de retorno (`nada_selecionado`,
os dois early-return de `corrigir`/`por_conteudo` vazios, e o resumo
final) — faltar em um deles quebraria o contador só naquele estado, o
tipo de bug que só aparece testando o caminho certo.

**`_selecionar_ids(db, termo, ids)`**: helper de módulo compartilhado
pelos quatro seletores por critério (unidade, fornecedor, faixa, texto).
Todos **somam** à seleção, nunca substituem — `classificar_por_unidade`
(v1.15.2) tinha um `DELETE FROM precos_selecionados WHERE termo=?` antes
de inserir, removido nesta versão; só `selecionar_todos_precos` continua
limpando tudo primeiro (é reset completo por definição, não um critério).

**`fornecedores_pesquisa_precos`**: lista os fornecedores só desta busca
(termo/ano/origem), não o cadastro inteiro — diferente de
`filtros_disponiveis()`'s `unidades`, que é global ao acervo (achado ao
revisar: um seletor de fornecedor com escopo global teria centenas de
opções irrelevantes pra maioria das buscas).

## Quarta vista: Economia (2026-08-08)

Primeiro passo de um pedido maior do usuário (preparar o sistema para
venda a prefeituras pequenas, com foco em relatórios de economia e
comparativo sobre os dados da própria prefeitura — arquitetura local,
sem servidor, decidida à parte). Até aqui só existia um número solto de
economia (estimado − homologado do ano inteiro, no Resumo Executivo);
nada por categoria, família ou comparado ano a ano.

**Sem round-trip extra**: a seção `economia` entra dentro de
`dados_painel`, a mesma consulta única que já serve as outras três
vistas — o comentário da função já explicava por quê ("a ponte JS custa
mais que a consulta"). Os totais do ano vêm de graça de
`executivo["cards"]` (já calculados por `dados_contratacoes`); só duas
coisas novas vão ao banco: `SUM(valor_estimado)` a mais na consulta do
ano anterior (para a comparação, mesmo corte de `comparacao_parcial` já
usado em Execução) e uma consulta em `itens` para família/categoria.

**Por modalidade reaproveita `desagios`**: a mesma lista que a vista
Análise já usa para o deságio %, só que agora guardando também
`estimado`/`homologado`/`economizado` em vez de descartar `r[2]`/`r[3]`
depois de calcular o `pct`.

**Por família de item usa `pca_builder.chave_agrupamento`**, o mesmo
agrupador do medidor de limite de fracionamento (`dados_fracionamento`'s
`por_objeto`) — nenhuma taxonomia nova. Por categoria agrupa pelo campo
cru que o próprio PNCP já manda por item (`categoria`, com
`material_servico` como reserva quando vem vazio) — não existe, e não foi
criada, nenhuma classificação própria de categoria no Licitarium.

**Entra na impressão do Painel de graça**: `imprimir_painel` só embrulha
o HTML que a tela já desenhou (`render_painel`, relatorios.py) — nenhum
gráfico novo em Python foi escrito para isso. Só o relatório avulso
("Economia e Comparativos", gerável sem abrir o Painel) precisou de porte
próprio, reaproveitando `_grafico_barras` — já genérico o bastante para
os três agrupamentos, sem nenhum SVG novo.

## Documento impresso não tem tema (2026-08-08)

Reversão consciente da v1.14.4 — vale registrar o porquê, senão daqui a
meses parece bug reintroduzido.

**O que a v1.14.4 corrigiu:** o relatório forçava a paleta pergaminho em
três overrides independentes, ignorando o tema que o usuário tinha
escolhido. Isso era errado e foi corrigido: o documento passou a seguir o
tema.

**Por que agora é o contrário:** seguir o tema resolveu o sintoma
(ignorar a escolha) mas trouxe outro — imprimir no Observatório gera
documento de fundo escuro, e nenhum papel de Tribunal de Contas é escuro.
A regra que substitui as duas é mais forte que ambas: **documento oficial
não tem tema**. O papel é peça institucional do município, sai sempre
branco/grafite; os três temas continuam valendo integralmente na tela.

**Cores de série:** fixadas no conjunto do Portal, não no do tema ativo.
Cada conjunto foi calibrado para o fundo do seu tema, e o papel agora é
branco fixo. Medido contra branco (WCAG 1.4.11 pede 3.0 para elemento
gráfico): Observatório cai a 2,99 (seq4) e 1,54 (seq5); Pergaminho, a
1,28–2,55 (seq1-seq3). O Portal é o que nasceu para superfície branca —
sua superfície de card já é `#ffffff`. As cores não mudaram: mudou qual
conjunto o papel usa.

**Pendência anotada, não corrigida:** mesmo no conjunto do Portal, `s3`
(#1baf7a, 2,82) e `s4` (#eda100, 2,17) ficam abaixo de 3.0 sobre branco.
Isso é **pré-existente** — quem usa o tema padrão já imprimia assim —, e
mexer nas cores de série exige revalidar daltonismo, que é o que
`design/DASHBOARD.md` protege desde o início. Fica registrado para uma
rodada própria.

**O que NÃO mudou:** o estandarte e o lema do rodapé mantêm as cores
cravadas no SVG da marca (`IDENTIDADE.md` §4: marca não troca de cor com
a pele). Por isso o teste que confere a sobriedade varre só o bloco
`:root {...}`, não o documento inteiro — o primeiro assert que escrevi
falhou justamente por pegar o dourado do estandarte.

## Nome acessível do gráfico, e por que sem role="img" (2026-08-09)

Auditoria de acessibilidade. O helper `svg()` emitia `role="img"` **sem
nome acessível**: todo gráfico entrava como uma imagem anônima.

O reflexo seria acrescentar `aria-label` e pronto. Não é o certo aqui, e a
razão é uma regra que já está neste arquivo: **"cor nunca sozinha — toda
série tem rótulo direto"**. Os rótulos e os valores destes gráficos moram
em `<text>` DENTRO do SVG. E `role="img"` torna os filhos apresentacionais
— com ele, o leitor de tela ouviria o nome do gráfico e perderia
exatamente os números.

Então: `role="img"` saiu, e o nome entra como `<title>`, que é o nome
acessível de um SVG embutido. O leitor de tela ouve o título e ainda
alcança os rótulos.

A injeção acontece em `desenharGraficos`, não nas 12 entradas de `DESENHO`:
é o ponto único por onde todo gráfico passa, e `cartaoGraf` já tem o
título do cartão, que é a melhor descrição que existe do desenho. Passar o
nome por parâmetro obrigaria a repetir a string em cada entrada.

**Contraste da série — pendente, não corrigido.** Medido contra a
superfície de cada tema (WCAG 1.4.11 pede 3.0 para elemento gráfico):
Portal `s3` 2,82 e `s4` 2,17; Pergaminho `s2` 2,76; Observatório passa. É
**pré-existente** e vale na tela, não só no papel — o Portal é o tema
padrão. Corrigir exige revalidar daltonismo pelo script de seis checks,
que é o que esta paleta protege desde o início; fica como rodada própria.

## A paleta foi validada, não avaliada (2026-08-09)

Rodado o validador de seis checks da skill `dataviz` nas três paletas de
série. **As três passam**: banda de luminosidade, piso de croma, separação
sob daltonismo, piso de visão normal e contraste.

| tema | separação CVD (pior par adjacente) | contraste |
|---|---|---|
| portal | ΔE 9,1 protan · 27,0 tritan | aviso: s3 2,74 · s4 2,11 |
| pergaminho | ΔE 8,2 protan · 7,9 tritan | aviso: s2 2,87 |
| observatorio | ΔE 8,4 protan · 24,4 tritan | passa |

**O aviso de contraste não pede troca de cor.** Pelo critério da skill ele
é satisfeito por "rótulo visível ou tabela" — e esse alívio já existe aqui
desde sempre, pela regra "cor nunca sozinha: toda série tem rótulo
direto". Conferido gráfico por gráfico: todo uso de cor em aviso tem
rótulo e valor na própria barra, e no relatório vem a tabela completa
embaixo.

**Não mexer na paleta por causa disso.** A separação sob daltonismo passa
perto do piso (8,2 no pergaminho); re-escalonar as cores para ganhar
contraste arriscaria justamente o check que mais importa. O caminho certo,
quando o contraste incomodar, é usar o slot mais escuro — não inventar
cor nova.

**Foi o que se fez no relatório de economia.** Os quatro gráficos de lá
usavam s1/s2/s3/s4, enquanto na tela os mesmos quatro usam o padrão s1.
São de série única: a cor não codifica nada, o título é que identifica.
Alinhados no s1 — segue o método ("one series → one color, slot 1"),
restaura a leitura igual entre tela e papel, e resolve o aviso de graça,
porque s1 é a única do conjunto acima de 3.0 contra papel branco.

**`tabular-nums` saiu dos números de exibição** (`.hero .n`, `.kpiv .v`,
`.kpi .n`). Largura fixa de dígito é para número que alinha na vertical —
tabela, eixo, onde continua. Em display, deixa o valor frouxo.
