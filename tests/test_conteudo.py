"""Preço por conteúdo: leitura da embalagem e comparação em unidade-base.

Preço de embalagem não se compara. No acervo do piloto, a caixa de papel A4
com 5.000 folhas sai a R$ 0,047 por folha e o pacote com 100 folhas, a
R$ 0,389 — oito vezes mais caro, e os dois entravam na mesma mediana.

O risco do outro lado é o falso positivo: em "SERINGA 10ML" o volume é a
capacidade da seringa, não o que se comprou, e comparar seringas por R$/litro
não quer dizer nada. Metade destes testes existe para o extrator continuar
recusando o que não deve converter.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import licitarium
import relatorios

ANO = 2026
# (id, descrição, unidade, valor unitário)
ITENS = [
    ("C1", "PAPEL SULFITE A4 C/5000 FLS", "Caixa", 232.80),
    ("C2", "PAPEL SULFITE A4 SERRILHADO", "PACOTE COM 100 FOLHAS", 38.90),
    ("C3", "PAPEL SULFITE A4 75G/M2 BRANCO 210MM X 297MM", "CX", 219.90),
    ("C4", "PAPEL SULFITE A4 PREMIUM", "Embalagem 2,50 KG", 60.00),
]


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(licitarium, "DIR_DADOS", tmp_path)
    monkeypatch.setattr(licitarium, "ARQUIVO_DB", tmp_path / "t.db")
    db = licitarium.abrir_db()
    db.execute("INSERT INTO contratacoes (numero_controle, ano, sequencial,"
               " orgao_cnpj, objeto, data_publicacao)"
               " VALUES ('K',?,3,'111','x',?)", (ANO, f"{ANO}-01-01"))
    for i, (id_, desc, un, valor) in enumerate(ITENS, 1):
        db.execute(
            "INSERT INTO itens (id, contratacao_controle, ano, sequencial,"
            " numero_item, descricao, unidade, quantidade,"
            " quantidade_homologada, valor_unitario_homologado,"
            " fornecedor_ni, raw)"
            " VALUES (?,'K',?,3,?,?,?,10,10,?,?,'{}')",
            (id_, ANO, i, desc, un, valor, f"ni{i}"))
    db.commit()
    db.close()
    return licitarium.Api()


# ── leitura da embalagem ────────────────────────────────────────────────

@pytest.mark.parametrize("descricao, unidade, esperado", [
    # contagem
    ("PAPEL SULFITE A4 C/5000 FLS", "Caixa", (5000.0, "un")),
    ("PAPEL SERRILHADO", "PACOTE COM 100 FOLHAS", (100.0, "un")),
    ("LUVA DE PROCEDIMENTO CAIXA COM 100 UNIDADES", "CX", (100.0, "un")),
    ("AGUA MINERAL", "Fardo 12,00 UN", (12.0, "un")),
    # massa e volume, convertidos para quilo e litro
    ("AÇÚCAR REFINADO", "Embalagem 1,00 KG", (1.0, "kg")),
    ("CAFÉ TORRADO E MOÍDO", "Pacote 400,00 G", (0.4, "kg")),
    ("ÁLCOOL 70", "Frasco 10,00 ML", (0.01, "l")),
    ("CLORO LÍQUIDO", "Galão 5,00 L", (5.0, "l")),
    # milhar com ponto: 1.000 folhas é mil, não uma
    ("BOBINA TÉRMICA C/1.000 FOLHAS", "RL", (1000.0, "un")),
])
def test_le_o_conteudo_declarado(descricao, unidade, esperado):
    lido = relatorios.conteudo(descricao, unidade)
    assert lido is not None, "deveria ter lido o conteúdo"
    assert lido[0] == pytest.approx(esperado[0]) and lido[1] == esperado[1]


@pytest.mark.parametrize("descricao, unidade", [
    # gramatura não é peso do que se comprou
    ("PAPEL SULFITE A4 75G/M2 BRANCO", "CX"),
    ("PAPEL SULFITE 90 G/M² BRANCO", "RESMA"),
    # dimensão não é conteúdo
    ("PAPEL A4 210MM X 297MM", "CX"),
    ("LONA PLASTICA 4M X 100M", "UN"),
    # capacidade do artefato: a seringa não é vendida a granel
    ("SERINGA 10ML DESCARTAVEL", "UN"),
    ("BALDE PLASTICO 20 LITROS", "UN"),
    # medida solta na descrição, sem dizer que é embalagem
    ("FIO DE NYLON ROLO 50M", "ROLO"),
    ("PNEU 175/70 R13", "UN"),
    # nada numérico
    ("CADEIRA DE RODAS REFORÇADA DOBRÁVEL", "UN"),
    ("SERVIÇO DE MANUTENÇÃO PREDIAL", "Serviço"),
    (None, None),
])
def test_recusa_o_que_nao_e_conteudo(descricao, unidade):
    assert relatorios.conteudo(descricao, unidade) is None


def test_preco_por_conteudo_desfaz_a_distorcao_da_embalagem():
    caixa = relatorios.preco_por_conteudo(232.80, "PAPEL A4 C/5000 FLS", "CX")
    pacote = relatorios.preco_por_conteudo(38.90, "PAPEL A4",
                                           "PACOTE COM 100 FOLHAS")
    assert caixa["valor"] == pytest.approx(0.046560)
    assert pacote["valor"] == pytest.approx(0.389)
    # o pacote parecia seis vezes mais barato e é oito vezes mais caro
    assert pacote["valor"] / caixa["valor"] == pytest.approx(8.355, rel=1e-3)
    assert caixa["rotulo"] == "unidade" and caixa["base"] == "un"


def test_sem_valor_nao_ha_o_que_normalizar():
    assert relatorios.preco_por_conteudo(None, "PAPEL A4 C/5000 FLS", "CX") \
        is None


# ── a comparação na tela ────────────────────────────────────────────────

def test_resumo_por_conteudo_usa_a_base_predominante(api):
    s = api.estatisticas_preco("papel a4", por_conteudo=True)
    # dois itens em folhas, um em quilo, um sem conteúdo legível
    assert s["por_conteudo"] and s["base"] == "un"
    assert s["rotulo_base"] == "unidade"
    assert s["n"] == 2 and s["sem_conversao"] == 2
    assert s["minimo"] == pytest.approx(0.046560)
    assert s["maximo"] == pytest.approx(0.389)


def test_resumo_normal_continua_sobre_o_preco_pago(api):
    s = api.estatisticas_preco("papel a4")
    assert not s.get("por_conteudo")
    assert s["n"] == 4 and s["maximo"] == 232.80


def test_pesquisa_sem_conteudo_legivel_avisa_em_vez_de_mentir(tmp_path,
                                                             monkeypatch):
    monkeypatch.setattr(licitarium, "DIR_DADOS", tmp_path)
    monkeypatch.setattr(licitarium, "ARQUIVO_DB", tmp_path / "v.db")
    db = licitarium.abrir_db()
    db.execute("INSERT INTO contratacoes (numero_controle, ano, objeto)"
               " VALUES ('K',2026,'x')")
    db.execute("INSERT INTO itens (id, contratacao_controle, descricao,"
               " unidade, valor_unitario_homologado)"
               " VALUES ('U1','K','CADEIRA DE RODAS DOBRAVEL','UN',635000.0)")
    db.commit()
    db.close()

    s = licitarium.Api().estatisticas_preco("cadeira", por_conteudo=True)
    assert s["n"] == 0 and s["sem_conversao"] == 1


def test_lista_traz_o_valor_por_conteudo_de_cada_item(api):
    itens = {i["id"]: i for i in api.listar("itens", {})["itens"]}
    assert itens["C1"]["por_conteudo"]["valor"] == pytest.approx(0.046560)
    assert itens["C4"]["por_conteudo"]["rotulo"] == "quilo"
    assert itens["C3"]["por_conteudo"] is None   # só gramatura e dimensão


# ── e no documento ──────────────────────────────────────────────────────

def test_documento_por_conteudo_declara_a_base_e_quem_ficou_de_fora(
        api, tmp_path):
    db = licitarium.abrir_db()
    try:
        r = relatorios.gerar(db, "precos",
                             {"termo": "papel a4", "por_conteudo": True},
                             "Orindiúva", "SP", tmp_path / "rel")
        html = Path(r["html"]).read_text(encoding="utf-8")
    finally:
        db.close()
    assert "Comparação por conteúdo" in html
    assert "por unidade" in html            # rótulo dos cards
    assert "R$ 0,0466" in html              # preço da folha, com casas
    assert "não entrou nesta comparação" in html


def test_documento_normal_nao_ganha_coluna_nem_aviso(api, tmp_path):
    db = licitarium.abrir_db()
    try:
        r = relatorios.gerar(db, "precos", {"termo": "papel a4"},
                             "Orindiúva", "SP", tmp_path / "rel")
        html = Path(r["html"]).read_text(encoding="utf-8")
    finally:
        db.close()
    assert "Comparação por conteúdo" not in html
    assert "R$ 232,80" in html
