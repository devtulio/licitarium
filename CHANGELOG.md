# Changelog

## Não lançado

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
