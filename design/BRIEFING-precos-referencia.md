# Briefing — Banco de preços com municípios de referência

> Proposta para discussão. Nada implementado. Redigido em 2026-08-01 sobre o
> acervo real de Orindiúva-SP (Licitarium 1.2.5).

## 1. O problema, medido

O banco de preços é o recurso do Licitarium mais alinhado ao seu objetivo —
instruir a pesquisa de preços do **art. 23 da Lei 14.133/2021**. Hoje ele
responde bem para insumos de frota e mal para o resto:

| termo buscado | preços no acervo |
|---|---|
| `filtro ar` | 91 |
| `combustivel` | 45 |
| `oleo lubrificante` | 44 |
| `pneu` | 41 |
| `papel a4` | **1** |
| `caneta` | **1** |
| `cesta basica`, `merenda` | **0** |

São 2.257 itens com preço homologado, mas espalhados em 2.174 descrições
distintas: **98% das descrições aparecem uma única vez**. Mediana de um preço
só é o próprio preço — não sustenta uma pesquisa perante o Tribunal de Contas.

A causa é estrutural, não é defeito de software: um município de 5,4 mil
habitantes compra pouco e compra variado. O acervo próprio nunca terá massa
para a maioria dos itens.

## 2. A proposta

Permitir que o usuário indique **municípios de referência** cujos itens
alimentam **apenas o banco de preços** — sem entrar no acervo oficial do seu
município.

Buscar `papel a4` passaria de 1 preço para dezenas, com a origem de cada um
rastreável até o processo publicado no PNCP.

### Por que é legítimo

O art. 23, §1º, I, admite expressamente, como parâmetro de pesquisa,
**contratações similares feitas pela Administração Pública** — inclusive de
outros entes federativos. O relatório de Pesquisa de Preços passa a citar o
município de origem de cada valor, o que **fortalece** a instrução em vez de
fragilizá-la.

## 3. A regra de ouro do desenho

> Município de referência entra no **banco de preços** e em nada mais.

O que **não** pode mudar, sob nenhuma hipótese:

- os KPIs da tela inicial (contratações, valor homologado, contratos vigentes);
- as abas Contratações, Contratos, Atas e PCA;
- os relatórios oficiais — Relação de Contratações, de Contratos, de Atas,
  Resumo Executivo e Alerta de Fracionamento;
- a montagem do PCA, que projeta o que **o seu órgão** vai contratar.

Misturar município alheio em qualquer um desses itens produziria documento
errado entregue ao Tribunal de Contas. Este é o principal risco do recurso, e
o desenho existe para eliminá-lo.

## 4. Modelo de dados

Uma coluna `municipio_ibge` em `contratacoes` e `itens`, preenchida com o
município de origem, mais um sinalizador `referencia` (0/1) — ou, de forma
equivalente, uma tabela `municipios_referencia` e o vínculo pelo código IBGE.

- Registros do município próprio: `referencia = 0` (todo o comportamento atual).
- Registros de referência: `referencia = 1`.
- **Toda** consulta existente ganha `WHERE referencia = 0`, exceto a busca de
  preços e o relatório de Pesquisa de Preços.

A migração é trivial: bancos atuais recebem `referencia = 0` em tudo.

Os órgãos descobertos na fase 1 dos municípios de referência **não** entram na
tabela `orgaos` (senão apareceriam no filtro de órgão e nos relatórios).

## 5. Sincronização

Para um município de referência só interessam duas das três fases:

| fase | município próprio | referência |
|---|---|---|
| 1 — contratações | sim | **sim** (necessária para chegar nos itens) |
| 2 — contratos, atas, PCA | sim | **não** |
| 3 — itens e preços | sim | **sim** (é o objetivo) |

Dispensar a fase 2 corta um terço do trabalho e todo o armazenamento de
contratos e atas alheios, que não teriam uso.

## 6. Custo — o que está medido e o que falta medir

Medido no acervo próprio (131 contratações, 2.674 itens, 12,8 MB):

- **20,4 itens por contratação**;
- **2,4 KB de JSON bruto por item**;
- contratações + itens somam **6,43 MB** — é a parcela que a referência
  replicaria; contratos, atas e PCA (0,46 MB) ficam de fora.

Regra de bolso resultante: **cada 100 contratações de um município de
referência custam cerca de 5 MB** e, no ritmo atual de sincronização,
poucos minutos na primeira carga.

**Medido em 2026-08-01** (`pncp.estimar_volume`, lendo `totalRegistros` do
envelope — contar paginando levava minutos por município e falhava no maior):

| município | contratações | preços | tamanho | coleta |
|---|---:|---:|---:|---:|
| Paulo de Faria | 223 | ~4.549 | 10,7 MB | 15 min |
| Riolândia | 207 | ~4.223 | 9,9 MB | 14 min |
| Guaraci | 166 | ~3.386 | 7,9 MB | 11 min |
| Icém | 87 (parcial) | ~1.775 | 4,2 MB | 6 min |
| Palestina | 24 | ~490 | 1,1 MB | 2 min |
| Nova Granada | 0 | — | — | — |
| **Olímpia** | **5.982** | **~122.033** | **286 MB** | **6,8 h** |
| *Orindiúva (nosso)* | *131* | *2.674 reais* | *12,8 MB reais* | — |

A estimativa foi conferida contra o acervo real: para Orindiúva prevê 2.672
itens contra 2.674 gravados.

**Decisão (2026-08-01): os cinco vizinhos pequenos entram; Olímpia fica de
fora.** Somados, os cinco são 707 contratações — cerca de 14.400 preços, 34 MB
e 48 minutos de coleta, uma vez. A base de preços sai de 2.257 para perto de
16.600, sete vezes maior. Olímpia sozinha custaria oito vezes mais que os cinco
juntos, em tamanho e em tempo; se um dia for adicionada, o aviso de volume
torna a escolha explícita.

**Duas lições que a medição trouxe:**

- **População não prediz volume.** Nova Granada tem 21 mil habitantes e nenhum
  registro no PNCP; Palestina, 11 mil habitantes e 24 contratações; Riolândia,
  porte parecido e 207. Só a consulta responde — daí o aviso antes de aceitar.
- **Cidade média muda a ordem de grandeza.** O briefing assumiu que referência
  custa alguns MB; isso vale entre vizinhos de porte parecido e não vale para
  uma cidade de 53 mil habitantes. Foi o que motivou o aviso de volume,
  implementado antes da entrega.

### 6.1 Aferição depois da coleta (2026-08-02)

Com os cinco coletados, dá para comparar a previsão com o que de fato entrou.
O tamanho real de cada um foi medido removendo o município de uma cópia do
acervo e comparando o arquivo depois de `VACUUM`:

| município | contratações | itens | JSON | disco real | previsto (antes) |
|---|---:|---:|---:|---:|---:|
| Guaraci | 166 | 3.930 | 8,16 MB | 14,57 MB | 7,9 MB |
| Paulo de Faria | 223 | 3.475 | 6,46 MB | 11,60 MB | 10,7 MB |
| Riolândia | 207 | 2.760 | 6,46 MB | 11,33 MB | 9,9 MB |
| Icém | 94 | 2.009 | 3,69 MB | 6,62 MB | 4,2 MB |
| Palestina | 24 | 413 | 0,72 MB | 1,28 MB | 1,1 MB |
| **total** | **714** | **12.587** | **25,5 MB** | **45,4 MB** | **34 MB** |

Três correções saíram daí:

- **A previsão media JSON, não disco.** Os 34 MB anunciados eram do JSON que
  viria do portal; o arquivo cresceu 45,4 MB. As colunas projetadas, os índices
  e o FTS custam quase tanto quanto o próprio JSON — razão medida entre 1,75 e
  1,80 nos cinco, agora aplicada na estimativa (`FATOR_DISCO`).
- **20,4 itens por contratação era otimista para fora de casa.** Os vizinhos
  dão 17,6 na média (de 13,3 em Riolândia a 23,7 em Guaraci). A constante
  passou a sair das 714 contratações de cinco municípios, não das 131 de um.
- **2,4 KB por item virou 2,1**, medido sobre 12.587 itens.

Recalibrada, a previsão para os cinco daria 45,9 MB contra os 45,4 reais.
O aviso de volume de Olímpia sobe de 286 MB para cerca de 384 MB — a decisão
de deixá-la de fora fica mais fundamentada, não menos.

Uma lição a mais: **estimativa medida num acervo só não vale para os outros.**
A dispersão entre vizinhos de porte parecido (13,3 a 23,7 itens por
contratação) é maior que a diferença entre a média deles e a de casa.

## 7. Interface

- **Configurações → Municípios de referência**: lista com adicionar e remover,
  usando o mesmo autocomplete do assistente de primeira execução. Ao remover,
  os itens daquele município saem do banco.
- **Aba Preços**: coluna e filtro de **origem** (Meu município / Todos), com o
  padrão a definir — sugiro *Todos*, já que o objetivo é ter massa, com o
  município visível em cada linha.
- **Resumo estatístico**: exibir quantos preços vêm do município próprio e
  quantos da referência, para o usuário saber sobre o que está decidindo.
- **Relatório de Pesquisa de Preços**: coluna Município e nota de rodapé
  citando o art. 23, §1º, I.

## 8. Riscos

| risco | mitigação |
|---|---|
| Referência contaminar relatório oficial | `referencia = 0` em todas as consultas oficiais, com teste automatizado que falha se algum relatório trouxer município alheio |
| Primeira carga longa demais | medir antes (§6); sincronizar referência **depois** do acervo próprio e em segundo plano; permitir cancelar |
| Banco crescer demais | limitar quantidade de municípios; guardar dos itens de referência só o necessário, descartando o JSON bruto |
| Comparar o incomparável | a origem sempre visível; o alerta de aderência do manual passa a valer em dobro |
| Preço de outro município ser pior parâmetro | é decisão do usuário, e o filtro de origem permite isolar o próprio município a qualquer momento |

## 9. Implementação sugerida, por etapas

1. **Medir** o volume dos municípios vizinhos (§6) — decide o resto.
2. Coluna `referencia` + migração + `WHERE referencia = 0` nas consultas
   oficiais, com os testes de blindagem. *Sem nenhuma mudança visível ainda.*
3. Sincronização de referência (fases 1 e 3) e tela de configuração.
4. Origem na aba Preços, no resumo estatístico e no relatório.

A etapa 2 é a que protege os documentos oficiais e pode ser entregue e
verificada sozinha, antes de existir qualquer município de referência.

## 10. Fora de escopo

- Acervo completo de outro município (contratos, atas, PCA) — o Licitarium
  continua sendo **o repositório do seu município**.
- Comparação automática com preços de fora do PNCP.
- Ranking ou avaliação de fornecedores de outros entes.
