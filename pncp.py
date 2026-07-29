"""Cliente da API de consulta do PNCP e motor de sincronização do Licitarium.

Só stdlib. Estratégia (DESIGN.md §3): sync em 2 fases —
  1) contratações por codigoMunicipioIbge (loop obrigatório por modalidade);
  2) contratos e atas por CNPJ dos órgãos descobertos na fase 1.
Endpoints /atualizacao permitem sync incremental por data de atualização.
O JSON bruto de cada registro é guardado na coluna `raw` (fonte da verdade);
as demais colunas são projeção para filtro/listagem.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

BASE = "https://pncp.gov.br/api/consulta"
USER_AGENT = "Licitarium/0.1 (repositorio local de contratacoes; open-source)"
DATA_INICIO_PNCP = date(2021, 1, 1)  # portal entrou no ar em ago/2021
JANELA_MAX_DIAS = 364  # API limita o range de datas por consulta

# Tabela de domínio do PNCP — modalidades da Lei 14.133/2021.
# /v1/contratacoes/* exige codigoModalidadeContratacao, daí o loop.
MODALIDADES = {
    1: "Leilão eletrônico",
    2: "Diálogo competitivo",
    3: "Concurso",
    4: "Concorrência eletrônica",
    5: "Concorrência presencial",
    6: "Pregão eletrônico",
    7: "Pregão presencial",
    8: "Dispensa de licitação",
    9: "Inexigibilidade",
    10: "Manifestação de interesse",
    11: "Pré-qualificação",
    12: "Credenciamento",
    13: "Leilão presencial",
}


class PncpErro(Exception):
    """Falha de comunicação com o PNCP após esgotar as tentativas."""


_INTERVALO_MIN = 0.5  # s entre requisições — o PNCP tem throttling agressivo
_ultima_req = 0.0


def _get(caminho, params, tentativas=5):
    """GET com pacing e retry/backoff. Dict do JSON, ou None quando sem dados."""
    global _ultima_req
    url = f"{BASE}{caminho}?{urllib.parse.urlencode(params)}"
    for tentativa in range(tentativas):
        espera = _INTERVALO_MIN - (time.monotonic() - _ultima_req)
        if espera > 0:
            time.sleep(espera)
        _ultima_req = time.monotonic()
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status == 204:
                    return None
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code == 204 or e.code == 404:
                return None  # sem registros para o filtro
            if e.code == 429 and tentativa < tentativas - 1:
                retry_after = e.headers.get("Retry-After")
                time.sleep(int(retry_after) if (retry_after or "").isdigit()
                           else 5 * (tentativa + 1))
                continue
            if e.code in (500, 502, 503, 504) and tentativa < tentativas - 1:
                time.sleep(2 ** tentativa)
                continue
            raise PncpErro(f"HTTP {e.code} em {caminho}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if tentativa < tentativas - 1:
                time.sleep(2 ** tentativa)
                continue
            raise PncpErro(f"sem conexão com o PNCP ({e})") from e


def _paginar(caminho, params, tamanho_pagina):
    """Itera todos os registros de todas as páginas de uma consulta."""
    pagina = 1
    while True:
        dados = _get(caminho, {**params, "pagina": pagina,
                               "tamanhoPagina": tamanho_pagina})
        if not dados or not dados.get("data"):
            return
        yield from dados["data"]
        if pagina >= dados.get("totalPaginas", 1):
            return
        pagina += 1


def _janelas(inicio, fim, max_dias=JANELA_MAX_DIAS):
    """Fatia [inicio, fim] em janelas de no máximo max_dias."""
    atual = inicio
    while atual <= fim:
        ate = min(atual + timedelta(days=max_dias - 1), fim)
        yield atual, ate
        atual = ate + timedelta(days=1)


def _amd(d):
    return d.strftime("%Y%m%d")


def _primeiro(item, *chaves):
    """Primeiro valor não-nulo entre variantes de grafia de campo da API."""
    for chave in chaves:
        if item.get(chave) is not None:
            return item[chave]
    return None


# ── upserts (raw sempre guardado; INSERT OR REPLACE é idempotente) ──────────

def _upsert_contratacao(db, item):
    numero = item.get("numeroControlePNCP")
    if not numero:
        return False
    orgao = item.get("orgaoEntidade") or {}
    unidade = item.get("unidadeOrgao") or {}
    db.execute(
        """INSERT OR REPLACE INTO contratacoes
           (numero_controle, ano, sequencial, orgao_cnpj, orgao_nome, unidade,
            modalidade_id, modalidade_nome, situacao, objeto,
            valor_estimado, valor_homologado, data_publicacao, data_atualizacao,
            raw, sync_em)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (numero, item.get("anoCompra"), item.get("sequencialCompra"),
         orgao.get("cnpj"), orgao.get("razaoSocial"), unidade.get("nomeUnidade"),
         item.get("modalidadeId"), item.get("modalidadeNome"),
         item.get("situacaoCompraNome"), item.get("objetoCompra"),
         item.get("valorTotalEstimado"), item.get("valorTotalHomologado"),
         item.get("dataPublicacaoPncp"), item.get("dataAtualizacao"),
         json.dumps(item, ensure_ascii=False), datetime.now().isoformat()))
    return True


def _upsert_contrato(db, item):
    numero = item.get("numeroControlePNCP")
    if not numero:
        return False
    orgao = item.get("orgaoEntidade") or {}
    db.execute(
        """INSERT OR REPLACE INTO contratos
           (numero_controle, contratacao_controle, orgao_cnpj,
            fornecedor_ni, fornecedor_nome, objeto, valor_global,
            vigencia_inicio, vigencia_fim, data_publicacao, data_atualizacao,
            raw, sync_em)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (numero,
         _primeiro(item, "numeroControlePncpCompra", "numeroControlePNCPCompra"),
         orgao.get("cnpj"),
         item.get("niFornecedor"), item.get("nomeRazaoSocialFornecedor"),
         item.get("objetoContrato"), item.get("valorGlobal"),
         _primeiro(item, "dataVigenciaInicio", "vigenciaInicio"),
         _primeiro(item, "dataVigenciaFim", "vigenciaFim"),
         item.get("dataPublicacaoPncp"), item.get("dataAtualizacao"),
         json.dumps(item, ensure_ascii=False), datetime.now().isoformat()))
    return True


def _upsert_ata(db, item):
    numero = _primeiro(item, "numeroControlePNCPAta", "numeroControlePNCP")
    if not numero:
        return False
    db.execute(
        """INSERT OR REPLACE INTO atas
           (numero_controle, contratacao_controle, orgao_cnpj,
            vigencia_inicio, vigencia_fim, data_atualizacao, raw, sync_em)
           VALUES (?,?,?,?,?,?,?,?)""",
        (numero,
         _primeiro(item, "numeroControlePNCPCompra", "numeroControlePncpCompra"),
         _primeiro(item, "cnpjOrgao", "cnpj"),
         _primeiro(item, "vigenciaInicio", "dataVigenciaInicio"),
         _primeiro(item, "vigenciaFim", "dataVigenciaFim"),
         _primeiro(item, "dataAtualizacao", "dataAtualizacaoGlobal"),
         json.dumps(item, ensure_ascii=False), datetime.now().isoformat()))
    return True


# ── fases de sincronização ──────────────────────────────────────────────────

def sync_contratacoes(db, codigo_ibge, inicio, fim, progresso=None):
    """Fase 1: contratações do município, por modalidade e janela de datas."""
    total = 0
    for codigo, nome in MODALIDADES.items():
        if progresso:
            progresso(f"Contratações — {nome}…")
        for a, b in _janelas(inicio, fim):
            for item in _paginar("/v1/contratacoes/atualizacao",
                                 {"dataInicial": _amd(a), "dataFinal": _amd(b),
                                  "codigoModalidadeContratacao": codigo,
                                  "codigoMunicipioIbge": codigo_ibge},
                                 tamanho_pagina=50):
                total += _upsert_contratacao(db, item)
    db.commit()
    return total


def descobrir_orgaos(db):
    """CNPJs distintos das contratações viram órgãos monitorados."""
    db.execute(
        """INSERT OR IGNORE INTO orgaos (cnpj, razao_social, ativo, origem)
           SELECT DISTINCT orgao_cnpj, orgao_nome, 1, 'descoberto'
           FROM contratacoes WHERE orgao_cnpj IS NOT NULL""")
    db.commit()


def sync_contratos(db, cnpj, inicio, fim, progresso=None):
    """Fase 2: contratos de um órgão (API não filtra por município)."""
    total = 0
    for a, b in _janelas(inicio, fim):
        for item in _paginar("/v1/contratos/atualizacao",
                             {"dataInicial": _amd(a), "dataFinal": _amd(b),
                              "cnpjOrgao": cnpj},
                             tamanho_pagina=500):
            total += _upsert_contrato(db, item)
    db.commit()
    return total


def sync_atas(db, cnpj, inicio, fim, progresso=None):
    """Fase 2: atas de registro de preços de um órgão."""
    total = 0
    for a, b in _janelas(inicio, fim):
        for item in _paginar("/v1/atas/atualizacao",
                             {"dataInicial": _amd(a), "dataFinal": _amd(b),
                              "cnpj": cnpj},
                             tamanho_pagina=500):
            total += _upsert_ata(db, item)
    db.commit()
    return total


def _config(db, chave, valor=None):
    if valor is None:
        linha = db.execute("SELECT valor FROM config WHERE chave=?", (chave,)).fetchone()
        return linha[0] if linha else None
    db.execute("INSERT OR REPLACE INTO config (chave, valor) VALUES (?,?)", (chave, valor))
    db.commit()


def _log(db, tipo, inicio, fim, registros, status, erro=None):
    db.execute(
        """INSERT INTO sync_log (iniciado_em, tipo, janela_ini, janela_fim,
                                 registros, status, erro)
           VALUES (?,?,?,?,?,?,?)""",
        (datetime.now().isoformat(), tipo, inicio.isoformat(), fim.isoformat(),
         registros, status, erro))
    db.commit()


def sincronizar_tudo(db, codigo_ibge, progresso=None):
    """Sync completo incremental. Falha em um tipo não bloqueia os demais.

    Retorna resumo {tipo: registros | None se falhou}.
    """
    hoje = date.today()
    resumo = {}

    def janela_de(tipo):
        ultimo = _config(db, f"last_sync_{tipo}")
        if not ultimo:
            return DATA_INICIO_PNCP
        # 1 dia de sobreposição: garante pegar registros atualizados no
        # exato dia da última sincronização (upsert torna a repetição inócua)
        return date.fromisoformat(ultimo) - timedelta(days=1)

    # fase 1 — contratações por município
    inicio = janela_de("contratacoes")
    try:
        n = sync_contratacoes(db, codigo_ibge, inicio, hoje, progresso)
        _config(db, "last_sync_contratacoes", hoje.isoformat())
        _log(db, "contratacoes", inicio, hoje, n, "ok")
        resumo["contratacoes"] = n
    except PncpErro as e:
        _log(db, "contratacoes", inicio, hoje, 0, "erro", str(e))
        resumo["contratacoes"] = None

    descobrir_orgaos(db)

    # fase 2 — contratos e atas por CNPJ de órgão ativo
    orgaos = [r[0] for r in db.execute(
        "SELECT cnpj FROM orgaos WHERE ativo=1").fetchall()]
    for tipo, func in (("contratos", sync_contratos), ("atas", sync_atas)):
        inicio = janela_de(tipo)
        total, falhou = 0, False
        for cnpj in orgaos:
            if progresso:
                progresso(f"{tipo.capitalize()} — órgão {cnpj}…")
            try:
                total += func(db, cnpj, inicio, hoje, progresso)
            except PncpErro as e:
                falhou = True
                _log(db, tipo, inicio, hoje, total, "erro", f"{cnpj}: {e}")
        if not falhou:
            _config(db, f"last_sync_{tipo}", hoje.isoformat())
            _log(db, tipo, inicio, hoje, total, "ok")
            resumo[tipo] = total
        else:
            resumo[tipo] = None
    return resumo
