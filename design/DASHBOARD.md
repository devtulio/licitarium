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
