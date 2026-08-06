<p align="center"><img src="design/estandarte-t3.svg" width="140" alt="Estandarte do Licitarium"></p>

# Licitarium — Repositório Municipal de Contratações Públicas

![Versão](https://img.shields.io/github/v/release/devtulio/licitarium?label=vers%C3%A3o&color=blue) ![Lei](https://img.shields.io/badge/Lei-14.133%2F2021-green) ![Fonte](https://img.shields.io/badge/fonte-PNCP-informational) ![Tecnologia](https://img.shields.io/badge/tecnologia-Python%20%2B%20SQLite-orange) ![Licença](https://img.shields.io/badge/licença-MIT-green) ![Acesso](https://img.shields.io/badge/acesso-desktop%20offline-blueviolet) ![Plataforma](https://img.shields.io/badge/plataforma-Windows-lightgrey) [![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.21682535-1682D4)](https://doi.org/10.5281/zenodo.21682535) [![CI](https://github.com/devtulio/licitarium/actions/workflows/ci.yml/badge.svg)](https://github.com/devtulio/licitarium/actions/workflows/ci.yml)

## Descrição

O **Licitarium** espelha, no computador do órgão, tudo o que o município publica
no [PNCP — Portal Nacional de Contratações Públicas](https://pncp.gov.br):
contratações (editais e avisos), contratos, atas de registro de preços, o Plano
de Contratações Anual (PCA) e os **itens de cada compra, com o preço unitário
pago e o fornecedor vencedor**. O acervo fica pesquisável, offline e permanente.

O problema que ele resolve: consultar o próprio histórico de compras no portal
exige navegar processo a processo, e não há como cruzar preços entre exercícios.
O Licitarium baixa esse histórico uma vez, mantém atualizado sozinho e responde
em milissegundos — inclusive quando o portal está fora do ar.

É um **programa de computador**, não um site: instalação por executável único,
sem servidor, sem porta de rede, sem banco a configurar. Serve a qualquer
prefeitura brasileira — nada é fixo no código quanto ao município. O piloto
roda em Orindiúva-SP.

*Licitarium* — do latim *licitatio* (lance, leilão) + *-arium* (lugar que
guarda): o lugar que guarda as licitações. **SVB · HASTA · PVBLICA.**

![Licitarium — tema Portal](docs/screenshots/portal.png)

<p align="center">
  <img src="docs/screenshots/pergaminho.png" width="49%" alt="Tema Pergaminho">
  <img src="docs/screenshots/observatorio.png" width="49%" alt="Tema Observatório">
</p>

## O que ele faz

### Acervo

Cinco abas, todas com busca, filtros (ano, modalidade, situação, órgão),
ordenação por clique, colunas ajustáveis com o mouse e exportação CSV:

| Aba | Conteúdo |
|---|---|
| **Contratações** | Editais e avisos: pregões, dispensas, inexigibilidades e demais modalidades da Lei 14.133 |
| **Contratos** | Contratos firmados, com fornecedor, valor global e vigência, com selo de situação (vigente / vence em 60 dias / encerrado) |
| **Atas** | Atas de registro de preços, com objeto e vigência, com o mesmo selo de situação |
| **PCA** | Itens do Plano de Contratações Anual de cada órgão |
| **Preços** | Banco de preços: cada item contratado, com unidade, quantidade, valor unitário homologado e fornecedor vencedor |

Clicar em qualquer linha abre o detalhe completo, incluindo o **registro
integral em JSON** exatamente como consta no PNCP, e um link direto para a
página oficial do processo no portal.

Na tela inicial, três indicadores clicáveis (total de contratações, valor
homologado no ano, contratos vigentes) e alertas de **vencimento em 60 dias** e
de **propostas em aberto**.

### Banco de preços

Busca por palavras soltas: `papel a4` encontra `PAPEL SULFITE A4 BRANCO` na
ordem que você digitar, ignorando acentos (`oleo` acha `ÓLEO`) e aceitando
palavra pela metade (`sulfit` acha `SULFITE`). Índice FTS5 interno — resposta
instantânea mesmo com o acervo inteiro.

Para cada termo: **menor preço, mediana, média, maior preço**, quantos itens e
quantos fornecedores — subsídio direto à pesquisa de preços do **art. 23 da Lei
14.133/2021**, com a origem de cada valor rastreável até o processo no PNCP.

A série vem descrita: **faixa central, desvio padrão e coeficiente de
variação**, com a leitura escrita ao lado — acima de 50% de variação, a amostra
provavelmente mistura itens não comparáveis. Preço que destoa é **apontado pelo
critério de Tukey**, nunca removido sozinho: o programa mostra a faixa normal e
oferece o descarte, mas desprezar preço coletado é decisão de quem assina.
O filtro por **unidade de medida** agrupa as grafias do portal — *CX*, *Caixa*
e *CAIXAS* são uma opção só.

**Corrigir pelo IPCA** traz cada preço a valor de hoje pela série 433 do Banco
Central, a partir da data do resultado: R$ 208,04 de março de 2022 equivalem a
R$ 252,06 em junho de 2026. A correção vai até o último mês publicado e o
documento declara qual é — o programa não projeta índice.

**Comparar por conteúdo** desfaz a distorção da embalagem: a caixa de papel A4
com 5.000 folhas sai a R$ 0,0466 por folha e o pacote com 100, a R$ 0,3890 —
8,4 vezes mais caro. O conteúdo é lido do que o órgão publicou, e gramatura,
dimensão ou capacidade de artefato não são confundidas com conteúdo.

Preço descartado sai do cálculo **com a razão registrada**: o relatório traz a
seção *Itens desconsiderados nesta pesquisa*, com o motivo de cada um, e marca
o que ficou sem justificativa. Os descartes ficam gravados por termo, então a
pesquisa pode ser refeita e conferida depois.

**Municípios de referência.** Um município pequeno compra pouco e compra
variado — no acervo do piloto, 98% das descrições aparecem uma única vez, e
mediana sobre um preço só não sustenta pesquisa. Por isso é possível indicar
municípios vizinhos cujos itens alimentam **apenas o banco de preços**, com
amparo no art. 23, §1º, I (contratações similares de outros entes). A origem
de cada valor fica visível na tela e no relatório; o acervo, os indicadores,
o PCA e os demais relatórios continuam exclusivamente do seu município.

Antes de aceitar, o programa consulta quanto o município vai custar em tempo e
em espaço — um vizinho pequeno cabe em minutos e poucos MB, uma cidade média
leva horas e centenas de MB. Depois de coletado, cada um mostra na lista
quanto ocupa no banco.

### Montar PCA

Usa o histórico de itens já contratados para sugerir o **Plano de Contratações
Anual** do exercício seguinte:

- agrupa itens semelhantes por radical da descrição, descartando prefixo
  burocrático ("AQUISIÇÃO DE", "CONTRATAÇÃO DE EMPRESA PARA");
- projeta o quantitativo (média dos anos disponíveis, último, maior ou soma);
- estima o preço (mediana, média, mais recente ou menor);
- aplica margem de segurança — padrão de 10%, editável por item;
- classifica em **curva ABC** e agrupa por **família** (PNEU, FILTRO, FRALDA…);
- sinaliza unidade divergente, ocorrência única e preço disperso;
- permite **mesclar e dividir** grupos, com preço ponderado pelo volume.

A lista é editável e os ajustes manuais sobrevivem a uma nova geração. A
entrega é uma **minuta para revisão**, não um arquivo de importação: os itens
do PNCP não trazem código de catálogo, então a conferência humana é necessária.

### Relatórios

Sete relatórios em HTML timbrado (prontos para imprimir em PDF) e, quando faz
sentido, também em CSV:

| Relatório | Uso |
|---|---|
| Relação de Contratações | Listagem para o Tribunal de Contas, com amparo legal e deságio |
| Relação de Contratos | Contratos do período, por órgão |
| Relação de Atas | Atas de registro de preços e vigências |
| Resumo Executivo Anual | Visão consolidada do exercício |
| Alerta de Fracionamento | Autocontrole: acompanha os limites do art. 75 por unidade |
| Pesquisa de Preços | Levantamento do art. 23, do menor ao maior unitário |
| Minuta do PCA | Plano sugerido, para revisão |

Os relatórios seguem o tema escolhido na tela, mas a **impressão sai sempre
clara**, para não gastar tinta nem prejudicar a leitura em papel.

## Como funciona

- Na primeira execução você escolhe o município (tabela IBGE embutida, 5.571
  municípios) e o Licitarium baixa todo o histórico publicado desde 2021.
- A cada abertura, sincroniza só o que mudou — respeitando um intervalo de 10
  minutos desde a última coleta, porque nada muda no PNCP nesse tempo e repetir
  a busca só sobrecarrega o portal. O botão **Sincronizar** coleta sempre. A
  interface fica utilizável durante a sincronização.
- Os órgãos do município (prefeitura, câmara, fundos…) são **descobertos
  sozinhos** a partir das contratações; você pode acrescentar outros por CNPJ.
- Tudo num banco SQLite local, em `%LOCALAPPDATA%\Licitarium`. O banco é cache
  reconstruível: se corromper, uma nova carga resolve.
- Sem internet, o programa abre normalmente com os dados locais e avisa que não
  conseguiu atualizar.

**Desempenho da sincronização** (acervo real de Orindiúva-SP, atualização
depois de uma semana sem abrir): **33 segundos**, 69 consultas ao portal. As
três fases baixam em paralelo e, dentro de cada contratação, só os itens que
mudaram são reconsultados.

**Quando o portal falha**, quase sempre é lentidão, não recusa: num dia de
medição no acervo do piloto, os 20 erros registrados eram todos tempo de
resposta esgotado — nenhum bloqueio, nenhum erro de servidor. O cliente tenta
cinco vezes, **esperando mais a cada tentativa** (30 a 90 s), sorteia o
intervalo entre elas para as conexões não voltarem em bloco e **reduz o número
de conexões simultâneas** ao perceber o portal sobrecarregado. O que falha fica
registrado e é refeito na coleta seguinte.

**Desempenho do Painel**: a consulta que alimenta as três visões custa ~120 ms
num acervo de 114 MB (3.360 contratações, 25 mil itens); montar e desenhar os
gráficos, ~2 ms. A compactação do banco, que bloqueia leituras, só roda quando
há mais de 5% do arquivo em espaço ocioso.

### Privacidade

O Licitarium **apenas lê** dados públicos do PNCP. Nada do seu computador é
enviado a lugar nenhum, não há telemetria, não há conta de usuário e o programa
não abre porta de rede. As únicas conexões de saída são para `pncp.gov.br` e,
para checar se saiu versão nova, para a API pública do GitHub.

## Instalação

**Executável (recomendado):** baixe o `Licitarium.vX.Y.Z.exe` da página de
[releases](../../releases) e execute. Não precisa instalar nada, nem ter Python,
nem direitos de administrador.

> **Aviso do SmartScreen:** por ser um executável novo e não assinado, o Windows
> pode exibir "aplicativo não reconhecido". Clique em **Mais informações →
> Executar assim mesmo**. O código é aberto — você pode auditar e compilar você
> mesmo.
>
> **Windows 11 com Smart App Control:** essa proteção bloqueia binários sem
> assinatura digital. Com ela ativa, a atualização automática fica desligada
> (o aviso de versão nova leva ao download manual) e o próprio primeiro
> download pode ser barrado. Alternativas: rodar a partir do código-fonte,
> desligar o Smart App Control, ou aguardar uma versão assinada.

**A partir do código:**

```bash
pip install -r requirements.txt
python licitarium.py
```

Requisitos: Windows 10/11 com WebView2 (já incluído no Windows 11; no Windows 10,
[instale o runtime](https://developer.microsoft.com/microsoft-edge/webview2/)).
A única dependência externa é o `pywebview` — todo o resto é biblioteca padrão
do Python.

Manual completo do usuário: [MANUAL.html](MANUAL.html) (abra no navegador; o
botão 🖨 gera o PDF).

## Arquitetura

Um processo só: janela [pywebview](https://pywebview.flowrl.com/) (WebView2)
conversando com o Python por uma ponte `js_api` — sem servidor HTTP, sem porta,
sem firewall. Os dados vêm da API de consulta pública do PNCP; o JSON bruto de
cada registro é guardado como **fonte da verdade**, e as colunas do banco são
projeção dele (campo novo na interface não exige baixar tudo de novo).

```
licitarium.py        entry: janela + classe Api (ponte com o JS)
pncp.py              cliente da API do PNCP + motor de sincronização
pca_builder.py       motor da minuta do PCA (agrupamento, ABC, projeções)
relatorios.py        geração dos relatórios em HTML/CSV
ui/index.html        marcação
ui/estilo.css        três temas por data-theme
ui/app.js            lógica da interface
tests/               pytest — motor de sync com HTTP mockado
tests-e2e/           Playwright — interface com a ponte mockada
```

Decisões de projeto e os fatos da API que as motivaram: [DESIGN.md](DESIGN.md).
Identidade visual e as notas históricas por trás dela (epigrafia romana, tabula
ansata, a divisa *sub hasta publica*): [design/IDENTIDADE.md](design/IDENTIDADE.md).

## Desenvolvimento

```bash
pip install -r requirements.txt pytest
python -m pytest tests/              # motor de sync, API e relatórios
npm install && npx playwright test   # interface (Chromium)
pyinstaller --clean Licitarium.spec  # gera dist/"Licitarium vX.Y.Z.exe"
```

A cada push, o CI roda os testes de Python e de interface no Windows; ao marcar
uma tag `v*`, compila o executável e o anexa à release.

## Sistemas irmãos

Dois programas de desktop com a mesma arquitetura: Python + pywebview + SQLite,
num executável só, sem servidor e sem porta de rede aberta. O Licitarium lê dados
públicos; o Peculium guarda dados pessoais num cofre cifrado.

| Sistema | Cuida de | |
|---|---|---|
| **Licitarium** — Repositório do PNCP | espelho local das contratações públicas do município | **(este)** |
| **Peculium** — Patrimônio Pessoal | carteira de investimentos, custos e imposto | [repositório](https://github.com/devtulio/peculium) |

---

## Painel

A tela inicial resume o exercício em gráficos, em três visões — **Execução**
(como está o ano), **Análise** (o que mudou e onde concentra) e **Vigilância**
(o que precisa de ação). Os alertas ficam acima das três e levam à lista já
filtrada.

Os gráficos são SVG desenhado pelo próprio programa — sem biblioteca e sem
rede —, seguem um método com paleta validada para daltonismo e contraste, e
saem em **A3 paisagem** pelo botão de impressão. As decisões estão em
[design/DASHBOARD.md](design/DASHBOARD.md).

Os gráficos são desenhados na largura real do cartão e redesenhados quando a
janela muda de tamanho; trocar de visão não vai ao banco de novo.

## Cópia do acervo

O banco é um espelho reconstruível do PNCP, mas recoletar **municípios de
referência** custa de minutos a horas cada um. Em Configurações, **Salvar
cópia…** guarda o acervo inteiro num `.zip` e **Restaurar cópia…** o devolve,
conferindo o arquivo antes e preservando o banco anterior.

## Como citar

Cada versão recebe um DOI no Zenodo. O DOI acima resolve sempre para a versão
mais recente; a página do Zenodo lista o DOI específico de cada uma.

> SILVA, T. R. M. **Licitarium: repositório municipal de contratações públicas
> do PNCP**. Zenodo. https://doi.org/10.5281/zenodo.21682535

## Licença

[MIT](LICENSE) — © 2026 Túlio Ribeiro de Moura e Silva.

Os dados exibidos são públicos, originários do Portal Nacional de Contratações
Públicas (PNCP), nos termos da Lei 14.133/2021 e da Lei de Acesso à Informação.
O Licitarium não é um produto oficial do PNCP nem do Governo Federal.
