# Changelog

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
