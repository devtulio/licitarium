"""Testes do montador de minuta do PCA."""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import licitarium
import pca_builder


@pytest.fixture
def db():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(licitarium.SCHEMA)
    dados = [
        # (id, ano, descricao, unidade, qtd, unitario, data)
        ("a", 2024, "FILTRO DE AR DO MOTOR MODELO X", "UND", 100, 90.0, "2024-05-01"),
        ("b", 2025, "FILTRO DE AR DO MOTOR MODELO Y", "UND", 200, 100.0, "2025-05-01"),
        ("c", 2025, "FILTRO DE AR DO MOTOR MODELO Z", "UND", 100, 110.0, "2025-08-01"),
        ("d", 2025, "PAPEL SULFITE A4 BRANCO", "RESMA", 50, 20.0, "2025-03-01"),
        ("e", 2024, "PROPOSTA PARA TODOS OS ITENS", "UN", 1, 500000.0, "2024-01-01"),
    ]
    con.executemany(
        "INSERT INTO itens (id, contratacao_controle, ano, sequencial,"
        " numero_item, descricao, unidade, quantidade_homologada,"
        " valor_unitario_homologado, data_resultado, material_servico)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,'Material')",
        [(i, "C", ano, 1, n, desc, un, q, v, d)
         for n, (i, ano, desc, un, q, v, d) in enumerate(dados, 1)])
    con.commit()
    yield con
    con.close()


def test_chave_ignora_pontuacao_e_palavras_vazias():
    assert pca_builder.chave_agrupamento("Filtro de ar do motor, modelo X") \
        == "FILTRO AR MOTOR"
    assert pca_builder.chave_agrupamento("PAPEL SULFITE A4", 2) == "PAPEL SULFITE"
    assert pca_builder.chave_agrupamento("") == ""


def test_consolida_agrupando_e_descarta_lote(db):
    grupos = {g["chave"]: g for g in pca_builder.consolidar(db)}
    assert "FILTRO AR MOTOR" in grupos
    # o lote "proposta para todos os itens" não vira item de plano
    assert not any("TODOS" in k for k in grupos)
    filtro = grupos["FILTRO AR MOTOR"]
    assert filtro["itens"] == 3 and filtro["anos"] == [2024, 2025]
    # média dos anos: 2024=100, 2025=300 -> 200; +10% -> 220
    assert filtro["quantidade_base"] == 200.0
    assert filtro["quantidade"] == 220.0
    assert filtro["valor_unitario"] == 100.0        # mediana de 90/100/110


def test_bases_de_quantidade(db):
    def qtd(base):
        g = {x["chave"]: x for x in pca_builder.consolidar(db, base=base,
                                                           margem=0)}
        return g["FILTRO AR MOTOR"]["quantidade"]
    assert qtd("media") == 200.0
    assert qtd("ultimo") == 300.0      # 2025
    assert qtd("maior") == 300.0
    assert qtd("soma") == 400.0


def test_estatisticas_de_preco(db):
    def preco(est):
        g = {x["chave"]: x for x in pca_builder.consolidar(db, estatistica=est)}
        return g["FILTRO AR MOTOR"]["valor_unitario"]
    assert preco("mediana") == 100.0
    assert preco("media") == 100.0
    assert preco("menor") == 90.0
    assert preco("recente") == 110.0   # resultado de 2025-08


def test_margem_aplicada(db):
    g = {x["chave"]: x for x in pca_builder.consolidar(db, margem=25)}
    assert g["PAPEL SULFITE"[:0] or "PAPEL SULFITE A4"]["quantidade"] == 62.5


def test_filtro_por_anos(db):
    grupos = pca_builder.consolidar(db, anos=[2025])
    filtro = {g["chave"]: g for g in grupos}["FILTRO AR MOTOR"]
    assert filtro["anos"] == [2025] and filtro["quantidade_base"] == 300.0


def test_minuta_persiste_e_preserva_edicao(db):
    n = pca_builder.gerar_minuta(db, 2027, {"margem": 10})
    assert n >= 2
    itens = pca_builder.listar_minuta(db, 2027)
    alvo = next(i for i in itens if i["chave"] == "FILTRO AR MOTOR")
    # o gestor ajusta a quantidade e marca como editado
    db.execute("UPDATE pca_minuta_itens SET quantidade=999, editado=1"
               " WHERE id=?", (alvo["id"],))
    db.commit()
    # regerar não pode descartar o ajuste manual
    pca_builder.gerar_minuta(db, 2027, {"margem": 50})
    itens = pca_builder.listar_minuta(db, 2027)
    alvo = next(i for i in itens if i["chave"] == "FILTRO AR MOTOR")
    assert alvo["quantidade"] == 999 and alvo["editado"] == 1
    # os não editados seguem o parâmetro novo
    papel = next(i for i in itens if "PAPEL" in i["chave"])
    assert papel["quantidade"] == 75.0          # 50 * 1,5


def test_totais_ignora_excluidos(db):
    pca_builder.gerar_minuta(db, 2027, {})
    itens = pca_builder.listar_minuta(db, 2027)
    db.execute("UPDATE pca_minuta_itens SET incluir=0 WHERE id=?",
               (itens[0]["id"],))
    db.commit()
    t = pca_builder.totais(pca_builder.listar_minuta(db, 2027))
    assert t["excluidos"] == 1
    assert t["grupos"] == len(itens) - 1


def test_marca_unidade_divergente(db):
    db.execute("INSERT INTO itens (id, contratacao_controle, ano, sequencial,"
               " numero_item, descricao, unidade, quantidade_homologada,"
               " valor_unitario_homologado, data_resultado)"
               " VALUES ('f','C',2025,1,9,'FILTRO DE AR DO MOTOR W','CX',10,"
               "95.0,'2025-09-01')")
    db.commit()
    g = {x["chave"]: x for x in pca_builder.consolidar(db)}
    assert g["FILTRO AR MOTOR"]["unidades_divergentes"] is True
