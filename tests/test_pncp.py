"""Testes do motor de sync (HTTP mockado — nenhuma chamada real ao PNCP)."""
import sqlite3
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import licitarium
import pncp


@pytest.fixture
def db():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(licitarium.SCHEMA)
    yield con
    con.close()


def contratacao(numero, cnpj="11111111000111", **extra):
    base = {
        "numeroControlePNCP": numero, "anoCompra": 2026, "sequencialCompra": 1,
        "orgaoEntidade": {"cnpj": cnpj, "razaoSocial": "Prefeitura Teste"},
        "unidadeOrgao": {"nomeUnidade": "Secretaria"},
        "modalidadeId": 8, "modalidadeNome": "Dispensa de licitação",
        "situacaoCompraNome": "Homologada", "objetoCompra": "Objeto de teste",
        "valorTotalEstimado": 100.0, "valorTotalHomologado": 90.0,
        "dataPublicacaoPncp": "2026-03-01", "dataAtualizacao": "2026-03-02",
    }
    base.update(extra)
    return base


def test_janelas_respeitam_limite():
    janelas = list(pncp._janelas(date(2021, 1, 1), date(2023, 6, 15)))
    assert janelas[0][0] == date(2021, 1, 1)
    assert janelas[-1][1] == date(2023, 6, 15)
    for a, b in janelas:
        assert (b - a).days < pncp.JANELA_MAX_DIAS
    # janelas contíguas, sem buraco nem sobreposição
    for (_, fim_ant), (ini_seg, _) in zip(janelas, janelas[1:]):
        assert (ini_seg - fim_ant).days == 1


def test_paginar_percorre_todas_as_paginas(monkeypatch):
    paginas = {
        1: {"data": [{"n": 1}, {"n": 2}], "totalPaginas": 2},
        2: {"data": [{"n": 3}], "totalPaginas": 2},
    }
    monkeypatch.setattr(pncp, "_get",
                        lambda caminho, params: paginas[params["pagina"]])
    itens = list(pncp._paginar("/x", {}, 50))
    assert [i["n"] for i in itens] == [1, 2, 3]


def test_paginar_sem_dados(monkeypatch):
    monkeypatch.setattr(pncp, "_get", lambda caminho, params: None)
    assert list(pncp._paginar("/x", {}, 50)) == []


def test_sync_contratacoes_idempotente(db, monkeypatch):
    def fake_get(caminho, params):
        if params["codigoModalidadeContratacao"] == 8 and params["pagina"] == 1:
            return {"data": [contratacao("PNCP-1"), contratacao("PNCP-2")],
                    "totalPaginas": 1}
        return None
    monkeypatch.setattr(pncp, "_get", fake_get)
    n1 = pncp.sync_contratacoes(db, "3534203", date(2026, 1, 1), date(2026, 3, 1))
    n2 = pncp.sync_contratacoes(db, "3534203", date(2026, 1, 1), date(2026, 3, 1))
    assert n1 == n2 == 2
    assert db.execute("SELECT COUNT(*) FROM contratacoes").fetchone()[0] == 2
    linha = db.execute("SELECT * FROM contratacoes WHERE numero_controle='PNCP-1'"
                       ).fetchone()
    assert linha["orgao_cnpj"] == "11111111000111"
    assert linha["valor_homologado"] == 90.0
    assert "numeroControlePNCP" in linha["raw"]


def test_descobrir_orgaos(db, monkeypatch):
    monkeypatch.setattr(pncp, "_get", lambda c, p:
        {"data": [contratacao("A", cnpj="11111111000111"),
                  contratacao("B", cnpj="22222222000122")], "totalPaginas": 1}
        if p["codigoModalidadeContratacao"] == 8 and p["pagina"] == 1 else None)
    pncp.sync_contratacoes(db, "1", date(2026, 1, 1), date(2026, 1, 2))
    pncp.descobrir_orgaos(db)
    cnpjs = {r[0] for r in db.execute("SELECT cnpj FROM orgaos")}
    assert cnpjs == {"11111111000111", "22222222000122"}
    # rodar de novo não duplica nem desfaz desativação manual
    db.execute("UPDATE orgaos SET ativo=0 WHERE cnpj='22222222000122'")
    pncp.descobrir_orgaos(db)
    assert db.execute("SELECT COUNT(*) FROM orgaos").fetchone()[0] == 2
    assert db.execute("SELECT ativo FROM orgaos WHERE cnpj='22222222000122'"
                      ).fetchone()[0] == 0


def test_sincronizar_tudo_continua_apos_falha(db, monkeypatch):
    servido = []  # 1 registro numa única janela (como na API real, em que
                  # o item só aparece na janela da sua dataAtualizacao)
    def fake_get(caminho, params):
        if "contratos" in caminho:
            raise pncp.PncpErro("PNCP fora do ar")
        if "contratacoes" in caminho:
            if (params["codigoModalidadeContratacao"] == 8
                    and params["pagina"] == 1 and not servido):
                servido.append(1)
                return {"data": [contratacao("PNCP-1")], "totalPaginas": 1}
            return None
        return None  # atas: vazio, mas sem erro
    monkeypatch.setattr(pncp, "_get", fake_get)
    resumo = pncp.sincronizar_tudo(db, "3534203")
    assert resumo["contratacoes"] == 1
    assert resumo["contratos"] is None     # falhou, não bloqueou o resto
    assert resumo["atas"] == 0
    # last_sync só avança para quem concluiu
    assert pncp._config(db, "last_sync_contratacoes") is not None
    assert pncp._config(db, "last_sync_contratos") is None
    erros = db.execute("SELECT COUNT(*) FROM sync_log WHERE status='erro'"
                       ).fetchone()[0]
    assert erros >= 1


def test_sync_incremental_com_sobreposicao(db, monkeypatch):
    """Segunda rodada parte de last_sync - 1 dia (catch-up seguro)."""
    chamadas = []
    def fake_get(caminho, params):
        if "contratacoes" in caminho:
            chamadas.append(params["dataInicial"])
        return None
    monkeypatch.setattr(pncp, "_get", fake_get)
    pncp._config(db, "last_sync_contratacoes", "2026-07-20")
    pncp.sincronizar_tudo(db, "1")
    assert chamadas and all(c == "20260719" for c in chamadas)
