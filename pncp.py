"""Cliente da API de consulta do PNCP e motor de sincronização do Licitarium.

Só stdlib. Estratégia (DESIGN.md §3): sync em 2 fases —
  1) contratações por codigoMunicipioIbge (loop obrigatório por modalidade);
  2) contratos e atas por CNPJ dos órgãos descobertos na fase 1.
Endpoints /atualizacao permitem sync incremental por data de atualização.
O JSON bruto de cada registro é guardado na coluna `raw` (fonte da verdade);
as demais colunas são projeção para filtro/listagem.
"""
import concurrent.futures
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

BASE = "https://pncp.gov.br/api/consulta"
# itens e resultados por item ficam na API interna do portal, não na de
# consulta; devolvem array puro (sem envelope data/totalPaginas)
BASE_PNCP = "https://pncp.gov.br/api/pncp"
USER_AGENT = "Licitarium/0.1 (repositorio local de contratacoes; open-source)"
DATA_INICIO_PNCP = date(2021, 1, 1)  # portal entrou no ar em ago/2021
# /v1/pca/atualizacao rejeita dataInicio anterior a 01/04/2021 (HTTP 422
# "Data inicial inválida ou anterior a 20210401" — verificado 2026-07-29)
DATA_INICIO_PCA = date(2021, 4, 1)
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
_trava_pacing = threading.Lock()

# a latência do PNCP é de ~0,9 s por chamada e ele tolera conexões
# simultâneas: buscar os resultados de item em paralelo derruba a primeira
# carga de ~20 min para poucos minutos
CONEXOES_PARALELAS = 4
_bloqueios = 0            # 429 observados; se insistirem, volta ao sequencial
_trava_bloqueios = threading.Lock()


def _registrar_bloqueio():
    global _bloqueios
    with _trava_bloqueios:
        _bloqueios += 1


def _paralelismo_atual():
    with _trava_bloqueios:
        return 1 if _bloqueios >= 3 else CONEXOES_PARALELAS


def _get(caminho, params, tentativas=5, base=None, pacing=True):
    """GET com pacing e retry/backoff. Dict do JSON, ou None quando sem dados.

    Com pacing=False a espera entre chamadas é dispensada: quem controla o
    ritmo passa a ser o número de conexões simultâneas.
    """
    global _ultima_req
    url = f"{base or BASE}{caminho}?{urllib.parse.urlencode(params)}"
    for tentativa in range(tentativas):
        if pacing:
            with _trava_pacing:
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
                corpo = resp.read()
                # alguns endpoints (ex.: PCA) devolvem 200 com corpo vazio
                # quando não há registros na janela
                return json.loads(corpo) if corpo.strip() else None
        except urllib.error.HTTPError as e:
            if e.code == 204 or e.code == 404:
                return None  # sem registros para o filtro
            if e.code == 429 and tentativa < tentativas - 1:
                _registrar_bloqueio()
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
            valor_estimado, valor_homologado, data_encerramento_proposta,
            data_publicacao, data_atualizacao, raw, sync_em)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (numero, item.get("anoCompra"), item.get("sequencialCompra"),
         orgao.get("cnpj"), orgao.get("razaoSocial"), unidade.get("nomeUnidade"),
         item.get("modalidadeId"), item.get("modalidadeNome"),
         item.get("situacaoCompraNome"), item.get("objetoCompra"),
         item.get("valorTotalEstimado"), item.get("valorTotalHomologado"),
         item.get("dataEncerramentoProposta"),
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
            numero_contrato, ano_contrato, sequencial_contrato,
            fornecedor_ni, fornecedor_nome, objeto, valor_global,
            vigencia_inicio, vigencia_fim, data_publicacao, data_atualizacao,
            raw, sync_em)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (numero,
         _primeiro(item, "numeroControlePncpCompra", "numeroControlePNCPCompra"),
         orgao.get("cnpj"),
         item.get("numeroContratoEmpenho"), item.get("anoContrato"),
         item.get("sequencialContrato"),
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
            numero_ata, ano_ata, objeto,
            vigencia_inicio, vigencia_fim, data_atualizacao, raw, sync_em)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (numero,
         _primeiro(item, "numeroControlePNCPCompra", "numeroControlePncpCompra"),
         _primeiro(item, "cnpjOrgao", "cnpj"),
         item.get("numeroAtaRegistroPreco"), item.get("anoAta"),
         item.get("objetoContratacao"),
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
            db.commit()  # transação curta por janela: não segurar trava
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
        db.commit()  # transação curta por janela
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
        db.commit()  # transação curta por janela
    return total


def _upsert_pca(db, plano):
    """Achata os itens de um plano (PCA) — contexto do plano vai em cada linha."""
    id_pca = plano.get("idPcaPncp")
    if not id_pca:
        return 0
    agora = datetime.now().isoformat()
    n = 0
    for item in plano.get("itens") or []:
        numero = item.get("numeroItem")
        if numero is None:
            continue
        db.execute(
            """INSERT OR REPLACE INTO pca_itens
               (id, id_pca, ano, orgao_cnpj, unidade, numero_item, descricao,
                categoria, grupo, quantidade, valor_total, data_atualizacao,
                raw, sync_em)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (f"{id_pca}#{numero}", id_pca, plano.get("anoPca"),
             plano.get("orgaoEntidadeCnpj"), plano.get("nomeUnidade"), numero,
             item.get("descricaoItem"), item.get("nomeClassificacaoCatalogo"),
             item.get("grupoContratacaoNome"), item.get("quantidadeEstimada"),
             item.get("valorTotal"), item.get("dataAtualizacao"),
             json.dumps(item, ensure_ascii=False), agora))
        n += 1
    return n


def sync_pca(db, cnpj, inicio, fim, progresso=None):
    """Fase 2: itens do Plano de Contratações Anual de um órgão.

    Atenção: este endpoint usa dataInicio/dataFim — os demais usam
    dataInicial/dataFinal (verificado contra a API real em 2026-07-29).
    """
    total = 0
    inicio = max(inicio, DATA_INICIO_PCA)  # endpoint rejeita datas anteriores
    if inicio > fim:
        return 0
    for a, b in _janelas(inicio, fim):
        for plano in _paginar("/v1/pca/atualizacao",
                              {"dataInicio": _amd(a), "dataFim": _amd(b),
                               "cnpj": cnpj},
                              tamanho_pagina=500):
            total += _upsert_pca(db, plano)
        db.commit()  # transação curta por janela
    return total


def _itens_da_compra(cnpj, ano, sequencial):
    """Itens de uma contratação (endpoint devolve array puro, paginado)."""
    pagina = 1
    while True:
        lote = _get(f"/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/itens",
                    {"pagina": pagina, "tamanhoPagina": 100}, base=BASE_PNCP)
        if not lote:
            return
        yield from lote
        if len(lote) < 100:
            return
        pagina += 1


def _resultado_do_item(cnpj, ano, sequencial, numero_item, pacing=True):
    """Resultado homologado de um item: vencedor e valor unitário fechado."""
    lote = _get(
        f"/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/itens/{numero_item}"
        f"/resultados", {}, base=BASE_PNCP, pacing=pacing)
    if not lote:
        return None
    # o mais recente não cancelado é o que vale
    validos = [r for r in lote if not r.get("dataCancelamento")]
    return (validos or lote)[0]


def _upsert_item(db, contratacao, item, resultado):
    numero = item.get("numeroItem")
    if numero is None:
        return 0
    r = resultado or {}
    db.execute(
        """INSERT OR REPLACE INTO itens
           (id, contratacao_controle, orgao_cnpj, ano, sequencial, numero_item,
            descricao, material_servico, categoria, unidade, quantidade,
            valor_unitario_estimado, valor_total_estimado, tem_resultado,
            valor_unitario_homologado, valor_total_homologado,
            quantidade_homologada, fornecedor_ni, fornecedor_nome,
            fornecedor_porte, data_resultado, situacao, data_atualizacao,
            raw, sync_em)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (f"{contratacao['numero_controle']}#{numero}",
         contratacao["numero_controle"], contratacao["orgao_cnpj"],
         contratacao["ano"], contratacao["sequencial"], numero,
         item.get("descricao"), item.get("materialOuServicoNome"),
         item.get("itemCategoriaNome"), item.get("unidadeMedida"),
         item.get("quantidade"), item.get("valorUnitarioEstimado"),
         item.get("valorTotal"), 1 if item.get("temResultado") else 0,
         r.get("valorUnitarioHomologado"), r.get("valorTotalHomologado"),
         r.get("quantidadeHomologada"), r.get("niFornecedor"),
         r.get("nomeRazaoSocialFornecedor"), r.get("porteFornecedorNome"),
         r.get("dataResultado"), item.get("situacaoCompraItemNome"),
         item.get("dataAtualizacao"),
         json.dumps({"item": item, "resultado": r}, ensure_ascii=False),
         datetime.now().isoformat()))
    return 1


def sync_itens(db, progresso=None, limite=None):
    """Fase 3: itens e resultados das contratações — o banco de preços.

    Custa uma requisição por contratação mais uma por item com resultado, e
    por isso só visita contratação nova ou alterada desde a última coleta
    (itens_versao guarda a dataAtualizacao vigente naquele momento).
    """
    pendentes = [dict(r) for r in db.execute(
        """SELECT numero_controle, orgao_cnpj, ano, sequencial, data_atualizacao
           FROM contratacoes
           WHERE orgao_cnpj IS NOT NULL AND sequencial IS NOT NULL
             AND (itens_versao IS NULL OR itens_versao <> data_atualizacao)
           ORDER BY data_publicacao DESC""")]
    if limite:
        pendentes = pendentes[:limite]
    total = 0
    for i, c in enumerate(pendentes, 1):
        if progresso:
            progresso(f"Itens — contratação {i} de {len(pendentes)}…")
        try:
            itens = list(_itens_da_compra(c["orgao_cnpj"], c["ano"],
                                          c["sequencial"]))
            # os resultados são independentes entre si: buscar em paralelo
            com_resultado = [i for i in itens if i.get("temResultado")]
            resultados = {}
            if com_resultado:
                conexoes = min(_paralelismo_atual(), len(com_resultado))
                paralelo = conexoes > 1
                with concurrent.futures.ThreadPoolExecutor(conexoes) as ex:
                    futuros = {
                        ex.submit(_resultado_do_item, c["orgao_cnpj"],
                                  c["ano"], c["sequencial"], i["numeroItem"],
                                  not paralelo): i["numeroItem"]
                        for i in com_resultado}
                    for f in concurrent.futures.as_completed(futuros):
                        resultados[futuros[f]] = f.result()
            for item in itens:
                total += _upsert_item(db, c, item,
                                      resultados.get(item.get("numeroItem")))
            db.execute("UPDATE contratacoes SET itens_versao=?,"
                       " itens_sync_em=? WHERE numero_controle=?",
                       (c["data_atualizacao"], datetime.now().isoformat(),
                        c["numero_controle"]))
            db.commit()
        except PncpErro:
            db.commit()  # preserva o que já entrou; tenta de novo na próxima
            raise
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
    for tipo, func in (("contratos", sync_contratos), ("atas", sync_atas),
                       ("pca", sync_pca)):  # fase 2, por CNPJ de órgão
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

    # fase 3 — itens das contratações (banco de preços); é a mais custosa,
    # então vem no fim: se falhar, o resto do acervo já está gravado
    try:
        n = sync_itens(db, progresso)
        _config(db, "last_sync_itens", hoje.isoformat())
        _log(db, "itens", hoje, hoje, n, "ok")
        resumo["itens"] = n
    except PncpErro as e:
        _log(db, "itens", hoje, hoje, 0, "erro", str(e))
        resumo["itens"] = None

    # devolve ao disco o espaço que as regravações deixaram para trás
    # (200 páginas ≈ 0,8 MB; VACUUM do acervo municipal leva ~0,1 s)
    if db.execute("PRAGMA freelist_count").fetchone()[0] > 200:
        if progresso:
            progresso("Compactando o acervo…")
        db.execute("VACUUM")
    return resumo
