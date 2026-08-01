"""Blindagem do município de referência.

Município de referência alimenta **apenas o banco de preços**. Se um registro
dele vazar para a aba Contratações, para os KPIs, para o PCA ou — pior — para
um relatório entregue ao Tribunal de Contas, o documento sai errado.

Estes testes existem para que esse vazamento quebre o build, e não a
credibilidade de um processo. Ver design/BRIEFING-precos-referencia.md.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import licitarium
import pca_builder
import relatorios

ANO = 2026


@pytest.fixture
def api(tmp_path, monkeypatch):
    """Acervo com um processo do município e um de referência, lado a lado."""
    monkeypatch.setattr(licitarium, "DIR_DADOS", tmp_path)
    monkeypatch.setattr(licitarium, "ARQUIVO_DB", tmp_path / "t.db")
    db = licitarium.abrir_db()
    for controle, ref, valor in (("MEU-1", 0, 1000.0), ("REF-1", 1, 9999.0)):
        db.execute(
            "INSERT INTO contratacoes (numero_controle, ano, sequencial,"
            " orgao_cnpj, modalidade_id, modalidade_nome, situacao, objeto,"
            " valor_estimado, valor_homologado, data_publicacao,"
            " data_encerramento_proposta, referencia, raw)"
            " VALUES (?,?,1,'111',8,?,?,?,?,?,?,"
            " datetime('now','+10 day'),?,'{}')",
            (controle, ANO, f"Dispensa {controle}", f"Situacao {controle}",
             f"Objeto {controle}", valor, valor, f"{ANO}-02-01", ref))
        db.execute(
            "INSERT INTO itens (id, contratacao_controle, ano, sequencial,"
            " numero_item, descricao, unidade, quantidade,"
            " quantidade_homologada, valor_unitario_homologado,"
            " fornecedor_ni, data_resultado, referencia, raw)"
            " VALUES (?,?,?,1,1,'PAPEL SULFITE A4','RESMA',10,10,?,?,?,?,'{}')",
            (f"{controle}#1", controle, ANO, valor, f"ni{ref}",
             f"{ANO}-02-10", ref))
    db.commit()
    db.close()
    return licitarium.Api()


def _db():
    return licitarium.abrir_db()


# ── o que NÃO pode enxergar a referência ────────────────────────────────

def test_kpis_contam_so_o_municipio(api):
    k = api.get_estado()["kpis"]
    assert k["contratacoes"] == 1
    assert k["homologado_ano"] == 1000.0       # 9999 é de fora
    assert k["propostas_abertas"] == 1


def test_aba_contratacoes_nao_lista_referencia(api):
    r = api.listar("contratacoes", {})
    assert r["total"] == 1
    assert [i["numero_controle"] for i in r["itens"]] == ["MEU-1"]


def test_filtros_do_acervo_nao_oferecem_opcao_de_fora(api):
    f = api.filtros_disponiveis()
    assert all("REF-1" not in s for s in f["situacoes"])
    assert any("MEU-1" in s for s in f["situacoes"])


def test_relatorios_oficiais_nao_trazem_referencia(api):
    db = _db()
    try:
        d = relatorios.dados_contratacoes(db, ano=ANO)
        assert d["totais"]["n"] == 1
        assert d["totais"]["homologado"] == 1000.0

        e = relatorios.dados_executivo(db, ANO)
        assert sum(m["n"] for m in e["modalidades"]) == 1
        assert all("REF-1" not in (m["modalidade_nome"] or "")
                   for m in e["modalidades"])

        fr = relatorios.dados_fracionamento(db, ANO)
        assert sum(u["total"] for u in fr["unidades"]) == 1000.0
    finally:
        db.close()


def test_relatorio_gerado_nao_menciona_a_referencia(api, tmp_path):
    """A prova final: o HTML entregue ao TCE não pode citar processo alheio."""
    db = _db()
    try:
        for tipo in ("contratacoes", "executivo"):
            r = relatorios.gerar(db, tipo, {"ano": ANO}, "Orindiúva", "SP",
                                 tmp_path / "rel")
            html = Path(r["html"]).read_text(encoding="utf-8")
            assert "MEU-1" in html or "Objeto MEU-1" in html
            assert "REF-1" not in html, tipo
    finally:
        db.close()


def test_pca_projeta_so_as_compras_do_proprio_orgao(api):
    db = _db()
    try:
        grupos = pca_builder.consolidar(db)
        # um único grupo (mesma descrição), alimentado só pelo item de casa
        assert len(grupos) == 1
        g = grupos[0]
        # 10 unidades + a margem padrão de 10%; se somasse o item de fora
        # seriam 20 unidades e o preço unitário mudaria
        assert g["quantidade"] == 11.0
        assert g["valor_unitario"] == 1000.0
    finally:
        db.close()


# ── o que PRECISA enxergar a referência ─────────────────────────────────

def test_banco_de_precos_soma_os_dois(api):
    """O ponto do recurso: mais preços para a pesquisa do art. 23."""
    s = api.estatisticas_preco("papel sulfite")
    assert s["n"] == 2
    assert s["minimo"] == 1000.0 and s["maximo"] == 9999.0
    assert s["fornecedores"] == 2
    assert api.listar("itens", {"so_homologados": True})["total"] == 2


def test_relatorio_de_precos_usa_os_dois(api):
    db = _db()
    try:
        d = relatorios.dados_precos(db, "papel sulfite")
        assert len(d["linhas"]) == 2
    finally:
        db.close()


def test_banco_antigo_ganha_a_coluna_como_municipio_proprio(api):
    """Migração: acervo já baixado é todo do município do usuário."""
    db = _db()
    try:
        db.execute("ALTER TABLE contratacoes DROP COLUMN referencia")
        db.execute("INSERT INTO contratacoes (numero_controle, ano, raw)"
                   " VALUES ('ANTIGO', ?, '{}')", (ANO,))
        db.commit()
    finally:
        db.close()
    db = _db()                                    # reabre: migra
    try:
        assert db.execute("SELECT referencia FROM contratacoes"
                          " WHERE numero_controle='ANTIGO'").fetchone()[0] == 0
    finally:
        db.close()
