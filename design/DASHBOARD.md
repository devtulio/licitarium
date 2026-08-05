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
já filtrada.

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
- **Vazio é vazio.** Sem dado, o cartão diz o que falta; nunca desenha zero.

### Paleta

As cores de série vivem em `ui/estilo.css` (`--s1…--s4`, `--seq1…--seq5`) e
**não mudam com o tema**: foram validadas contra a superfície clara e a escura,
e trocá-las por tema exigiria validar uma paleta nova para cada pele. O tema
manda no papel de parede, não no significado do dado.

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

## Impressão

`🖨 Imprimir` gera **A3 paisagem**, uma vista por página. O SVG enviado ao
documento é o mesmo que está na tela — redesenhar no Python seria uma segunda
implementação para divergir da primeira. `print-color-adjust: exact` impede o
navegador de "economizar tinta" e devolver barras cinzentas; por ser vetorial,
a saída não tem resolução de tela, e sim a da impressora.
