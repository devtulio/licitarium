# Changelog

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
