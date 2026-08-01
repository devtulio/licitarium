"""Testes dos relatórios (consultas + geração de arquivos)."""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import licitarium
import relatorios


@pytest.fixture
def db():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(licitarium.SCHEMA)
    raw_c = json.dumps({"amparoLegal": {"nome": "Art. 75, II"}})
    con.executemany(
        "INSERT INTO contratacoes (numero_controle, ano, sequencial,"
        " modalidade_nome, objeto, valor_estimado, valor_homologado,"
        " data_publicacao, raw) VALUES (?,?,?,?,?,?,?,?,?)",
        [("A", 2026, 1, "Dispensa", "Merenda", 100.0, 80.0,
          "2026-03-01", raw_c),
         ("B", 2026, 2, "Pregão", "Obras", 200.0, None, "2026-04-01", raw_c),
         ("C", 2025, 1, "Pregão", "Antigo", 50.0, 50.0, "2025-01-01", raw_c)])
    con.executemany(
        "INSERT INTO contratos (numero_controle, fornecedor_nome, objeto,"
        " valor_global, vigencia_inicio, vigencia_fim, data_publicacao, raw)"
        " VALUES (?,?,?,?,?,?,?,?)",
        [("CT1", "Fornecedor X", "Serviço", 1000.0, "2026-01-01", "2099-01-01",
          "2026-01-05", json.dumps({"numeroContratoEmpenho": "7/2026"})),
         ("CT2", "Fornecedor Y", "Vencido", 500.0, "2020-01-01", "2020-12-31",
          "2020-01-05", "{}")])
    con.execute(
        "INSERT INTO atas (numero_controle, contratacao_controle,"
        " vigencia_inicio, vigencia_fim, raw) VALUES (?,?,?,?,?)",
        ("AT1", "A", "2026-01-01", "2099-01-01",
         json.dumps({"numeroAtaRegistroPreco": "9", "anoAta": 2026,
                     "objetoContratacao": "RP merenda"})))
    con.commit()
    yield con
    con.close()


def test_dados_contratacoes_amparo_e_desagio(db):
    d = relatorios.dados_contratacoes(db, ano=2026)
    assert d["totais"]["n"] == 2
    assert d["linhas"][0]["amparo"] == "Art. 75, II"
    # deságio só sobre o processo com ambos os valores: 1 - 80/100 = 20%
    assert round(d["totais"]["desagio"], 1) == 20.0
    assert d["totais"]["estimado"] == 300.0


def test_dados_contratos_vigentes(db):
    assert relatorios.dados_contratos(db, vigentes=True)["totais"]["n"] == 1
    assert relatorios.dados_contratos(db, ano=2020)["totais"]["n"] == 1
    assert relatorios.dados_contratos(db)["totais"]["n"] == 2


def test_dados_executivo(db):
    d = relatorios.dados_executivo(db, 2026)
    assert d["cards"]["n"] == 2
    assert d["cards"]["contratos_vigentes"] == 1
    # contrato e ata com fim em 2099 não entram nos 90 dias
    assert d["vencendo"] == []
    assert d["meses"]["03"]["n"] == 1


def test_gerar_html_e_csv(db, tmp_path):
    r = relatorios.gerar(db, "contratacoes", {"ano": 2026},
                         "Testópolis", "SP", tmp_path)
    html = Path(r["html"]).read_text(encoding="utf-8")
    assert "Testópolis" in html and "MERENDA" not in html  # caixa alta é CSS
    assert "Merenda" in html and "Art. 75, II" in html
    assert "2 contratações" in html
    csv_texto = Path(r["csv"]).read_text(encoding="utf-8-sig")
    assert csv_texto.splitlines()[0].startswith("sequencial;ano;")
    assert len(csv_texto.splitlines()) == 3  # cabeçalho + 2 linhas


def test_gerar_executivo_sem_csv(db, tmp_path):
    r = relatorios.gerar(db, "executivo", {"ano": 2026}, "T", "SP", tmp_path)
    assert r["csv"] is None
    assert "Resumo Executivo" in Path(r["html"]).read_text(encoding="utf-8")


def test_filtro_orgao_nos_relatorios(db, tmp_path):
    db.execute("UPDATE contratacoes SET orgao_cnpj='111'")
    db.execute("UPDATE contratacoes SET orgao_cnpj='222'"
               " WHERE numero_controle='A'")
    db.commit()
    assert relatorios.dados_contratacoes(db, ano=2026,
                                         orgao="222")["totais"]["n"] == 1
    assert relatorios.dados_executivo(db, 2026, orgao="222")["cards"]["n"] == 1
    r = relatorios.gerar(db, "contratacoes",
                         {"ano": 2026, "orgao": "222",
                          "orgao_nome": "Câmara de Testópolis"},
                         "Testópolis", "SP", tmp_path)
    assert "orgao_222" in r["html"]
    assert "Câmara de Testópolis" in Path(r["html"]).read_text(encoding="utf-8")


def test_precos_estatisticas_e_relatorio(db, tmp_path):
    db.executemany(
        "INSERT INTO itens (id, contratacao_controle, ano, sequencial,"
        " numero_item, descricao, unidade, quantidade_homologada,"
        " valor_unitario_homologado, valor_total_homologado, fornecedor_ni,"
        " fornecedor_nome, data_resultado) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [("a", "A", 2026, 1, 1, "PAPEL A4 75G", "RESMA", 10, 20.0, 200.0,
          "1", "FORN A", "2026-03-10"),
         ("b", "A", 2026, 1, 2, "PAPEL A4 90G", "RESMA", 5, 30.0, 150.0,
          "2", "FORN B", "2026-04-10"),
         ("c", "B", 2025, 9, 1, "PAPEL A4 75G", "RESMA", 8, 10.0, 80.0,
          "1", "FORN A", "2025-05-10"),
         ("d", "B", 2025, 9, 2, "CANETA AZUL", "UN", 100, 1.5, 150.0,
          "1", "FORN A", "2025-05-10")])
    db.commit()
    d = relatorios.dados_precos(db, "papel")
    assert d["resumo"]["n"] == 3
    assert d["resumo"]["minimo"] == 10.0 and d["resumo"]["maximo"] == 30.0
    assert d["resumo"]["mediana"] == 20.0          # 10, 20, 30
    assert d["resumo"]["fornecedores"] == 2
    assert [l["valor_unitario_homologado"] for l in d["linhas"]] == [10., 20., 30.]
    # filtro por exercício
    assert relatorios.dados_precos(db, "papel", ano=2025)["resumo"]["n"] == 1
    r = relatorios.gerar(db, "precos", {"termo": "papel A4"}, "T", "SP", tmp_path)
    html = Path(r["html"]).read_text(encoding="utf-8")
    assert "Pesquisa de Preços" in html and "art. 23" in html
    assert "pesquisa_precos_papel_a4" in r["html"]
    assert r["csv"] and Path(r["csv"]).exists()


def test_precos_termo_vazio_e_sem_achados(db, tmp_path):
    with pytest.raises(ValueError):
        relatorios.gerar(db, "precos", {"termo": "  "}, "T", "SP", tmp_path)
    r = relatorios.gerar(db, "precos", {"termo": "inexistente"}, "T", "SP",
                         tmp_path)
    assert "Nenhum item homologado" in Path(r["html"]).read_text(encoding="utf-8")
    assert r["csv"] is None


def test_num_contrato_normaliza():
    assert relatorios.num_contrato("0033/26", 2026) == "33/2026"
    assert relatorios.num_contrato("35", 2026) == "35/2026"
    assert relatorios.num_contrato("7/2026", 2026) == "7/2026"
    assert relatorios.num_contrato(None, 2026) is None
    assert relatorios.num_contrato("0042/25", None) == "42"


def test_fracionamento(db, tmp_path):
    db.execute("UPDATE contratacoes SET modalidade_id=8, unidade='Sec. Adm'"
               " WHERE ano=2026")
    db.commit()
    d = relatorios.dados_fracionamento(db, 2026, limites={"compras": 100})
    # A: homologado 80; B: sem homologado, cai no estimado 200 -> total 280
    assert d["n"] == 2 and d["total"] == 280.0
    assert d["unidades"][0]["pct"] == 280.0
    r = relatorios.gerar(db, "fracionamento", {"ano": 2026},
                         "Testópolis", "SP", tmp_path)
    html = Path(r["html"]).read_text(encoding="utf-8")
    assert "Alerta de Fracionamento" in html and "autocontrole" in html
    assert r["csv"] and Path(r["csv"]).exists()


def test_relatorio_segue_tema_mas_imprime_claro(db, tmp_path):
    r = relatorios.gerar(db, "contratacoes", {"ano": 2026}, "T", "SP",
                         tmp_path, tema="observatorio")
    html = Path(r["html"]).read_text(encoding="utf-8")
    assert "#10151c" in html                      # paleta escura na tela
    assert "@media print" in html and "#f5efe2" in html  # impressão clara


def test_tipo_desconhecido(db, tmp_path):
    with pytest.raises(ValueError):
        relatorios.gerar(db, "xxx", {}, "T", "SP", tmp_path)


def test_documento_distingue_cnpj_de_cpf():
    """O `niFornecedor` do PNCP guarda os dois — no acervo real há 34 CPFs.

    Máscara de CNPJ aplicada às cegas transformaria 01472188616 em
    "01.472.188/616-" e o relatório sairia com o documento adulterado.
    """
    assert relatorios.documento("13286494000164") == "13.286.494/0001-64"
    assert relatorios.documento("01472188616") == "014.721.886-16"
    # já formatado na origem continua correto (idempotente)
    assert relatorios.documento("13.286.494/0001-64") == "13.286.494/0001-64"
    # o que não é nenhum dos dois sai como veio, sem inventar pontuação
    assert relatorios.documento("A1B2") == "A1B2"
    assert relatorios.documento("123") == "123"
    assert relatorios.documento(None) == "–"
    assert relatorios.documento("") == "–"


def test_relatorios_imprimem_documento_com_mascara(db):
    db.execute(
        "INSERT INTO contratos (numero_controle, orgao_cnpj, fornecedor_ni,"
        " fornecedor_nome, objeto, valor_global, data_publicacao, raw)"
        " VALUES ('K-1','111','13286494000164','FORN LTDA','Objeto',10.0,"
        " '2026-02-02','{}')")
    db.execute(
        "INSERT INTO contratos (numero_controle, orgao_cnpj, fornecedor_ni,"
        " fornecedor_nome, objeto, valor_global, data_publicacao, raw)"
        " VALUES ('K-2','111','01472188616','JOSE DA SILVA','Objeto',10.0,"
        " '2026-02-03','{}')")
    db.commit()
    html = relatorios.render_contratos(
        relatorios.dados_contratos(db, ano=2026), "Orindiúva", "SP", "2026")
    assert "13.286.494/0001-64" in html
    assert "014.721.886-16" in html
    assert "13286494000164" not in html      # nada de número cru
