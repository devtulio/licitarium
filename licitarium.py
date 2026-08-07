"""Licitarium — repositório local de contratações públicas municipais (PNCP).

Entry point: janela pywebview + banco SQLite + ponte Api exposta ao JS.
A versão vigente é a constante VERSAO, logo abaixo — e só ela.
"""
import csv
import json
import shutil
import re
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import unicodedata
import urllib.request
import webbrowser
import zipfile
from datetime import date, datetime
from pathlib import Path

import webview

import pca_builder
import pncp
import relatorios

VERSAO = "1.13.1"
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
  itens_versao TEXT, itens_sync_em TEXT,
  -- 0 = município do usuário; 1 = município de referência, que alimenta
  -- só o banco de preços e nunca os relatórios oficiais
  referencia INTEGER DEFAULT 0, municipio_ibge TEXT,
  raw TEXT, sync_em TEXT);
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
  data_atualizacao TEXT,
  referencia INTEGER DEFAULT 0, municipio_ibge TEXT,
  raw TEXT, sync_em TEXT);
CREATE TABLE IF NOT EXISTS pca_itens (
  id TEXT PRIMARY KEY, id_pca TEXT, ano INTEGER, orgao_cnpj TEXT, unidade TEXT,
  numero_item INTEGER, descricao TEXT, categoria TEXT, grupo TEXT,
  quantidade REAL, valor_total REAL, data_atualizacao TEXT,
  raw TEXT, sync_em TEXT);
CREATE TABLE IF NOT EXISTS pca_minuta (
  ano_alvo INTEGER PRIMARY KEY, parametros TEXT, gerado_em TEXT);
CREATE TABLE IF NOT EXISTS pca_minuta_itens (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ano_alvo INTEGER, chave TEXT,
  descricao TEXT, unidade TEXT, categoria TEXT, quantidade REAL,
  valor_unitario REAL, margem REAL, incluir INTEGER DEFAULT 1,
  editado INTEGER DEFAULT 0, origem TEXT, mesclado_de TEXT);
-- Itens que o usuário tirou de uma pesquisa de preços e por quê. A IN
-- SEGES 65/2021 exige motivar a desconsideração de preço coletado, e a
-- justificativa tem de acompanhar o documento — por isso vive no banco, e
-- não na tela.
CREATE TABLE IF NOT EXISTS precos_descartes (
  termo TEXT, item_id TEXT, motivo TEXT, criado_em TEXT,
  PRIMARY KEY (termo, item_id));
-- IPCA mensal do Banco Central (série 433), para trazer preço antigo a
-- valor de hoje. Competência no formato AAAA-MM; variação em % do mês.
CREATE TABLE IF NOT EXISTS ipca (
  competencia TEXT PRIMARY KEY, variacao REAL);
CREATE TABLE IF NOT EXISTS municipios_referencia (
  ibge TEXT PRIMARY KEY, nome TEXT, uf TEXT, adicionado_em TEXT);
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
-- busca por palavras soltas nos itens: "papel a4" acha "PAPEL SULFITE A4"
CREATE VIRTUAL TABLE IF NOT EXISTS itens_fts USING fts5(
  descricao, fornecedor_nome, content='itens', content_rowid='rowid');
CREATE TRIGGER IF NOT EXISTS tg_itens_fts_ins AFTER INSERT ON itens BEGIN
  INSERT INTO itens_fts(rowid, descricao, fornecedor_nome)
  VALUES (new.rowid, new.descricao, new.fornecedor_nome);
END;
CREATE TRIGGER IF NOT EXISTS tg_itens_fts_del AFTER DELETE ON itens BEGIN
  INSERT INTO itens_fts(itens_fts, rowid, descricao, fornecedor_nome)
  VALUES ('delete', old.rowid, old.descricao, old.fornecedor_nome);
END;
CREATE TRIGGER IF NOT EXISTS tg_itens_fts_upd AFTER UPDATE ON itens BEGIN
  INSERT INTO itens_fts(itens_fts, rowid, descricao, fornecedor_nome)
  VALUES ('delete', old.rowid, old.descricao, old.fornecedor_nome);
  INSERT INTO itens_fts(rowid, descricao, fornecedor_nome)
  VALUES (new.rowid, new.descricao, new.fornecedor_nome);
END;
"""

# whitelists p/ valores vindos do JS (tipo, coluna de ordenação)
# webview.SAVE_DIALOG foi marcado como obsoleto; FileDialog.SAVE é o
# substituto (mesmo valor). Mantém compatibilidade com versões anteriores.
DIALOGO_SALVAR = getattr(getattr(webview, "FileDialog", None), "SAVE",
                         None) or webview.SAVE_DIALOG
DIALOGO_ABRIR = getattr(getattr(webview, "FileDialog", None), "OPEN",
                        None) or webview.OPEN_DIALOG
# versão do formato da cópia de segurança: muda quando o zip deixar de ser
# lido pelas versões anteriores
ACERVO_SCHEMA = 1

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
              # a quantidade homologada manda; sem resultado, a do edital
              "quantidade": "COALESCE(quantidade_homologada, quantidade)",
              "unitario": "COALESCE(valor_unitario_homologado,"
                          " valor_unitario_estimado)",
              "fornecedor": "fornecedor_nome", "data": "data_resultado",
              # a tabela guarda o código IBGE; ordenar por ele daria uma
              # ordem sem sentido para quem lê, então o nome é resolvido
              # aqui — o do próprio município vem da config
              "municipio": "COALESCE((SELECT m.nome FROM municipios_referencia m"
                           " WHERE m.ibge = itens.municipio_ibge),"
                           " (SELECT valor FROM config"
                           "  WHERE chave='municipio_nome'))",
              "origem": "(ano*100000+COALESCE(sequencial,0))"},
}
PADRAO_ORDEM = {"contratacoes": "data_publicacao DESC",
                "contratos": "data_publicacao DESC",
                "atas": "vigencia_fim DESC",
                "pca": "ano DESC, numero_item",
                "itens": "data_resultado DESC, id"}


# O que o programa encontrou de errado ao abrir o banco, para a tela contar
# ao usuário. Fica em memória: quando o aviso nasce, gravar no banco ainda
# não é possível.
AVISO_ABERTURA = None


def _conectar():
    """Abre o banco e tira da frente um arquivo de transações órfão.

    O `-wal` guarda o que ainda não foi gravado no `.db`. Se sobrar um `-wal`
    escrito para outro momento do arquivo — cópia da pasta, restauração de
    backup, sincronizador de nuvem, encerramento à força —, o SQLite aplica
    aquelas páginas velhas sobre o banco atual e o resultado é
    `database disk image is malformed`, antes mesmo de a janela abrir.
    Aconteceu em 2026-08-05: o `.db` estava íntegro (29.489 itens,
    `integrity_check` ok) e só o `-wal` de três dias antes derrubava tudo.

    Aqui o `-wal` é posto de lado e o banco reabre. O que ele continha se
    perde — mas é o que ainda não tinha sido gravado, e o acervo se
    completa na sincronização seguinte.
    """
    global AVISO_ABERTURA
    db = None
    try:
        db = sqlite3.connect(ARQUIVO_DB)
        # conectar não lê nada: a corrupção só aparece na primeira consulta
        db.execute("PRAGMA table_info(atas)").fetchall()
        return db
    except sqlite3.DatabaseError as e:
        # no Windows o arquivo fica travado enquanto a conexão viver, e
        # renomear é justamente o que vem a seguir
        if db is not None:
            db.close()
        if "malformed" not in str(e) and "not a database" not in str(e):
            raise
    carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
    if _banco_intacto():
        movidos = []
        for sufixo in ("-wal", "-shm"):
            f = Path(str(ARQUIVO_DB) + sufixo)
            if f.exists():
                f.rename(f.with_name(f"{f.name}.orfao-{carimbo}"))
                movidos.append(f.name)
        AVISO_ABERTURA = (
            "O arquivo de transações do banco estava inconsistente e foi "
            "posto de lado. O acervo está íntegro; o que faltar volta na "
            "próxima sincronização.")
        return sqlite3.connect(ARQUIVO_DB)
    # O banco em si se perdeu. O acervo pode ser baixado de novo do PNCP,
    # mas isso custa horas de coleta — e um diagnóstico errado aqui apaga da
    # tela um acervo que talvez alguém consiga recuperar. Por isso a decisão
    # é do usuário, e o arquivo só sai do lugar se ele mandar.
    if not _confirmar_recomeco():
        raise SystemExit(
            "Abertura cancelada. O banco continua onde estava, intacto.")
    guardado = ARQUIVO_DB.with_name(f"{ARQUIVO_DB.name}.corrompido-{carimbo}")
    ARQUIVO_DB.rename(guardado)
    for sufixo in ("-wal", "-shm"):
        f = Path(str(ARQUIVO_DB) + sufixo)
        if f.exists():
            f.unlink()
    AVISO_ABERTURA = (
        f"O banco estava corrompido e foi guardado como {guardado.name}. "
        "Um banco novo foi criado — sincronize para baixar o acervo de novo.")
    return sqlite3.connect(ARQUIVO_DB)


def _confirmar_recomeco():
    """Pergunta antes de aposentar o banco, com a janela ainda inexistente.

    A interface do programa é a própria página, que só nasce depois do
    banco; quando isto roda, a única forma de falar com o usuário é uma
    caixa do Windows.
    """
    aviso = (f"O banco do Licitarium não pôde ser lido:\n{ARQUIVO_DB}\n\n"
             "Posso guardar o arquivo atual (renomeado) e começar um banco "
             "novo — o acervo volta na sincronização, baixando do PNCP de "
             "novo, o que pode levar bastante tempo.\n\n"
             "Escolha Não para sair sem tocar em nada e cuidar do arquivo "
             "você mesmo.\n\nComeçar um banco novo?")
    try:
        import ctypes
        # MB_YESNO | MB_ICONWARNING; 6 = Sim
        return ctypes.windll.user32.MessageBoxW(
            None, aviso, "Licitarium", 0x04 | 0x30) == 6
    except Exception:
        return True    # sem interface gráfica (linha de comando, testes)


def _banco_intacto():
    """O arquivo principal responde sozinho, sem o `-wal`?

    `immutable=1` faz o SQLite ignorar `-wal` e `-shm` e ler só o `.db` —
    é o que separa "o banco quebrou" de "o arquivo de transações não é
    deste banco".
    """
    try:
        db = sqlite3.connect(f"file:{ARQUIVO_DB}?mode=ro&immutable=1", uri=True)
        try:
            return db.execute("PRAGMA quick_check(1)").fetchone()[0] == "ok"
        finally:
            db.close()
    except (sqlite3.DatabaseError, OSError):
        return False


def fechar_limpo():
    """Grava o `-wal` no banco e o zera antes de sair.

    Um `-wal` que não sobrevive ao encerramento não tem como voltar órfão
    na abertura seguinte — é a metade preventiva do problema tratado em
    `_conectar`.
    """
    try:
        db = sqlite3.connect(ARQUIVO_DB)
        try:
            db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        finally:
            db.close()
    except sqlite3.DatabaseError:
        pass   # sair é mais importante que encerrar bonito


def abrir_db():
    # ponytail: conexão nova por operação — chamadas vêm de threads distintas
    # (js bridge + thread de sync) e o volume municipal não justifica pool
    DIR_DADOS.mkdir(parents=True, exist_ok=True)
    db = _conectar()
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
    for tabela in ("contratacoes", "itens"):
        cols = {r[1] for r in db.execute(f"PRAGMA table_info({tabela})")}
        if cols and "referencia" not in cols:
            db.execute(f"ALTER TABLE {tabela} ADD COLUMN"
                       " referencia INTEGER DEFAULT 0")
            db.commit()
        if cols and "municipio_ibge" not in cols:
            db.execute(f"ALTER TABLE {tabela} ADD COLUMN municipio_ibge TEXT")
            db.commit()
        # tudo o que já estava no banco é do município do usuário: sem isso a
        # coluna Origem da aba Preços nasceria vazia no acervo inteiro
        if cols:
            db.execute(
                f"UPDATE {tabela} SET municipio_ibge ="
                " (SELECT valor FROM config WHERE chave='municipio_ibge')"
                " WHERE municipio_ibge IS NULL AND referencia=0")
            db.commit()
    colunas_m = {r[1] for r in db.execute("PRAGMA table_info(pca_minuta_itens)")}
    if colunas_m and "mesclado_de" not in colunas_m:
        db.execute("ALTER TABLE pca_minuta_itens ADD COLUMN mesclado_de TEXT")
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
    # o filtro por unidade agrupa sinônimos, e o agrupamento é o mesmo em
    # Python e em SQL — daí a função viajar para dentro do banco
    db.create_function("unidade_canonica", 1, _unidade_canonica,
                       deterministic=True)
    # mesmo raciocínio: o medidor de limite do Painel agrupa dispensa por
    # objeto (relatorios.dados_painel), e o clique no alerta precisa filtrar
    # a lista exatamente pelos mesmos objetos — a função tem de ser uma só
    db.create_function("agrupamento_objeto", 1,
                       lambda o: pca_builder.chave_agrupamento(o, 2),
                       deterministic=True)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=10000")
    # o índice de busca nasce vazio; banco que já tinha itens precisa popular
    # (COUNT(*) em tabela FTS externa lê o conteúdo, não serve de teste)
    sem_fts = not db.execute("SELECT 1 FROM sqlite_master WHERE"
                             " name='itens_fts'").fetchone()
    db.executescript(SCHEMA)
    if sem_fts and db.execute("SELECT COUNT(*) FROM itens").fetchone()[0]:
        db.execute("INSERT INTO itens_fts(itens_fts) VALUES('rebuild')")
        db.commit()
    return db


# Cada órgão digita a unidade como quer: no acervo do piloto são 566 textos
# distintos para 16 mil itens — "UN", "UNIDADE", "Unidade  " e "UND" são a
# mesma coisa, e filtrar por texto cru obrigaria a marcar um por um. O grupo
# só serve de filtro; a coluna e os relatórios seguem mostrando o original.
UNIDADES_SINONIMAS = {
    "Unidade": ("UN", "UND", "UNID", "UNIDADE", "UNIDADES", "UD"),
    "Peça": ("PC", "PCA", "PECA", "PECAS", "PC.", "PÇ"),
    "Caixa": ("CX", "CAIXA", "CAIXAS", "CXA"),
    "Pacote": ("PCT", "PACOTE", "PACOTES", "PCTE"),
    "Fardo": ("FD", "FARDO", "FARDOS"),
    "Embalagem": ("EMB", "EMBALAGEM", "EMBALAGENS"),
    "Quilograma": ("KG", "QUILO", "QUILOS", "QUILOGRAMA", "KILO",
                   "KILOGRAMA", "KGS"),
    "Grama": ("G", "GR", "GRAMA", "GRAMAS"),
    "Litro": ("L", "LT", "LTS", "LITRO", "LITROS"),
    "Mililitro": ("ML", "MILILITRO", "MILILITROS"),
    "Metro": ("M", "MT", "MTS", "METRO", "METROS"),
    "Metro quadrado": ("M2", "M²", "METRO QUADRADO"),
    "Metro cúbico": ("M3", "M³", "METRO CUBICO"),
    "Frasco": ("FR", "FRS", "FRASCO", "FRASCOS"),
    "Ampola": ("AMP", "AMPOLA", "AMPOLAS"),
    "Comprimido": ("CP", "CMP", "COMP", "COMPRIMIDO", "COMPRIMIDOS"),
    "Cápsula": ("CAP", "CAPS", "CAPSULA", "CAPSULAS"),
    "Serviço": ("SV", "SERV", "SERVICO", "SERVICOS"),
    "Rolo": ("RL", "ROLO", "ROLOS"),
    "Galão": ("GL", "GALAO", "GALOES"),
    "Tubo": ("TB", "TUBO", "TUBOS"),
    "Par": ("PAR", "PARES"),
    "Dúzia": ("DZ", "DUZIA", "DUZIAS"),
    "Kit": ("KIT", "KITS", "CONJUNTO", "CJ"),
    "Lata": ("LT.", "LATA", "LATAS"),
    "Saco": ("SC", "SACO", "SACOS"),
    "Bloco": ("BL", "BLOCO", "BLOCOS"),
    "Resma": ("RM", "RESMA", "RESMAS"),
    "Hora": ("H", "HR", "HORA", "HORAS"),
    "Mês": ("MES", "MESES", "MENSAL"),
}
_CANONICA = {texto: grupo
             for grupo, textos in UNIDADES_SINONIMAS.items()
             for texto in textos}
# "Embalagem 1,00 KG", "Pacote 400,00 G", "Frasco 10,00 ML": o PNCP cola a
# quantidade na unidade. O grupo é a palavra; o tamanho continua legível na
# coluna, que mostra o texto original.
_SO_A_PALAVRA = re.compile(r"^([A-Za-zÀ-ÿ]+)[\s.]+[\d.,]+.*$")


def _unidade_canonica(texto):
    """Agrupa as grafias de uma mesma unidade sob um rótulo legível."""
    if not texto:
        return None
    limpo = " ".join(str(texto).split())
    chave = _SO_A_PALAVRA.sub(r"\1", limpo)
    sem_acento = (unicodedata.normalize("NFD", chave)
                  .encode("ascii", "ignore").decode())
    return _CANONICA.get(sem_acento.upper().rstrip("."), limpo.capitalize())


def _corrigir_pelo_ipca(linhas, ipca):
    """Troca cada preço pelo valor corrigido, guardando o resto da linha.

    Item sem data utilizável, ou mais recente que o último índice, fica de
    fora: corrigir sem saber de quando é o preço seria inventar.
    """
    corrigidas = []
    for r in linhas:
        valor = relatorios.corrigir(r[1], r[4], ipca)
        if valor is not None:
            corrigidas.append((r[0], valor, r[2], r[3], r[4]))
    corrigidas.sort(key=lambda x: x[1])
    return corrigidas, len(linhas) - len(corrigidas)


def _normalizar_por_conteudo(linhas):
    """Troca o preço de embalagem pelo preço da unidade-base.

    Comparar R$/quilo com R$/folha não quer dizer nada, então a série fica
    com a base **mais frequente** do resultado; o que sobrou é contado e
    dito ao usuário, em vez de sumir em silêncio.
    """
    convertidos = []
    for r in linhas:
        p = relatorios.preco_por_conteudo(r[1], r[2], r[3])
        if p:
            convertidos.append((r[0], p["valor"], p["base"],
                                relatorios.base_implicita(r[3])))
    if not convertidos:
        return [], None, len(linhas)
    # quem só é comparável porque a unidade já era a base não vota na
    # escolha — ver relatorios.escolher_base
    base = relatorios.escolher_base([(b, i) for _, _, b, i in convertidos])
    serie = sorted(((i, v) for i, v, b, _ in convertidos if b == base),
                   key=lambda x: x[1])
    return serie, base, len(linhas) - len(serie)


def _blocos(ids, tamanho=400):
    """Fatia a lista de ids em blocos para o SQLite.

    Uma cláusula IN com milhares de parâmetros esbarra no limite de
    variáveis por consulta; vários NOT IN encadeados dão o mesmo resultado.
    """
    ids = [str(i) for i in (ids or []) if i]
    return [ids[i:i + tamanho] for i in range(0, len(ids), tamanho)]


def _termo_fts(busca):
    """Cada palavra vira prefixo obrigatório: "papel a4" -> papel* AND a4*."""
    palavras = re.findall(r"[0-9A-Za-zÀ-ÿ]+", busca or "")
    return " AND ".join(f'"{p}"*' for p in palavras) if palavras else None


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
                    # o que o programa consertou sozinho ao abrir o banco;
                    # None no caso normal
                    "aviso_abertura": AVISO_ABERTURA,
                    "municipio": cfg.get("municipio_nome"),
                    "uf": cfg.get("municipio_uf"),
                    "ibge": cfg.get("municipio_ibge"),
                    "tema": cfg.get("tema", "portal"),
                    "largura": cfg.get("largura", "compacta"),
                    "fonte": cfg.get("fonte", "normal"),
                    "densidade": cfg.get("densidade", "confortavel"),
                    "colunas": cfg.get("colunas", "{}"),
                    # onde o usuário estava: o Painel é a tela inicial, mas
                    # quem trabalha numa aba volta para ela
                    "aba": cfg.get("aba", "painel"),
                    "painel_vista": cfg.get("painel_vista", "execucao"),
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
            "SELECT COUNT(*) FROM contratacoes WHERE referencia=0"
        ).fetchone()[0]
        homologado_ano = db.execute(
            "SELECT COALESCE(SUM(valor_homologado),0) FROM contratacoes "
            "WHERE referencia=0 AND substr(data_publicacao,1,4)=?",
            (ano,)).fetchone()[0]
        vigentes = db.execute(
            "SELECT COUNT(*) FROM contratos WHERE substr(vigencia_fim,1,10)>=?",
            (hoje,)).fetchone()[0]
        vencendo_contratos = db.execute(
            "SELECT COUNT(*) FROM contratos WHERE date(vigencia_fim)"
            " BETWEEN date('now') AND date('now','+60 day')").fetchone()[0]
        vencendo_atas = db.execute(
            "SELECT COUNT(*) FROM atas WHERE date(vigencia_fim)"
            " BETWEEN date('now') AND date('now','+60 day')").fetchone()[0]
        propostas_abertas = db.execute(
            "SELECT COUNT(*) FROM contratacoes"
            " WHERE referencia=0"
            " AND datetime(data_encerramento_proposta) >= datetime('now')"
        ).fetchone()[0]
        return {"contratacoes": n_contratacoes,
                "homologado_ano": homologado_ano, "vigentes": vigentes,
                "vencendo_60_contratos": vencendo_contratos,
                "vencendo_60_atas": vencendo_atas,
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

    # ── municípios de referência (só banco de preços) ────────────────────

    def listar_municipios_referencia(self):
        db = abrir_db()
        try:
            linhas = db.execute(
                """SELECT m.ibge, m.nome, m.uf,
                          (SELECT COUNT(*) FROM itens i
                           WHERE i.municipio_ibge = m.ibge
                             AND i.valor_unitario_homologado IS NOT NULL) itens,
                          (SELECT COALESCE(SUM(LENGTH(i.raw)),0) FROM itens i
                           WHERE i.municipio_ibge = m.ibge)
                          + (SELECT COALESCE(SUM(LENGTH(c.raw)),0)
                             FROM contratacoes c
                             WHERE c.municipio_ibge = m.ibge) bytes_raw
                   FROM municipios_referencia m ORDER BY m.nome""").fetchall()
            return [{"ibge": r["ibge"], "nome": r["nome"], "uf": r["uf"],
                     "itens": r["itens"],
                     "mb": round(r["bytes_raw"] * pncp.FATOR_DISCO / 1e6, 1)}
                    for r in linhas]
        finally:
            db.close()

    def estimar_municipio_referencia(self, codigo):
        """Peso da coleta antes de o usuário mandar baixar.

        Município médio muda a ordem de grandeza: Olímpia-SP tem 5.982
        contratações contra 131 de Orindiúva — 286 MB e quase 7 horas de
        coleta. Sem este aviso, o usuário descobriria isso no meio da noite.
        """
        try:
            return pncp.estimar_volume(str(codigo))
        except pncp.PncpErro as e:
            return {"erro": str(e)}

    def adicionar_municipio_referencia(self, codigo, nome, uf):
        """Entra na lista; os preços chegam na próxima sincronização."""
        codigo = str(codigo)
        db = abrir_db()
        try:
            if codigo == (pncp._config(db, "municipio_ibge") or ""):
                return {"ok": False,
                        "erro": "este já é o município do acervo"}
            db.execute(
                "INSERT OR IGNORE INTO municipios_referencia"
                " (ibge, nome, uf, adicionado_em) VALUES (?,?,?,?)",
                (codigo, nome, uf, datetime.now().isoformat()))
            db.commit()
            return {"ok": True}
        finally:
            db.close()

    def remover_municipio_referencia(self, codigo):
        """Sai da lista e leva junto os registros que trouxe.

        Só apaga o que tem `referencia=1`: se o mesmo processo existisse no
        acervo próprio, ele não pode ser tocado.
        """
        codigo = str(codigo)
        db = abrir_db()
        try:
            for tabela in ("itens", "contratacoes"):
                db.execute(f"DELETE FROM {tabela}"
                           " WHERE referencia=1 AND municipio_ibge=?", (codigo,))
            db.execute("DELETE FROM municipios_referencia WHERE ibge=?",
                       (codigo,))
            pncp._config(db, f"last_sync_ref_{codigo}", "")
            db.commit()
            return {"ok": True}
        finally:
            db.close()

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
        # município de referência alimenta só o banco de preços (aba
        # Preços): no acervo ele não existe
        if tipo == "contratacoes":
            where.append("referencia=0")
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
        if f.get("vencendo") and tipo in ("contratos", "atas"):
            # mesmo critério do alerta (Api._kpis/relatorios.dados_executivo):
            # janela FECHADA de 60 dias, não "vigente" sem limite superior —
            # era essa a diferença entre o alerta contar 25 e a lista trazer
            # tudo que ainda não venceu (ex.: 50)
            where.append("date(vigencia_fim)"
                         " BETWEEN date('now') AND date('now','+60 day')")
        if f.get("propostas") and tipo == "contratacoes":
            where.append(
                "datetime(data_encerramento_proposta) >= datetime('now')")
        if f.get("parada") and tipo == "contratacoes":
            # mesmo critério do alerta "sem resultado" do Painel
            # (relatorios.dados_painel): publicado há mais de 90 dias e sem
            # nenhum valor homologado ainda
            where.append("valor_homologado IS NULL"
                         " AND date(data_publicacao) < date('now','-90 day')")
        if f.get("objetos") and tipo == "contratacoes":
            # clique no alerta de limite anual: só os objetos que o Painel
            # apontou como perto/acima do limite, não a modalidade inteira
            grupo = [str(o) for o in f["objetos"] if o]
            if grupo:
                where.append("modalidade_id=8 AND agrupamento_objeto(objeto)"
                             f" IN ({','.join('?' * len(grupo))})")
                args += grupo
        if f.get("so_homologados") and tipo == "itens":
            where.append("valor_unitario_homologado IS NOT NULL")
        if f.get("origem") == "proprio" and tipo == "itens":
            where.append("referencia=0")
        if f.get("unidade") and tipo == "itens":
            where.append("unidade_canonica(unidade)=?")
            args.append(f["unidade"])
        if f.get("busca"):
            termo = _termo_fts(f["busca"]) if tipo == "itens" else None
            if termo:
                # palavras em qualquer ordem: "papel a4" acha "PAPEL ... A4"
                where.append("rowid IN (SELECT rowid FROM itens_fts"
                             " WHERE itens_fts MATCH ?)")
                args.append(termo)
            else:
                campos = {"contratacoes": ["objeto", "numero_controle"],
                          "contratos": ["objeto", "fornecedor_nome",
                                        "numero_controle", "numero_contrato"],
                          "atas": ["numero_controle", "numero_ata", "objeto"],
                          "pca": ["descricao", "grupo"],
                          "itens": ["descricao", "fornecedor_nome"]}[tipo]
                where.append("(" + " OR ".join(f"{c} LIKE ?" for c in campos)
                             + ")")
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
            nomes = self._nomes_de_municipio(db) if tipo == "itens" else {}
            # correção monetária só quando pedida: a série é lida uma vez
            # para a página inteira, não por item
            ipca = (relatorios.fatores_ipca(db)
                    if tipo == "itens" and f.get("corrigir") else None)
            publicacao = {}
            if ipca:
                publicacao = {r[0]: r[1] for r in db.execute(
                    "SELECT numero_controle, data_publicacao"
                    " FROM contratacoes")}
            itens = []
            for r in linhas:
                d = dict(r)
                d.pop("raw", None)  # listagem não precisa do JSON completo
                if tipo == "itens":
                    d["municipio_nome"] = nomes.get(d.get("municipio_ibge"))
                    if ipca:
                        d["corrigido"] = relatorios.corrigir(
                            d.get("valor_unitario_homologado"),
                            d.get("data_resultado") or publicacao.get(
                                d.get("contratacao_controle")), ipca)
                    # o que o item custa na unidade-base, quando o texto diz
                    # quanto vem na embalagem — sobre o valor corrigido, se a
                    # correção estiver ligada, senão a coluna divergiria do
                    # resumo, que corrige antes de normalizar
                    d["por_conteudo"] = relatorios.preco_por_conteudo(
                        d.get("corrigido") if ipca
                        else d.get("valor_unitario_homologado"),
                        d.get("descricao"), d.get("unidade"))
                itens.append(d)
            return {"itens": itens, "total": total}
        finally:
            db.close()

    @staticmethod
    def _nomes_de_municipio(db):
        nomes = {r["ibge"]: r["nome"] for r in db.execute(
            "SELECT ibge, nome FROM municipios_referencia")}
        proprio = pncp._config(db, "municipio_ibge")
        if proprio:
            nomes[proprio] = pncp._config(db, "municipio_nome") or proprio
        return nomes

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

    # ── descartes da pesquisa de preços ─────────────────────────────────

    def descartes(self, busca):
        """O que já foi desconsiderado nesta pesquisa, com o motivo."""
        termo = relatorios.chave_termo(busca)
        if not termo:
            return []
        db = abrir_db()
        try:
            # a descrição vem junto: a lista de descartados precisa dizer
            # qual item é, e o id sozinho não diz nada a quem lê
            return [dict(r) for r in db.execute(
                "SELECT d.item_id, d.motivo, i.descricao, i.unidade,"
                "       i.valor_unitario_homologado valor"
                "  FROM precos_descartes d"
                "  LEFT JOIN itens i ON i.id = d.item_id"
                " WHERE d.termo=? ORDER BY d.criado_em", (termo,))]
        finally:
            db.close()

    def descartar_preco(self, busca, item_id, motivo=None):
        """Tira o item da pesquisa; o motivo pode vir depois.

        Exigir a justificativa no clique atrapalharia quem descarta dez
        itens de uma vez — o relatório é que cobra, apontando o que ficou
        sem razão registrada.
        """
        termo = relatorios.chave_termo(busca)
        if not termo or not item_id:
            return {"ok": False}
        db = abrir_db()
        try:
            db.execute(
                "INSERT INTO precos_descartes (termo, item_id, motivo,"
                " criado_em) VALUES (?,?,?,?)"
                " ON CONFLICT(termo, item_id) DO UPDATE SET motivo=excluded.motivo",
                (termo, str(item_id), motivo or None,
                 datetime.now().isoformat()))
            db.commit()
            return {"ok": True}
        finally:
            db.close()

    def restaurar_preco(self, busca, item_id=None):
        """Devolve um item à pesquisa — ou todos, se não vier item."""
        termo = relatorios.chave_termo(busca)
        if not termo:
            return {"ok": False}
        db = abrir_db()
        try:
            if item_id:
                db.execute("DELETE FROM precos_descartes"
                           " WHERE termo=? AND item_id=?", (termo, str(item_id)))
            else:
                db.execute("DELETE FROM precos_descartes WHERE termo=?",
                           (termo,))
            db.commit()
            return {"ok": True}
        finally:
            db.close()

    def motivos_descarte(self):
        """Lista para a tela montar o seletor, na ordem em que aparece."""
        return [{"id": k, "texto": v} for k, v in relatorios.MOTIVOS_DESCARTE.items()]

    def estatisticas_preco(self, busca, ano=None, origem=None,
                           excluidos=None, por_conteudo=False,
                           corrigir=False):
        """Resumo do valor unitário homologado para um termo — a resposta de
        'quanto pagamos por isso?' que instrui a pesquisa de preços.

        Com `por_conteudo`, o resumo passa a ser sobre o preço da
        unidade-base (R$/folha, R$/quilo): a caixa com 5.000 folhas e o
        pacote com 100 deixam de entrar na mesma mediana como se fossem
        comparáveis. Com `corrigir`, cada preço é trazido a valor do último
        mês do IPCA antes de qualquer conta.
        """
        if not (busca or "").strip():
            return None
        termo = _termo_fts(busca)
        where = ["valor_unitario_homologado IS NOT NULL"]
        args = []
        if termo:
            where.append("rowid IN (SELECT rowid FROM itens_fts"
                         " WHERE itens_fts MATCH ?)")
            args.append(termo)
        else:
            where.append("descricao LIKE ?")
            args.append(f"%{busca.strip()}%")
        if ano:
            where.append("ano=?")
            args.append(ano)
        if origem == "proprio":
            where.append("referencia=0")
        # itens que o usuário desmarcou na lista: a pesquisa de preços do
        # art. 23 só vale sobre itens comparáveis, e é ele quem julga isso
        for grupo in _blocos(excluidos):
            where.append("id NOT IN (%s)" % ",".join("?" * len(grupo)))
            args += grupo
        db = abrir_db()
        try:
            linhas = db.execute(
                "SELECT id, valor_unitario_homologado, descricao, unidade,"
                " COALESCE(data_resultado, (SELECT data_publicacao"
                "   FROM contratacoes c"
                "  WHERE c.numero_controle = itens.contratacao_controle)) data"
                " FROM itens WHERE "
                + " AND ".join(where) + " ORDER BY 2", args).fetchall()
            if not linhas:
                return None
            ipca = None
            if corrigir:
                ipca = relatorios.fatores_ipca(db)
                linhas, sem_indice = _corrigir_pelo_ipca(linhas, ipca)
                if not linhas:
                    return {"n": 0, "corrigido": True,
                            "sem_indice": sem_indice,
                            "ipca_ate": ipca["ate"]}
            base = None
            if por_conteudo:
                linhas, base, sem_conversao = _normalizar_por_conteudo(linhas)
                if not linhas:
                    return {"n": 0, "por_conteudo": True,
                            "sem_conversao": sem_conversao}
            resumo = relatorios.resumo_estatistico(
                [r[1] for r in linhas])
            if corrigir:
                resumo.update(corrigido=True, ipca_ate=ipca["ate"],
                              ipca_ate_extenso=relatorios.mes_por_extenso(
                                  ipca["ate"]),
                              sem_indice=sem_indice)
                relatorios.marcar_amostra_reduzida(resumo, sem_indice)
            if por_conteudo:
                resumo.update(por_conteudo=True, base=base,
                              rotulo_base=relatorios.BASES[base][0],
                              sem_conversao=sem_conversao)
            # itens fora do intervalo de Tukey: apontados, nunca removidos
            # sozinhos — descartar preço de pesquisa é decisão de quem assina
            if resumo.get("limite_sup") is not None:
                resumo["fora_da_curva"] = [
                    r[0] for r in linhas
                    if r[1] < resumo["limite_inf"] or r[1] > resumo["limite_sup"]]
            # contagens sobre a mesma série que virou resumo: no modo por
            # conteúdo, os itens sem conversão não entraram
            ids = [r[0] for r in linhas]
            fornecedores, proprios = 0, 0
            for grupo in _blocos(ids):
                marcas = ",".join("?" * len(grupo))
                fornecedores += db.execute(
                    f"SELECT COUNT(DISTINCT fornecedor_ni) FROM itens"
                    f" WHERE id IN ({marcas})", grupo).fetchone()[0]
                proprios += db.execute(
                    f"SELECT COUNT(*) FROM itens WHERE referencia=0"
                    f" AND id IN ({marcas})", grupo).fetchone()[0]
            resumo.update(fornecedores=fornecedores, proprios=proprios,
                          referencia=resumo["n"] - proprios)
            return resumo
        finally:
            db.close()

    def painel(self, ano=None, orgao=None):
        """Dados das três subabas do Painel, numa chamada só."""
        db = abrir_db()
        try:
            if not ano:
                ano = db.execute(
                    "SELECT MAX(ano) FROM contratacoes WHERE referencia=0"
                ).fetchone()[0] or date.today().year
            cfg = {r["chave"]: r["valor"] for r in
                   db.execute("SELECT chave, valor FROM config")}
            return relatorios.dados_painel(
                db, ano, orgao,
                {"compras": cfg.get("limite_dispensa_compras"),
                 "obras": cfg.get("limite_dispensa_obras")})
        finally:
            db.close()

    def imprimir_painel(self, vistas, ano=None):
        """Grava o painel em A3 paisagem e abre para impressão.

        `vistas` é o que a tela desenhou — [[nome, html], …]. O SVG vem
        pronto de lá justamente para o papel não divergir da tela.
        """
        db = abrir_db()
        try:
            municipio = pncp._config(db, "municipio_nome") or "Município"
            uf = pncp._config(db, "municipio_uf") or ""
            tema = pncp._config(db, "tema") or "portal"
        finally:
            db.close()
        html = relatorios.render_painel(
            [(str(n), str(h)) for n, h in (vistas or [])],
            municipio, uf, ano or date.today().year, tema)
        destino = DIR_DADOS / "relatorios"
        destino.mkdir(parents=True, exist_ok=True)
        arquivo = destino / f"painel_{ano or date.today().year}.html"
        arquivo.write_text(html, encoding="utf-8")
        webbrowser.open(arquivo.as_uri())
        return {"ok": True, "arquivo": str(arquivo)}

    def filtros_disponiveis(self):
        db = abrir_db()
        try:
            anos = [r[0] for r in db.execute(
                "SELECT DISTINCT ano FROM contratacoes"
                " WHERE referencia=0 AND ano IS NOT NULL ORDER BY 1 DESC")]
            situacoes = [r[0] for r in db.execute(
                "SELECT DISTINCT situacao FROM contratacoes"
                " WHERE referencia=0 AND situacao IS NOT NULL ORDER BY 1")]
            modalidades = [{"id": r[0], "nome": r[1]} for r in db.execute(
                "SELECT DISTINCT modalidade_id, modalidade_nome"
                " FROM contratacoes"
                " WHERE referencia=0 AND modalidade_id IS NOT NULL"
                " ORDER BY 2")]
            orgaos = [{"cnpj": r[0], "nome": r[1]} for r in db.execute(
                "SELECT cnpj, razao_social FROM orgaos ORDER BY razao_social")]
            # unidades do banco de preços, já agrupadas: as raras ficam no
            # fim da lista porque a ordem é por quantidade de itens
            contagem = {}
            for (texto,) in db.execute(
                    "SELECT unidade FROM itens"
                    " WHERE valor_unitario_homologado IS NOT NULL"
                    "   AND unidade IS NOT NULL"):
                grupo = _unidade_canonica(texto)
                if grupo:
                    contagem[grupo] = contagem.get(grupo, 0) + 1
            unidades = [{"nome": g, "n": n} for g, n in
                        sorted(contagem.items(), key=lambda x: (-x[1], x[0]))]
            return {"anos": anos, "situacoes": situacoes,
                    "modalidades": modalidades, "orgaos": orgaos,
                    "unidades": unidades}
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

    def sincronizar(self, forcado=True):
        """Dispara a coleta. `forcado=False` é a da abertura do programa.

        A da abertura respeita um intervalo mínimo: abrir cinco vezes numa
        hora disparava cinco coletas completas, e o PNCP não muda em dez
        minutos. O botão Sincronizar continua valendo sempre.
        """
        if not self._sync_ativo.acquire(blocking=False):
            return False  # já rodando
        threading.Thread(target=self._rodar_sync, args=(bool(forcado),),
                         daemon=True).start()
        return True

    def _rodar_sync(self, forcado=True):
        try:
            self._status.update(rodando=True, msg="Conectando ao PNCP…",
                                resumo=None, erro=None)
            self._avisar_ui()
            db = abrir_db()
            try:
                ibge = pncp._config(db, "municipio_ibge")
                if not ibge:
                    return
                resumo = pncp.sincronizar_tudo(db, ibge, self._progresso,
                                               forcado=forcado)
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

    # ── minuta de PCA ───────────────────────────────────────────────────

    def gerar_minuta_pca(self, ano_alvo, params=None):
        db = abrir_db()
        try:
            n = pca_builder.gerar_minuta(db, int(ano_alvo), params or {},
                                         (params or {}).get("orgao"))
            return {"ok": True, "grupos": n}
        except Exception as e:
            return {"ok": False, "erro": str(e)}
        finally:
            db.close()

    def listar_minuta_pca(self, ano_alvo):
        db = abrir_db()
        try:
            itens = pca_builder.listar_minuta(db, int(ano_alvo))
            cfg = db.execute("SELECT * FROM pca_minuta WHERE ano_alvo=?",
                             (int(ano_alvo),)).fetchone()
            return {"itens": itens,
                    "familias": pca_builder.resumo_familias(itens),
                    "totais": pca_builder.totais(itens),
                    "parametros": json.loads(cfg["parametros"]) if cfg else None,
                    "gerado_em": cfg["gerado_em"] if cfg else None}
        finally:
            db.close()

    def editar_item_minuta(self, item_id, campos):
        permitidos = {"descricao", "unidade", "categoria", "quantidade",
                      "valor_unitario", "margem", "incluir"}
        campos = {k: v for k, v in (campos or {}).items() if k in permitidos}
        if not campos:
            return {"ok": False, "erro": "nada a alterar"}
        sets = ", ".join(f"{k}=?" for k in campos) + ", editado=1"
        db = abrir_db()
        try:
            db.execute(f"UPDATE pca_minuta_itens SET {sets} WHERE id=?",
                       list(campos.values()) + [int(item_id)])
            db.commit()
            return {"ok": True}
        finally:
            db.close()

    def mesclar_itens_minuta(self, ano_alvo, ids):
        db = abrir_db()
        try:
            return pca_builder.mesclar(db, int(ano_alvo),
                                       [int(i) for i in (ids or [])])
        finally:
            db.close()

    def dividir_item_minuta(self, item_id):
        db = abrir_db()
        try:
            return pca_builder.dividir(db, int(item_id))
        finally:
            db.close()

    def anos_com_itens(self):
        db = abrir_db()
        try:
            return [r[0] for r in db.execute(
                "SELECT DISTINCT ano FROM itens"
                " WHERE referencia=0 AND ano IS NOT NULL"
                " AND valor_unitario_homologado IS NOT NULL ORDER BY 1")]
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
                self._nova_versao = tag
                # o nome do exe carrega a versão, então casa por padrão e
                # não por nome fixo — e o GitHub troca o espaço do nome do
                # arquivo por ponto ao publicar o anexo ("Licitarium.v1.2.4
                # .exe"), por isso os dois separadores. Segue achando as
                # releases antigas, que se chamavam só "Licitarium.exe".
                self._asset_url = next(
                    (a.get("browser_download_url") for a in d.get("assets", [])
                     if re.fullmatch(r"Licitarium([ .]v[\d.]+)?\.exe",
                                     a.get("name") or "")), None)
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
            # o nome do arquivo carrega a versão: trocar o conteúdo sem
            # renomear deixaria "Licitarium v1.2.3.exe" rodando a 1.2.4
            atual = Path(sys.executable)
            versao_nova = getattr(self, "_nova_versao", None)
            final = (atual.with_name(f"Licitarium v{versao_nova}.exe")
                     if versao_nova and atual.name.startswith("Licitarium")
                     else atual)
            bat.write_text(_script_atualizacao(atual, novo, final),
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

    def _linhas_minuta_csv(self, ano):
        db = abrir_db()
        try:
            return [{k: i[k] for k in
                     ("descricao", "unidade", "categoria", "quantidade",
                      "valor_unitario", "margem", "valor_total")}
                    for i in pca_builder.listar_minuta(db, int(ano),
                                                       so_incluidos=True)]
        finally:
            db.close()

    # ── acervo: cópia de segurança e restauração ────────────────────────

    def exportar_acervo(self):
        """Salva o acervo inteiro num arquivo .zip.

        O banco é reconstruível a partir do PNCP — mas reconstruir custa
        horas quando há municípios de referência (foram seis, e a coleta de
        cada um leva minutos a horas). A cópia troca essas horas por um
        arquivo.

        A cópia sai pela API de backup do SQLite, e não copiando o arquivo:
        a thread de sincronização pode estar gravando, e um arquivo copiado
        no meio de uma transação nasce inconsistente.
        """
        db = abrir_db()
        try:
            municipio = pncp._config(db, "municipio_nome") or "acervo"
            contagens = {t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                         for t in ("contratacoes", "contratos", "atas",
                                   "itens", "pca_itens",
                                   "municipios_referencia")}
        finally:
            db.close()
        agora = datetime.now()
        sugerido = (f"DB_LICITARIUM_BACKUP_{agora:%Y-%m-%d}_"
                    f"{agora:%H-%M-%S}.zip")
        destino = self._janela.create_file_dialog(
            DIALOGO_SALVAR, save_filename=sugerido, file_types=("Zip (*.zip)",))
        if not destino:
            return {"ok": False, "erro": None}       # cancelado
        caminho = destino if isinstance(destino, str) else destino[0]
        manifesto = {"_sgx": "LICITARIUM", "schema": ACERVO_SCHEMA,
                     "exportedAt": agora.isoformat(), "versao": VERSAO,
                     "municipio": municipio, "contagens": contagens}
        with tempfile.TemporaryDirectory() as tmp:
            copia = Path(tmp) / "licitarium.db"
            origem = abrir_db()
            try:
                destino_db = sqlite3.connect(copia)
                try:
                    origem.backup(destino_db)
                finally:
                    destino_db.close()
            finally:
                origem.close()
            with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as z:
                z.write(copia, "licitarium.db")
                z.writestr("manifesto.json",
                           json.dumps(manifesto, ensure_ascii=False, indent=2))
        return {"ok": True, "arquivo": caminho,
                "mb": round(Path(caminho).stat().st_size / 1e6, 1),
                "contagens": contagens}

    def importar_acervo(self):
        """Põe no lugar do acervo atual o de um arquivo .zip exportado.

        Substituir o banco de um programa em execução é o tipo de operação
        que só se faz com o arquivo já conferido: o zip é aberto num
        diretório temporário e o banco de dentro passa por `quick_check`
        antes de qualquer coisa. O acervo atual não é apagado — vira
        `.substituido-<data>`, e desfazer é renomear de volta.
        """
        escolha = self._janela.create_file_dialog(
            DIALOGO_ABRIR, file_types=("Cópia do Licitarium (*.zip)",))
        if not escolha:
            return {"ok": False, "erro": None}
        caminho = escolha if isinstance(escolha, str) else escolha[0]
        with tempfile.TemporaryDirectory() as tmp:
            try:
                with zipfile.ZipFile(caminho) as z:
                    nomes = z.namelist()
                    if "licitarium.db" not in nomes:
                        return {"ok": False,
                                "erro": "o arquivo não é uma cópia do "
                                        "Licitarium (falta o banco)"}
                    z.extract("licitarium.db", tmp)
                    manifesto = (json.loads(z.read("manifesto.json"))
                                 if "manifesto.json" in nomes else {})
            except (zipfile.BadZipFile, json.JSONDecodeError, KeyError):
                return {"ok": False, "erro": "arquivo .zip ilegível"}
            novo = Path(tmp) / "licitarium.db"
            conferencia = sqlite3.connect(f"file:{novo}?mode=ro", uri=True)
            try:
                if conferencia.execute(
                        "PRAGMA quick_check(1)").fetchone()[0] != "ok":
                    return {"ok": False,
                            "erro": "o banco dentro do arquivo está corrompido"}
                itens = conferencia.execute(
                    "SELECT COUNT(*) FROM itens").fetchone()[0]
            except sqlite3.DatabaseError:
                return {"ok": False,
                        "erro": "o banco dentro do arquivo não pôde ser lido"}
            finally:
                conferencia.close()
            carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
            if ARQUIVO_DB.exists():
                ARQUIVO_DB.rename(ARQUIVO_DB.with_name(
                    f"{ARQUIVO_DB.name}.substituido-{carimbo}"))
            for sufixo in ("-wal", "-shm"):
                f = Path(str(ARQUIVO_DB) + sufixo)
                if f.exists():
                    f.unlink()
            shutil.move(str(novo), str(ARQUIVO_DB))
        return {"ok": True, "itens": itens,
                "municipio": manifesto.get("municipio"),
                "exportado_em": manifesto.get("exportedAt")}

    def exportar_csv(self, tipo, filtros=None):
        if tipo == "minuta_pca":
            ano = (filtros or {}).get("ano") or date.today().year + 1
            linhas = self._linhas_minuta_csv(ano)
            if not linhas:
                return {"ok": False, "erro": "gere a minuta antes de exportar"}
            destino = self._janela.create_file_dialog(
                DIALOGO_SALVAR, save_filename=f"minuta_pca_{ano}.csv",
                file_types=("CSV (*.csv)",))
            if not destino:
                return {"ok": False, "erro": None}
            caminho = destino if isinstance(destino, str) else destino[0]
            with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.DictWriter(f, fieldnames=linhas[0].keys(), delimiter=";")
                w.writeheader()
                w.writerows(linhas)
            return {"ok": True, "arquivo": caminho, "linhas": len(linhas)}
        if tipo not in TABELAS:
            return {"ok": False, "erro": "tipo inválido"}
        destino = self._janela.create_file_dialog(
            DIALOGO_SALVAR, save_filename=f"{tipo}.csv",
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


def _script_atualizacao(exe_atual, exe_novo, exe_final=None):
    """Gera o .bat que espera o app fechar, troca o exe e reabre.

    `exe_final` permite que o arquivo assuma o nome da versão nova; quando
    igual ao atual, a troca é no lugar (comportamento de sempre).

    A folga antes do start dá tempo de o Windows liberar o arquivo recém
    movido. Não há retry aqui de propósito: quando o bootloader falha, ele
    fica na tela com a caixa de erro, então o processo existe e qualquer
    checagem por tasklist daria falso positivo — a defesa é validar o exe
    antes da troca (ver Api._validar_exe).
    """
    exe_final = exe_final or exe_atual
    return f"""@echo off
:espera
del "{exe_atual}" >nul 2>&1
if exist "{exe_atual}" (
  timeout /t 1 /nobreak >nul
  goto espera
)
move /y "{exe_novo}" "{exe_final}" >nul
timeout /t 3 /nobreak >nul
start "" "{exe_final}"
del "%~f0"
"""


ARQUIVO_LOG = "ultimo-erro.log"


def registrar_falha(assunto, erro):
    """Deixa por escrito o que derrubou a abertura.

    O executável é compilado sem console: sem isto, uma falha na partida
    não deixa rastro nenhum e o usuário só vê a janela de erro do WebView2,
    que fala de proxy e firewall e não menciona o programa.
    """
    try:
        DIR_DADOS.mkdir(parents=True, exist_ok=True)
        with (DIR_DADOS / ARQUIVO_LOG).open("a", encoding="utf-8") as f:
            f.write(f"\n=== {datetime.now():%Y-%m-%d %H:%M:%S} · v{VERSAO}\n")
            f.write(f"{assunto}: {erro}\n")
            f.write(traceback.format_exc())
    except OSError:
        pass


def _avisar(texto, titulo="Licitarium"):
    """Caixa do Windows — a única interface disponível antes da janela."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, texto, titulo, 0x10)
    except Exception:
        print(texto, file=sys.stderr)


def _interface_no_ar(url, tentativas=25):
    """Espera o servidor local que serve a interface responder.

    O pywebview publica os arquivos da interface num servidor em
    127.0.0.1 e manda o WebView2 buscá-los ali. Quando esse servidor não
    sobe — firewall, antivírus, proxy sem exceção para endereço local —, a
    janela mostra ERR_CONNECTION_REFUSED, um erro do navegador que não diz
    nada sobre o Licitarium.
    """
    if not (url or "").startswith("http"):
        return True                      # servido direto do arquivo: nada a esperar
    for _ in range(tentativas):
        try:
            with urllib.request.urlopen(url, timeout=1):
                return True
        except urllib.error.HTTPError:
            return True                  # respondeu, ainda que com erro HTTP
        except (urllib.error.URLError, OSError):
            time.sleep(0.2)
    return False


def _conferir_interface(janela):
    """Roda em paralelo à janela: se a interface não subir, explica."""
    url = getattr(janela, "original_url", None) or getattr(janela, "url", "")
    if _interface_no_ar(url):
        return
    registrar_falha("interface não respondeu", url)
    _avisar(
        "O Licitarium não conseguiu abrir a própria interface.\n\n"
        "Ela é publicada num servidor local (endereço 127.0.0.1) e lida pela "
        "janela do programa. Algo nesta máquina está impedindo essa conversa "
        "interna — normalmente um antivírus, um firewall ou um proxy sem "
        "exceção para endereços locais.\n\n"
        "O que costuma resolver:\n"
        "1. Configurações do Windows > Rede > Proxy: marcar \"não usar proxy "
        "para endereços locais\";\n"
        "2. liberar o Licitarium no antivírus/firewall;\n"
        "3. fechar instâncias antigas do programa e abrir de novo.\n\n"
        f"Detalhes gravados em {DIR_DADOS / ARQUIVO_LOG}")


def main():
    api = Api()
    db = abrir_db()
    try:  # título já nasce com o município (a UI reconfirma no boot)
        municipio = pncp._config(db, "municipio_nome")
        uf = pncp._config(db, "municipio_uf")
        # abre maximizado por padrão: as listas são largas
        maximizar = (pncp._config(db, "maximizar") or "1") == "1"
        tema = pncp._config(db, "tema") or "portal"
    finally:
        db.close()
    _escrever_tema_da_splash(tema)
    titulo = f"Licitarium — {municipio}/{uf}" if municipio else "Licitarium"
    # caminho puro, sem query nem fragmento: é a única forma comprovada de
    # o WebView2 achar o arquivo dentro do exe (ver CHANGELOG 0.9.1)
    api._janela = webview.create_window(
        titulo, str(DIR_APP / "ui" / "index.html"), js_api=api,
        width=1100, height=740, min_size=(900, 600), maximized=maximizar)
    threading.Thread(target=_conferir_interface, args=(api._janela,),
                     daemon=True).start()
    # armazenamento persistente: sem isso o WebView2 abre um perfil novo a
    # cada execução e o localStorage (usado como reserva pela splash) some
    try:
        webview.start(private_mode=False,
                      storage_path=str(DIR_DADOS / "webview"))
    except Exception as e:
        registrar_falha("falha ao abrir a janela", e)
        _avisar(f"O Licitarium não conseguiu abrir a janela.\n\n{e}\n\n"
                f"Detalhes em {DIR_DADOS / ARQUIVO_LOG}")
        raise
    # a janela fechou: consolida o -wal para a próxima abertura não achar
    # arquivo de transação nenhum pela frente
    fechar_limpo()


def _escrever_tema_da_splash(tema):
    """Entrega o tema à página antes de ela carregar.

    A splash precisa da cor certa no primeiro quadro, e nem URL nem
    localStorage servem: a URL não aceita parâmetro dentro do exe e o
    localStorage vive numa origem cuja porta muda a cada execução. Um
    arquivo ao lado do index.html é lido de forma síncrona pelo navegador,
    então a composição já nasce correta.
    """
    if tema not in ("portal", "pergaminho", "observatorio"):
        tema = "portal"
    try:
        (DIR_APP / "ui" / "tema.js").write_text(
            f'window.__TEMA = "{tema}";\n', encoding="utf-8")
    except OSError:
        pass  # sem permissão de escrita: a página cai no tema padrão


if __name__ == "__main__":
    # --verificar: chegar aqui já prova que a runtime empacotada carregou;
    # usado pelo autoupdate para validar e aquecer o exe novo antes da troca
    if "--verificar" in sys.argv:
        print(VERSAO)
        sys.exit(0)
    main()
