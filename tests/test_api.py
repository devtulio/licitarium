"""Testes da ponte Api (listar/ordenação/detalhe) com banco temporário."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import licitarium


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(licitarium, "DIR_DADOS", tmp_path)
    monkeypatch.setattr(licitarium, "ARQUIVO_DB", tmp_path / "t.db")
    db = licitarium.abrir_db()
    db.executemany(
        "INSERT INTO contratacoes (numero_controle, ano, objeto,"
        " valor_estimado, valor_homologado, data_publicacao)"
        " VALUES (?,?,?,?,?,?)",
        [("A", 2026, "Zebra", 10.0, None, "2026-01-01"),
         ("B", 2026, "Arroz", 30.0, 25.0, "2026-02-01"),
         ("C", 2025, "Milho", 20.0, 15.0, "2025-06-01")])
    db.execute("UPDATE contratacoes SET orgao_cnpj='111' WHERE"
               " numero_controle IN ('A','B')")
    db.execute("UPDATE contratacoes SET orgao_cnpj='222' WHERE"
               " numero_controle='C'")
    db.executemany(
        "INSERT INTO pca_itens (id, id_pca, ano, numero_item, descricao,"
        " valor_total) VALUES (?,?,?,?,?,?)",
        [("P#1", "P", 2026, 1, "Papel", 100.0),
         ("P#2", "P", 2026, 2, "Toner", 900.0)])
    db.commit()
    db.close()
    return licitarium.Api()


def test_ordenacao_por_coluna(api):
    r = api.listar("contratacoes", {"ord": "objeto", "dir": "asc"})
    assert [i["objeto"] for i in r["itens"]] == ["Arroz", "Milho", "Zebra"]
    r = api.listar("contratacoes", {"ord": "valor", "dir": "desc"})
    # valor = COALESCE(homologado, estimado): B=25, C=15, A=10
    assert [i["numero_controle"] for i in r["itens"]] == ["B", "C", "A"]
    r = api.listar("contratacoes", {"ord": "numero", "dir": "asc"})
    # cronológico: 1/2025, 1/2026, 2/2026 (fixture: C=1/2025? A e B são 2026)
    assert [i["numero_controle"] for i in r["itens"]][0] == "C"


def test_ordenacao_invalida_cai_no_padrao(api):
    r = api.listar("contratacoes", {"ord": "raw; DROP TABLE config", "dir": "asc"})
    # coluna fora da whitelist é ignorada -> padrão data_publicacao DESC
    assert [i["numero_controle"] for i in r["itens"]] == ["B", "A", "C"]


def test_listar_e_detalhe_pca(api):
    r = api.listar("pca", {"ord": "valor", "dir": "desc"})
    assert [i["descricao"] for i in r["itens"]] == ["Toner", "Papel"]
    d = api.detalhe("pca", "P#1")
    assert d["descricao"] == "Papel"


def test_abrir_pncp_ata_monta_url_da_ata(api, monkeypatch):
    db = licitarium.abrir_db()
    db.execute(
        "INSERT INTO atas (numero_controle, raw) VALUES (?, '{}')",
        ("45148970000177-1-000030/2026-000010",))
    db.commit()
    db.close()
    urls = []
    monkeypatch.setattr(licitarium.webbrowser, "open", urls.append)
    assert api.abrir_pncp("atas", "45148970000177-1-000030/2026-000010")
    assert urls == ["https://pncp.gov.br/app/atas/45148970000177/2026/30/10"]
    # número fora do padrão não abre link errado
    db = licitarium.abrir_db()
    db.execute("INSERT INTO atas (numero_controle, raw) VALUES ('X', '{}')")
    db.commit()
    db.close()
    assert not api.abrir_pncp("atas", "X")
    assert len(urls) == 1


def test_script_atualizacao():
    from pathlib import PurePath
    s = licitarium._script_atualizacao(PurePath(r"C:\App\Licitarium.exe"),
                                       PurePath(r"C:\d\novo.exe"))
    assert r'del "C:\App\Licitarium.exe"' in s
    assert r'move /y "C:\d\novo.exe" "C:\App\Licitarium.exe"' in s
    assert 'start "" "C:' in s and "goto espera" in s


def test_migracao_atas_reprojeta_do_raw(tmp_path, monkeypatch):
    """Banco 0.2.0 (atas sem numero_ata) ganha as colunas preenchidas do raw."""
    import json
    import sqlite3 as sq
    monkeypatch.setattr(licitarium, "DIR_DADOS", tmp_path)
    monkeypatch.setattr(licitarium, "ARQUIVO_DB", tmp_path / "m.db")
    con = sq.connect(tmp_path / "m.db")
    con.execute("CREATE TABLE atas (numero_controle TEXT PRIMARY KEY,"
                " contratacao_controle TEXT, orgao_cnpj TEXT,"
                " vigencia_inicio TEXT, vigencia_fim TEXT,"
                " data_atualizacao TEXT, raw TEXT, sync_em TEXT)")
    con.execute("INSERT INTO atas (numero_controle, raw) VALUES ('X', ?)",
                (json.dumps({"numeroAtaRegistroPreco": "13", "anoAta": 2026}),))
    con.commit()
    con.close()
    con = sq.connect(tmp_path / "m.db")
    con.execute("CREATE TABLE contratos (numero_controle TEXT PRIMARY KEY,"
                " contratacao_controle TEXT, orgao_cnpj TEXT,"
                " fornecedor_ni TEXT, fornecedor_nome TEXT, objeto TEXT,"
                " valor_global REAL, vigencia_inicio TEXT, vigencia_fim TEXT,"
                " data_publicacao TEXT, data_atualizacao TEXT, raw TEXT,"
                " sync_em TEXT)")
    con.execute("INSERT INTO contratos (numero_controle, raw) VALUES ('Y', ?)",
                (json.dumps({"numeroContratoEmpenho": "0033/26",
                             "anoContrato": 2026, "sequencialContrato": 35}),))
    con.commit()
    con.close()
    db = licitarium.abrir_db()
    r = db.execute("SELECT numero_ata, ano_ata FROM atas").fetchone()
    c = db.execute("SELECT numero_contrato, ano_contrato, sequencial_contrato"
                   " FROM contratos").fetchone()
    db.close()
    assert (r["numero_ata"], r["ano_ata"]) == ("13", 2026)
    assert (c["numero_contrato"], c["ano_contrato"],
            c["sequencial_contrato"]) == ("0033/26", 2026, 35)


def test_filtro_por_orgao(api):
    assert api.listar("contratacoes", {"orgao": "111"})["total"] == 2
    assert api.listar("contratacoes", {"orgao": "222"})["total"] == 1
    assert api.listar("contratacoes", {"orgao": "999"})["total"] == 0


def test_filtro_ano_pca(api):
    assert api.listar("pca", {"ano": 2026})["total"] == 2
    assert api.listar("pca", {"ano": 2024})["total"] == 0
