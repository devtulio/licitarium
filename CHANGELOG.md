# Changelog

## 1.13.0 — 2026-08-07

**Contrato e ata deixam de dividir o mesmo alerta**

- O card "contratos/atas vencem em 60 dias" virou **dois**: um para
  contratos, outro para atas — cada um leva à sua própria aba já filtrada.
  Antes o alerta somava os dois e o clique só conseguia abrir uma das duas
  telas, então metade da contagem nunca aparecia na lista.
- Mesma separação no chip que aparece no topo das listas (`chip-vencendo`).
- **Cards do Painel com tamanho padronizado.** Antes cada card só media o
  próprio texto — "5 objetos acima do limite anual de dispensa" ficava bem
  mais largo que "1 processo com proposta aberta" na mesma fileira. Agora
  todos dividem a largura da fileira igualmente.

253 pytest + 98 E2E.

## 1.12.1 — 2026-08-07

**"25 contratos vencem" abria lista de 50 — o filtro era "vigentes", não
"vence em 60 dias"**

- O alerta conta contratos e atas com vigência terminando dentro de uma
  **janela fechada de 60 dias**. O clique aplicava o filtro **Vigentes**,
  que não tem limite superior — todo contrato ainda ativo entrava, mesmo um
  vencendo daqui a um ano. Achado reportado pelo usuário: 25 no alerta, 50
  na lista.
- Ganhou filtro e caixa próprios (**Vence em 60 dias**), distintos de
  **Vigentes**: a caixa antiga continua útil sozinha (ver tudo que ainda
  não venceu, sem prazo), e agora as duas podem ser ligadas ou desligadas
  independentemente, na mão ou pelo alerta.
- Mesma correção nos **dois lugares** que levam a esse alerta: o chip do
  Painel e o chip de vencimento que aparece no topo das listas.

252 pytest + 96 E2E.

## 1.12.0 — 2026-08-07

**Clicar num alerta do Painel agora filtra a lista de verdade**

- **Objetos acima do limite anual**: até aqui o clique não fazia nada além de
  trocar de aba — o filtro de modalidade nunca era aplicado. Agora abre a
  lista já com **Dispensa**, o **exercício** e os **objetos exatos** que o
  alerta apontou (não todas as dispensas do ano); um aviso acima da lista
  diz que o filtro veio do alerta, com botão para tirá-lo.
- **Processo sem resultado há mais de 90 dias**: esse alerta nunca teve
  filtro nenhum — o critério só existia dentro da contagem. Ganhou filtro
  próprio, com caixa dedicada (**Sem resultado (90+ dias)**) que também pode
  ser ligada na mão, sem passar pelo alerta.
- **Contratos/atas vencendo e propostas abertas** já filtravam, mas por uma
  corrida: o clique na aba resetava os filtros e recarregava a lista sem
  filtro nenhum, e o clique no alerta religava o filtro e recarregava de
  novo — duas consultas disputando qual pintava a tela por último. Virou
  uma consulta só, sem corrida.
- Os quatro alertas passaram a levar também o **órgão** selecionado no
  Painel — antes a lista abria sempre com "todos os órgãos", mesmo quando o
  alerta foi contado com um órgão específico filtrado.

Mudança de comportamento, sem efeito em nenhum número já publicado — os
alertas sempre contaram certo; só o clique não levava até o que foi contado.
250 pytest + 95 E2E.

## 1.11.2 — 2026-08-07

**Tooltip próprio e corte vertical nos gráficos de linha**

- O `<title>` nativo do navegador saiu: demorava ~1s para aparecer e não
  seguia o cursor. No lugar, um **rótulo próprio, instantâneo**, com o valor
  em destaque e o rótulo secundário — em todos os nove gráficos do Painel.
- **Passar o mouse sobre o gráfico de acumulado do exercício ou o de
  concentração de fornecedores** traz uma **linha vertical** que segue o
  cursor: em vez de mirar os 2px da linha, qualquer ponto do gráfico serve, e
  o rótulo passa a listar o valor de **cada série** naquele ponto — os três
  anos lado a lado, não um de cada vez. Tirando o mouse, o gráfico volta ao
  ponto de referência que segue sempre visível (mês corrente, 10º
  fornecedor).
- Mudança de interface, sem efeito em número, cálculo ou relatório algum.
  245 pytest + 91 E2E; os quatro testes novos conferidos falhando com a
  camada de interação desligada.

## 1.11.1 — 2026-08-06

**Os gráficos do Painel respondem ao cursor**

- Passar o mouse sobre uma barra, ponto ou célula **acende a marca e recua as
  demais**. Num gráfico de doze meses com duas séries, é o que permite saber qual
  marca se está lendo — antes só havia o rótulo do sistema, que não diz qual
  retângulo o produziu.
- **Barra não muda de tamanho.** Ela vale o número que representa, e crescer ao
  ser apontada faria a marca mentir sobre o valor. Quem cresce é o que é ponto —
  círculo da agenda, seta de estouro de limite —, onde tamanho não codifica dado.
- Transições de 150 ms, e nenhuma animação de entrada: o painel redesenha a cada
  troca de exercício e de subaba, e repetir o espetáculo a cada vez cansaria.
  Quem pede menos movimento no sistema (`prefers-reduced-motion`) recebe o
  realce sem transição.

## 1.11.0 — 2026-08-06

**Dois defeitos que só o acervo cheio revelou**

- **Preço por quilo saía dividido pela caixa de transporte.** A descrição do
  hortifruti traz o padrão comercial do CEAGESP — *"SACO COM 20 KG"* — junto da
  especificação, e a unidade licitada é o quilo. O preço unitário já estava por
  quilo, mas o programa lia os 20 kg da descrição e dividia de novo: abóbora a
  R$ 5,45/kg virava **R$ 0,27/kg**, banana R$ 0,165/kg. Eram **1.245 itens**,
  16% de tudo que o extrator lia.
- Agora, quando a **unidade licitada já é a unidade-base** (quilo, litro, metro
  ou unidade), o conteúdo vale 1 e nada é dividido. O efeito colateral é bem-
  vindo: a mercadoria **a granel passa a se comparar com a embalada** — o feijão
  por quilo entra na mesma série do pacote de 5 kg, e a caneta avulsa na do
  pacote com 12. Antes as duas ficavam de fora da comparação.
- **A correção pelo IPCA podia mover a mediana sem que fosse inflação.** Os
  preços mais recentes que o último índice publicado saem da série — e com eles
  muda a composição da amostra. Em *"instalação manutenção"*, 76 de 330 preços
  saíram, todos recentes e baratos, e a mediana subiu **92%**, num período em
  que o IPCA acumulado não passava de 25%.
- Acima de **10% da série excluída**, a tela e o relatório passam a dizer, com
  destaque, que a diferença para os valores nominais não decorre apenas da
  correção monetária. O texto do relatório também deixou de atribuir a exclusão
  só à "falta de data": a causa mais comum é o preço ser posterior ao índice.
- **Embalagem individual dispensa o marcador.** Até aqui, a medida na descrição
  só era lida com `C/`, `COM` ou `CAIXA COM` — a regra existia para não
  confundir *"SERINGA 10ML"* (capacidade do artefato) com conteúdo. Mas quando a
  unidade de compra **é** a embalagem do produto (pacote, balde, galão, pote,
  lata, frasco), a medida escrita é o conteúdo: *"BATATA PALHA 1KG"* num pacote
  é um quilo. Recupera **1.501 itens**, quase todos de merenda escolar.
- Caixa e fardo ficam **de fora** dessa leitura, de propósito: são embalagens
  coletivas e o preço é o da caixa inteira. Foi de onde saíram todos os erros da
  amostra — *"FERMENTO BIOLÓGICO 10G"* em caixa a R$ 216 daria **R$ 21.600/kg**,
  e *"ÓLEO DE SOJA 900ML"* em caixa a R$ 139,50 daria R$ 155/litro.
- **A unidade-base da comparação passou a ser escolhida só por quem declara
  conteúdo.** Como todo item vendido a unidade agora vale "1 unidade", esses
  itens passariam a decidir a base pelo peso do número: em *leite*, 140 avulsos
  faziam a comparação sair **por unidade** e jogavam fora 89 itens em litro e
  101 em quilo — justamente os que a comparação existe para pôr lado a lado. O
  mesmo em *café*, que perdia 100 itens em quilo. Agora o voto é de quem
  declarou embalagem; se ninguém declarou, o avulso decide, que é o certo numa
  pesquisa só de itens unitários.
- A comparação por conteúdo **não filtra lote** — o item lançado como *"Proposta
  para todos os itens"* entra com o valor do lote. Quem o tira da série é o
  descarte com razão, com o motivo próprio, que deixa registro no documento.

## 1.10.5 — 2026-08-06

**Quando o programa não abre, ele passa a dizer por quê**

- A interface do Licitarium é publicada num servidor local (`127.0.0.1`) e lida
  pela janela do programa. Quando esse servidor não sobe — antivírus, firewall
  ou proxy sem exceção para endereços locais —, aparecia a página de erro do
  navegador falando de proxy e firewall, **sem mencionar o Licitarium**.
- Agora o programa confere se a interface respondeu e, se não respondeu, mostra
  uma janela própria explicando o que aconteceu e os três caminhos que costumam
  resolver.
- O executável é compilado **sem console**: até aqui, uma falha na partida não
  deixava rastro nenhum. Passa a gravar `ultimo-erro.log` na pasta de dados,
  com data, versão e detalhe técnico — é o primeiro lugar a olhar quando o
  programa não abre.

## 1.10.4 — 2026-08-05

**O Painel travava ao filtrar por órgão — e era um erro de consulta**

- `contratações` e `itens` têm as duas uma coluna com o CNPJ do órgão. Na
  consulta que junta as duas, sem dizer de qual tabela, o SQLite recusa tudo
  com *ambiguous column name*: escolher um órgão simplesmente não montava o
  painel, e a tela ficava como estava — parecendo travada.
- **Trocar de subaba ia ao banco de novo** sem necessidade: as três visões já
  estão montadas, então trocar agora é só mostrar.
- **A compactação do acervo bloqueia toda leitura** enquanto roda — 0,6 s num
  acervo de 114 MB — e disparava com apenas 0,8 MB de espaço livre, ou seja,
  em quase toda sincronização. Agora só quando há desperdício de verdade (5% do
  arquivo e no mínimo 2.000 páginas).
- O painel mostra que está carregando e, se a consulta falhar, **diz o erro**
  em vez de ficar mudo.

**Erros do PNCP: o portal não recusa, ele demora**

- No acervo do piloto, **todos** os erros de um dia foram *the read operation
  timed out* — nenhuma recusa, nenhum bloqueio. Insistir com o mesmo prazo
  curto repetia a falha: o tempo de espera agora **cresce a cada tentativa**
  (30, 45, 60, 75, 90 s).
- A mensagem dizia "sem conexão com o PNCP", o que mandava procurar defeito na
  internet. Agora diz que **o portal não respondeu a tempo**.
- Erro de servidor e tempo esgotado passam a **reduzir o número de conexões
  simultâneas**, como o 429 já fazia: diante de um portal sobrecarregado o
  programa insistia a quatro conexões.
- O tempo de espera entre tentativas ganhou **sorteio**, para as conexões que
  falharam juntas não voltarem no mesmo instante.
- **Abrir o programa não repete a coleta inteira**: a sincronização automática
  respeita um intervalo de 10 minutos desde a última. O botão **Sincronizar**
  continua valendo sempre.

## 1.10.3 — 2026-08-05

**Cada tema com a sua paleta de gráficos**

- No **Pergaminho**, as barras azuis liam como corpo estranho sobre o papel
  sépia. As séries passam a ser **terracota, ocre, verde e ardósia**, validadas
  contra a superfície do tema — a ardósia fria fica na quarta posição porque
  quatro tons quentes não se separam sob daltonismo.
- No **Observatório**, o mapa de calor quase não diferenciava os níveis: os
  degraus da rampa eram próximos demais para fundo escuro. Refeitos com mais
  separação de luminosidade.
- O **relatório impresso** acompanha o Pergaminho, que é o tema do papel.

## 1.10.2 — 2026-08-05

**O Painel passa a usar a tela**

- Os gráficos eram desenhados numa largura fixa e escalados para caber: em
  monitor largo, cada um ficava ilhado no meio do cartão, com faixas vazias dos
  dois lados. Agora **cada gráfico é desenhado na medida do espaço** e
  redesenhado quando a janela muda de tamanho — as barras crescem, os rótulos
  se espalham e o cartão fica cheio.
- **Os estilos do painel não estavam sendo aplicados.** A seção tinha só o
  identificador, e as regras usavam a classe: títulos, tabelas e notas ficavam
  com a formatação genérica. Corrigido — tabelas ganham colunas de largura
  previsível e texto longo é cortado com reticências, em vez de encostar na
  coluna vizinha.
- **Rótulos que se sobrepunham**: na curva de concentração o texto caía sobre a
  linha (e destacava "todos os fornecedores = 100%", que não informa nada);
  na agenda, nomes de vencimentos próximos se encavalavam; no deságio, a escala
  não acompanhava o eixo ao mudar a largura.
- Os avisos concordam em número: *1 processo com proposta aberta*, não
  *1 processos*.

## 1.10.1 — 2026-08-05

**Correções no Painel — três números que induziam a erro**

- **A comparação com o ano anterior media períodos diferentes.** O painel
  confrontava o acumulado do exercício em curso com o **ano inteiro**
  anterior: em agosto, "caiu 67%" dizia apenas que faltavam quatro meses.
  Agora compara com o **mesmo período** do ano anterior, e o rótulo diz isso.
- **O funil misturava escopos.** "Vigentes hoje" contava contratos de qualquer
  exercício, enquanto as demais etapas eram só do ano escolhido — a última
  barra chegava a ser maior que a primeira. As quatro etapas passam a falar do
  mesmo conjunto.
- **O medidor de limite não separava nada.** Ele agrupava por unidade
  administrativa, e o campo do PNCP traz o nome do órgão: no acervo do piloto,
  as 16 dispensas caíam todas numa linha só, com 874%. Agora o agrupamento é
  por **objeto**, que é também o critério do art. 75 — e passando de 100% o
  medidor mostra quantas vezes o limite foi excedido, em vez de uma barra cheia
  idêntica à de quem está em 100%.
- **Mês sem contratação voltou ao eixo.** Meses vazios eram omitidos, e o
  gráfico emendava fevereiro com abril sem avisar que março existia.

## 1.10.0 — 2026-08-05

**Painel — a nova tela inicial**

- O programa passa a abrir num **Painel** com gráficos do exercício, em três
  visões: **Execução** (como está o ano), **Análise** (o que mudou e onde
  concentra) e **Vigilância** (o que precisa de ação). A visão escolhida fica
  guardada, e os seletores de exercício e órgão valem para as três.
- **Execução**: valor homologado com comparação ao ano anterior, contratações,
  deságio médio, contratos vigentes, valores mês a mês (estimado × homologado),
  modalidades, vencimentos de 90 dias e principais fornecedores.
- **Análise**: acumulado do ano contra os dois anteriores, deságio por
  modalidade, concentração de fornecedores e mapa de calor de processos por mês
  e modalidade.
- **Vigilância**: medidores do limite anual de dispensa por unidade, funil do
  edital ao contrato e agenda dos próximos 90 dias.
- Os **alertas** — limite de dispensa, vencimentos, propostas abertas e
  processos sem resultado há mais de 90 dias — ficam acima das três visões e
  levam à lista já filtrada.
- **Impressão em A3 paisagem**, uma visão por página, com o mesmo desenho da
  tela. Os gráficos são vetoriais, então saem na resolução da impressora, e as
  cores são preservadas no papel.

**Correção**

- O gráfico de valores mensais usava, na barra de *homologado*, o valor
  estimado quando o processo ainda não tinha homologação — mostrava como pago o
  que era estimativa. Agora homologado é homologado; processo sem resultado não
  entra nessa barra nem no acumulado.

## 1.9.0 — 2026-08-05

**Corrigir pelo IPCA**

- Nova caixa **Corrigir pelo IPCA** na aba Preços: cada valor é trazido a
  preços de hoje antes de qualquer conta. R$ 208,04 pagos em março de 2022
  equivalem a **R$ 252,06** em junho de 2026 — comparar reais de anos
  diferentes subestimava o preço atual em mais de 20%.
- O índice é a **série 433 do Banco Central**, baixada junto com a
  sincronização e guardada no banco (poucos KB). Falha ao baixá-la não
  atrapalha a coleta do acervo.
- A data-base de cada preço é a **data do resultado**; sem ela, a da publicação
  do processo. O índice do mês da compra já está no preço pago, então a
  correção acumula os meses seguintes.
- **O programa não projeta índice.** A correção vai até o último mês publicado,
  e tela e relatório declaram qual é. Preço mais recente que o índice, ou sem
  data utilizável, fica de fora e é contado no aviso.
- As duas caixas convivem: com correção e conteúdo ligados, o preço por
  conteúdo já sai corrigido — senão a coluna divergiria do resumo.

## 1.8.0 — 2026-08-05

**Comparar por conteúdo**

- Nova caixa **Comparar por conteúdo** na aba Preços. Ligada, o resumo inteiro
  passa a ser por **unidade-base** (R$/folha, R$/quilo, R$/litro, R$/metro) e a
  lista ganha a coluna correspondente.
- Resolve a distorção da embalagem: a caixa de papel A4 com 5.000 folhas a
  R$ 232,80 custa **R$ 0,0466 por folha**, enquanto o pacote com 100 folhas a
  R$ 38,90 custa **R$ 0,3890** — 8,4 vezes mais caro. Os dois entravam na
  mesma mediana como se fossem comparáveis.
- O conteúdo é lido do que o órgão publicou, no campo de unidade
  (*Embalagem 1,00 KG*) ou na descrição quando ela declara a embalagem
  (*C/5000 FLS*, *CAIXA COM 100 UNIDADES*).
- **O programa prefere não converter a converter errado.** Gramatura
  (*75G/M²*), dimensão (*210MM X 297MM*) e capacidade de artefato
  (*SERINGA 10ML*) não viram conteúdo — nesses casos a coluna fica com um
  traço. Metade dos testes desta versão existe para garantir isso.
- Comparar R$/quilo com R$/folha não diria nada: a comparação usa a
  unidade-base mais frequente e informa **quantos itens ficaram de fora**.
- O relatório em PDF acompanha o modo, com a coluna nova, os valores em
  unidade-base e a declaração de quantos preços não entraram na comparação.

## 1.7.0 — 2026-08-05

**A razão de cada preço descartado, gravada e impressa**

- O aviso de itens descartados virou uma **lista**: cada item mostra o que é,
  quanto custava e um seletor de **razão**. Seis motivos prontos — item não
  comparável, embalagem ou unidade diferente, preço inexequível, preço
  excessivamente elevado, contratação antiga demais, valor de lote lançado como
  item único — e **Outro…** abre campo livre.
- O relatório ganhou a seção **Itens desconsiderados nesta pesquisa**, com
  preço, fornecedor, processo e motivo. Antes o item simplesmente sumia do
  documento: quem conferia não tinha como saber que a série fora filtrada —
  justamente o que o art. 23 e a IN SEGES 65/2021 não admitem.
- **Descartar continua sendo um clique**; a razão pode vir depois. O que ficar
  sem justificativa é contado no aviso da tela e **marcado no documento**, como
  pendência a resolver antes de juntar o relatório ao processo.
- Os descartes passam a ser **gravados por pesquisa**: voltar ao mesmo termo
  amanhã traz de volta o que foi desconsiderado e por quê.
- O documento passou a ler os descartes do banco, e não do estado da tela — o
  relatório sai igual mesmo gerado depois, de outra tela.

## 1.6.0 — 2026-08-05

**Cópia do acervo**

- **Configurações → Cópia do acervo** ganhou dois botões: **Salvar cópia…**
  guarda tudo num arquivo `.zip` (contratações, contratos, atas, itens, PCA,
  configurações e a lista de municípios de referência) e **Restaurar cópia…**
  devolve esse arquivo ao lugar.
- O Licitarium nasceu sem cópia de segurança porque o acervo é reconstruível a
  partir do PNCP — e continua sendo. Só que reconstruir o próprio município
  leva minutos enquanto **cada município de referência custa de minutos a
  horas**, e a lista deles se perde junto com o banco. A cópia troca essas
  horas por um arquivo.
- A cópia sai pela API de backup do SQLite, e não copiando o arquivo do disco:
  com a sincronização gravando, um arquivo copiado nasceria pela metade.
- Restaurar confere o arquivo antes de tocar em qualquer coisa e **guarda o
  acervo atual** como `.substituido-<data>`, em vez de apagá-lo.

## 1.5.2 — 2026-08-05

- **O programa não aposenta mais um banco por conta própria.** A 1.5.1 passou
  a guardar como `.corrompido-<data>` o banco que não conseguisse ler, criando
  um novo em seguida. Só que um diagnóstico de corrupção pode estar errado — e
  quando está, o que desaparece da tela é um acervo que custou horas de coleta.
  Agora o programa **pergunta antes**, numa caixa do Windows: começar um banco
  novo ou sair sem tocar em nada. Escolhendo sair, o arquivo continua
  exatamente onde estava, para você cuidar dele.

## 1.5.1 — 2026-08-05

- **Correção: o programa deixava de abrir por causa do diário de transações.**
  O SQLite mantém um arquivo `-wal` com o que ainda não foi gravado no banco.
  Se sobrar um `-wal` de outro momento do arquivo — cópia da pasta, restauração
  de backup, sincronizador de nuvem, encerramento à força —, ele é aplicado
  sobre o banco atual e produz `database disk image is malformed` antes mesmo
  de a janela aparecer, com um traceback no lugar de qualquer explicação.
  Foi o que aconteceu aqui: o banco estava íntegro (29.489 itens,
  verificação sem erro) e só o diário de três dias antes derrubava tudo.
- Agora o Licitarium **confere o banco ao abrir**. Diário incompatível é posto
  de lado como `.orfao-<data>` e o programa segue, avisando na tela. Banco
  realmente corrompido é guardado como `.corrompido-<data>` e um novo é criado
  — o acervo volta na sincronização, porque a fonte é o PNCP.
- E ao fechar, o diário é **consolidado no banco**, para não sobrar nada capaz
  de voltar órfão na abertura seguinte.

## 1.5.0 — 2026-08-05

**Análise estatística da pesquisa de preços**

- Ao lado de média e mediana, o resumo passa a mostrar a **faixa central** dos
  preços, o **desvio padrão** e o **coeficiente de variação**, com a leitura
  escrita: até 15% os preços são homogêneos; acima de 50% a amostra é dispersa
  demais e provavelmente tem item não comparável no meio. Os mesmos números
  saem no relatório em PDF.
- **Preço fora da curva é apontado**, pelo critério de Tukey (uma vez e meia a
  faixa central), com a faixa normal escrita no aviso e um botão que descarta
  os itens de uma vez. Nada sai sozinho da conta: desprezar preço coletado é
  decisão de quem assina, e o item continua na lista para conferência.
- Com menos de cinco preços a análise se cala, em vez de apresentar como
  estatística o que seria opinião.

**Filtro por unidade de medida**

- A aba Preços ganhou o filtro **Todas as unidades**, com as grafias já
  agrupadas: *CX*, *Caixa* e *CAIXAS* viram uma opção só. No acervo do piloto
  isso reduz 566 textos distintos a 192 opções, ordenadas da mais comum para a
  mais rara e com a contagem de itens ao lado. A coluna da lista continua
  mostrando o texto original do PNCP.

**Outras melhorias**

- A coluna **Qtde** da aba Preços passa a ordenar, como as demais.

## 1.4.3 — 2026-08-03

- **O aviso de volume dizia um tamanho menor que o real.** Ele previa os MB
  de JSON que viriam do portal, não o quanto o arquivo ia crescer — e o banco
  cobra quase o dobro, entre colunas, índices e busca. Com os cinco
  municípios de referência já coletados (714 contratações, 12.587 itens,
  45,4 MB), as estimativas foram refeitas: agora o aviso fala de espaço em
  disco e a previsão para esses cinco erra 0,5 MB, contra 11 MB antes.

## 1.4.2 — 2026-08-02

- **Tamanho de cada município de referência.** A lista em Configurações passa
  a mostrar quanto cada município ocupa no banco, ao lado da contagem de
  preços. Um vizinho custa de 1 a 15 MB, conforme o quanto publica; agora dá
  para ver qual deles está pesando antes de decidir remover.

## 1.4.1 — 2026-08-02

- **Link para o PNCP no relatório de pesquisa de preços.** O número do
  processo passa a levar à página oficial daquela contratação no portal.
  Em PDF fica clicável; no papel, o número continua legível. Quem recebe o
  levantamento confere cada preço na fonte, em vez de confiar só na tabela.
- **Colunas Município e Unid. deixam de quebrar** no relatório: "Paulo de
  Faria" e "Fardo 64,00 RO" ocupavam duas linhas cada. A coluna de descrição
  cede o espaço.

## 1.4.0 — 2026-08-02

**Escolher quais preços entram na pesquisa**

- Cada linha da aba Preços passa a ter uma **caixa de seleção**, marcada por
  padrão. Desmarque o que não for comparável e o resumo se refaz na hora: o
  item sai do cálculo e do **relatório de pesquisa de preços**, mas continua
  na tela, para dar para voltar atrás.
- Resolve a distorção mais comum: buscar *papel higiênico* traz também
  *suporte de papel higiênico* e *locação de banheiro químico*. No acervo do
  piloto, descartar esses dois derruba a média de R$ 53,63 para R$ 30,74 e o
  maior preço de R$ 249,80 para R$ 33,90.
- Um aviso mostra quantos itens foram descartados, com **Restaurar todos**. A
  escolha vale para a pesquisa em curso; trocar o termo recomeça.

## 1.3.2 — 2026-08-01

- **A coluna Município passa a ordenar**, como as demais da aba Preços. A
  ordem é alfabética pelo nome do município, e não pelo código interno.

## 1.3.1 — 2026-08-01

- **Coluna Município na aba Preços.** A origem de cada preço passa a ter
  coluna própria, sempre visível, em vez de aparecer apenas nos itens vindos
  de fora. Os preços de municípios de referência continuam destacados.
- **Municípios de referência listados como os órgãos monitorados**, com o
  código IBGE e a contagem de preços de cada um. Enquanto a sincronização não
  roda, a lista mostra *ainda sem preços — serão baixados na próxima
  sincronização*.
- As larguras de coluna salvas antes desta versão são descartadas na aba
  Preços, que ganhou uma coluna; as demais abas não mudam.

## 1.3.0 — 2026-08-01

**Municípios de referência no banco de preços**

Um município pequeno compra pouco e compra variado: no acervo do piloto, 98%
das descrições de item aparecem uma única vez. Buscar *papel A4* devolvia um
único preço, e mediana sobre um preço só não sustenta uma pesquisa perante o
Tribunal de Contas.

- Em **Configurações → Municípios de referência** dá para indicar municípios
  vizinhos. Os itens deles passam a aparecer no **banco de preços**, ao lado
  dos seus, com amparo no **art. 23, §1º, I** da Lei 14.133/2021, que admite
  contratações similares de outros entes como parâmetro.
- **A referência não entra em mais nada.** Indicadores da tela inicial, abas
  Contratações, Contratos, Atas e PCA, o módulo Montar PCA e todos os
  relatórios oficiais continuam exclusivamente do seu município.
- Na lista, o preço vindo de fora traz o **nome do município** logo abaixo do
  processo; o resumo informa a composição (*12 do seu município e 47 de
  referência*) e a caixa **Só do meu município** isola a sua série.
- O **relatório de Pesquisa de Preços** ganhou coluna **Município**: valor de
  fora é aceitável, mas precisa estar identificado no documento.
- Cada município da lista mostra quantos preços trouxe. Remover apaga os
  preços dele sem tocar no seu acervo.

> Nem todo vizinho publica no PNCP — na região do piloto, um município de 21
> mil habitantes não tem registro algum. Depois de sincronizar, confira a
> contagem em Configurações.

## 1.2.5 — 2026-08-01

- **Correção da atualização automática da 1.2.4.** Ao publicar um anexo, o
  GitHub troca o espaço do nome do arquivo por ponto: o executável sobe como
  "Licitarium v1.2.4.exe" e fica disponível como **"Licitarium.v1.2.4.exe"**.
  A 1.2.4 procurava o nome com espaço e não encontrava o download, então não
  oferecia a troca automática. Agora os dois formatos são reconhecidos.

## 1.2.4 — 2026-08-01

- **O executável passa a trazer a versão no nome**: o arquivo baixado da
  página de releases se chama **"Licitarium.v1.2.4.exe"**, no mesmo padrão do
  manual. Dá para saber qual versão você tem só de olhar o arquivo, e as
  versões guardadas não se sobrescrevem.
- Ao atualizar sozinho, o programa também **renomeia o arquivo** para a versão
  nova — do contrário o nome passaria a mentir sobre o conteúdo. Se você tiver
  um atalho apontando para o executável, refaça-o depois da primeira
  atualização.

> Quem está na 1.2.3 ou anterior continua recebendo o aviso de versão nova,
> mas precisará **baixar manualmente desta vez**: aquelas versões procuram um
> arquivo com o nome antigo. Da 1.2.4 em diante a atualização automática volta
> a funcionar normalmente.

## 1.2.3 — 2026-08-01

- **Nome do manual em PDF segue o padrão dos sistemas irmãos.** Ao imprimir ou
  salvar o manual, o arquivo sai como **"Manual Operacional — Licitarium
  v1.2.3"**, no mesmo formato usado por SGCD, SGCA, SGDP e SGEA — assim os
  manuais dos cinco ficam juntos e ordenados na pasta. O cabeçalho de cada
  página impressa também acompanha o padrão.

## 1.2.2 — 2026-08-01

- **CNPJ e CPF com máscara nos relatórios.** O documento do fornecedor saía
  como um bloco de dígitos (`13286494000164`) nas relações impressas. Agora
  sai pontuado — e o programa distingue os dois: pessoa jurídica em
  `00.000.000/0000-00`, pessoa física em `000.000.000-00`, porque o campo
  do PNCP guarda os dois tipos. A exportação em CSV continua com o número
  puro, para não atrapalhar quem for tratar os dados em planilha.
- **Selo de vigência centralizado.** Na 1.2.1 o selo passou a acompanhar o
  rodapé da linha e, em contratos de objeto longo, ficava distante demais das
  datas. Voltou ao centro da célula, agora com um espaçamento entre a data e
  o selo.

## 1.2.1 — 2026-08-01

- **Alinhamento do selo de vigência.** Em contratos e atas com objeto longo,
  o selo ficava no meio da linha, longe do nome do fornecedor. Agora ele
  acompanha a última linha da descrição, na mesma altura do fornecedor.

## 1.2.0 — 2026-08-01

**Novidades desta versão**

- **Situação da vigência em contratos e atas.** Cada registro passa a exibir,
  ao lado das datas, um selo com a sua situação: **Vigente** (verde),
  **Vence em N dias** (amarelo, nos 60 dias finais — o mesmo prazo do alerta
  do topo da tela) e **Encerrado** (vermelho). Dá para ver de relance o que
  precisa de atenção sem abrir registro por registro.
- O selo traz sempre o texto junto da cor, e a data completa no rótulo de
  passagem do mouse: quem não distingue as cores, ou imprime em preto e
  branco, continua lendo a informação.

**Correções**

- Os selos de situação (inclusive os das contratações, que já existiam)
  tinham **contraste insuficiente** entre texto e fundo nos temas claros,
  abaixo do mínimo de acessibilidade para textos pequenos. A tinta foi
  escurecida nos três temas até passar no critério AA.

## 1.1.1 — 2026-07-31

Sincronização muito mais rápida. Medido no acervo real, numa atualização
depois de uma semana sem abrir o programa: **de 20 minutos para 33 segundos**,
e de 1.724 para 69 consultas ao PNCP.

**Correções**

- A coleta em paralelo introduzida na 1.1.0 se desligava sozinha e não voltava
  mais: bastavam três recusas do PNCP — comuns logo no início — para o
  programa cair no ritmo lento pelo resto da execução, justamente na etapa
  mais demorada. Agora só contam as recusas recentes, e o ritmo volta ao
  normal assim que o portal se acalma.

**Melhorias**

- **Itens que não mudaram não são mais reconsultados.** O PNCP altera a data
  da contratação por motivos que não têm nada a ver com os itens dela, e isso
  fazia o programa rebuscar o preço de todos eles. Medido: 1.815 consultas
  para nenhum item alterado. Agora a data de cada item é comparada antes.
- **Editais, contratos, atas e PCA são baixados em paralelo**, como já
  acontecia com os itens. A etapa dos editais caiu de 38 s para 4,5 s.

## 1.1.0 — 2026-07-31

Versão de desempenho: a coleta ficou muito mais rápida e a busca do banco de
preços passou a entender palavras soltas.

**Novidades desta versão**

- **Busca por palavras** no banco de preços e na aba Itens: digitar
  `papel a4` encontra `PAPEL SULFITE A4 BRANCO` mesmo com as palavras fora de
  ordem e separadas por outras. Acentos são ignorados (`oleo` acha `ÓLEO`) e
  palavras incompletas valem como início (`sulfit` acha `SULFITE`). A busca
  usa um índice de texto interno, então continua instantânea.
- **Coleta de itens em paralelo**: a primeira sincronização, que percorre
  todos os itens e seus vencedores, deixou de ser feita uma requisição por
  vez. Se o PNCP começar a recusar as conexões, o programa volta sozinho ao
  ritmo antigo.
- **Compactação automática do acervo**: ao final da sincronização, quando o
  arquivo tem muito espaço ocioso, ele é compactado.
- **Organização do código**: a interface, que era um arquivo único de 1.713
  linhas, virou três (`ui/index.html`, `ui/estilo.css`, `ui/app.js`). Nada
  muda para quem usa o programa.
- **Manual com tema**: os três temas do programa (Pergaminho, Portal e
  Observatório) também valem para o manual, com seletor no canto da página.
  O estandarte da capa mantém as cores da marca em qualquer tema, e a
  impressão sai sempre em pergaminho.

## 1.0.0 — 2026-07-31

Primeira versão estável. O acervo, os relatórios para o Tribunal de Contas,
o banco de preços e a montagem do PCA estão completos e em uso real.

**Novidades desta versão**

- **Montar PCA**: novo módulo que usa o histórico de itens contratados para
  sugerir o Plano de Contratações Anual do próximo exercício. Agrupa por
  semelhança de descrição, projeta o quantitativo (média dos anos, último,
  maior ou soma), estima o preço (mediana, média, mais recente ou menor) e
  aplica margem de segurança — tudo configurável, com padrão de 10%.
  Sinaliza unidades divergentes e itens de ocorrência única. A lista é
  editável e os ajustes manuais sobrevivem a uma nova geração.
- Exportação da minuta em CSV e novo relatório **Minuta do PCA**.
- **Revisão em famílias**: os itens são agrupados por tipo (PNEU, FILTRO,
  FRALDA…) e a lista pode ser filtrada por família.
- **Curva ABC**: cada item recebe classe conforme o peso no valor total,
  mostrando onde concentrar a revisão.
- **Mesclar e dividir itens**: junta o que o agrupamento separou
  indevidamente, somando quantidades e ponderando o preço pelo volume; dá
  para desfazer a qualquer momento.
- Novo aviso de **preço disperso** (grupo cujo maior preço é muitas vezes o
  menor, sinal de lote lançado como item único) e agrupamento que ignora
  aberturas de edital como "aquisição de" e "contratação de empresa para".

## 0.9.4 — 2026-07-31

- **Uma única tela de abertura**: a imagem fixa que aparecia logo ao clicar no
  executável foi removida. Fica apenas a tela de abertura do aplicativo, que
  acompanha o tema escolhido. O executável também ficou mais leve.

## 0.9.3 — 2026-07-31

- **Fim da troca de tela na abertura**: a tela de abertura trocava de
  composição no meio do carregamento — nascia numa e era substituída por
  outra ao ler o tema. O tema passou a ser entregue à interface antes de ela
  carregar, então a composição correta aparece já no primeiro instante e
  permanece.

## 0.9.2 — 2026-07-31

- **Tela de abertura no tema certo**: a janela passou a usar armazenamento
  próprio, então a preferência de tema sobrevive ao fechamento do programa —
  antes o navegador embutido abria um perfil novo a cada execução e a tela de
  abertura caía sempre na composição padrão. Na primeira abertura após esta
  atualização, a tela é remontada assim que o tema é lido do banco.

## 0.9.1 — 2026-07-31

- **Correção crítica**: o executável da 0.9.0 abria com "Arquivo não
  encontrado". A tela era carregada por um endereço com parâmetro
  (`index.html?tema=…`) que funciona ao rodar pelo código-fonte, mas dentro
  do executável faz o navegador embutido procurar um arquivo com esse nome
  literal. O tema da tela de abertura passou a ser lido do armazenamento
  local do próprio aplicativo.

## 0.9.0 — 2026-07-30

- **Tela de abertura (splash)** em dois estágios: uma imagem aparece assim que
  o executável é aberto, enquanto o programa se prepara, e em seguida a tela
  de abertura do próprio aplicativo — com composição própria para cada tema
  (Portal: cartão com selo; Pergaminho: cartão com estandarte; Observatório:
  selo com anel). A barra acompanha as etapas reais do carregamento.

- Janela abre **maximizada** por padrão, com opção para desligar nas
  configurações.
- Estado da sincronização e origem dos dados (PNCP · versão) movidos do
  rodapé para o cabeçalho, junto à marca; abas em caixa alta.

## 0.8.0 — 2026-07-30

- **Colunas ajustáveis com o mouse**: arraste a borda direita de um cabeçalho
  para redimensionar e dê duplo clique para ajustar ao conteúdo (autofit),
  em todas as listas. As larguras são salvas por aba e há "Restaurar larguras
  padrão" nas configurações. A coluna de objeto/descrição nunca é reduzida
  abaixo do mínimo legível.
- Nome de fornecedor sem o sufixo societário (LTDA, ME, EPP…) na aba Preços,
  com o nome íntegro no tooltip e nos relatórios.

## 0.7.0 — 2026-07-30

- **Banco de preços municipal**: nova aba **Preços** com os itens de cada
  contratação — descrição, unidade, quantidade, valor unitário homologado e
  fornecedor vencedor. Buscar um termo mostra menor preço, mediana, média,
  maior preço, quantidade de itens e de fornecedores.
- **Relatório de Pesquisa de Preços**: levantamento timbrado do histórico de
  preços unitários homologados para um termo, do menor para o maior, com
  fornecedor e processo de origem — subsídio ao art. 23 da Lei 14.133/2021.
- Coleta de itens como terceira fase da sincronização, só revisitando
  contratação nova ou alterada (controle por `itens_versao`).
- Correção: com o Smart App Control do Windows 11 ativo, a atualização
  automática fica desligada e o exe novo é validado antes de substituir o
  atual (era a causa do erro "Failed to load Python DLL").

## 0.6.0 — 2026-07-29

- **Valor estimado distinguido do homologado**: processos sem homologação
  registrada exibem o valor em itálico com "est." — antes um processo em
  andamento parecia ter valor final.
- **Diálogos com foco**: abrir Relatórios, Configurações ou o detalhe trava a
  rolagem do fundo, leva o foco para o diálogo e prende o Tab nele.
- **Selo no cabeçalho**; barras de rolagem na paleta do tema; badge de
  situação encurtada; título da janela com o município.
- **Rodapé informativo**: "Sincronizado hoje às HH:MM" no lugar do traço.
- **Estado vazio contextual**: oferece sincronizar (acervo vazio) ou limpar
  filtros (busca sem resultado), com o selo em marca d'água.
- **Botão "Limpar filtros"** quando há filtro ativo.
- **Densidade das listas** (Confortável/Compacta) nas configurações.
- **Atualização automática mais resiliente**: valida o tamanho do download e
  reabre o programa se a primeira tentativa falhar (o antivírus varrendo o
  executável recém-escrito podia impedir a abertura).

## 0.5.0 — 2026-07-29

- **PCA corrigido**: o endpoint rejeita datas anteriores a 01/04/2021 (422) e
  responde 200 com corpo vazio quando não há dados — os dois casos derrubavam
  a sincronização. PCAs da Câmara de Orindiúva (2025/2026) agora sincronizam.
- **Relatórios seguem o tema** do app (Portal/Pergaminho/Observatório); a
  impressão usa sempre a paleta clara, seja qual for o tema.
- **Atas com coluna de objeto** (reprojetada do raw com migração automática),
  ordenável e coberta pela busca.
- **Número do contrato normalizado** para numero/ano (0033/26 → 33/2026) na
  lista, no detalhe e na relação.
- **Tamanho da fonte** nas configurações (Pequena a Extra grande).
- **Máscara de dinheiro** nos limites de dispensa.
- **JSON do detalhe formatado e colorido** conforme o tema; objeto do detalhe
  justificado.

## 0.4.0 — 2026-07-29

- **Alerta de Fracionamento** (relatório de uso interno): dispensas somadas
  por unidade × limites do art. 75, parametrizáveis nas configurações, com
  farol de atenção e lista completa para avaliação do gestor.
- **KPIs clicáveis e alertas na home**: cards navegam para as listas; chips
  de contratos/atas vencendo em 60 dias e de processos com propostas abertas.
- **Filtros novos**: "Propostas abertas" (contratações) e "Vigentes"
  (contratos/atas).
- **Atualização automática**: rodando pelo executável, o aviso de versão nova
  baixa, instala e reabre o programa sozinho.
- **Acessibilidade**: auditoria de contraste (21/21 pares AA nos 3 temas) e
  nomes acessíveis nos diálogos.
- **Qualidade**: suíte E2E (Playwright) com a ponte mockada no CI;
  screenshots dos 3 temas no README.

## 0.3.0 — 2026-07-29

- **Relatórios** (botão próprio): Relação de Contratações (TCE, com amparo
  legal e deságio), Relação de Contratos, Relação de Atas e Resumo Executivo
  Anual — HTML timbrado imprimível (nome do PDF correto) + CSV nas relações.
- **Filtro por órgão** na listagem (4 abas) e nos relatórios — prefeitura,
  câmara e demais órgãos separáveis; nome do órgão no cabeçalho e no nome do
  arquivo dos relatórios filtrados.
- **Números humanos**: contratações (nº/ano em coluna própria), contratos
  (0033/26/2026) e atas (13/2026) exibem o número do instrumento em vez do id
  longo do PNCP, com ordenação cronológica real; migração automática reprojeta
  bancos existentes a partir do raw.
- **Tratamento estético** nas listas e relatórios: colunas curtas
  centralizadas nos dois eixos, objeto justificado com hifenização, zebra
  sutil, dígitos tabulares.
- **Largura da página** (Compacta/Expandida) nas configurações, como no SGCD.
- Link "Ver no PNCP" das atas abre a página da própria ata (antes era
  genérico); busca ampliada (fornecedor e números de instrumento).

## 0.2.0 — 2026-07-29

- **PCA**: 4ª aba com os itens do Plano de Contratações Anual por órgão
  (endpoint `/v1/pca/atualizacao`; atenção: usa `dataInicio`/`dataFim`,
  diferente dos demais). Itens achatados com contexto do plano.
- **Ordenação por clique** no cabeçalho de todas as listas (whitelist de
  colunas no backend; ▲/▼ com aria-sort).
- **Objetos em caixa alta** nas listas e no detalhe.
- **Aviso de versão nova**: checagem da última release do GitHub ao abrir,
  com link no rodapé; falha em silêncio.
- Busca dos contratos agora cobre também o fornecedor.

## 0.1.2 — 2026-07-29

- Nova tentativa de arquivamento no Zenodo após reset do vínculo GitHub↔Zenodo
  (indisponibilidade do serviço travou o arquivamento das v0.1.0/v0.1.1 —
  afetou também os demais sistemas da família no mesmo período).

## 0.1.1 — 2026-07-29

- Versão no título do MANUAL.html (nome sugerido do PDF na impressão) e no
  cabeçalho impresso de página.
- `.zenodo.json` com metadados explícitos (o arquivamento automático da
  v0.1.0 no Zenodo falhou por metadados).

## 0.1.0 — 2026-07-29

Primeira versão funcional.

- Sync em 2 fases com o PNCP: contratações por município (todas as modalidades
  da Lei 14.133) e contratos/atas por CNPJ dos órgãos descobertos.
- Sync incremental ao abrir, com catch-up desde a última execução e bootstrap
  histórico desde 2021 na primeira configuração.
- Wizard de primeira execução com os 5.571 municípios do IBGE embutidos.
- Listagem com filtros (ano, modalidade, situação, busca no objeto), detalhe
  completo com JSON bruto do PNCP e link para a página oficial.
- KPIs (contratações, total homologado no ano, contratos vigentes).
- Órgãos monitorados: descoberta automática + cadastro manual por CNPJ.
- Exportação CSV do filtro atual.
- Três temas (Portal, Pergaminho, Observatório); identidade Licitarium completa
  (ver design/IDENTIDADE.md).
- Cliente PNCP só com stdlib: pacing de 0,5 s entre requisições, retry com
  backoff e respeito a Retry-After.
