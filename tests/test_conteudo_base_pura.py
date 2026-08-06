"""Unidade de compra que já é a base não se divide de novo.

Achado no acervo real: a descrição do hortifruti traz o padrão comercial do
CEAGESP ("SACO COM 20 KG") junto da especificação, e a unidade licitada é KG.
O preço unitário já é por quilo — dividir por 20 fazia abóbora a R$ 5,45/kg
virar R$ 0,27/kg. Eram 1.245 itens, 16% de tudo que o extrator lia.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import relatorios

CEAGESP = ("ABÓBORA CABOTIÁ, LEGUME IN NATURA, 1ª QUALIDADE, FRESCO, ÍNTEGRO"
           " E FIRME. PADRÃO COMERCIAL DE REFERENCIA CEAGESP: SACO COM 20 KG."
           " UNIDADE LICITADA: QUILOGRAMA.")


@pytest.mark.parametrize("unidade,base", [
    ("KG", "kg"), ("kg", "kg"), (" QUILO ", "kg"), ("LITRO", "l"),
    ("L", "l"), ("M", "m"), ("METRO", "m"), ("UN", "un"), ("Unidade", "un"),
])
def test_unidade_base_pura_vale_um(unidade, base):
    assert relatorios.conteudo("PRODUTO QUALQUER", unidade) == (1.0, base)


def test_caixa_de_transporte_nao_divide_preco_por_quilo():
    assert relatorios.conteudo(CEAGESP, "KG") == (1.0, "kg")
    # o preço por quilo é o próprio preço unitário
    p = relatorios.preco_por_conteudo(5.45, CEAGESP, "KG")
    assert p["valor"] == pytest.approx(5.45) and p["base"] == "kg"


def test_a_descricao_ainda_vale_quando_a_unidade_nao_e_base():
    """Sem o campo unidade dizer a medida, a descrição segue mandando."""
    assert relatorios.conteudo("PAPEL A4 CAIXA C/5000 FLS", "CX") == (5000.0,
                                                                     "un")
    assert relatorios.conteudo("ACUCAR PACOTE COM 5 KG", "PACOTE") == (5.0,
                                                                      "kg")


def test_unidade_com_numero_continua_mandando_na_descricao():
    """'Embalagem 5,00 KG' é o conteúdo real; não vira 1 kg."""
    assert relatorios.conteudo("ARROZ", "Embalagem 5,00 KG") == (5.0, "kg")
    assert relatorios.conteudo("BISCOITO", "Pacote 400,00 G") == (0.4, "kg")


def test_granel_e_embalado_passam_a_se_comparar():
    """É o ganho: os dois viram R$/kg e entram na mesma série."""
    granel = relatorios.preco_por_conteudo(6.00, "FEIJÃO CARIOCA", "KG")
    pacote = relatorios.preco_por_conteudo(30.00, "FEIJÃO CARIOCA",
                                           "Embalagem 5,00 KG")
    assert granel["base"] == pacote["base"] == "kg"
    assert granel["valor"] == pytest.approx(pacote["valor"])
