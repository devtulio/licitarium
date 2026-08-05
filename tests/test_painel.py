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


def test_medidor_de_limite_por_unidade(api):
    v = api.painel(ANO)["vigilancia"]
    saude = next(u for u in v["limites"] if u["unidade"] == "Saúde")
    assert saude["n"] == 2 and saude["total"] == pytest.approx(52000.0)
    # 52.000 sobre o limite do art. 75, II
    assert saude["pct"] == pytest.approx(52000 / v["limite_compras"] * 100)


def test_alertas_contam_o_que_exige_acao(api):
    a = api.painel(ANO)["alertas"]
    assert a["vencendo"] == 2                  # contrato em 20 dias e ata em 45
    assert a["paradas"] == 1                   # P2, publicada em janeiro
    # Saúde soma R$ 52.000 dos R$ 62.639,92 do art. 75, II — 83% do limite
    assert a["perto_do_limite"] == 1
    assert isinstance(a["propostas"], int)


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
