"""Testes dos relatórios (consultas + geração de arquivos)."""
import json
import re
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


def test_data_now_do_sql_sempre_em_localtime():
    """date('now')/datetime('now') do SQLite são UTC. Entre ~21h e meia-noite
    de Brasília, o UTC já é o dia seguinte — um contrato vencendo hoje lia
    como já vencido nos painéis de vigência/prazo (auditoria 2026-08-11).
    Comportamento depende do fuso da máquina que roda o teste (não dá pra
    simular sem mockar as funções de data do próprio SQLite), então a
    garantia aqui é estática: nenhum 'now' bruto sobra no arquivo."""
    fonte = Path(relatorios.__file__).read_text(encoding="utf-8")
    nus = re.findall(r"(?:date|datetime)\('now'(?!,'localtime')[^)]*\)", fonte)
    assert not nus, f"'now' sem localtime: {nus}"


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


def test_executivo_usa_grafico_pronto_quando_vem_da_tela(db, tmp_path):
    """`graficos` (ECharts que a tela já desenhou, achado 2026-08-11, mesmo
    padrão da pesquisa de preços) substitui `_grafico_meses`/`_grafico_barras`
    slot a slot; sem ele, o fallback hand-SVG segue funcionando."""
    marcador_meses = '<svg id="meses-de-mentirinha"></svg>'
    marcador_mod = '<svg id="modalidade-de-mentirinha"></svg>'
    r = relatorios.gerar(db, "executivo",
                         {"ano": 2026, "graficos": {"meses": marcador_meses,
                                                    "modalidade": marcador_mod}},
                         "T", "SP", tmp_path)
    html = Path(r["html"]).read_text(encoding="utf-8")
    assert marcador_meses in html and marcador_mod in html

    r2 = relatorios.gerar(db, "executivo", {"ano": 2026}, "T", "SP", tmp_path)
    html2 = Path(r2["html"]).read_text(encoding="utf-8")
    assert marcador_meses not in html2
    assert "<svg" in html2   # o fallback ainda desenha algo


def test_render_detalhe_usa_o_html_que_a_tela_ja_montou():
    """Ficha do modal de detalhe (achado 2026-08-12): `meta_html` vem
    pronto — rótulo/valor já formatados — e entra sem reimplementar nada
    em Python; só título e subtítulo passam pelo escape de sempre."""
    meta = ('<div><div class="k">Órgão</div>'
            '<div class="v">Prefeitura &amp; Câmara</div></div>')
    html = relatorios.render_detalhe(
        "Aquisição de <material>", "12345/2026-1", meta, "T", "SP")
    assert meta in html                        # HTML pronto, sem retoque
    assert "&lt;material&gt;" in html          # título passa pelo escape
    assert "12345/2026-1" in html
    assert 'size: A4 portrait' in html         # ficha de um registro é retrato


def test_render_detalhe_leva_o_json_colorido_do_modal():
    """achado 2026-08-12: a ficha impressa saía sem o "Dados completos"
    que o modal mostra — pedido do usuário, mesmo padrão de meta_html:
    a tela já colore (jsonColorido), o Python só encaixa."""
    raw = '<span class="j-chave">"objeto"</span>: <span class="j-str">"x"</span>'
    html = relatorios.render_detalhe("T", "1/2026", "<div></div>", "T", "SP",
                                     raw_html=raw)
    assert raw in html
    assert "Dados completos" in html

    sem_raw = relatorios.render_detalhe("T", "1/2026", "<div></div>", "T", "SP")
    assert "Dados completos" not in sem_raw    # sem raw_html, nem a seção aparece


def test_render_detalhe_cabecalho_e_municipio_objeto_desce_pro_corpo():
    """Pedido do usuário (2026-08-12): o cabeçalho é brasão + identificação
    do município (não o objeto, que é comprido demais pra ficar ali) —
    o objeto desce pro corpo, em caixa alta e justificado."""
    html = relatorios.render_detalhe(
        "objeto bem comprido de uma contratação qualquer", "1/2026",
        "<div></div>", "Orindiúva", "SP")
    # <title> e o h1 do cabeçalho mostram o município, não o objeto
    assert "<title>Orindiúva — SP</title>" in html
    assert "<h1>Orindiúva — SP</h1>" in html
    # o objeto vira parágrafo próprio, fora do cabeçalho, com a classe
    # que aplica caixa alta + justificado
    assert ('<p class="ficha-objeto">objeto bem comprido de uma '
            'contratação qualquer</p>') in html


def test_gerar_economia_sem_itens_nao_gera_csv(db, tmp_path):
    """Sem item com par estimado/homologado, por_familia fica vazia — mesmo
    critério de "sem dados" que os outros relatórios já usam (linhas_csv
    vazia não gera arquivo)."""
    r = relatorios.gerar(db, "economia", {"ano": 2026}, "T", "SP", tmp_path)
    assert r["csv"] is None
    html = Path(r["html"]).read_text(encoding="utf-8")
    assert "Economia e Comparativos" in html
    # 300 estimados (A+B) - 80 homologados (só A) = 220
    assert "220,00" in html


def test_economia_usa_graficos_prontos_nos_quatro_slots(db, tmp_path):
    """Os 4 gráficos de barra (modalidade/família/categoria/fornecedor)
    aceitam o SVG pronto vindo da tela, cada um no seu slot."""
    marcadores = {k: f'<svg id="{k}-de-mentirinha"></svg>'
                 for k in ("modalidade", "familia", "categoria", "fornecedor")}
    r = relatorios.gerar(db, "economia", {"ano": 2026, "graficos": marcadores},
                         "T", "SP", tmp_path)
    html = Path(r["html"]).read_text(encoding="utf-8")
    for marcador in marcadores.values():
        assert marcador in html


def test_gerar_economia_com_itens_traz_familia_no_documento_e_no_csv(db, tmp_path):
    db.execute(
        "INSERT INTO itens (id, contratacao_controle, ano, descricao,"
        " categoria, valor_total_estimado, valor_total_homologado,"
        " referencia, raw) VALUES ('A#1','A',2026,'MERENDA ESCOLAR',"
        " 'Alimentação',100.0,80.0,0,'{}')")
    db.commit()
    r = relatorios.gerar(db, "economia", {"ano": 2026}, "T", "SP", tmp_path)
    assert r["csv"] is not None
    csv_texto = Path(r["csv"]).read_text(encoding="utf-8-sig")
    assert "MERENDA ESCOLAR" in csv_texto
    html = Path(r["html"]).read_text(encoding="utf-8")
    assert "MERENDA ESCOLAR" in html
    assert "Alimentação" in html            # tabela por categoria


def test_economia_por_modalidade_nao_corta_o_grafico(db, tmp_path):
    """O gráfico "Por modalidade" cortava em 8 (relatorios.py, achado da
    auditoria 2026-08-11) enquanto a tabela logo abaixo, na mesma página,
    e a vista Economia na tela mostram a lista inteira — um município com
    mais de 8 modalidades no exercício via gráfico e tabela discordando em
    quantidade de itens. Sem par estimado/homologado por linha independente
    e valor_estimado decrescente, a nona modalidade era exatamente a que
    sumia do gráfico."""
    db.executemany(
        "INSERT INTO contratacoes (numero_controle, ano, sequencial,"
        " modalidade_nome, objeto, valor_estimado, valor_homologado,"
        " data_publicacao, referencia) VALUES (?,2026,?,?,?,?,?,'2026-01-01',0)",
        [(f"M{i}", i, f"Modalidade {i}", "Objeto",
          float(100 - i), float(80 - i)) for i in range(1, 10)])
    db.commit()
    r = relatorios.gerar(db, "economia", {"ano": 2026}, "T", "SP", tmp_path)
    html = Path(r["html"]).read_text(encoding="utf-8")
    grafico = html.split("Por modalidade</h3>")[1].split("Por família de item")[0]
    for i in range(1, 10):
        assert f"Modalidade {i}" in grafico, f"Modalidade {i} sumiu do gráfico"


def test_economia_lista_fornecedores_com_documento_mascarado(db, tmp_path):
    """CNPJ e CPF convivem no `niFornecedor` do PNCP — a máscara é escolhida
    pelo número de dígitos (`documento()`), nunca aplicada às cegas."""
    db.executemany(
        "INSERT INTO itens (id, contratacao_controle, ano, descricao,"
        " fornecedor_ni, fornecedor_nome, valor_total_estimado,"
        " valor_total_homologado, referencia, raw)"
        " VALUES (?,?,2026,?,?,?,?,?,0,'{}')",
        [("A#1", "A", "MERENDA", "11222333000144", "ALIMENTOS SA",
          100.0, 80.0),
         ("A#2", "A", "CONSULTORIA", "12345678901", "JOSE DA SILVA",
          50.0, 45.0)])
    db.commit()
    r = relatorios.gerar(db, "economia", {"ano": 2026}, "T", "SP", tmp_path)
    html = Path(r["html"]).read_text(encoding="utf-8")
    assert "Economia por fornecedor" in html
    assert "11.222.333/0001-44" in html          # CNPJ, 14 dígitos
    assert "123.456.789-01" in html              # CPF, 11 dígitos
    # o de maior economia vem primeiro na tabela
    assert html.index("ALIMENTOS SA") < html.index("JOSE DA SILVA")


def test_sem_brasao_configurado_mantem_o_estandarte(db, tmp_path):
    r = relatorios.gerar(db, "contratacoes", {"ano": 2026}, "T", "SP", tmp_path)
    html = Path(r["html"]).read_text(encoding="utf-8")
    assert 'viewBox="0 0 64 64"' in html          # o estandarte, sem trocar
    assert "<img" not in html


def test_com_brasao_configurado_ele_substitui_o_estandarte(db, tmp_path):
    db.execute("INSERT INTO config (chave, valor) VALUES"
               " ('brasao', 'data:image/png;base64,QQ==')")
    db.commit()
    r = relatorios.gerar(db, "contratacoes", {"ano": 2026}, "T", "SP", tmp_path)
    html = Path(r["html"]).read_text(encoding="utf-8")
    assert ('<img src="data:image/png;base64,QQ==" alt="Brasão do '
            'município"') in html
    assert 'viewBox="0 0 64 64"' not in html      # estandarte saiu do cabeçalho
    assert "LICITARIVM" in html                   # mas segue no rodapé


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


def test_precos_estatisticas_e_relatorio(db, tmp_path, selecionar_tudo):
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
    selecionar_tudo(db, "papel A4")
    r = relatorios.gerar(db, "precos", {"termo": "papel A4"}, "T", "SP", tmp_path)
    html = Path(r["html"]).read_text(encoding="utf-8")
    assert "Pesquisa de Preços" in html and "art. 23" in html
    assert "pesquisa_precos_papel_a4" in r["html"]
    assert r["csv"] and Path(r["csv"]).exists()


def test_precos_a_zero_reais_nao_quebra_o_coeficiente_de_variacao(
        db, tmp_path, selecionar_tudo):
    """cv = desvio/média, None quando a média é exatamente zero (itens de
    doação/brinde na pesquisa). desvio ainda existe (é 0.0, "não é None"),
    então a guarda antiga (checava desvio) deixava passar e
    r["cv"] * 100 quebrava sobre None (achado da auditoria 2026-08-11)."""
    db.executemany(
        "INSERT INTO itens (id, contratacao_controle, ano, sequencial,"
        " numero_item, descricao, unidade, quantidade_homologada,"
        " valor_unitario_homologado, valor_total_homologado, fornecedor_ni,"
        " fornecedor_nome, data_resultado) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [("a", "A", 2026, 1, 1, "BRINDE CANETA", "UN", 10, 0.0, 0.0,
          "1", "FORN A", "2026-03-10"),
         ("b", "A", 2026, 1, 2, "BRINDE CANETA", "UN", 5, 0.0, 0.0,
          "2", "FORN B", "2026-04-10")])
    db.commit()
    d = relatorios.dados_precos(db, "brinde caneta")
    assert d["resumo"]["media"] == 0.0
    assert d["resumo"]["desvio"] == 0.0
    assert d["resumo"]["cv"] is None
    selecionar_tudo(db, "brinde caneta")
    r = relatorios.gerar(db, "precos", {"termo": "brinde caneta"}, "T", "SP",
                         tmp_path)
    html = Path(r["html"]).read_text(encoding="utf-8")
    assert "Pesquisa de Preços" in html   # não quebrou


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


def test_teto_da_dispensa_classifica_pelo_amparo_nao_pela_modalidade():
    """Achado 2026-08-12, portado do licitarium-relatorios: `modalidade_id=8`
    (Dispensa) não é sinônimo de "sujeita ao limite do art. 75, II" — o
    amparo (lido do `raw`) é quem decide, e três situações precisam de
    tratamento diferente."""
    # art. 75, II — compras/serviços comuns: responde ao teto de compras
    assert relatorios.teto_da_dispensa(
        "Lei 14.133/2021, Art. 75, II", 100.0, 200.0) == 100.0
    # formato curto (sem "Lei 14.133/2021,") também casa
    assert relatorios.teto_da_dispensa("Art. 75, II", 100.0, 200.0) == 100.0
    # art. 75, I — obras/serviços de engenharia: teto PRÓPRIO
    assert relatorios.teto_da_dispensa(
        "Lei 14.133/2021, Art. 75, I", 100.0, 200.0) == 200.0
    # inciso III (e demais) não tem teto por valor — "I" não pode casar
    # como prefixo de "III"
    assert relatorios.teto_da_dispensa(
        "Lei 14.133/2021, Art. 75, III", 100.0, 200.0) is None
    # outra lei (agricultura familiar etc.): dispensa própria, sem teto
    assert relatorios.teto_da_dispensa("Lei 11.947/2009", 100.0, 200.0) \
        is None
    # amparo ausente: conservador — não afirma limite que não se sabe
    assert relatorios.teto_da_dispensa(None, 100.0, 200.0) is None


def test_dispensa_sem_teto_por_valor_nao_soma_e_fica_declarada(db):
    """O falso positivo real que motivou a correção: R$ 1.057.448,50 de
    agricultura familiar (dispensa própria, Lei 11.947/2009, sem teto por
    valor) aparecia como "1688% do limite" — o maior valor da lista, sem
    irregularidade nenhuma."""
    raw_af = json.dumps({"amparoLegal": {"nome": "Lei 11.947/2009"}})
    db.execute(
        "INSERT INTO contratacoes (numero_controle, ano, sequencial,"
        " orgao_cnpj, unidade, modalidade_id, modalidade_nome, objeto,"
        " valor_homologado, data_publicacao, referencia, raw)"
        " VALUES ('AF1',2026,50,'111','Sec. Adm',8,'Dispensa',"
        " 'Gêneros da agricultura familiar',1057448.50,'2026-06-01',0,?)",
        (raw_af,))
    db.execute("UPDATE contratacoes SET modalidade_id=8, unidade='Sec. Adm'"
               " WHERE ano=2026 AND numero_controle IN ('A','B')")
    db.commit()

    d = relatorios.dados_fracionamento(db, 2026, limites={"compras": 100})
    # a dispensa sem teto não conta no total nem nas unidades...
    assert d["total"] == 280.0
    assert all(u["total"] != pytest.approx(1057448.50) for u in d["unidades"])
    # ...mas também não desaparece: sai declarada à parte
    assert len(d["fora_do_limite_legal"]) == 1
    assert d["fora_do_limite_legal"][0]["objeto"] == \
        "Gêneros da agricultura familiar"


def test_obra_e_medida_contra_o_limite_de_obras_nao_de_compras(db):
    """Art. 75, I (obras/serviços de engenharia) tem teto PRÓPRIO — antes,
    tudo caía no limite de compras e uma obra de R$ 150 mil marcava 150%
    quando o certo era medir contra o limite dobrado."""
    raw_obra = json.dumps({"amparoLegal": {"nome": "Lei 14.133/2021, Art. 75, I"}})
    db.execute(
        "INSERT INTO contratacoes (numero_controle, ano, sequencial,"
        " orgao_cnpj, unidade, modalidade_id, modalidade_nome, objeto,"
        " valor_homologado, data_publicacao, referencia, raw)"
        " VALUES ('OB1',2026,60,'111','Obras',8,'Dispensa',"
        " 'Reforma de telhado',150000.0,'2026-06-01',0,?)", (raw_obra,))
    db.commit()

    d = relatorios.dados_fracionamento(
        db, 2026, limites={"compras": 100000, "obras": 200000})
    obra = next(u for u in d["unidades"] if u["unidade"] == "Obras")
    assert obra["tipo"] == "obras"
    assert obra["pct"] == pytest.approx(75.0)   # 150.000 / 200.000, não / 100.000


def test_dois_orgaos_sob_o_teto_nao_somam_pra_estourar(db):
    """O teto do art. 75 é "por órgão ou entidade" (§1º) — Prefeitura e
    Câmara que dispensam a mesma coisa têm cada uma o seu limite. Somar as
    duas contra um teto só acusaria fracionamento onde há duas compras
    legais."""
    raw_ii = json.dumps({"amparoLegal": {"nome": "Art. 75, II"}})
    db.executemany(
        "INSERT INTO contratacoes (numero_controle, ano, sequencial,"
        " orgao_cnpj, orgao_nome, unidade, modalidade_id, modalidade_nome,"
        " objeto, valor_homologado, data_publicacao, referencia, raw)"
        " VALUES (?,2026,?,?,?,'Sec. Adm',8,'Dispensa','Material',"
        " 60000.0,'2026-06-01',0,?)",
        [("PREF1", 70, "111", "PREFEITURA", raw_ii),
         ("CAM1", 71, "222", "CÂMARA", raw_ii)])
    db.commit()

    d = relatorios.dados_fracionamento(db, 2026, limites={"compras": 100000})
    pcts = {u["orgao_nome"]: u["pct"] for u in d["unidades"]
           if u["total"] == pytest.approx(60000.0)}
    assert pcts == {"PREFEITURA": pytest.approx(60.0),
                    "CÂMARA": pytest.approx(60.0)}
    # nenhuma das duas passa de 100% sozinha — juntas passariam (120%)
    assert all(pct < 100 for pct in pcts.values())


def test_render_fracionamento_mostra_tipo_e_orgao_quando_ha_mais_de_um(
        db, tmp_path):
    """Coluna Tipo (Obras/Compras) sempre aparece; coluna Órgão só quando
    há mais de um órgão com dispensa no exercício — mesmo padrão da
    coluna Unidade em Contratações."""
    raw_ii = json.dumps({"amparoLegal": {"nome": "Art. 75, II"}})
    db.executemany(
        "INSERT INTO contratacoes (numero_controle, ano, sequencial,"
        " orgao_cnpj, orgao_nome, unidade, modalidade_id, modalidade_nome,"
        " objeto, valor_homologado, data_publicacao, referencia, raw)"
        " VALUES (?,2026,?,?,?,'Sec. Adm',8,'Dispensa','Material',"
        " 1000.0,'2026-06-01',0,?)",
        [("PREF2", 80, "111", "PREFEITURA", raw_ii),
         ("CAM2", 81, "222", "CÂMARA", raw_ii)])
    db.commit()

    r = relatorios.gerar(db, "fracionamento", {"ano": 2026}, "T", "SP", tmp_path)
    html = Path(r["html"]).read_text(encoding="utf-8")
    assert "<th>Órgão</th>" in html
    assert "PREFEITURA" in html and "CÂMARA" in html
    assert "Compras" in html


def test_categoria_relatorio_cobre_os_oito_tipos_em_quatro_cores():
    """Selo de procedência (achado 2026-08-13, portado do diagnóstico de
    identidade do licitarium-relatorios): cada tipo de relatório tem uma
    categoria e uma cor — cadastral/analítico/vigilância/planejamento,
    como a CGU distingue apuração/avaliação/consultoria na capa."""
    tipos_com_pagina = {"contratacoes", "contratos", "atas", "executivo",
                        "economia", "fracionamento", "minuta_pca", "precos"}
    assert set(relatorios.CATEGORIA_RELATORIO) == tipos_com_pagina
    cores = {cor for _, cor in relatorios.CATEGORIA_RELATORIO.values()}
    assert len(cores) == 4
    rotulos = {rotulo for rotulo, _ in relatorios.CATEGORIA_RELATORIO.values()}
    assert rotulos == {"Cadastral", "Analítico", "Vigilância", "Planejamento"}


def test_pagina_sem_categoria_fica_como_antes(db, tmp_path):
    """Painel e ficha de detalhe já têm identidade visual própria e chamam
    `_pagina` sem `categoria` — nenhuma etiqueta, régua ou faixa de acervo
    deve aparecer nesse caso, e o rodapé mantém o texto de sempre."""
    html = relatorios._pagina("Título", "<p>corpo</p>", "T", "SP", "período",
                              paisagem=False)
    assert 'class="etiqueta"' not in html
    assert 'class="regua"' not in html
    assert 'class="faixa-acervo"' not in html
    assert "Documento gerado automaticamente a partir de dados públicos" \
        in html


def test_gerar_traz_etiqueta_da_categoria_e_faixa_de_acervo(db, tmp_path):
    """`gerar()` computa o acervo uma vez (MAX(sync_em) entre as três
    tabelas) e passa a mesma fotografia — mesmo hash — pra qualquer tipo
    de relatório gerado a partir do mesmo estado do banco."""
    db.execute("UPDATE contratacoes SET sync_em='2026-08-13T10:22:00'")
    db.execute("UPDATE contratos SET sync_em='2026-08-13T10:22:00'")
    db.commit()

    r1 = relatorios.gerar(db, "contratacoes", {"ano": 2026}, "T", "SP", tmp_path)
    html1 = Path(r1["html"]).read_text(encoding="utf-8")
    assert '<span class="etiqueta">Cadastral</span>' in html1
    assert "Acervo sincronizado em 13/08/2026 ·" in html1
    assert "Apurado a partir do PNCP · acervo sincronizado em 13/08/2026" \
        in html1

    r2 = relatorios.gerar(db, "contratos", {"ano": 2026}, "T", "SP", tmp_path)
    html2 = Path(r2["html"]).read_text(encoding="utf-8")
    hash1 = html1.split("Acervo sincronizado em 13/08/2026 · ")[1][:6]
    hash2 = html2.split("Acervo sincronizado em 13/08/2026 · ")[1][:6]
    assert hash1 == hash2   # mesmo estado do banco, mesmo hash


def test_metodo_e_categoria_nos_cinco_relatorios_que_nao_tinham(db):
    """Achado 2026-08-13 (portado do diagnóstico de identidade): contratações,
    contratos, atas, executivo e economia não tinham nenhuma nota de método
    — só fracionamento, minuta e preços tinham. Os cinco ganham uma."""
    d_rel = relatorios.dados_contratacoes(db, ano=2026)
    assert '<div class="caixa-aviso">' in relatorios.render_contratacoes(
        d_rel, "T", "SP", "período", categoria=("Cadastral", "acento"))

    d_ct = relatorios.dados_contratos(db, ano=2026)
    assert '<div class="caixa-aviso">' in relatorios.render_contratos(
        d_ct, "T", "SP", "período")

    d_at = relatorios.dados_atas(db, ano=2026)
    assert '<div class="caixa-aviso">' in relatorios.render_atas(
        d_at, "T", "SP", "período")

    d_pn = relatorios.dados_painel(db, 2026)
    assert '<div class="caixa-aviso">' in relatorios.render_executivo(
        d_pn, "T", "SP")
    assert '<div class="caixa-aviso">' in relatorios.render_economia(
        d_pn, "T", "SP")


def test_documento_sai_com_a_paleta_institucional(db, tmp_path):
    """Documento oficial não tem tema (reversão consciente da v1.14.4).

    Lá o relatório passou a seguir o tema da tela porque forçava pergaminho
    e ignorava a escolha do usuário. Aqui a regra é mais forte: o papel que
    vai ao Tribunal de Contas é peça do município — branco, grafite, sem
    ouro nem vinho.

    Que ele não siga a tela virou garantia **estrutural** na v1.20.1: não
    existe mais parâmetro de tema em `gerar`/`render_*`/`_pagina` para
    seguir. O que sobra a testar é a paleta em si.
    """
    import inspect
    assert "tema" not in inspect.signature(relatorios.gerar).parameters

    r = relatorios.gerar(db, "contratacoes", {"ano": 2026}, "T", "SP", tmp_path)
    html = Path(r["html"]).read_text(encoding="utf-8")
    # a paleta é o que importa; o estandarte tem cores próprias cravadas no
    # SVG (design/IDENTIDADE.md: marca não troca de cor com a pele), então a
    # varredura é só no bloco de variáveis
    paleta = re.search(r":root \{(.*?)\}", html, re.S).group(1)
    assert "--bg:#ffffff" in paleta        # papel branco
    assert "#10151c" not in paleta         # nada do Observatório
    assert "#f5efe2" not in paleta         # nem do pergaminho
    assert "#8b2e2e" not in paleta         # nem o vinho do acento antigo
    assert "#b08d3e" not in paleta         # nem o dourado das réguas
    assert "double" not in html            # régua dupla de diploma saiu


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


# ── auditoria de segurança (2026-08-09): dois sinks de XSS armazenado ────────
# O relatório é aberto com `webbrowser.open` no navegador REAL do usuário
# (origem file://), não dentro do WebView — script que sai daqui executa fora
# da janela do programa. Vetor confirmado: `importar_acervo` troca o banco
# inteiro por um .zip de terceiro, validado só por `quick_check`, sem
# conferência de tipo de coluna.

def test_quantidade_nao_numerica_nao_vira_html(db):
    """`quantidade_homologada` é REAL, mas afinidade do SQLite não converte
    texto — ele fica gravado como TEXT e saía cru no `<td class="num">`."""
    payload = "<script>alert(1)</script>"
    for i in range(6):
        db.execute(
            "INSERT INTO itens (id, contratacao_controle, ano, descricao,"
            " unidade, valor_unitario_homologado, quantidade_homologada,"
            " data_resultado, referencia)"
            " VALUES (?,'A',2026,'PAPEL A4 SULFITE','UN',?,?,'2026-01-01',0)",
            (f"Q#{i}", 10.0 + i, payload))
    db.commit()
    html = relatorios.render_precos(
        relatorios.dados_precos(db, "papel"), "T", "SP")
    assert payload not in html
    assert "<script>" not in html

    # a coluna promete número: o que não é número vira travessão
    assert relatorios.quantidade(payload) == "–"
    assert relatorios.quantidade(None) == "–"
    assert relatorios.quantidade(300.0) == "300"
    assert relatorios.quantidade(1500.5) == "1.500,50"


def test_moeda_nao_numerica_nao_derruba_o_relatorio():
    """moeda()/moeda_fina() não tinham a mesma proteção de quantidade() —
    TEXT numa coluna REAL (auditoria 2026-08-09/11) fazia f"{v:,.2f}"
    levantar ValueError e derrubar o relatório inteiro, não só aquela
    célula."""
    assert relatorios.moeda("N/D") == "–"
    assert relatorios.moeda(None) == "–"
    assert relatorios.moeda(100.0) == "R$ 100,00"
    assert relatorios.moeda_fina("N/D") == "–"
    assert relatorios.moeda_fina(None) == "–"
    assert relatorios.moeda_fina(0.0466) == "R$ 0,0466"


def test_preco_por_conteudo_nao_numerico_nao_quebra():
    """Mesma raiz: preco_por_conteudo() faz valor/quantidade sem proteção,
    e é chamada para TODA linha de dados_precos (relatorios.py:1231),
    incondicional — não só quando a comparação "por conteúdo" está ligada."""
    assert relatorios.preco_por_conteudo("N/D", "PAPEL A4 SULFITE", "UN") is None
    assert relatorios.preco_por_conteudo(None, "PAPEL A4 SULFITE", "UN") is None
    r = relatorios.preco_por_conteudo(100.0, "PAPEL A4 SULFITE C/500 FL", "PCT")
    assert r is not None and r["valor"] == pytest.approx(0.2)


def test_resumo_estatistico_descarta_valor_nao_numerico():
    """4ª quina da mesma raiz — encontrada testando a correção do achado
    #2: sum()/variância em resumo_estatistico() quebravam com TEXT numa
    lista de valor_unitario_homologado (banco anterior à validação na
    ingestão do PNCP). A linha malformada é descartada, a estatística
    segue com o resto — mesmo critério de sync_ipca."""
    assert relatorios.resumo_estatistico(["N/D", None]) is None
    r = relatorios.resumo_estatistico([10.0, "N/D", 20.0, 30.0])
    assert r["n"] == 3
    assert r["media"] == 20.0
    assert r["minimo"] == 10.0 and r["maximo"] == 30.0


def test_precos_com_valor_corrompido_no_banco_nao_quebra_o_relatorio(
        db, tmp_path, selecionar_tudo):
    """render_precos com um banco anterior à validação na ingestão: uma
    linha de valor_unitario_homologado corrompida (TEXT) convivendo com
    linhas boas não pode derrubar o documento inteiro."""
    db.executemany(
        "INSERT INTO itens (id, contratacao_controle, ano, sequencial,"
        " numero_item, descricao, unidade, quantidade_homologada,"
        " valor_unitario_homologado, valor_total_homologado, fornecedor_ni,"
        " fornecedor_nome, data_resultado) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [("a", "A", 2026, 1, 1, "PAPEL A4 SULFITE", "RESMA", 10, 20.0, 200.0,
          "1", "FORN A", "2026-03-10"),
         ("b", "A", 2026, 1, 2, "PAPEL A4 SULFITE", "RESMA", 5, "N/D", None,
          "2", "FORN B", "2026-04-10")])
    db.commit()
    selecionar_tudo(db, "papel a4 sulfite")
    r = relatorios.gerar(db, "precos", {"termo": "papel a4 sulfite"}, "T",
                         "SP", tmp_path)
    html = Path(r["html"]).read_text(encoding="utf-8")
    assert "Pesquisa de Preços" in html
    assert "N/D" not in html


def test_competencia_do_ipca_com_marcacao_nao_vira_html(db):
    """`mes_por_extenso` validava só o mês; o ano voltava cru na prosa da
    correção monetária — "<payload>-06" virava "jun/<payload>"."""
    payload = "<script>alert(1)</script>"
    assert relatorios.mes_por_extenso(f"{payload}-06") is None
    # competência fora do formato some, em vez de virar texto
    assert relatorios.mes_por_extenso("2026-13") is None
    assert relatorios.mes_por_extenso("2026") is None
    assert relatorios.mes_por_extenso("2026-06") == "jun/2026"

    db.execute("INSERT INTO ipca (competencia, variacao) VALUES (?, 0.5)",
               (f"{payload}-06",))
    for i in range(6):
        db.execute(
            "INSERT INTO itens (id, contratacao_controle, ano, descricao,"
            " unidade, valor_unitario_homologado, quantidade_homologada,"
            " data_resultado, referencia)"
            " VALUES (?,'A',2026,'PAPEL A4 SULFITE','UN',?,10,"
            " '2026-01-01',0)", (f"I#{i}", 10.0 + i))
    db.commit()
    html = relatorios.render_precos(
        relatorios.dados_precos(db, "papel", corrigir_ipca=True), "T", "SP")
    assert payload not in html
    assert "<script>" not in html


def test_documento_de_precos_recusa_sair_sem_selecao(db, tmp_path):
    """Achado da auditoria de 2026-08-09 — o pior defeito que apareceu.

    Com a tela dizendo "Nenhum item selecionado ainda", gerar o documento
    produzia um relatório sobre a busca INTEIRA: mediana e máximo de uma
    série que o usuário nunca curou, incluindo preço de município de
    referência, e sem nenhum aviso no papel. Pesquisa de preços é peça de
    processo — número errado ali é o pior defeito possível.
    """
    for i, valor in enumerate((10.0, 12.0, 15.0, 400.0, 500.0, 600.0)):
        db.execute(
            "INSERT INTO itens (id, contratacao_controle, ano, descricao,"
            " unidade, valor_unitario_homologado, quantidade_homologada,"
            " data_resultado, referencia)"
            " VALUES (?,'A',2026,'PAPEL A4 SULFITE','UN',?,10,"
            " '2026-01-01',0)", (f"S#{i}", valor))
    db.commit()

    with pytest.raises(ValueError, match="selecione"):
        relatorios.gerar(db, "precos", {"termo": "papel"}, "T", "SP", tmp_path)

    # com seleção, sai — e sobre o que foi selecionado, não sobre tudo
    for i in range(3):
        db.execute("INSERT INTO precos_selecionados (termo, item_id,"
                   " criado_em) VALUES (?,?,'x')",
                   (relatorios.chave_termo("papel"), f"S#{i}"))
    db.commit()
    r = relatorios.gerar(db, "precos", {"termo": "papel"}, "T", "SP", tmp_path)
    html = Path(r["html"]).read_text(encoding="utf-8")
    assert "R$ 12,00" in html                 # mediana dos 3 selecionados
    assert "R$ 600,00" not in html            # o que ficou de fora, ficou

    # a chamada direta (teste, uso fora da tela) segue sem exigir seleção
    assert relatorios.dados_precos(db, "papel")["resumo"]["n"] == 3
