<p align="center"><img src="design/estandarte-t3.svg" width="140" alt="Estandarte do Licitarium"></p>

# Licitarium

**Repositório local de contratações públicas municipais.** O Licitarium espelha,
no seu computador, tudo o que o seu município publica no
[PNCP](https://pncp.gov.br) — contratações (editais e avisos), contratos e atas
de registro de preços — e mantém esse acervo pesquisável, offline e permanente.

*Licitarium* — do latim *licitatio* (lance, leilão) + *-arium* (lugar que
guarda): o lugar que guarda as licitações. **SVB · HASTA · PVBLICA.**

## Como funciona

- Na primeira execução você escolhe o município; o Licitarium baixa todo o
  histórico publicado no PNCP desde 2021.
- A cada abertura, sincroniza só o que mudou desde a última vez (e você pode
  sincronizar manualmente quando quiser).
- Os órgãos do município (prefeitura, câmara, fundos…) são descobertos
  automaticamente a partir das contratações; você pode adicionar outros por CNPJ.
- Tudo fica num banco SQLite local. Nenhum dado seu é enviado a lugar algum —
  o Licitarium apenas **lê** dados públicos.
- Busca, filtros por ano/modalidade/situação, detalhe completo de cada registro,
  link para a página oficial no PNCP e exportação CSV.
- Três temas: Portal (padrão), Pergaminho e Observatório.

## Instalação

**Executável (recomendado):** baixe o `Licitarium.exe` da página de
[releases](../../releases) e execute. Não precisa instalar nada.

> **Aviso do SmartScreen:** por ser um executável novo e não assinado, o Windows
> pode exibir "aplicativo não reconhecido". Clique em **Mais informações →
> Executar assim mesmo**. O código é aberto — você pode auditar e compilar você
> mesmo.

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
