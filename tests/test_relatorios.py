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


def test_fracionamento_tem_o_medidor_de_limite(db, tmp_path):
    """Pedido do usuário (2026-08-08): a tabela já tinha o farol em texto
    ("ACIMA DO LIMITE"/"Atenção") — o gráfico (porta de
    ui/painel.js:grafLimites) mostra a distância até lá num olhar só, com
    "×o limite" acima de 100% em vez de uma barra do tamanho da de 100%
    escondendo a gravidade."""
    db.execute("UPDATE contratacoes SET modalidade_id=8, unidade='Sec. Adm'"
               " WHERE ano=2026")
    db.commit()
    r = relatorios.gerar(db, "fracionamento", {"ano": 2026, "limites":
                         {"compras": 100}}, "T", "SP", tmp_path)
    html = Path(r["html"]).read_text(encoding="utf-8")
    assert html.count("<svg") >= 1
    assert "2,8× o limite" in html      # 280/100
    assert "var(--erro)" in html        # cor de estouro


def test_relatorio_imprime_no_mesmo_tema_da_tela(db, tmp_path):
    """Achado do usuário (2026-08-08): o relatório saía sempre em pergaminho
    na impressão, mesmo com outro tema ativo na tela (ex.: Portal). Agora
    acompanha o tema passado sem override — inclusive o Observatório, que
    antes virava claro só no papel."""
    r = relatorios.gerar(db, "contratacoes", {"ano": 2026}, "T", "SP",
                         tmp_path, tema="observatorio")
    html = Path(r["html"]).read_text(encoding="utf-8")
    assert "#10151c" in html               # paleta escura na tela...
    assert "#f5efe2" not in html           # ...e nenhum override pergaminho
    assert "#faf6ec" not in html           # zebra também não força claro


def test_todos_os_relatorios_saem_em_paisagem(db, tmp_path):
    """Pedido do usuário (2026-08-08): melhor uso da largura da página —
    executivo e fracionamento eram os dois únicos ainda em retrato."""
    db.execute("UPDATE contratacoes SET modalidade_id=8 WHERE ano=2026")
    db.commit()
    for tipo, params in (("executivo", {"ano": 2026}),
                         ("fracionamento", {"ano": 2026}),
                         ("contratacoes", {"ano": 2026}),
                         ("contratos", {}), ("atas", {})):
        r = relatorios.gerar(db, tipo, params, "T", "SP", tmp_path)
        html = Path(r["html"]).read_text(encoding="utf-8")
        assert "landscape" in html, f"{tipo} não saiu em paisagem"
        assert "portrait" not in html, f"{tipo} ainda tem @page portrait"


def test_executivo_usa_os_graficos_do_painel(db, tmp_path):
    """Pedido do usuário (2026-08-08): o resumo executivo reaproveita os
    gráficos do Painel (mesma consulta, dados_painel) em vez de só tabelas
    com uma barra de largura fixa via CSS."""
    r = relatorios.gerar(db, "executivo", {"ano": 2026}, "T", "SP", tmp_path)
    html = Path(r["html"]).read_text(encoding="utf-8")
    assert html.count("<svg") >= 2       # sparkline do hero + colunas do mês
    assert 'class="card hero"' in html
    assert 'class="card kpiv"' in html
    assert "Por modalidade — valor homologado" in html


def test_minuta_pca_mostra_a_curva_abc():
    """Pedido do usuário (2026-08-08): pca_builder.classificar_abc já rodava
    dentro de listar_minuta e alimentava a tela de Montar PCA, mas a classe
    nunca aparecia no documento impresso — só a lista crua de itens."""
    d = {"ano": 2027, "parametros": {"margem": 10},
         "totais": {"grupos": 3, "valor": 1000.0},
         "itens": [
             {"descricao": "Item A", "categoria": "Material", "unidade": "UN",
              "quantidade": 1, "valor_unitario": 800.0, "valor_total": 800.0,
              "abc": "A"},
             {"descricao": "Item B", "categoria": "Material", "unidade": "UN",
              "quantidade": 1, "valor_unitario": 150.0, "valor_total": 150.0,
              "abc": "B"},
             {"descricao": "Item C", "categoria": "Material", "unidade": "UN",
              "quantidade": 1, "valor_unitario": 50.0, "valor_total": 50.0,
              "abc": "C"},
         ]}
    html = relatorios.render_minuta_pca(d, "T", "SP")
    assert "Curva ABC" in html
    assert "1 item classe A = 80% do valor" in html
    assert "1 item classe B = 15% do valor" in html
    assert "1 item classe C = 5% do valor" in html
    assert '<th class="ctr" title="Curva ABC' in html


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


def test_url_pncp_do_processo():
    assert relatorios.url_pncp("96291141000180", 2024, 4344) == \
        "https://pncp.gov.br/app/editais/96291141000180/2024/4344"
    # sem os três dados não há link: melhor nenhum do que quebrado
    for faltando in (("", 2024, 1), ("111", None, 1), ("111", 2024, None)):
        assert relatorios.url_pncp(*faltando) is None


def test_relatorio_de_precos_liga_o_processo_ao_pncp(db):
    """Transparência: quem recebe o documento confere na fonte oficial."""
    db.execute(
        "INSERT INTO itens (id, contratacao_controle, orgao_cnpj, ano,"
        " sequencial, numero_item, descricao, unidade, quantidade_homologada,"
        " valor_unitario_homologado, valor_total_homologado, fornecedor_nome,"
        " data_resultado, municipio_ibge)"
        " VALUES ('P#1','C-1','96291141000180',2024,4344,1,'PAPEL HIGIENICO',"
        " 'Fardo 64,00 RO',200,28.8,5760.0,'QUALITY PAPER LTDA',"
        " '2024-09-26','3536604')")
    db.commit()
    html = relatorios.render_precos(
        relatorios.dados_precos(db, "papel"), "Orindiúva", "SP")
    assert ('href="https://pncp.gov.br/app/editais/96291141000180/2024/4344"'
            in html)
    assert ">4344/2024</a>" in html
    # município e unidade em coluna que não quebra
    assert '<td class="muni">' in html and '<td class="unid">' in html
    assert "white-space:nowrap" in html
