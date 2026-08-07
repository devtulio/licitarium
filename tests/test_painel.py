"""Painel: os números das três vistas e o documento em A3.

O painel é a primeira tela do programa, e cada número dele vira decisão: se o
deságio, o funil ou o medidor de limite mentirem, mentem para quem assina.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import licitarium
import relatorios

ANO = 2026


def _db():
    return licitarium.abrir_db()


@pytest.fixture
def api(tmp_path, monkeypatch):
    """Dois exercícios, com dispensa, pregão, contrato e ata vencendo."""
    monkeypatch.setattr(licitarium, "DIR_DADOS", tmp_path)
    monkeypatch.setattr(licitarium, "ARQUIVO_DB", tmp_path / "t.db")
    db = licitarium.abrir_db()
    contratacoes = [
        # (id, ano, modalidade, unidade, estimado, homologado, publicação)
        ("D1", ANO, 8, "Saúde", 30000.0, 27000.0, f"{ANO}-02-10"),
        ("D2", ANO, 8, "Saúde", 25000.0, 25000.0, f"{ANO}-03-05"),
        ("P1", ANO, 6, "Educação", 400000.0, 320000.0, f"{ANO}-03-20"),
        # sem homologação e publicada há muito tempo: é pendência
        ("P2", ANO, 6, "Educação", 90000.0, None, f"{ANO}-01-05"),
        ("D3", ANO - 1, 8, "Saúde", 20000.0, 18000.0, f"{ANO - 1}-04-01"),
    ]
    for id_, ano, mod, uni, est, hom, pub in contratacoes:
        db.execute(
            "INSERT INTO contratacoes (numero_controle, ano, sequencial,"
            " orgao_cnpj, unidade, modalidade_id, modalidade_nome, objeto,"
            " valor_estimado, valor_homologado, data_publicacao, referencia,"
            " raw) VALUES (?,?,1,'111',?,?,?,'Objeto',?,?,?,0,'{}')",
            (id_, ano, uni, mod, "Dispensa" if mod == 8 else "Pregão",
             est, hom, pub))
    # item homologado: é o que faz a contratação contar como "com resultado"
    db.execute("INSERT INTO itens (id, contratacao_controle, ano, descricao,"
               " unidade, valor_unitario_homologado, raw)"
               " VALUES ('D1#1','D1',?, 'ITEM','UN',2700.0,'{}')", (ANO,))
    venc = (date.today() + timedelta(days=20)).isoformat()
    db.execute("INSERT INTO contratos (numero_controle, contratacao_controle,"
               " orgao_cnpj, fornecedor_ni, fornecedor_nome, objeto,"
               " valor_global, vigencia_inicio, vigencia_fim, data_publicacao,"
               " raw) VALUES ('K1','D1','111','9','FORNECEDOR UM LTDA','Obj',"
               " 27000.0,?,?,?, '{}')", (f"{ANO}-01-01", venc, f"{ANO}-02-15"))
    db.execute("INSERT INTO atas (numero_controle, contratacao_controle,"
               " orgao_cnpj, numero_ata, ano_ata, objeto, vigencia_inicio,"
               " vigencia_fim, raw) VALUES ('A1','P1','111','5',?, 'Obj',?,?,"
               " '{\"numeroAtaRegistroPreco\":\"5\",\"anoAta\":2026}')",
               (ANO, f"{ANO}-01-01",
                (date.today() + timedelta(days=45)).isoformat()))
    db.commit()
    db.close()
    return licitarium.Api()


# ── execução ────────────────────────────────────────────────────────────

def test_cards_e_serie_mensal(api):
    d = api.painel(ANO)
    c = d["execucao"]["cards"]
    assert c["n"] == 4                       # só o exercício pedido
    assert c["homologado"] == pytest.approx(372000.0)
    assert c["contratos_vigentes"] == 1 and c["atas_vigentes"] == 1
    meses = {m["mes"]: m for m in d["execucao"]["meses"]}
    assert len(d["execucao"]["meses"]) == 12          # o ano inteiro, com zeros
    assert meses[2]["valor"] == pytest.approx(27000.0)
    assert meses[3]["valor"] == pytest.approx(345000.0)
    assert meses[3]["estimado"] == pytest.approx(425000.0)
    assert meses[7]["valor"] == 0                     # mês sem contratação
    # o ano anterior vem junto: é contra ele que o hero compara
    assert d["execucao"]["homologado_anterior"] == pytest.approx(18000.0)


def test_modalidades_ordenadas_por_valor(api):
    d = api.painel(ANO)
    mods = d["execucao"]["modalidades"]
    assert mods[0]["modalidade_nome"] == "Pregão"
    assert mods[0]["n"] == 2


# ── análise ─────────────────────────────────────────────────────────────

def test_serie_acumulada_e_so_do_homologado(api):
    """Processo sem homologação não entra no acumulado de homologado.

    O resumo executivo usa COALESCE(homologado, estimado) para não zerar
    processo em andamento; no painel isso faria o gráfico mostrar como pago
    o que ainda é estimativa.
    """
    a = api.painel(ANO)["analise"]
    assert sorted(a["series"]) == [str(ANO - 2), str(ANO - 1), str(ANO)]
    atual = a["series"][str(ANO)]
    assert len(atual) == 12
    assert atual[1] == pytest.approx(27000.0)     # fev
    assert atual[2] == pytest.approx(372000.0)    # mar, acumulado
    assert atual[11] == pytest.approx(372000.0)   # acumulado não decresce
    # P2 tem R$ 90.000 estimados e nenhuma homologação: fica de fora
    assert atual[0] == 0
    assert a["series"][str(ANO - 2)][11] == 0     # exercício sem dados


def test_desagio_por_modalidade(api):
    a = api.painel(ANO)["analise"]
    pcts = {d["modalidade"]: d["pct"] for d in a["desagios"]}
    # pregão: 320.000 sobre 400.000 estimados = 20% de deságio
    assert pcts["Pregão"] == pytest.approx(20.0)
    # dispensas: 52.000 sobre 55.000 = 5,45%
    assert pcts["Dispensa"] == pytest.approx(5.4545, rel=1e-3)


def test_curva_de_concentracao_termina_em_cem(api):
    a = api.painel(ANO)["analise"]
    assert a["curva"][-1] == pytest.approx(100.0)
    assert a["fornecedores_total"] == 1


def test_calor_agrupa_a_cauda_em_outras(api):
    a = api.painel(ANO)["analise"]
    assert "Outras" in a["calor"]
    assert all(len(v) == 12 for v in a["calor"].values())
    assert a["calor"]["Dispensa"][1] == 1        # uma dispensa em fevereiro
    assert a["calor"]["Pregão"][2] == 1


# ── vigilância ──────────────────────────────────────────────────────────

def test_funil_do_edital_ao_contrato(api):
    f = api.painel(ANO)["vigilancia"]["funil"]
    assert f["publicadas"] == 4
    assert f["com_resultado"] == 1     # só D1 tem item homologado
    assert f["com_contrato"] == 1
    assert f["vigentes"] == 1


def test_medidor_de_limite_agrupa_por_objeto(api):
    """Por unidade o medidor não separava nada.

    O campo `unidade` do PNCP traz o nome do órgão: no acervo do piloto, as
    16 dispensas caíam todas em "MUNICIPIO DE ORINDIUVA" e o termômetro
    virava uma linha só. O art. 75 fala em objeto de mesma natureza, que é
    também o agrupamento útil.
    """
    db = _db()
    try:
        db.execute("UPDATE contratacoes SET objeto='AQUISIÇÃO DE PAPEL A4'"
                   " WHERE numero_controle='D1'")
        db.execute("UPDATE contratacoes SET objeto='AQUISICAO DE PAPEL A4"
                   " SULFITE' WHERE numero_controle='D2'")
        # mesma unidade administrativa, objeto diferente
        db.execute("INSERT INTO contratacoes (numero_controle, ano, sequencial,"
                   " orgao_cnpj, unidade, modalidade_id, modalidade_nome,"
                   " objeto, valor_estimado, valor_homologado, data_publicacao,"
                   " referencia, raw) VALUES ('D9',?,9,'111','Saúde',8,"
                   " 'Dispensa','CONTRATAÇÃO DE MANUTENÇÃO PREDIAL',9000,9000,"
                   " ?,0,'{}')", (ANO, f"{ANO}-05-05"))
        db.commit()
    finally:
        db.close()

    v = api.painel(ANO)["vigilancia"]
    limites = {o["objeto"]: o for o in v["limites"]}
    # os dois papéis caem na mesma chave; a manutenção fica separada
    papel = limites["PAPEL A4"]
    assert papel["n"] == 2 and papel["total"] == pytest.approx(52000.0)
    assert papel["pct"] == pytest.approx(52000 / v["limite_compras"] * 100)
    assert limites["MANUTENÇÃO PREDIAL"]["n"] == 1


def test_alertas_contam_o_que_exige_acao(api):
    a = api.painel(ANO)["alertas"]
    # contrato e ata não somam mais num alerta só: cada um vai a uma tela
    assert a["vencendo_contratos"] == 1        # K1, em 20 dias
    assert a["vencendo_atas"] == 1             # A1, em 45 dias
    assert a["paradas"] == 1                   # P2, publicada em janeiro
    # o objeto das duas dispensas soma R$ 52.000 dos R$ 62.639,92 do
    # art. 75, II — 83% do limite, sem estourar
    assert a["perto_do_limite"] == 1 and a["acima_do_limite"] == 0
    assert isinstance(a["propostas"], int)


def test_alerta_distingue_perto_de_acima_do_limite(api):
    db = _db()
    try:
        db.execute("UPDATE contratacoes SET valor_homologado=90000"
                   " WHERE numero_controle='D1'")
        db.commit()
    finally:
        db.close()
    a = api.painel(ANO)["alertas"]
    assert a["acima_do_limite"] == 1


# ── o clique no alerta tem de filtrar a lista, não só levar até ela ────────
# Esta seção fecha o círculo: cada alerta carrega junto os dados que o
# clique precisa para filtrar a lista exatamente pelo que ele contou —
# nunca "a modalidade inteira" nem "nada".

def test_alerta_de_limite_expoe_os_objetos_que_contou(api):
    """O clique filtra por estes objetos, não por toda dispensa do ano.

    D1 e D2 nascem com objeto genérico ("Objeto") no fixture — a chave
    agrupada é "OBJETO"; o teste seguinte usa objetos de verdade.
    """
    a = api.painel(ANO)["alertas"]
    assert a["objetos_perto_do_limite"] == ["OBJETO"]


def test_clique_no_alerta_de_limite_traz_so_esses_objetos(api):
    """De ponta a ponta: o que o alerta contou é o que a lista mostra.

    D1 e D2 (papel A4) somam 83% do limite e disparam o alerta; D3 é
    dispensa do exercício anterior e P1/P2 não são dispensa — nenhum dos
    três pode aparecer na lista filtrada.
    """
    db = _db()
    try:
        db.execute("UPDATE contratacoes SET objeto='AQUISIÇÃO DE PAPEL A4'"
                   " WHERE numero_controle='D1'")
        db.execute("UPDATE contratacoes SET objeto='AQUISICAO DE PAPEL A4"
                   " SULFITE' WHERE numero_controle='D2'")
        db.execute("UPDATE contratacoes SET objeto='CONTRATAÇÃO DE"
                   " MANUTENÇÃO PREDIAL' WHERE numero_controle='D3'")
        db.commit()
    finally:
        db.close()

    objetos = api.painel(ANO)["alertas"]["objetos_perto_do_limite"]
    r = api.listar("contratacoes", {"objetos": objetos})
    assert {i["numero_controle"] for i in r["itens"]} == {"D1", "D2"}
    assert r["total"] == 2


def test_lista_sem_objetos_no_filtro_nao_aplica_nada(api):
    """Filtro vazio ou ausente não pode virar `IN ()`, que zeraria a lista."""
    r = api.listar("contratacoes", {"objetos": []})
    assert r["total"] > 0
    r2 = api.listar("contratacoes", {})
    assert r2["total"] == r["total"]


def test_clique_no_alerta_de_parada_traz_so_o_processo_parado(api):
    """P2: publicada em janeiro, sem homologação — é a única pendência.

    Mesmo critério do alerta (relatorios.dados_painel): mais de 90 dias
    desde a publicação e nenhum valor homologado ainda.
    """
    a = api.painel(ANO)["alertas"]
    assert a["paradas"] == 1

    r = api.listar("contratacoes", {"parada": True})
    assert r["total"] == 1 and r["itens"][0]["numero_controle"] == "P2"


def test_parada_nao_reaparece_apos_homologar(api):
    db = _db()
    try:
        db.execute("UPDATE contratacoes SET valor_homologado=90000"
                   " WHERE numero_controle='P2'")
        db.commit()
    finally:
        db.close()
    r = licitarium.Api().listar("contratacoes", {"parada": True})
    assert r["total"] == 0


def test_clique_no_alerta_de_vencimento_nao_traz_o_vigente_distante(api):
    """"Vigentes" (sem teto) não é "vence em 60 dias" (janela fechada).

    K1 vence em 20 dias — entra nos dois filtros. Um contrato vigente com
    vigência a 200 dias só pode aparecer em "vigentes"; em "vencendo" ele
    infla a lista sem ter nada a ver com o alerta que o usuário clicou —
    foi assim que "25 vencem em 60 dias" virava lista de 50.
    """
    db = _db()
    try:
        venc_longe = (date.today() + timedelta(days=200)).isoformat()
        db.execute("INSERT INTO contratos (numero_controle,"
                   " contratacao_controle, orgao_cnpj, fornecedor_ni,"
                   " fornecedor_nome, objeto, valor_global, vigencia_inicio,"
                   " vigencia_fim, data_publicacao, raw) VALUES ('K2','D1',"
                   " '111','9','FORNECEDOR UM LTDA','Obj',10000.0,"
                   f" '{ANO}-01-01', ?, '{ANO}-02-15', '{{}}')", (venc_longe,))
        db.commit()
    finally:
        db.close()

    todos_vigentes = licitarium.Api().listar("contratos", {"vigentes": True})
    assert todos_vigentes["total"] == 2                # K1 e K2

    so_vencendo = licitarium.Api().listar("contratos", {"vencendo": True})
    assert so_vencendo["total"] == 1
    assert so_vencendo["itens"][0]["numero_controle"] == "K1"


def test_vencendo_tambem_vale_para_atas(api):
    db = _db()
    try:
        # A1 (fixture base) vence em 45 dias; esta vence em 200 — só a
        # primeira pode sobrar se o filtro estiver aplicado de verdade
        db.execute("INSERT INTO atas (numero_controle, contratacao_controle,"
                   " orgao_cnpj, numero_ata, ano_ata, objeto, vigencia_inicio,"
                   " vigencia_fim, raw) VALUES ('A2','P1','111','6',?,'Obj',"
                   f" '{ANO}-01-01', ?,"
                   " '{\"numeroAtaRegistroPreco\":\"6\",\"anoAta\":2026}')",
                   (ANO, (date.today() + timedelta(days=200)).isoformat()))
        db.commit()
    finally:
        db.close()

    r = licitarium.Api().listar("atas", {"vencendo": True})
    assert r["total"] == 1 and r["itens"][0]["numero_controle"] == "A1"


def test_kpi_do_topo_tambem_separa_contrato_de_ata(tmp_path, monkeypatch):
    """Mesma métrica, call site irmão de dados_painel (Api._kpis).

    O chip do topo das listas usa uma consulta separada da do Painel — os
    dois calculam a mesma coisa, então os dois tinham o bug de somar
    contrato com ata, e os dois precisam da mesma correção.
    """
    monkeypatch.setattr(licitarium, "DIR_DADOS", tmp_path)
    monkeypatch.setattr(licitarium, "ARQUIVO_DB", tmp_path / "k.db")
    db = licitarium.abrir_db()
    db.execute("INSERT INTO contratacoes (numero_controle, ano, objeto)"
               " VALUES ('K',2026,'x')")
    venc = (date.today() + timedelta(days=10)).isoformat()
    db.execute("INSERT INTO contratos (numero_controle, contratacao_controle,"
               " orgao_cnpj, vigencia_fim, raw) VALUES ('C1','K','111',?,"
               " '{}')", (venc,))
    db.execute("INSERT INTO atas (numero_controle, contratacao_controle,"
               " orgao_cnpj, numero_ata, ano_ata, vigencia_fim, raw)"
               " VALUES ('A1','K','111','1',2026,?,'{}')", (venc,))
    db.execute("INSERT INTO atas (numero_controle, contratacao_controle,"
               " orgao_cnpj, numero_ata, ano_ata, vigencia_fim, raw)"
               " VALUES ('A2','K','111','2',2026,?,'{}')", (venc,))
    db.commit()
    db.close()

    k = licitarium.Api()._kpis(licitarium.abrir_db())
    assert k["vencendo_60_contratos"] == 1
    assert k["vencendo_60_atas"] == 2


def test_comparacao_com_o_ano_anterior_usa_o_mesmo_periodo(api):
    """Comparar oito meses com doze é aritmética do calendário.

    O acervo tem uma contratação de abril do exercício anterior. Pedindo o
    exercício corrente, ela só entra na comparação se já tiver passado a
    data de hoje — do contrário o painel diria "caiu" só porque o ano ainda
    não terminou.
    """
    hoje = date.today()
    d = api.painel(hoje.year)
    assert d["comparacao_parcial"] is True

    # exercício fechado compara ano inteiro com ano inteiro
    assert api.painel(ANO - 1)["comparacao_parcial"] is (ANO - 1 == hoje.year)


def test_funil_conta_o_mesmo_conjunto_nas_quatro_etapas(api):
    """A última etapa não pode ser maior que a primeira.

    "Vigentes hoje" contava contratos de qualquer exercício: no acervo real
    isso dava 50 vigentes para 34 publicadas, e o funil alargava no fim.
    """
    db = _db()
    try:
        # contrato vigente de um exercício anterior: não é deste funil
        db.execute("INSERT INTO contratos (numero_controle,"
                   " contratacao_controle, orgao_cnpj, fornecedor_ni,"
                   " fornecedor_nome, objeto, valor_global, vigencia_inicio,"
                   " vigencia_fim, data_publicacao, raw)"
                   " VALUES ('K9','D3','111','9','OUTRO','Obj',1000,?,?,?,'{}')",
                   (f"{ANO - 1}-01-01",
                    (date.today() + timedelta(days=300)).isoformat(),
                    f"{ANO - 1}-02-01"))
        db.commit()
    finally:
        db.close()

    f = api.painel(ANO)["vigilancia"]["funil"]
    assert f["vigentes"] == 1                       # só o contrato de D1
    assert f["publicadas"] >= f["com_resultado"] >= f["vigentes"]


def test_ano_ausente_usa_o_mais_recente_do_acervo(api):
    assert api.painel()["ano"] == ANO


# ── o painel impresso ───────────────────────────────────────────────────

def test_documento_sai_em_a3_paisagem(tmp_path, monkeypatch):
    monkeypatch.setattr(licitarium, "DIR_DADOS", tmp_path)
    monkeypatch.setattr(licitarium, "ARQUIVO_DB", tmp_path / "t.db")
    licitarium.abrir_db().close()
    monkeypatch.setattr(licitarium.webbrowser, "open", lambda *a, **k: None)

    r = licitarium.Api().imprimir_painel(
        [["execucao", "<div class='card'>gráfico</div>"],
         ["analise", "<svg><rect/></svg>"]], ANO)
    assert r["ok"]
    html = Path(r["arquivo"]).read_text(encoding="utf-8")
    assert "size: A3 landscape" in html
    # o navegador "economiza tinta" por padrão e devolveria barras cinzentas
    assert "print-color-adjust: exact" in html
    assert "Execução do exercício" in html and "Análise comparativa" in html
    assert "<svg><rect/></svg>" in html          # o SVG da tela vai inteiro
    assert "break-after:page" in html            # uma vista por página


def test_impressao_ignora_vista_vazia(tmp_path, monkeypatch):
    monkeypatch.setattr(licitarium, "DIR_DADOS", tmp_path)
    monkeypatch.setattr(licitarium, "ARQUIVO_DB", tmp_path / "t.db")
    licitarium.abrir_db().close()
    monkeypatch.setattr(licitarium.webbrowser, "open", lambda *a, **k: None)

    r = licitarium.Api().imprimir_painel([["execucao", "<b>x</b>"],
                                          ["analise", ""]], ANO)
    html = Path(r["arquivo"]).read_text(encoding="utf-8")
    assert "Análise comparativa" not in html


def test_filtro_de_orgao_nao_quebra_o_painel(api):
    """`contratacoes` e `itens` têm as duas uma coluna orgao_cnpj.

    Sem prefixo na consulta com JOIN, o SQLite recusa tudo com "ambiguous
    column name" — e o painel não abre para quem filtra por órgão.
    """
    d = api.painel(ANO, "111")
    assert d["vigilancia"]["funil"]["publicadas"] == 4
    assert d["execucao"]["cards"]["n"] == 4

    # órgão sem nada no acervo devolve painel vazio, não exceção
    vazio = api.painel(ANO, "000")
    assert vazio["execucao"]["cards"]["n"] == 0
    assert vazio["vigilancia"]["funil"]["publicadas"] == 0
