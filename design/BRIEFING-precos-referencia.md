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

**Não medido ainda:** o volume real dos municípios vizinhos. Tentei levantar
Paulo de Faria, Icém, Nova Granada, Palestina e Olímpia enquanto redigia este
briefing, mas o PNCP entrou em instabilidade (timeouts sucessivos) e só
consegui confirmar o nosso próprio (131 contratações desde 2021, em 40 s).
**Antes de implementar, essa medição precisa ser refeita** — ela define se o
banco cresce para 30 MB ou para 300 MB, e se a primeira carga leva minutos ou
uma hora.

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
