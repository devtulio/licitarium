# Painel — decisões de desenho

O Painel é a primeira tela do programa. Cada número dele vira decisão de quem
assina processo, então as escolhas abaixo são regra, não estilo.

## Por que três vistas, e não uma tela só

Três perguntas diferentes, três leituras diferentes:

| Vista | Pergunta | Não serve para |
|---|---|---|
| **Execução** | como está o ano | achar padrão |
| **Análise** | o que mudou e onde concentra | decidir o que fazer hoje |
| **Vigilância** | o que exige ação agora | medir desempenho |

Amontoar as três numa página só produziria a tela que ninguém lê.

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
