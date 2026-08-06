"""Quem declara conteúdo escolhe a unidade-base; quem só é avulso, não.

Medido no acervo real: com o voto implícito valendo, "leite" era comparado
por unidade (140 itens vendidos a unidade, cada um valendo 1) e deixava de
fora 89 itens em litro e 101 em quilo — exatamente os que a comparação
existe para pôr lado a lado. Em "café" saíam 100 itens em quilo.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import licitarium
import relatorios

# (id, descrição, unidade, valor) — leite como aparece no acervo: caixinha
# avulsa, fardo declarado e leite em pó por quilo
LEITE = [
    ("L1", "LEITE UHT INTEGRAL", "UN", 4.50),
    ("L2", "LEITE UHT INTEGRAL", "UN", 4.80),
    ("L3", "LEITE UHT INTEGRAL", "UN", 5.10),
    ("L4", "LEITE UHT INTEGRAL", "Fardo 12,00 L", 54.00),
    ("L5", "LEITE EM PO INSTANTANEO", "Embalagem 0,80 KG", 28.00),
]


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(licitarium, "DIR_DADOS", tmp_path)
    monkeypatch.setattr(licitarium, "ARQUIVO_DB", tmp_path / "t.db")
    db = licitarium.abrir_db()
    db.execute("INSERT INTO contratacoes (numero_controle, ano, objeto)"
               " VALUES ('K',2026,'x')")
    for id_, desc, un, valor in LEITE:
        db.execute(
            "INSERT INTO itens (id, contratacao_controle, ano, descricao,"
            " unidade, quantidade_homologada, valor_unitario_homologado,"
            " fornecedor_ni, raw) VALUES (?,'K',2026,?,?,10,?,?,'{}')",
            (id_, desc, un, valor, id_))
    db.commit()
    db.close()
    return licitarium.Api()


def test_voto_implicito_nao_escolhe_a_base():
    """Três avulsos não derrubam um litro declarado."""
    bases = [("un", True), ("un", True), ("un", True), ("l", False)]
    assert relatorios.escolher_base(bases) == "l"


def test_sem_ninguem_declarando_o_implicito_vale():
    """Pesquisa só de item avulso: comparar por unidade é o certo."""
    assert relatorios.escolher_base([("un", True), ("un", True)]) == "un"


def test_entre_declarados_ganha_o_mais_frequente():
    bases = [("kg", False), ("kg", False), ("l", False), ("un", True)]
    assert relatorios.escolher_base(bases) == "kg"


def test_sem_base_nenhuma():
    assert relatorios.escolher_base([]) is None


@pytest.mark.parametrize("unidade, implicita", [
    ("KG", True), ("UN", True), ("Unidade", True), ("L", True),
    ("Embalagem 1,00 KG", False), ("Fardo 12,00 UN", False),
    ("CX", False), ("PCT", False),
])
def test_o_que_conta_como_voto_implicito(unidade, implicita):
    assert relatorios.base_implicita(unidade) is implicita


def test_leite_avulso_nao_expulsa_o_leite_em_litro(api):
    """O caso real, ponta a ponta pela ponte da tela."""
    s = api.estatisticas_preco("leite", por_conteudo=True)
    assert s["base"] == "l" and s["rotulo_base"] == "litro"
    # o fardo de 12 L entra; os avulsos e o leite em pó ficam de fora e são
    # contados — o usuário precisa saber quantos
    assert s["n"] == 1 and s["sem_conversao"] == 4
    assert s["minimo"] == pytest.approx(4.50)


def test_o_relatorio_escolhe_a_mesma_base_que_a_tela(api):
    db = licitarium.abrir_db()
    try:
        d = relatorios.dados_precos(db, "leite", por_conteudo=True)
    finally:
        db.close()
    assert d["resumo"]["base"] == "l"
