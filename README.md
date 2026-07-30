<p align="center"><img src="design/estandarte-t3.svg" width="140" alt="Estandarte do Licitarium"></p>

# Licitarium

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21682535.svg)](https://doi.org/10.5281/zenodo.21682535)

**Repositório local de contratações públicas municipais.** O Licitarium espelha,
no seu computador, tudo o que o seu município publica no
[PNCP](https://pncp.gov.br) — contratações (editais e avisos), contratos, atas
de registro de preços, o Plano de Contratações Anual (PCA) e os **itens de cada
compra, com o preço unitário pago e o fornecedor vencedor** — e mantém esse
acervo pesquisável, offline e permanente.

*Licitarium* — do latim *licitatio* (lance, leilão) + *-arium* (lugar que
guarda): o lugar que guarda as licitações. **SVB · HASTA · PVBLICA.**

![Licitarium — tema Portal](docs/screenshots/portal.png)

<p align="center">
  <img src="docs/screenshots/pergaminho.png" width="49%" alt="Tema Pergaminho">
  <img src="docs/screenshots/observatorio.png" width="49%" alt="Tema Observatório">
</p>

## Como funciona

- Na primeira execução você escolhe o município; o Licitarium baixa todo o
  histórico publicado no PNCP desde 2021.
- A cada abertura, sincroniza só o que mudou desde a última vez (e você pode
  sincronizar manualmente quando quiser).
- Os órgãos do município (prefeitura, câmara, fundos…) são descobertos
  automaticamente a partir das contratações; você pode adicionar outros por CNPJ.
- Tudo fica num banco SQLite local. Nenhum dado seu é enviado a lugar algum —
  o Licitarium apenas **lê** dados públicos.
- Busca, filtros por ano/modalidade/situação/órgão, detalhe completo de cada
  registro, link para a página oficial no PNCP e exportação CSV.
- **Banco de preços**: cada item já contratado com valor unitário homologado e
  fornecedor vencedor. Busque "papel A4" e veja menor preço, mediana, média e
  maior preço já pagos — apoio direto à pesquisa de preços do art. 23.
- **Relatórios timbrados** prontos para o Tribunal de Contas: relações de
  contratações (com amparo legal e deságio), contratos e atas, resumo executivo
  anual e pesquisa de preços.
- Três temas: Portal (padrão), Pergaminho e Observatório.

## Instalação

**Executável (recomendado):** baixe o `Licitarium.exe` da página de
[releases](../../releases) e execute. Não precisa instalar nada.

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

## Desenvolvimento

```bash
pip install -r requirements.txt pytest
python -m pytest tests/            # testes do motor de sync (HTTP mockado)
pyinstaller --clean Licitarium.spec  # gera dist/Licitarium.exe
```

Arquitetura e decisões: [DESIGN.md](DESIGN.md).
Identidade visual e notas históricas: [design/IDENTIDADE.md](design/IDENTIDADE.md).

## Licença

[MIT](LICENSE). Dados exibidos são públicos, originários do Portal Nacional de
Contratações Públicas (PNCP) — Lei 14.133/2021.
