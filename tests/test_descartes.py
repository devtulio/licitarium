"""Descarte de preço: registro da razão e presença no documento.

O art. 23 da Lei 14.133/2021 e a IN SEGES 65/2021 não admitem desprezar um
preço coletado sem dizer por quê. Antes da 1.7.0 o descarte vivia só na tela:
sumia ao trocar o termo e o relatório não mencionava que a série fora
filtrada — o documento saía dizendo menos do que o responsável havia feito.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import licitarium
import relatorios

ANO = 2026
ITENS = [("I1", "PAPEL SULFITE A4 75G", "RESMA", 24.90),
         ("I2", "PAPEL SULFITE A4 CAIXA 5000 FLS", "CX", 232.80),
         ("I3", "SUPORTE PARA PAPEL A4 EM ACRILICO", "UN", 89.00)]


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(licitarium, "DIR_DADOS", tmp_path)
    monkeypatch.setattr(licitarium, "ARQUIVO_DB", tmp_path / "t.db")
    db = licitarium.abrir_db()
    db.execute("INSERT INTO contratacoes (numero_controle, ano, sequencial,"
               " orgao_cnpj, objeto, data_publicacao)"
               " VALUES ('K',?,7,'111','x',?)", (ANO, f"{ANO}-01-01"))
    for i, (id_, desc, un, valor) in enumerate(ITENS, 1):
        db.execute(
            "INSERT INTO itens (id, contratacao_controle, ano, sequencial,"
            " numero_item, descricao, unidade, quantidade,"
            " quantidade_homologada, valor_unitario_homologado,"
            " fornecedor_ni, fornecedor_nome, raw)"
            " VALUES (?,'K',?,7,?,?,?,10,10,?,?,?,'{}')",
            (id_, ANO, i, desc, un, valor, f"ni{i}", f"FORNECEDOR {i}"))
    db.commit()
    db.close()
    return licitarium.Api()


def _db():
    return licitarium.abrir_db()


def test_descarte_sobrevive_a_troca_de_termo_e_ao_fechamento(api):
    api.descartar_preco("papel a4", "I3", "nao_comparavel")
    # outra pesquisa não vê o descarte desta
    assert api.descartes("caneta") == []
    # e a mesma pesquisa, escrita de outro jeito, vê
    guardados = api.descartes("  Papel   A4 ")
    assert [(d["item_id"], d["motivo"]) for d in guardados] \
        == [("I3", "nao_comparavel")]
    # a lista traz o que a tela precisa mostrar, não só o id
    assert guardados[0]["descricao"] == "SUPORTE PARA PAPEL A4 EM ACRILICO"
    assert guardados[0]["valor"] == 89.00


def test_razao_pode_vir_depois_do_descarte(api):
    api.descartar_preco("papel a4", "I3")
    assert api.descartes("papel a4")[0]["motivo"] is None

    api.descartar_preco("papel a4", "I3", "embalagem")
    d = api.descartes("papel a4")
    assert len(d) == 1 and d[0]["motivo"] == "embalagem"


def test_restaurar_devolve_um_item_ou_todos(api):
    for item in ("I2", "I3"):
        api.descartar_preco("papel a4", item, "nao_comparavel")

    api.restaurar_preco("papel a4", "I3")
    assert [d["item_id"] for d in api.descartes("papel a4")] == ["I2"]

    api.restaurar_preco("papel a4")
    assert api.descartes("papel a4") == []


def test_motivos_da_tela_sao_os_mesmos_do_documento(api):
    ids = [m["id"] for m in api.motivos_descarte()]
    assert ids == list(relatorios.MOTIVOS_DESCARTE)
    assert relatorios.rotulo_motivo("inexequivel") \
        == "Preço manifestamente inexequível"
    # texto livre chega ao documento como foi escrito
    assert relatorios.rotulo_motivo("comprado com desconto de campanha") \
        == "comprado com desconto de campanha"
    assert relatorios.rotulo_motivo(None) is None


def test_documento_tira_do_calculo_e_mostra_na_secao_propria(api, tmp_path):
    api.descartar_preco("papel a4", "I3", "nao_comparavel")
    db = _db()
    try:
        d = relatorios.dados_precos(db, "papel a4")
        assert [l["valor_unitario_homologado"] for l in d["linhas"]] \
            == [24.90, 232.80]
        assert d["resumo"]["n"] == 2
        assert [l["id"] for l in d["desconsiderados"]] == ["I3"]

        r = relatorios.gerar(db, "precos", {"termo": "papel a4"},
                             "Orindiúva", "SP", tmp_path / "rel")
        html = Path(r["html"]).read_text(encoding="utf-8")
    finally:
        db.close()
    principal, _, fora = html.partition("Itens desconsiderados nesta pesquisa")
    assert "89,00" not in principal          # não entra no cálculo
    assert "SUPORTE PARA PAPEL A4" in fora   # mas o documento diz que existiu
    assert "Item não comparável ao objeto pesquisado" in fora


def test_documento_acusa_o_que_ficou_sem_justificativa(api, tmp_path):
    api.descartar_preco("papel a4", "I3")          # sem razão
    api.descartar_preco("papel a4", "I2", "embalagem")
    db = _db()
    try:
        r = relatorios.gerar(db, "precos", {"termo": "papel a4"},
                             "Orindiúva", "SP", tmp_path / "rel")
        html = Path(r["html"]).read_text(encoding="utf-8")
    finally:
        db.close()
    assert "1 item está sem justificativa registrada" in html
    assert 'class="sem-motivo"' in html
    assert "registre a razão antes de juntar este" in html


def test_pesquisa_sem_descarte_nao_ganha_secao(api, tmp_path):
    db = _db()
    try:
        r = relatorios.gerar(db, "precos", {"termo": "papel a4"},
                             "Orindiúva", "SP", tmp_path / "rel")
        html = Path(r["html"]).read_text(encoding="utf-8")
    finally:
        db.close()
    assert "Itens desconsiderados" not in html


def test_termo_vazio_nao_grava_descarte(api):
    assert api.descartar_preco("", "I1", "embalagem") == {"ok": False}
    assert api.descartes("") == []
