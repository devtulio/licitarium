"""Licitarium — repositório local de contratações públicas municipais (PNCP).

Entry point: janela pywebview + banco SQLite + ponte Api exposta ao JS.
Versão 0.9.1
"""
import csv
import json
import re
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from datetime import date, datetime
from pathlib import Path

import webview

import pncp
import relatorios

VERSAO = "0.9.1"
# dentro do exe onefile os arquivos ficam na pasta temporária do bundle;
# _MEIPASS é o caminho oficial para chegar até eles
DIR_APP = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
DIR_DADOS = Path.home() / "AppData" / "Local" / "Licitarium"
ARQUIVO_DB = DIR_DADOS / "licitarium.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS config (chave TEXT PRIMARY KEY, valor TEXT);
CREATE TABLE IF NOT EXISTS orgaos (
  cnpj TEXT PRIMARY KEY, razao_social TEXT, ativo INTEGER DEFAULT 1,
  origem TEXT DEFAULT 'descoberto');
CREATE TABLE IF NOT EXISTS contratacoes (
  numero_controle TEXT PRIMARY KEY, ano INTEGER, sequencial INTEGER,
  orgao_cnpj TEXT, orgao_nome TEXT, unidade TEXT,
  modalidade_id INTEGER, modalidade_nome TEXT, situacao TEXT, objeto TEXT,
  valor_estimado REAL, valor_homologado REAL,
  data_encerramento_proposta TEXT,
  data_publicacao TEXT, data_atualizacao TEXT,
  itens_versao TEXT, itens_sync_em TEXT, raw TEXT, sync_em TEXT);
CREATE TABLE IF NOT EXISTS contratos (
  numero_controle TEXT PRIMARY KEY, contratacao_controle TEXT, orgao_cnpj TEXT,
  numero_contrato TEXT, ano_contrato INTEGER, sequencial_contrato INTEGER,
  fornecedor_ni TEXT, fornecedor_nome TEXT, objeto TEXT, valor_global REAL,
  vigencia_inicio TEXT, vigencia_fim TEXT,
  data_publicacao TEXT, data_atualizacao TEXT, raw TEXT, sync_em TEXT);
CREATE TABLE IF NOT EXISTS atas (
  numero_controle TEXT PRIMARY KEY, contratacao_controle TEXT, orgao_cnpj TEXT,
  numero_ata TEXT, ano_ata INTEGER, objeto TEXT,
  vigencia_inicio TEXT, vigencia_fim TEXT, data_atualizacao TEXT,
  raw TEXT, sync_em TEXT);
CREATE TABLE IF NOT EXISTS itens (
  id TEXT PRIMARY KEY, contratacao_controle TEXT, orgao_cnpj TEXT,
  ano INTEGER, sequencial INTEGER, numero_item INTEGER,
  descricao TEXT, material_servico TEXT, categoria TEXT, unidade TEXT,
  quantidade REAL, valor_unitario_estimado REAL, valor_total_estimado REAL,
  tem_resultado INTEGER,
  valor_unitario_homologado REAL, valor_total_homologado REAL,
  quantidade_homologada REAL, fornecedor_ni TEXT, fornecedor_nome TEXT,
  fornecedor_porte TEXT, data_resultado TEXT, situacao TEXT,
  data_atualizacao TEXT, raw TEXT, sync_em TEXT);
CREATE TABLE IF NOT EXISTS pca_itens (
  id TEXT PRIMARY KEY, id_pca TEXT, ano INTEGER, orgao_cnpj TEXT, unidade TEXT,
  numero_item INTEGER, descricao TEXT, categoria TEXT, grupo TEXT,
  quantidade REAL, valor_total REAL, data_atualizacao TEXT,
  raw TEXT, sync_em TEXT);
CREATE TABLE IF NOT EXISTS sync_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT, iniciado_em TEXT, tipo TEXT,
  janela_ini TEXT, janela_fim TEXT, registros INTEGER, status TEXT, erro TEXT);
CREATE INDEX IF NOT EXISTS ix_contratacoes_pub ON contratacoes (data_publicacao);
CREATE INDEX IF NOT EXISTS ix_contratacoes_mod ON contratacoes (modalidade_id);
CREATE INDEX IF NOT EXISTS ix_contratos_pub ON contratos (data_publicacao);
CREATE INDEX IF NOT EXISTS ix_atas_vig ON atas (vigencia_fim);
CREATE INDEX IF NOT EXISTS ix_pca_ano ON pca_itens (ano);
CREATE INDEX IF NOT EXISTS ix_itens_desc ON itens (descricao);
CREATE INDEX IF NOT EXISTS ix_itens_contratacao ON itens (contratacao_controle);
CREATE INDEX IF NOT EXISTS ix_itens_unit ON itens (valor_unitario_homologado);
"""

# whitelists p/ valores vindos do JS (tipo, coluna de ordenação)
TABELAS = {"contratacoes": "contratacoes", "contratos": "contratos",
           "atas": "atas", "pca": "pca_itens", "itens": "itens"}
CHAVES = {"pca": "id", "itens": "id"}  # demais usam numero_controle
ORDENAVEIS = {
    "contratacoes": {"numero": "(ano*100000+COALESCE(sequencial,0))",
                     "modalidade": "modalidade_nome", "objeto": "objeto",
                     "valor": "COALESCE(valor_homologado, valor_estimado)",
                     "situacao": "situacao"},
    "contratos": {"numero":
                  "(COALESCE(ano_contrato,0)*100000+COALESCE(sequencial_contrato,0))",
                  "objeto": "objeto",
                  "vigencia": "vigencia_fim", "valor": "valor_global"},
    "atas": {"numero":
             "(COALESCE(ano_ata,0)*100000+CAST(COALESCE(numero_ata,'0') AS INTEGER))",
             "origem": "contratacao_controle", "objeto": "objeto",
             "vigencia": "vigencia_fim"},
    "pca": {"item": "numero_item", "descricao": "descricao",
            "categoria": "categoria", "quantidade": "quantidade",
            "valor": "valor_total"},
    "itens": {"descricao": "descricao", "unidade": "unidade",
              "unitario": "COALESCE(valor_unitario_homologado,"
                          " valor_unitario_estimado)",
              "fornecedor": "fornecedor_nome", "data": "data_resultado",
              "origem": "(ano*100000+COALESCE(sequencial,0))"},
}
PADRAO_ORDEM = {"contratacoes": "data_publicacao DESC",
                "contratos": "data_publicacao DESC",
                "atas": "vigencia_fim DESC",
                "pca": "ano DESC, numero_item",
                "itens": "data_resultado DESC, id"}


def abrir_db():
    # ponytail: conexão nova por operação — chamadas vêm de threads distintas
    # (js bridge + thread de sync) e o volume municipal não justifica pool
    DIR_DADOS.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(ARQUIVO_DB)
    db.row_factory = sqlite3.Row
    # migrações: atas e contratos ganharam o número humano como colunas
    # (0.2.x); bancos antigos são reprojetados do raw (fonte da verdade)
    colunas_atas = {r[1] for r in db.execute("PRAGMA table_info(atas)")}
    if colunas_atas and "numero_ata" not in colunas_atas:
        db.execute("ALTER TABLE atas ADD COLUMN numero_ata TEXT")
        db.execute("ALTER TABLE atas ADD COLUMN ano_ata INTEGER")
        db.execute("UPDATE atas SET"
                   " numero_ata=json_extract(raw,'$.numeroAtaRegistroPreco'),"
                   " ano_ata=json_extract(raw,'$.anoAta')")
        db.commit()
    colunas_a = {r[1] for r in db.execute("PRAGMA table_info(atas)")}
    if colunas_a and "objeto" not in colunas_a:
        db.execute("ALTER TABLE atas ADD COLUMN objeto TEXT")
        db.execute("UPDATE atas SET"
                   " objeto=json_extract(raw,'$.objetoContratacao')")
        db.commit()
    colunas_c = {r[1] for r in db.execute("PRAGMA table_info(contratacoes)")}
    if colunas_c and "itens_versao" not in colunas_c:
        # controle da coleta de itens: só revisita contratação alterada
        db.execute("ALTER TABLE contratacoes ADD COLUMN itens_versao TEXT")
        db.execute("ALTER TABLE contratacoes ADD COLUMN itens_sync_em TEXT")
        db.commit()
    if colunas_c and "data_encerramento_proposta" not in colunas_c:
        db.execute("ALTER TABLE contratacoes"
                   " ADD COLUMN data_encerramento_proposta TEXT")
        db.execute("UPDATE contratacoes SET data_encerramento_proposta="
                   "json_extract(raw,'$.dataEncerramentoProposta')")
        db.commit()
    colunas_ct = {r[1] for r in db.execute("PRAGMA table_info(contratos)")}
    if colunas_ct and "numero_contrato" not in colunas_ct:
        db.execute("ALTER TABLE contratos ADD COLUMN numero_contrato TEXT")
        db.execute("ALTER TABLE contratos ADD COLUMN ano_contrato INTEGER")
        db.execute("ALTER TABLE contratos ADD COLUMN sequencial_contrato INTEGER")
        db.execute("UPDATE contratos SET"
                   " numero_contrato=json_extract(raw,'$.numeroContratoEmpenho'),"
                   " ano_contrato=json_extract(raw,'$.anoContrato'),"
                   " sequencial_contrato=json_extract(raw,'$.sequencialContrato')")
        db.commit()
    # WAL + busy_timeout: a thread de sync grava enquanto a ponte JS lê/grava
    # config — sem isso, "database is locked" na primeira concorrência
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=10000")
    db.executescript(SCHEMA)
    return db


class Api:
    """Métodos chamados do JS via window.pywebview.api.*"""

    def __init__(self):
        # _janela: o prefixo é obrigatório — pywebview expõe e inspeciona todo
        # atributo público do js_api, e a janela nativa entra em recursão
        self._janela = None  # definida em main()
        self._sync_ativo = threading.Lock()
        self._status = {"rodando": False, "msg": "", "resumo": None, "erro": None}
        self._municipios = None

    # ── estado e configuração ───────────────────────────────────────────

    def get_estado(self):
        db = abrir_db()
        try:
            cfg = {r["chave"]: r["valor"] for r in
                   db.execute("SELECT chave, valor FROM config")}
            return {"versao": VERSAO,
                    "municipio": cfg.get("municipio_nome"),
                    "uf": cfg.get("municipio_uf"),
                    "ibge": cfg.get("municipio_ibge"),
                    "tema": cfg.get("tema", "portal"),
                    "largura": cfg.get("largura", "compacta"),
                    "fonte": cfg.get("fonte", "normal"),
                    "densidade": cfg.get("densidade", "confortavel"),
                    "colunas": cfg.get("colunas", "{}"),
                    "maximizar": cfg.get("maximizar", "1"),
                    "limite_dispensa_compras":
                        cfg.get("limite_dispensa_compras",
                                str(relatorios.LIMITE_PADRAO_COMPRAS)),
                    "limite_dispensa_obras":
                        cfg.get("limite_dispensa_obras",
                                str(relatorios.LIMITE_PADRAO_OBRAS)),
                    "last_sync": cfg.get("last_sync_contratacoes"),
                    "sincronizado_em": db.execute(
                        "SELECT MAX(iniciado_em) FROM sync_log"
                        " WHERE status='ok'").fetchone()[0],
                    "kpis": self._kpis(db)}
        finally:
            db.close()

    def _kpis(self, db):
        ano = str(date.today().year)
        hoje = date.today().isoformat()
        n_contratacoes = db.execute(
            "SELECT COUNT(*) FROM contratacoes").fetchone()[0]
        homologado_ano = db.execute(
            "SELECT COALESCE(SUM(valor_homologado),0) FROM contratacoes "
            "WHERE substr(data_publicacao,1,4)=?", (ano,)).fetchone()[0]
        vigentes = db.execute(
            "SELECT COUNT(*) FROM contratos WHERE substr(vigencia_fim,1,10)>=?",
            (hoje,)).fetchone()[0]
        vencendo_60 = db.execute(
            "SELECT (SELECT COUNT(*) FROM contratos WHERE date(vigencia_fim)"
            " BETWEEN date('now') AND date('now','+60 day')) +"
            " (SELECT COUNT(*) FROM atas WHERE date(vigencia_fim)"
            " BETWEEN date('now') AND date('now','+60 day'))").fetchone()[0]
        propostas_abertas = db.execute(
            "SELECT COUNT(*) FROM contratacoes"
            " WHERE datetime(data_encerramento_proposta) >= datetime('now')"
        ).fetchone()[0]
        return {"contratacoes": n_contratacoes,
                "homologado_ano": homologado_ano, "vigentes": vigentes,
                "vencendo_60": vencendo_60,
                "propostas_abertas": propostas_abertas}

    def set_titulo(self, texto):
        if self._janela:
            self._janela.set_title(texto)
        return True

    def set_config(self, chave, valor):
        if chave not in ("tema", "largura", "fonte", "densidade",
                         "colunas", "maximizar", "limite_dispensa_compras",
                         "limite_dispensa_obras"):
            return False
        db = abrir_db()
        try:
            pncp._config(db, chave, valor)
            return True
        finally:
            db.close()

    # ── wizard / município ──────────────────────────────────────────────

    def municipios(self, texto, uf=None):
        if self._municipios is None:
            with open(DIR_APP / "ui" / "municipios.json", encoding="utf-8") as f:
                self._municipios = json.load(f)
        texto = (texto or "").strip().lower()
        achados = [m for m in self._municipios
                   if texto in m["n"].lower() and (not uf or m["uf"] == uf)]
        return achados[:12]

    def configurar_municipio(self, codigo, nome, uf):
        db = abrir_db()
        try:
            pncp._config(db, "municipio_ibge", str(codigo))
            pncp._config(db, "municipio_nome", nome)
            pncp._config(db, "municipio_uf", uf)
        finally:
            db.close()
        return True

    def trocar_municipio(self, codigo, nome, uf):
        """Troca = reinicia o acervo (banco é cache reconstruível)."""
        db = abrir_db()
        try:
            for tabela in ("contratacoes", "contratos", "atas", "orgaos",
                           "sync_log"):
                db.execute(f"DELETE FROM {tabela}")
            db.execute("DELETE FROM config WHERE chave LIKE 'last_sync_%'")
            db.commit()
        finally:
            db.close()
        return self.configurar_municipio(codigo, nome, uf)

    # ── órgãos ──────────────────────────────────────────────────────────

    def listar_orgaos(self):
        db = abrir_db()
        try:
            return [dict(r) for r in db.execute(
                "SELECT cnpj, razao_social, ativo, origem FROM orgaos "
                "ORDER BY razao_social")]
        finally:
            db.close()

    def set_orgao_ativo(self, cnpj, ativo):
        db = abrir_db()
        try:
            db.execute("UPDATE orgaos SET ativo=? WHERE cnpj=?",
                       (1 if ativo else 0, cnpj))
            db.commit()
            return True
        finally:
            db.close()

    def add_orgao(self, cnpj, nome):
        cnpj = "".join(c for c in (cnpj or "") if c.isdigit())
        if len(cnpj) != 14:
            return {"ok": False, "erro": "CNPJ deve ter 14 dígitos"}
        db = abrir_db()
        try:
            db.execute(
                "INSERT OR IGNORE INTO orgaos (cnpj, razao_social, ativo, origem)"
                " VALUES (?,?,1,'manual')", (cnpj, nome or cnpj))
            db.commit()
            return {"ok": True}
        finally:
            db.close()

    # ── listagem e detalhe ──────────────────────────────────────────────

    def listar(self, tipo, filtros=None, pagina=1):
        tabela = TABELAS.get(tipo)
        if not tabela:
            return {"itens": [], "total": 0}
        f = filtros or {}
        where, args = [], []
        if f.get("ano"):
            if tipo == "itens":
                where.append("ano=?")
                args.append(f["ano"])
            elif tipo in ("contratacoes", "pca"):
                # ano do processo/plano, não da publicação: o PNCP reescreve
                # dataPublicacaoPncp quando o órgão atualiza um processo,
                # jogando um "36/2024" para o ano corrente
                where.append("ano=?")
                args.append(f["ano"])
            else:
                coluna = "vigencia_inicio" if tipo == "atas" else "data_publicacao"
                where.append(f"substr({coluna},1,4)=?")
                args.append(str(f["ano"]))
        if f.get("modalidade") and tipo == "contratacoes":
            where.append("modalidade_id=?")
            args.append(f["modalidade"])
        if f.get("situacao") and tipo == "contratacoes":
            where.append("situacao=?")
            args.append(f["situacao"])
        if f.get("orgao"):
            where.append("orgao_cnpj=?")
            args.append(f["orgao"])
        if f.get("vigentes") and tipo in ("contratos", "atas"):
            where.append("date(vigencia_fim) >= date('now')")
        if f.get("propostas") and tipo == "contratacoes":
            where.append(
                "datetime(data_encerramento_proposta) >= datetime('now')")
        if f.get("so_homologados") and tipo == "itens":
            where.append("valor_unitario_homologado IS NOT NULL")
        if f.get("busca"):
            campos = {"contratacoes": ["objeto", "numero_controle"],
                      "contratos": ["objeto", "fornecedor_nome",
                                    "numero_controle", "numero_contrato"],
                      "atas": ["numero_controle", "numero_ata", "objeto"],
                      "pca": ["descricao", "grupo"],
                      "itens": ["descricao", "fornecedor_nome"]}[tipo]
            where.append("(" + " OR ".join(f"{c} LIKE ?" for c in campos) + ")")
            args += [f"%{f['busca']}%"] * len(campos)
        sql_where = (" WHERE " + " AND ".join(where)) if where else ""
        # ordenação por clique: só colunas da whitelist entram no SQL
        ordem = PADRAO_ORDEM[tipo]
        coluna_ord = ORDENAVEIS[tipo].get(f.get("ord") or "")
        if coluna_ord:
            direcao = "ASC" if f.get("dir") == "asc" else "DESC"
            ordem = f"{coluna_ord} {direcao}"
        db = abrir_db()
        try:
            total = db.execute(
                f"SELECT COUNT(*) FROM {tabela}{sql_where}", args).fetchone()[0]
            linhas = db.execute(
                f"SELECT * FROM {tabela}{sql_where} ORDER BY {ordem} "
                f"LIMIT 50 OFFSET ?", args + [(max(1, pagina) - 1) * 50])
            itens = []
            for r in linhas:
                d = dict(r)
                d.pop("raw", None)  # listagem não precisa do JSON completo
                itens.append(d)
            return {"itens": itens, "total": total}
        finally:
            db.close()

    def detalhe(self, tipo, numero_controle):
        tabela = TABELAS.get(tipo)
        if not tabela:
            return None
        chave = CHAVES.get(tipo, "numero_controle")
        db = abrir_db()
        try:
            r = db.execute(f"SELECT * FROM {tabela} WHERE {chave}=?",
                           (numero_controle,)).fetchone()
            if not r:
                return None
            d = dict(r)
            d["raw"] = json.loads(d["raw"]) if d.get("raw") else {}
            return d
        finally:
            db.close()

    def estatisticas_preco(self, busca, ano=None):
        """Resumo do valor unitário homologado para um termo — a resposta de
        'quanto pagamos por isso?' que instrui a pesquisa de preços."""
        if not (busca or "").strip():
            return None
        where = ["valor_unitario_homologado IS NOT NULL", "descricao LIKE ?"]
        args = [f"%{busca.strip()}%"]
        if ano:
            where.append("ano=?")
            args.append(ano)
        db = abrir_db()
        try:
            valores = [r[0] for r in db.execute(
                "SELECT valor_unitario_homologado FROM itens WHERE "
                + " AND ".join(where) + " ORDER BY 1", args)]
            if not valores:
                return None
            n = len(valores)
            meio = n // 2
            mediana = (valores[meio] if n % 2
                       else (valores[meio - 1] + valores[meio]) / 2)
            fornecedores = db.execute(
                "SELECT COUNT(DISTINCT fornecedor_ni) FROM itens WHERE "
                + " AND ".join(where), args).fetchone()[0]
            return {"n": n, "minimo": valores[0], "maximo": valores[-1],
                    "media": sum(valores) / n, "mediana": mediana,
                    "fornecedores": fornecedores}
        finally:
            db.close()

    def filtros_disponiveis(self):
        db = abrir_db()
        try:
            anos = [r[0] for r in db.execute(
                "SELECT DISTINCT ano FROM contratacoes "
                "WHERE ano IS NOT NULL ORDER BY 1 DESC")]
            situacoes = [r[0] for r in db.execute(
                "SELECT DISTINCT situacao FROM contratacoes "
                "WHERE situacao IS NOT NULL ORDER BY 1")]
            modalidades = [{"id": r[0], "nome": r[1]} for r in db.execute(
                "SELECT DISTINCT modalidade_id, modalidade_nome FROM contratacoes"
                " WHERE modalidade_id IS NOT NULL ORDER BY 2")]
            orgaos = [{"cnpj": r[0], "nome": r[1]} for r in db.execute(
                "SELECT cnpj, razao_social FROM orgaos ORDER BY razao_social")]
            return {"anos": anos, "situacoes": situacoes,
                    "modalidades": modalidades, "orgaos": orgaos}
        finally:
            db.close()

    # ── link oficial ────────────────────────────────────────────────────

    def abrir_pncp(self, tipo, numero_controle):
        if tipo == "pca":
            return False  # PNCP não tem página por item de PCA
        d = self.detalhe(tipo, numero_controle)
        if not d:
            return False
        if tipo == "itens":  # item leva à contratação de origem
            return self.abrir_pncp("contratacoes", d["contratacao_controle"])
        raw = d["raw"]
        orgao = (raw.get("orgaoEntidade") or {}).get("cnpj")
        if tipo == "contratacoes" and orgao:
            url = (f"https://pncp.gov.br/app/editais/{orgao}/"
                   f"{raw.get('anoCompra')}/{raw.get('sequencialCompra')}")
        elif tipo == "contratos" and orgao:
            url = (f"https://pncp.gov.br/app/contratos/{orgao}/"
                   f"{raw.get('anoContrato')}/{raw.get('sequencialContrato')}")
        elif tipo == "atas":
            # numero_controle da ata: CNPJ-1-SEQCOMPRA/ANO-SEQATA
            # página no portal: /app/atas/{cnpj}/{ano}/{seqCompra}/{seqAta}
            # (formato verificado contra o portal real em 2026-07-29)
            m = re.match(r"^(\d{14})-\d+-(\d+)/(\d{4})-(\d+)$",
                         d.get("numero_controle") or "")
            if not m:
                return False
            cnpj, seq_compra, ano, seq_ata = m.groups()
            url = (f"https://pncp.gov.br/app/atas/{cnpj}/{ano}/"
                   f"{int(seq_compra)}/{int(seq_ata)}")
        else:
            return False
        webbrowser.open(url)
        return True

    # ── sincronização ───────────────────────────────────────────────────

    def sincronizar(self):
        if not self._sync_ativo.acquire(blocking=False):
            return False  # já rodando
        threading.Thread(target=self._rodar_sync, daemon=True).start()
        return True

    def _rodar_sync(self):
        try:
            self._status.update(rodando=True, msg="Conectando ao PNCP…",
                                resumo=None, erro=None)
            self._avisar_ui()
            db = abrir_db()
            try:
                ibge = pncp._config(db, "municipio_ibge")
                if not ibge:
                    return
                resumo = pncp.sincronizar_tudo(db, ibge, self._progresso)
                self._status.update(resumo=resumo)
            finally:
                db.close()
        except Exception as e:  # nunca derrubar a thread silenciosamente
            self._status.update(erro=str(e))
        finally:
            self._status.update(rodando=False, msg="")
            self._sync_ativo.release()
            self._avisar_ui(fim=True)

    def _progresso(self, msg):
        self._status["msg"] = msg
        self._avisar_ui()

    def _avisar_ui(self, fim=False):
        if not self._janela:
            return
        evento = "onSyncFim" if fim else "onSyncProgresso"
        payload = json.dumps(self._status, ensure_ascii=False)
        try:
            self._janela.evaluate_js(f"window.{evento} && {evento}({payload})")
        except Exception:
            pass  # janela fechando

    def status_sync(self):
        return self._status

    def ultimo_log(self):
        db = abrir_db()
        try:
            return [dict(r) for r in db.execute(
                "SELECT * FROM sync_log ORDER BY id DESC LIMIT 10")]
        finally:
            db.close()

    # ── relatórios ──────────────────────────────────────────────────────

    def gerar_relatorio(self, tipo, params=None):
        db = abrir_db()
        try:
            municipio = pncp._config(db, "municipio_nome") or "Município"
            uf = pncp._config(db, "municipio_uf") or ""
            if params and params.get("orgao"):
                linha = db.execute(
                    "SELECT razao_social FROM orgaos WHERE cnpj=?",
                    (params["orgao"],)).fetchone()
                if linha:
                    params["orgao_nome"] = linha[0]
            if tipo == "fracionamento":
                params = params or {}
                params["limites"] = {
                    "compras": pncp._config(db, "limite_dispensa_compras"),
                    "obras": pncp._config(db, "limite_dispensa_obras")}
            tema = pncp._config(db, "tema") or "pergaminho"
            resultado = relatorios.gerar(db, tipo, params, municipio, uf,
                                         DIR_DADOS / "relatorios", tema)
        except ValueError as e:
            return {"ok": False, "erro": str(e)}
        finally:
            db.close()
        webbrowser.open(resultado["html"])
        return {"ok": True, **resultado}

    # ── atualização do aplicativo ───────────────────────────────────────

    def checar_atualizacao(self):
        """Compara a versão local com a última release do GitHub.

        Falha em silêncio (sem internet, rate limit): a checagem é cortesia,
        nunca pode atrapalhar o uso.
        """
        try:
            req = urllib.request.Request(
                "https://api.github.com/repos/devtulio/licitarium/releases/latest",
                headers={"User-Agent": pncp.USER_AGENT,
                         "Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(req, timeout=10) as r:
                d = json.load(r)
            tag = (d.get("tag_name") or "").lstrip("v")
            local = [int(x) for x in VERSAO.split(".")]
            remota = [int(x) for x in tag.split(".")] if tag else []
            if remota > local:
                self._atualizacao = d.get("html_url")
                self._asset_url = next(
                    (a.get("browser_download_url") for a in d.get("assets", [])
                     if a.get("name") == "Licitarium.exe"), None)
                # instalação automática só faz sentido rodando como exe e
                # sem Smart App Control barrando o binário novo
                auto = bool(self._asset_url and getattr(sys, "frozen", False)
                            and not self._sac_ativo())
                return {"nova": tag, "auto": auto}
        except Exception:
            pass
        return None

    @staticmethod
    def _sac_ativo():
        """Smart App Control do Windows 11 (bloqueia binário sem assinatura
        nem reputação). Com ele ligado a troca automática do exe não completa:
        as DLLs que o onefile extrai são barradas e o início falha em
        "Failed to load Python DLL". Melhor não prometer o que não funciona.
        """
        try:
            import winreg
            with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SYSTEM\CurrentControlSet\Control\CI\Policy") as k:
                # 0=desligado, 1=ativo, 2=avaliação
                return winreg.QueryValueEx(
                    k, "VerifiedAndReputablePolicyState")[0] == 1
        except (ImportError, OSError):
            return False

    def _validar_exe(self, exe, tentativas=3):
        """Roda o exe novo com --verificar antes de confiar nele.

        Vale por dois motivos: se o processo chega a executar Python, o
        empacotamento está íntegro; e a extração da runtime (que o onefile
        faz a cada abertura em %TEMP%\\_MEI<pid>) já aconteceu uma vez, o que
        tira do caminho o antivírus varrendo o binário recém-escrito — a causa
        do "Failed to load Python DLL" que aparecia no primeiro início.
        """
        for tentativa in range(tentativas):
            try:
                r = subprocess.run(
                    [str(exe), "--verificar"], timeout=90,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                if r.returncode == 0:
                    return True
            except (subprocess.TimeoutExpired, OSError):
                pass  # bootloader travado na caixa de erro: mata e repete
            time.sleep(3)
        return False

    def instalar_atualizacao(self):
        """Baixa o exe novo, valida, e troca pelo atual via script que espera
        o app fechar. Só quando rodando como executável (sys.frozen)."""
        if not (getattr(sys, "frozen", False)
                and getattr(self, "_asset_url", None)):
            return {"ok": False, "erro": "instalação automática indisponível"}
        if self._sac_ativo():
            return {"ok": False,
                    "erro": "o Smart App Control do Windows bloqueia programas "
                            "sem assinatura digital — baixe a versão nova pela "
                            "página do projeto"}
        try:
            destino = DIR_DADOS / "update"
            destino.mkdir(parents=True, exist_ok=True)
            novo = destino / "Licitarium.novo.exe"
            req = urllib.request.Request(
                self._asset_url, headers={"User-Agent": pncp.USER_AGENT})
            with urllib.request.urlopen(req, timeout=300) as r:
                esperado = int(r.headers.get("Content-Length") or 0)
                with open(novo, "wb") as f:
                    while bloco := r.read(1024 * 256):
                        f.write(bloco)
            # download truncado viraria um exe quebrado no lugar do bom
            if esperado and novo.stat().st_size != esperado:
                novo.unlink(missing_ok=True)
                return {"ok": False, "erro": "download incompleto"}
            if not self._validar_exe(novo):
                novo.unlink(missing_ok=True)
                return {"ok": False,
                        "erro": "o executável novo não abriu nesta máquina "
                                "(antivírus ou política do Windows) — a versão "
                                "atual foi mantida"}
            bat = destino / "atualizar.bat"
            bat.write_text(_script_atualizacao(Path(sys.executable), novo),
                           encoding="ascii", errors="replace")
            subprocess.Popen(
                ["cmd", "/c", str(bat)],
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                | subprocess.DETACHED_PROCESS,
                close_fds=True)
            # o script espera este processo liberar o exe; fechar a janela
            # encerra o app e deixa a troca acontecer
            threading.Timer(0.5, self._janela.destroy).start()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "erro": str(e)}

    def abrir_atualizacao(self):
        if getattr(self, "_atualizacao", None):
            webbrowser.open(self._atualizacao)
            return True
        return False

    # ── exportação ──────────────────────────────────────────────────────

    def exportar_csv(self, tipo, filtros=None):
        if tipo not in TABELAS:
            return {"ok": False, "erro": "tipo inválido"}
        destino = self._janela.create_file_dialog(
            webview.SAVE_DIALOG, save_filename=f"{tipo}.csv",
            file_types=("CSV (*.csv)",))
        if not destino:
            return {"ok": False, "erro": None}  # cancelado
        caminho = destino if isinstance(destino, str) else destino[0]
        # exporta o filtro atual completo, sem paginação
        db = abrir_db()
        try:
            resultado = self.listar(tipo, filtros, pagina=1)
            total = resultado["total"]
            itens, pagina = [], 1
            while len(itens) < total:
                lote = self.listar(tipo, filtros, pagina)["itens"]
                if not lote:
                    break
                itens += lote
                pagina += 1
            if not itens:
                return {"ok": False, "erro": "nada a exportar"}
            with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.DictWriter(f, fieldnames=itens[0].keys(), delimiter=";")
                w.writeheader()
                w.writerows(itens)
            return {"ok": True, "arquivo": caminho, "linhas": len(itens)}
        finally:
            db.close()


def _script_atualizacao(exe_atual, exe_novo):
    """Gera o .bat que espera o app fechar, troca o exe e reabre.

    A folga antes do start dá tempo de o Windows liberar o arquivo recém
    movido. Não há retry aqui de propósito: quando o bootloader falha, ele
    fica na tela com a caixa de erro, então o processo existe e qualquer
    checagem por tasklist daria falso positivo — a defesa é validar o exe
    antes da troca (ver Api._validar_exe).
    """
    return f"""@echo off
:espera
del "{exe_atual}" >nul 2>&1
if exist "{exe_atual}" (
  timeout /t 1 /nobreak >nul
  goto espera
)
move /y "{exe_novo}" "{exe_atual}" >nul
timeout /t 3 /nobreak >nul
start "" "{exe_atual}"
del "%~f0"
"""


def main():
    api = Api()
    db = abrir_db()
    try:  # título já nasce com o município (a UI reconfirma no boot)
        municipio = pncp._config(db, "municipio_nome")
        uf = pncp._config(db, "municipio_uf")
        # abre maximizado por padrão: as listas são largas
        maximizar = (pncp._config(db, "maximizar") or "1") == "1"
    finally:
        db.close()
    titulo = f"Licitarium — {municipio}/{uf}" if municipio else "Licitarium"
    # caminho simples: o pywebview resolve pelo _MEIPASS dentro do exe.
    # (URI file:// com query string faz o WebView2 procurar um arquivo
    # chamado "index.html?tema=..." e falhar com ERR_FILE_NOT_FOUND)
    api._janela = webview.create_window(
        titulo, str(DIR_APP / "ui" / "index.html"), js_api=api,
        width=1100, height=740, min_size=(900, 600), maximized=maximizar)
    _fechar_splash_nativa()
    webview.start()


def _fechar_splash_nativa():
    """Encerra a imagem que o PyInstaller mostra durante a extração.

    O módulo pyi_splash só existe dentro do exe empacotado; rodando do
    código-fonte não há nada para fechar.
    """
    try:
        import pyi_splash
        pyi_splash.close()
    except Exception:
        pass


if __name__ == "__main__":
    # --verificar: chegar aqui já prova que a runtime empacotada carregou;
    # usado pelo autoupdate para validar e aquecer o exe novo antes da troca
    if "--verificar" in sys.argv:
        print(VERSAO)
        sys.exit(0)
    main()
